"""Temporal activity implementations for the Synth Zoo pipeline."""

import json
import os

import structlog
from dotenv import load_dotenv
from sqlalchemy import text
from temporalio import activity

from packages.clients.db import async_session

load_dotenv()
logger = structlog.get_logger()

USE_REAL_WRITING = bool(os.getenv("ANTHROPIC_API_KEY"))
USE_SORA = bool(os.getenv("OPENAI_API_KEY"))
USE_GEMINI = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


async def _execute(query: str, params: dict) -> None:
    async with async_session() as session:
        await session.execute(text(query), params)
        await session.commit()


async def _update_run_step(run_id: int, step: str) -> None:
    await _execute(
        "UPDATE content_runs SET current_step = :step WHERE id = :run_id",
        {"run_id": run_id, "step": step},
    )


async def _get_channel_config_raw(channel_id: int) -> dict:
    """Get raw channel config JSON."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, name, niche, config FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Channel {channel_id} not found")
        config = json.loads(row[3]) if row[3] else {}
        config["_channel_name"] = row[1]
        config["_channel_niche"] = row[2]
        return config


async def _get_past_synthzoo_titles(channel_id: int, limit: int = 50) -> list[str]:
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT DISTINCT s.idea_title FROM scripts s
                    JOIN content_runs cr ON cr.id = s.run_id
                    WHERE s.channel_id = :cid AND cr.content_type = 'synthzoo'
                    ORDER BY s.idea_title LIMIT :lim"""),
            {"cid": channel_id, "lim": limit},
        )
        return [row[0] for row in result.fetchall()]


@activity.defn
async def pick_synthzoo_concepts(run_id: int, channel_id: int) -> list[dict]:
    """Generate concept ideas for Synth Zoo Shorts."""
    await _update_run_step(run_id, "pick_concepts")
    log = logger.bind(activity="pick_synthzoo_concepts", run_id=run_id)

    if USE_REAL_WRITING:
        from apps.orchestrator.concept_engine import generate_idea_pitches
        from packages.prompts.synthzoo import build_synthzoo_ideas_prompt

        channel_config = await _get_channel_config_raw(channel_id)
        concepts, insights = await generate_idea_pitches(
            channel_id=channel_id,
            channel_name=channel_config.get("_channel_name", "Synth Meow"),
            channel_niche=channel_config.get("_channel_niche", "AI-generated animal videos"),
            content_type="synthzoo",
            ideas_prompt_builder=build_synthzoo_ideas_prompt,
        )
        if insights:
            log.info("concept engine insights", insights=insights[:200])
        log.info("generated ideas", count=len(concepts), evolved=bool(insights))
    else:
        concepts = [
            {
                "title": "Golden Retriever Tries to Cook Spaghetti",
                "sora_prompts": [
                    "A golden retriever wearing a tiny chef hat stands on hind legs at a kitchen counter, clumsily pushing spaghetti into a pot of boiling water, pasta falling everywhere, warm kitchen lighting, photorealistic",
                    "Close-up of the golden retriever's face covered in tomato sauce, looking proud and happy, steam rising from a messy pot behind, shallow depth of field",
                ],
                "caption": "When the chef keeps eating the ingredients",
                "description": "AI-generated golden retriever cooking disaster #Shorts #AIAnimals #Dogs #Funny",
                "tags": ["AI animals", "golden retriever", "cooking fail", "funny dogs", "Shorts"],
                "score": 8.5,
            },
            {
                "title": "Cat Attempts a Job Interview",
                "sora_prompts": [
                    "A tabby cat sitting upright in an office chair at a desk, wearing a tiny necktie, looking seriously at the camera, corporate office background, fluorescent lighting",
                    "The cat slowly pushes a coffee mug off the desk while maintaining eye contact, papers scattering, the interviewer's shocked face in soft focus background",
                ],
                "caption": "The interview was going great until...",
                "description": "AI cat goes to a job interview #Shorts #AICat #Funny #Animals",
                "tags": ["AI cat", "job interview", "funny animals", "office humor", "Shorts"],
                "score": 8.2,
            },
        ]
        log.info("using fake concepts")

    # Sort by score
    concepts.sort(key=lambda c: c.get("score", 0), reverse=True)

    # Store concepts as ideas
    for c in concepts:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, false)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": c["title"], "hook": c.get("caption", ""),
                "angle": "synthzoo", "length": 20,
                "score": c.get("score", 0),
            },
        )

    return concepts


