"""Temporal activities for the Lad Stories pipeline.

Claymation-style character adventures. Key difference from other channels:
- Character bible + style bible injected into every prompt
- Sora audio kept at 90% (sound effects are the storytelling)
- Background music at 10%
"""

import json
import os
import subprocess

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


@activity.defn
async def pick_lad_stories_concepts(run_id: int, channel_id: int) -> list[dict]:
    """Generate Lad Stories adventure concepts."""
    await _update_run_step(run_id, "pick_concepts")
    log = logger.bind(activity="pick_lad_stories_concepts", run_id=run_id)

    if USE_REAL_WRITING:
        from apps.orchestrator.concept_engine import generate_idea_pitches
        from packages.prompts.lad_stories import build_lad_stories_ideas_prompt

        channel_config = await _get_channel_config_raw(channel_id)
        concepts, insights = await generate_idea_pitches(
            channel_id=channel_id,
            channel_name=channel_config.get("_channel_name", "Lad Stories"),
            channel_niche=channel_config.get("_channel_niche", "Claymation character adventures"),
            content_type="lad_stories",
            ideas_prompt_builder=build_lad_stories_ideas_prompt,
        )
        if insights:
            log.info("concept engine insights", insights=insights[:200])
        log.info("generated concepts", count=len(concepts), evolved=bool(insights))
    else:
        concepts = [
            {
                "title": "Lad Finds a Magic Mushroom",
                "sora_prompts": [
                    "A small round clay character walking through a forest diorama, claymation style",
                    "The clay character pokes a glowing mushroom that grows giant",
                    "The clay character rides the mushroom into the sky",
                ],
                "caption": "He should NOT have poked it",
                "description": "Lad and the mushroom #claymation #Shorts",
                "tags": ["claymation", "stop motion", "funny", "animation", "Shorts"],
                "score": 9.0,
            },
        ]
        log.info("using fake concepts")

    concepts.sort(key=lambda c: c.get("score", 0), reverse=True)

    for c in concepts:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, false)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": c["title"], "hook": c.get("caption", ""),
                "angle": "lad_stories", "length": 25,
                "score": c.get("score", 0),
            },
        )

    return concepts


@activity.defn
async def store_lad_stories_concept(run_id: int, channel_id: int, concept: dict) -> None:
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
async def generate_lad_stories_clips(run_id: int, channel_id: int, concept: dict) -> list[str]:
    """Generate Sora clips with character bible baked into every prompt."""
    await _update_run_step(run_id, "generate_clips")
    log = logger.bind(activity="generate_lad_stories_clips", run_id=run_id, title=concept.get("title"))

    output_dir = f"output/lad_stories_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    sora_prompts = concept.get("sora_prompts", [])
    if not sora_prompts:
        raise ValueError("Concept has no sora_prompts")

    clip_paths = []

    if USE_SORA:
        from packages.clients.sora import generate_video
        from packages.prompts.lad_stories import refine_sora_prompt

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
        log.info("sora not configured, creating placeholder clips")
        for i in range(len(sora_prompts)):
            output_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")
            _create_placeholder_clip(output_path, duration=8)
            clip_paths.append(output_path)

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "lad_stories_clips",
            "content": json.dumps({"clips": clip_paths, "concept_title": concept.get("title")}),
        },
    )

    log.info("all clips generated", count=len(clip_paths))
    return clip_paths


@activity.defn
async def prescreen_lad_stories_clips(run_id: int, channel_id: int, clips: list[str], concept: dict) -> list[dict]:
    await _update_run_step(run_id, "prescreen_clips")
    log = logger.bind(activity="prescreen_lad_stories_clips", run_id=run_id)

    if not USE_GEMINI:
        return [{"clip": i, "passed": True, "reason": "skipped"} for i in range(len(clips))]

    from packages.clients.gemini import review_video
    from packages.prompts.lad_stories import CHARACTER_BIBLE

    reviews = []
    sora_prompts = concept.get("sora_prompts", [])

    for i, clip_path in enumerate(clips):
        if not os.path.exists(clip_path):
            reviews.append({"clip": i, "passed": False, "reason": "file not found"})
            continue

        prompt_text = sora_prompts[i] if i < len(sora_prompts) else "Unknown"

        review_prompt = f"""Watch this AI-generated claymation clip. Check:
1. Does it look like claymation/stop-motion? (visible clay textures, handmade feel)
2. Is there a small round terracotta-orange clay character (Lad)?
3. Does the scene match: {prompt_text[:300]}
4. Visual quality and charm factor?

Return JSON (no markdown):
{{"style_match": 7, "character_match": 7, "scene_match": 7, "quality_score": 7, "passed": true, "issues": [], "description": "What appears"}}

Set passed=false if style_match < 4 or character_match < 3."""

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
            log.info("clip prescreened", clip=i, passed=review.get("passed"))
        except Exception as e:
            log.warning("prescreen failed", clip=i, error=str(e))
            reviews.append({"clip": i, "passed": True, "reason": f"error: {str(e)}"})

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id, "type": "clip_prescreen", "content": json.dumps(reviews)},
    )
    return reviews