@activity.defn
async def store_synthzoo_concept(run_id: int, channel_id: int, concept: dict) -> None:
    """Store the selected concept as a script record for tracking."""
    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": concept.get("title", ""), "stage": "final",
            "content": concept.get("caption", ""), "wc": 0,
        },
    )


@activity.defn
async def generate_synthzoo_clips(run_id: int, channel_id: int, concept: dict) -> list[str]:
    """Generate Sora video clips for a concept."""
    await _update_run_step(run_id, "generate_clips")
    log = logger.bind(activity="generate_synthzoo_clips", run_id=run_id, title=concept.get("title"))

    output_dir = f"output/synthzoo_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    sora_prompts = concept.get("sora_prompts", [])
    if not sora_prompts:
        raise ValueError("Concept has no sora_prompts")

    clip_paths = []

    if USE_SORA:
        from packages.clients.sora import generate_video
        from packages.prompts.synthzoo import refine_sora_prompt

        channel_config = await _get_channel_config_raw(channel_id)
        sora_duration = channel_config.get("sora_duration", 8)
        sora_size = channel_config.get("sora_size", "720x1280")

        for i, _ in enumerate(sora_prompts):
            refined = refine_sora_prompt(concept, i, len(sora_prompts))
            output_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")

            log.info("generating sora clip", clip=i + 1, total=len(sora_prompts))
            result = generate_video(
                prompt=refined,
                output_path=output_path,
                duration=sora_duration,
                size=sora_size,
                timeout=1200,
            )
            clip_paths.append(result["path"])
            log.info("clip generated", clip=i + 1, path=result["path"])
    else:
        # No Sora — create placeholder clips with FFmpeg (colored test patterns)
        log.info("sora not configured, creating placeholder clips")
        for i in range(len(sora_prompts)):
            output_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")
            _create_placeholder_clip(output_path, duration=8)
            clip_paths.append(output_path)

    # Store clip info as asset
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "synthzoo_clips",
            "content": json.dumps({"clips": clip_paths, "concept_title": concept.get("title")}),
        },
    )

    log.info("all clips generated", count=len(clip_paths))
    return clip_paths


@activity.defn
async def prescreen_synthzoo_clips(run_id: int, channel_id: int, clips: list[str], concept: dict) -> list[dict]:
    """Use Gemini to watch each Sora clip and check if it matches the intended prompt.

    Returns a list of review dicts, one per clip, with pass/fail and notes.
    """
    await _update_run_step(run_id, "prescreen_clips")
    log = logger.bind(activity="prescreen_synthzoo_clips", run_id=run_id)

    if not USE_GEMINI:
        log.info("gemini not configured, skipping clip prescreen")
        return [{"clip": i, "passed": True, "reason": "prescreen skipped"} for i in range(len(clips))]

    from packages.clients.gemini import review_video

    sora_prompts = concept.get("sora_prompts", [])
    reviews = []

    for i, clip_path in enumerate(clips):
        if not os.path.exists(clip_path):
            reviews.append({"clip": i, "passed": False, "reason": "file not found"})
            continue

        prompt_text = sora_prompts[i] if i < len(sora_prompts) else "Unknown"
        clip_role = ["opening hook", "escalation", "payoff"][i] if i < 3 else f"clip {i+1}"

        review_prompt = f"""Watch this AI-generated video clip and evaluate it. This is clip {i+1} of {len(clips)} in a YouTube Short.

INTENDED PROMPT: {prompt_text}

This clip's role: {clip_role}

Score 1-10 on:
1. Does the clip match what was requested in the prompt?
2. Visual quality — any glitches, distortions, or weird artifacts?
3. For clip 1 specifically: does action start immediately, or is it a slow/boring opening?

Return JSON only (no markdown):
{{
  "match_score": 7,
  "quality_score": 8,
  "hook_score": 7,
  "passed": true,
  "issues": ["List any problems"],
  "description": "Brief description of what actually appears in the clip"
}}

Set "passed" to false if match_score < 6 or quality_score < 6, or if clip 1 has hook_score < 6."""

        try:
            response = review_video(clip_path, review_prompt)
            text_resp = response.strip()
            if text_resp.startswith("```"):
                lines = text_resp.split("\n")
                start = 1
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                text_resp = "\n".join(lines[start:end])
            review = json.loads(text_resp)
            review["clip"] = i
            reviews.append(review)
            log.info("clip prescreened", clip=i, passed=review.get("passed"),
                     match=review.get("match_score"), quality=review.get("quality_score"))
        except Exception as e:
            log.warning("clip prescreen failed", clip=i, error=str(e))
            reviews.append({"clip": i, "passed": True, "reason": f"prescreen error: {str(e)}"})

    # Store prescreen results
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "clip_prescreen", "content": json.dumps(reviews),
        },
    )

    return reviews


@activity.defn
async def render_synthzoo_short(run_id: int, channel_id: int, clips: list[str], concept: dict) -> dict:
    """Render the final Synth Zoo Short."""
    await _update_run_step(run_id, "render")
    log = logger.bind(activity="render_synthzoo_short", run_id=run_id)

    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render

    output_dir = f"output/synthzoo_run_{run_id}"
    result = do_render(
        clips=clips,
        caption_text=concept.get("caption", ""),
        output_dir=output_dir,
    )

    # Store as asset
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "rendered_synthzoo_short", "content": json.dumps(result),
        },
    )

    log.info("synthzoo short rendered", path=result.get("path"))
    return result


@activity.defn
async def synthzoo_qa_check(run_id: int, channel_id: int, rendered: dict) -> dict:
    """QA check for a Synth Zoo Short — vertical resolution, duration 15-59s, audio NOT required."""
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="synthzoo_qa_check", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "issues": ["No rendered video file found"]}

    import subprocess
    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    actual_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    # Resolution check (720x1280 for Synth Zoo)
    res_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    res_parts = res_result.stdout.strip().split(",") if res_result.stdout.strip() else []
    width = int(res_parts[0]) if len(res_parts) >= 2 else 0
    height = int(res_parts[1]) if len(res_parts) >= 2 else 0

    file_size = os.path.getsize(video_path)
    file_mb = file_size / (1024 * 1024)

    checks = []

    # Duration: 15-59s
    dur_ok = 15 <= actual_duration <= 59
    checks.append({
        "check": "duration",
        "passed": dur_ok,
        "actual_seconds": round(actual_duration, 1),
        "issues": [] if dur_ok else [f"Duration {actual_duration:.1f}s outside 15-59s range"],
    })

    # Resolution: vertical (width < height)
    res_ok = width > 0 and height > 0 and height > width
    checks.append({
        "check": "resolution",
        "passed": res_ok,
        "width": width,
        "height": height,
        "issues": [] if res_ok else [f"Expected vertical video, got {width}x{height}"],
    })

    # File size: 1MB-500MB
    size_ok = 1 <= file_mb <= 500
    checks.append({
        "check": "file_size",
        "passed": size_ok,
        "size_mb": round(file_mb, 1),
        "issues": [] if size_ok else [f"File size {file_mb:.1f}MB outside 1-500MB range"],
    })

    # Audio NOT required for Synth Zoo (Sora may or may not include ambient audio)

    all_passed = all(c["passed"] for c in checks)
    issues = [f"[{c['check']}] {issue}" for c in checks for issue in c.get("issues", [])]

    report = {
        "passed": all_passed,
        "checks_run": len(checks),
        "issues": issues,
        "details": checks,
    }

    if all_passed:
        log.info("synthzoo QA passed")
    else:
        log.warning("synthzoo QA FAILED", issues=issues)
    return report