@activity.defn
async def render_lad_stories_short(run_id: int, channel_id: int, clips: list[str], concept: dict) -> dict:
    """Render — Sora audio at 90% (sound effects tell the story), music at 10%."""
    await _update_run_step(run_id, "render")
    log = logger.bind(activity="render_lad_stories_short", run_id=run_id)

    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render

    output_dir = f"output/lad_stories_run_{run_id}"
    result = do_render(
        clips=clips,
        caption_text=concept.get("caption", ""),
        output_dir=output_dir,
        music_volume=0.10,
        sora_volume=0.90,
        content_type="lad_stories_short",
        output_filename="lad_stories_short.mp4",
    )

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id, "type": "rendered_lad_stories_short", "content": json.dumps(result)},
    )

    log.info("lad stories short rendered", path=result.get("path"))
    return result


@activity.defn
async def lad_stories_qa_check(run_id: int, channel_id: int, rendered: dict) -> dict:
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="lad_stories_qa_check", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "issues": ["No video file"]}

    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    actual_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

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
    dur_ok = 8 <= actual_duration <= 59
    checks.append({"check": "duration", "passed": dur_ok, "actual_seconds": round(actual_duration, 1),
                    "issues": [] if dur_ok else [f"Duration {actual_duration:.1f}s outside 15-59s"]})
    res_ok = width > 0 and height > 0 and height > width
    checks.append({"check": "resolution", "passed": res_ok, "width": width, "height": height,
                    "issues": [] if res_ok else [f"Expected vertical, got {width}x{height}"]})
    size_ok = 1 <= file_mb <= 500
    checks.append({"check": "file_size", "passed": size_ok, "size_mb": round(file_mb, 1),
                    "issues": [] if size_ok else [f"Size {file_mb:.1f}MB outside range"]})

    audio_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    has_audio = bool(audio_result.stdout.strip())
    checks.append({"check": "audio", "passed": has_audio, "issues": [] if has_audio else ["No audio"]})

    all_passed = all(c["passed"] for c in checks)
    issues = [f"[{c['check']}] {issue}" for c in checks for issue in c.get("issues", [])]
    report = {"passed": all_passed, "checks_run": len(checks), "issues": issues, "details": checks}
    log.info("QA " + ("passed" if all_passed else "FAILED"))
    return report


@activity.defn
async def review_lad_stories_video(run_id: int, channel_id: int, rendered: dict, concept: dict) -> dict:
    await _update_run_step(run_id, "video_review")
    log = logger.bind(activity="review_lad_stories_video", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"reviewed": False, "reason": "No video"}
    if not USE_GEMINI:
        return {"reviewed": False, "reason": "No Gemini", "overall_score": 0}

    from packages.clients.gemini import review_video

    prompt = f"""Watch this claymation YouTube Short. The main character should be a small terracotta-orange clay figure called "Lad."

Title: {concept.get('title', '')}
Caption: {concept.get('caption', '')}

Score 1-10:
1. CLAYMATION STYLE: Does it look like real claymation/stop-motion? Handmade textures?
2. CHARACTER CONSISTENCY: Is the same clay character visible across clips?
3. STORY: Is there a clear mini story with setup, complication, payoff?
4. CHARM: Is it funny, endearing, or surprising?
5. SOUND: Are there good sound effects that tell the story?

Return JSON (no markdown):
{{"style_score": 7, "character_score": 7, "story_score": 8, "charm_score": 8, "sound_score": 7, "overall_score": 7.4, "publish_recommendation": "yes/no/maybe", "top_issue": "Biggest problem", "summary": "One sentence", "suggestions": ["Suggestion 1"], "reviewed": true}}"""

    try:
        response = review_video(video_path, prompt)
        text_resp = response.strip()
        if text_resp.startswith("```"):
            lines = text_resp.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text_resp = "\n".join(lines[start:end])
        review = json.loads(text_resp)
        review["reviewed"] = True
    except Exception as e:
        log.warning("review failed", error=str(e))
        review = {"reviewed": False, "reason": str(e), "overall_score": 0}

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id, "type": "video_review", "content": json.dumps(review)},
    )
    # Store feedback for the feedback loop
    from apps.orchestrator.feedback_loop import store_feedback
    await store_feedback(channel_id, review)

    log.info("review complete", overall=review.get("overall_score"))
    return review


@activity.defn
async def publish_lad_stories_short(run_id: int, channel_id: int, concept: dict, qa: dict, rendered: dict) -> dict:
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish_lad_stories_short", run_id=run_id)

    if not qa.get("passed"):
        return {"published": False, "reason": "QA failed"}

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"published": False, "reason": "No video"}

    channel_config = await _get_channel_config_raw(channel_id)
    youtube_token_file = channel_config.get("youtube_token_file")

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    if not is_upload_configured(youtube_token_file=youtube_token_file):
        return {"published": False, "status": "ready_for_manual_upload",
                "title": concept.get("title"), "video_path": video_path}

    description = concept.get("description", "")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"

    privacy = concept.pop("_privacy_override", "private")

    thumbnail_path = rendered.get("thumbnail_path")

    result = upload_video(
        video_path=video_path,
        title=concept.get("title", ""),
        description=description,
        tags=concept.get("tags", []),
        category="Entertainment",
        privacy_status=privacy,
        youtube_token_file=youtube_token_file,
        made_for_kids=False,
        thumbnail_path=thumbnail_path,
    )

    if result.get("published"):
        await _execute("UPDATE content_runs SET status = 'published' WHERE id = :run_id", {"run_id": run_id})

    log.info("publish complete", **result)
    return result


def _create_placeholder_clip(output_path: str, duration: int = 8):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=0xc2703e:s=720x1280:d={duration}:r=30",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-vf", "drawtext=text='LAD STORIES\\nPlaceholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-t", str(duration), "-shortest", output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