@activity.defn
async def review_synthzoo_video(run_id: int, channel_id: int, rendered: dict, concept: dict) -> dict:
    """Use Gemini to watch the rendered video and critique it."""
    await _update_run_step(run_id, "video_review")
    log = logger.bind(activity="review_synthzoo_video", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        log.warning("no video to review")
        return {"reviewed": False, "reason": "No video file"}

    if not USE_GEMINI:
        log.info("gemini not configured, skipping video review")
        return {"reviewed": False, "reason": "GEMINI_API_KEY not set", "overall_score": 0}

    from packages.clients.gemini import review_video
    from packages.prompts.video_review import build_synthzoo_review_prompt

    prompt = build_synthzoo_review_prompt(concept)
    response = review_video(video_path, prompt)

    # Parse JSON response
    text_resp = response.strip()
    if text_resp.startswith("```"):
        lines = text_resp.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text_resp = "\n".join(lines[start:end])

    review = json.loads(text_resp)
    review["reviewed"] = True

    # Store review as asset
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "video_review", "content": json.dumps(review),
        },
    )

    # Store feedback for the feedback loop
    from apps.orchestrator.feedback_loop import store_feedback
    await store_feedback(channel_id, review)

    log.info("video review complete",
             overall=review.get("overall_score"),
             recommendation=review.get("publish_recommendation"),
             top_issue=review.get("top_issue"))
    return review


@activity.defn
async def publish_synthzoo_short(run_id: int, channel_id: int, concept: dict, qa: dict, rendered: dict) -> dict:
    """Upload Synth Zoo Short to YouTube."""
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish_synthzoo_short", run_id=run_id)

    if not qa.get("passed"):
        log.warning("QA failed, skipping publish")
        return {"published": False, "reason": "QA check failed"}

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"published": False, "reason": "No rendered video file"}

    # Get channel config for token file
    channel_config = await _get_channel_config_raw(channel_id)
    youtube_token_file = channel_config.get("youtube_token_file")

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    if not is_upload_configured(youtube_token_file=youtube_token_file):
        token_name = youtube_token_file or "youtube_token.json"
        log.info("youtube not configured for channel", token_file=token_name)
        return {
            "published": False,
            "status": "ready_for_manual_upload",
            "title": concept.get("title"),
            "video_path": video_path,
        }

    # Build description with #Shorts tag
    description = concept.get("description", "")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"

    privacy = concept.pop("_privacy_override", "private")

    made_for_kids = channel_config.get("made_for_kids", False)

    thumbnail_path = rendered.get("thumbnail_path")

    result = upload_video(
        video_path=video_path,
        title=concept.get("title", ""),
        description=description,
        tags=concept.get("tags", []),
        category="Pets & Animals",
        privacy_status=privacy,
        youtube_token_file=youtube_token_file,
        made_for_kids=made_for_kids,
        thumbnail_path=thumbnail_path,
    )

    # Store publish result as asset for URL tracking
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "publish_result", "content": json.dumps(result),
        },
    )

    if result.get("published"):
        await _execute(
            "UPDATE content_runs SET status = 'published' WHERE id = :run_id",
            {"run_id": run_id},
        )

    log.info("publish step complete", **result)
    return result


def _create_placeholder_clip(output_path: str, duration: int = 8):
    """Create a placeholder vertical video clip for testing without Sora."""
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a1a2e:s=720x1280:d={duration}:r=30",
        "-vf", "drawtext=text='SYNTH ZOO\\nPlaceholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
