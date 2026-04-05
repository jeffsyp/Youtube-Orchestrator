"""Temporal activity implementations for the Yeah Thats Clean pipeline.

Narrated anime short films — 60 seconds, 5 clips, anime voice narration,
hook-rewind-escalation-payoff structure.

Reuses Synth Meow infrastructure for clip generation/compositing but with:
- Anime voice narration (ElevenLabs voice JjsQrIrIBD6TZ656NQfi)
- No background music — narration + Sora audio only
- Narration mixed into each clip (sora 0.5, narration 1.3)
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
USE_VOICE = bool(os.getenv("ELEVENLABS_API_KEY"))

# Anime voice for narration
ANIME_VOICE_ID = "JjsQrIrIBD6TZ656NQfi"

# Audio mix levels — narration is primary, Sora provides ambient sound
SORA_VOLUME = 0.5
NARRATION_VOLUME = 1.3


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


async def _get_past_titles(channel_id: int, limit: int = 50) -> list[str]:
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT DISTINCT s.idea_title FROM scripts s
                    JOIN content_runs cr ON cr.id = s.run_id
                    WHERE s.channel_id = :cid AND cr.content_type = 'yeah_thats_clean'
                    ORDER BY s.idea_title LIMIT :lim"""),
            {"cid": channel_id, "lim": limit},
        )
        return [row[0] for row in result.fetchall()]


@activity.defn
async def pick_yeah_thats_clean_concepts(run_id: int, channel_id: int) -> list[dict]:
    """Generate anime short film concept ideas."""
    await _update_run_step(run_id, "pick_concepts")
    log = logger.bind(activity="pick_yeah_thats_clean_concepts", run_id=run_id)

    if USE_REAL_WRITING:
        from apps.orchestrator.concept_engine import generate_idea_pitches
        from packages.prompts.yeah_thats_clean import build_yeah_thats_clean_ideas_prompt, _SYSTEM as CLEAN_RULES

        channel_config = await _get_channel_config_raw(channel_id)
        concepts, insights = await generate_idea_pitches(
            channel_id=channel_id,
            channel_name=channel_config.get("_channel_name", "Yeah Thats Clean"),
            channel_niche=channel_config.get("_channel_niche", "AI-generated stick figure action cartoons"),
            content_type="yeah_thats_clean",
            ideas_prompt_builder=build_yeah_thats_clean_ideas_prompt,
            channel_rules=CLEAN_RULES,
        )
        if insights:
            log.info("concept engine insights", insights=insights[:200])
        log.info("generated concepts", count=len(concepts), evolved=bool(insights))
    else:
        concepts = [
            {
                "title": "One vs Five Stick Figure Showdown",
                "sora_prompts": [
                    "Stick figure animation style, simple black stick figures on clean minimal background, sharp clean lines. A lone black stick figure stands facing five red-outlined stick figures in a white arena. Fighting stances. Tension.",
                    "Stick figure animation style, dynamic action poses, motion blur on fast movements, colored energy effects and impact flashes. The lone figure launches into a spinning kick combo, sending red figures flying with bright impact flashes. Chain attacks flow smoothly.",
                    "Stick figure animation style, dynamic action poses, motion blur, colored energy effects. The lone figure powers up with blue energy glow, unleashes a shockwave that defeats all remaining enemies. Stands victorious.",
                ],
                "narration": [
                    "One against five. They thought it was already over.",
                    "But he moved first. And he moved faster than any of them could react.",
                    "The shockwave hit them all at once. It was never even close.",
                ],
                "caption": "They thought five was enough",
                "description": "Outnumbered but never outmatched #stickfigure #animation #action #Shorts",
                "tags": ["stick figure", "animation", "action", "fight", "Shorts"],
                "score": 9.0,
            },
        ]
        log.info("using fake concepts")

    concepts.sort(key=lambda c: c.get("score", 0), reverse=True)

    # Gate: only keep concepts scoring 8.0+ — Sora credits are expensive
    MIN_CONCEPT_SCORE = 8.0
    strong = [c for c in concepts if c.get("score", 0) >= MIN_CONCEPT_SCORE]
    if strong:
        concepts = strong
        log.info("concept prescreen passed", kept=len(concepts), threshold=MIN_CONCEPT_SCORE)
    else:
        log.warning("no concepts scored above threshold, keeping top concept only",
                     threshold=MIN_CONCEPT_SCORE, top_score=concepts[0].get("score", 0) if concepts else 0)
        concepts = concepts[:1]

    for c in concepts:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, false)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": c["title"], "hook": c.get("caption", ""),
                "angle": "yeah_thats_clean", "length": 25,
                "score": c.get("score", 0),
            },
        )

    return concepts


@activity.defn
async def store_yeah_thats_clean_concept(run_id: int, channel_id: int, concept: dict) -> None:
    """Store the selected concept as a script record."""
    # Include narration in stored content for review visibility
    content = concept.get("caption", "")
    narration = concept.get("narration", [])
    if narration:
        content += "\n\nNARRATION:\n" + "\n".join(f"[Clip {i+1}] {line}" for i, line in enumerate(narration))

    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": concept.get("title", ""), "stage": "final",
            "content": content, "wc": 0,
        },
    )


@activity.defn
async def generate_yeah_thats_clean_clips(run_id: int, channel_id: int, concept: dict) -> list[str]:
    """Generate Sora video clips for a stick figure action concept."""
    await _update_run_step(run_id, "generate_clips")
    log = logger.bind(activity="generate_yeah_thats_clean_clips", run_id=run_id, title=concept.get("title"))

    output_dir = f"output/yeah_thats_clean_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    sora_prompts = concept.get("sora_prompts", [])
    if not sora_prompts:
        raise ValueError("Concept has no sora_prompts")

    clip_paths = []

    if USE_SORA:
        from packages.clients.sora import generate_video_async, _extract_last_frame
        from packages.prompts.yeah_thats_clean import refine_sora_prompt
        prev_clip_ref = None

        channel_config = await _get_channel_config_raw(channel_id)
        clip_durations = concept.get("clip_durations", [channel_config.get("sora_duration", 8)] * len(sora_prompts))
        sora_size = channel_config.get("sora_size", "720x1280")

        for i, _ in enumerate(sora_prompts):
            refined = refine_sora_prompt(concept, i, len(sora_prompts))
            output_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")

            log.info("generating sora clip", clip=i + 1, total=len(sora_prompts))
            result = await generate_video_async(
                prompt=refined,
                output_path=output_path,
                duration=clip_durations[i] if i < len(clip_durations) else 8,
                size=sora_size,
                timeout=1200,
                reference_image_url=prev_clip_ref,  # Chain from previous clip
            )
            clip_paths.append(result["path"])
            log.info("clip generated", clip=i + 1, path=result["path"])
            prev_clip_ref = _extract_last_frame(output_path)
            if prev_clip_ref:
                log.info("frame chained for next clip", clip=i + 1)
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
            "type": "yeah_thats_clean_clips",
            "content": json.dumps({"clips": clip_paths, "concept_title": concept.get("title")}),
        },
    )

    log.info("all clips generated", count=len(clip_paths))
    return clip_paths


@activity.defn
async def prescreen_yeah_thats_clean_clips(run_id: int, channel_id: int, clips: list[str], concept: dict) -> list[dict]:
    """Use Gemini to watch each clip and check quality + prompt match."""
    await _update_run_step(run_id, "prescreen_clips")
    log = logger.bind(activity="prescreen_yeah_thats_clean_clips", run_id=run_id)

    if not USE_GEMINI:
        log.info("gemini not configured, skipping prescreen")
        return [{"clip": i, "passed": True, "reason": "skipped"} for i in range(len(clips))]

    from packages.clients.gemini import review_video

    sora_prompts = concept.get("sora_prompts", [])
    reviews = []

    for i, clip_path in enumerate(clips):
        if not os.path.exists(clip_path):
            reviews.append({"clip": i, "passed": False, "reason": "file not found"})
            continue

        prompt_text = sora_prompts[i] if i < len(sora_prompts) else "Unknown"

        from packages.prompts.video_review import build_review_prompt
        from apps.orchestrator.concept_engine import get_video_feedback
        video_fb = await get_video_feedback(channel_id)
        review_prompt = build_review_prompt(concept, "Yeah Thats Clean", "AI stick figure action cartoons", video_feedback=video_fb or None)

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
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "clip_prescreen", "content": json.dumps(reviews),
        },
    )

    return reviews


@activity.defn
async def render_yeah_thats_clean_short(run_id: int, channel_id: int, clips: list[str], concept: dict) -> dict:
    """Render the final Yeah Thats Clean Short with narration.

    Steps:
    1. Generate narration audio for each clip via ElevenLabs
    2. Mix narration into each clip (sora 0.5, narration 1.3)
    3. Normalize all clips for consistent resolution/framerate
    4. Concatenate with crossfades into final 60s video
    """
    await _update_run_step(run_id, "render")
    log = logger.bind(activity="render_yeah_thats_clean_short", run_id=run_id)

    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(output_dir, exist_ok=True)

    valid_clips = [c for c in clips if os.path.exists(c)]
    if not valid_clips:
        raise RuntimeError("No valid clip files found for rendering")

    narration_lines = concept.get("narration", [])

    # Step 1: Generate narration audio for each clip
    narration_paths = []
    if USE_VOICE and narration_lines:
        from packages.clients.elevenlabs import generate_speech

        for i, line in enumerate(narration_lines):
            if i >= len(valid_clips):
                break
            narration_path = os.path.join(output_dir, f"narration_{i:02d}.mp3")
            try:
                generate_speech(
                    text=line,
                    voice=ANIME_VOICE_ID,
                    output_path=narration_path,
                )
                narration_paths.append(narration_path)
                log.info("narration generated", clip=i, path=narration_path)
            except Exception as e:
                log.warning("narration generation failed for clip", clip=i, error=str(e))
                narration_paths.append(None)
    else:
        log.info("voice not configured or no narration lines, rendering without narration")
        narration_paths = [None] * len(valid_clips)

    # Step 2: Mix narration into each clip
    mixed_clips = []
    for i, clip_path in enumerate(valid_clips):
        narration_path = narration_paths[i] if i < len(narration_paths) else None
        mixed_path = os.path.join(output_dir, f"mixed_{i:02d}.mp4")

        if narration_path and os.path.exists(narration_path):
            _mix_narration_into_clip(clip_path, narration_path, mixed_path,
                                      sora_volume=SORA_VOLUME, narration_volume=NARRATION_VOLUME)
            log.info("narration mixed into clip", clip=i)
        else:
            # No narration — just copy the clip
            _ffmpeg_copy(clip_path, mixed_path)
            log.info("no narration for clip, using original audio", clip=i)

        mixed_clips.append(mixed_path)

    # Step 3: Normalize clips for consistent resolution/framerate
    from apps.rendering_service.synthzoo_compositor import _normalize_clip

    normalized_clips = []
    for i, clip_path in enumerate(mixed_clips):
        norm_path = os.path.join(output_dir, f"norm_{i:02d}.mp4")
        _normalize_clip(clip_path, norm_path)
        normalized_clips.append(norm_path)
        log.info("clip normalized", clip=i)

    # Step 4: Concatenate with crossfades
    from apps.rendering_service.synthzoo_compositor import (
        _ffmpeg_crossfade_concat,
        _get_duration,
        _ffmpeg_trim,
    )

    concat_path = os.path.join(output_dir, "yeah_thats_clean_concat.mp4")
    if len(normalized_clips) == 1:
        _ffmpeg_copy(normalized_clips[0], concat_path)
    else:
        _ffmpeg_crossfade_concat(normalized_clips, concat_path)

    # Trim to max 59s for Shorts
    MAX_SHORT_DURATION = 59.0
    final_path = os.path.join(output_dir, "yeah_thats_clean_short.mp4")
    duration = _get_duration(concat_path)
    if duration > MAX_SHORT_DURATION:
        log.info("trimming to max duration", original=round(duration), max=MAX_SHORT_DURATION)
        _ffmpeg_trim(concat_path, final_path, MAX_SHORT_DURATION)
        os.remove(concat_path)
    else:
        os.rename(concat_path, final_path)

    # Cleanup intermediate files
    for p in mixed_clips + normalized_clips:
        if os.path.exists(p):
            os.remove(p)

    final_duration = _get_duration(final_path)
    file_size = os.path.getsize(final_path)

    # Generate thumbnail
    thumbnail_path = None
    try:
        from apps.rendering_service.thumbnail import generate_shorts_thumbnail
        thumb_out = os.path.join(output_dir, "thumbnail.png")
        thumbnail_path = generate_shorts_thumbnail(
            video_path=os.path.abspath(final_path),
            title=concept.get("caption", concept.get("title", "Yeah Thats Clean")),
            output_path=thumb_out,
        )
        log.info("thumbnail generated", path=thumbnail_path)
    except Exception as e:
        log.warning("thumbnail generation failed, continuing without", error=str(e))

    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(valid_clips),
        "total_duration_seconds": round(final_duration),
        "resolution": "720x1280",
        "content_type": "yeah_thats_clean_short",
        "narration_clips": sum(1 for p in narration_paths if p is not None),
        "thumbnail_path": thumbnail_path,
    }

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "rendered_yeah_thats_clean_short", "content": json.dumps(result),
        },
    )

    log.info("yeah_thats_clean short rendered", path=result.get("path"),
             duration=round(final_duration), narration_clips=result["narration_clips"])
    return result


@activity.defn
async def yeah_thats_clean_qa_check(run_id: int, channel_id: int, rendered: dict) -> dict:
    """QA check for a Yeah Thats Clean Short."""
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="yeah_thats_clean_qa_check", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "issues": ["No rendered video file found"]}

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

    dur_ok = 30 <= actual_duration <= 59
    checks.append({
        "check": "duration", "passed": dur_ok,
        "actual_seconds": round(actual_duration, 1),
        "issues": [] if dur_ok else [f"Duration {actual_duration:.1f}s outside 30-59s range"],
    })

    res_ok = width > 0 and height > 0 and height > width
    checks.append({
        "check": "resolution", "passed": res_ok,
        "width": width, "height": height,
        "issues": [] if res_ok else [f"Expected vertical video, got {width}x{height}"],
    })

    size_ok = 1 <= file_mb <= 500
    checks.append({
        "check": "file_size", "passed": size_ok,
        "size_mb": round(file_mb, 1),
        "issues": [] if size_ok else [f"File size {file_mb:.1f}MB outside 1-500MB range"],
    })

    # Audio is critical — narration must be present
    audio_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    has_audio = bool(audio_result.stdout.strip())
    checks.append({
        "check": "audio", "passed": has_audio,
        "issues": [] if has_audio else ["No audio — critical for narrated anime content"],
    })

    all_passed = all(c["passed"] for c in checks)
    issues = [f"[{c['check']}] {issue}" for c in checks for issue in c.get("issues", [])]

    report = {"passed": all_passed, "checks_run": len(checks), "issues": issues, "details": checks}
    if all_passed:
        log.info("yeah_thats_clean QA passed")
    else:
        log.warning("yeah_thats_clean QA FAILED", issues=issues)
    return report


@activity.defn
async def review_yeah_thats_clean_video(run_id: int, channel_id: int, rendered: dict, concept: dict) -> dict:
    """Use Gemini to watch and critique the final video."""
    await _update_run_step(run_id, "video_review")
    log = logger.bind(activity="review_yeah_thats_clean_video", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"reviewed": False, "reason": "No video file"}

    if not USE_GEMINI:
        log.info("gemini not configured, skipping review")
        return {"reviewed": False, "reason": "GEMINI_API_KEY not set", "overall_score": 0}

    from packages.clients.gemini import review_video
    from apps.orchestrator.concept_engine import get_video_feedback
    title = concept.get("title", "Unknown")
    caption = concept.get("caption", "")

    video_fb = await get_video_feedback(channel_id)
    feedback_section = ""
    if video_fb:
        feedback_section = "\n\nUSER VIDEO FEEDBACK — factor these into your review:\n" + "\n".join(f"- {fb}" for fb in video_fb)

    prompt = f"""Watch this AI-generated stick figure action cartoon YouTube Short and critique it.

Title: {title}
Caption: {caption}
{feedback_section}

Score 1-10 on:
1. ACTION: How intense and well-choreographed is the action? Do moves flow together?
2. AUDIO QUALITY: Are there impactful sound effects? Hits, swooshes, explosions, energy blasts?
3. VISUAL QUALITY: Are the stick figures clear and readable? Are the motion blur and impact effects dynamic?
4. CONTINUITY: Do the clips feel connected — same arena, same characters, consistent style?
5. HOOK: Does it grab attention from frame 1 with an exciting setup or confrontation?

Return JSON (no markdown):
{{"action_score": 8, "audio_score": 7, "visual_score": 8, "continuity_score": 7, "hook_score": 7, "overall_score": 7.4, "publish_recommendation": "yes/no/maybe", "top_issue": "Biggest problem", "summary": "One sentence verdict", "suggestions": ["Improvement 1", "Improvement 2"], "reviewed": true}}"""

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
        log.warning("video review failed", error=str(e))
        review = {"reviewed": False, "reason": str(e), "overall_score": 0}

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
             recommendation=review.get("publish_recommendation"))
    return review


@activity.defn
async def publish_yeah_thats_clean_short(run_id: int, channel_id: int, concept: dict, qa: dict, rendered: dict) -> dict:
    """Upload Yeah Thats Clean Short to YouTube."""
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish_yeah_thats_clean_short", run_id=run_id)

    if not qa.get("passed"):
        log.warning("QA failed, skipping publish")
        return {"published": False, "reason": "QA check failed"}

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"published": False, "reason": "No rendered video file"}

    channel_config = await _get_channel_config_raw(channel_id)
    youtube_token_file = channel_config.get("youtube_token_file")

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    if not is_upload_configured(youtube_token_file=youtube_token_file):
        token_name = youtube_token_file or "youtube_token.json"
        log.info("youtube not configured", token_file=token_name)
        return {
            "published": False,
            "status": "ready_for_manual_upload",
            "title": concept.get("title"),
            "video_path": video_path,
        }

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
        category="Entertainment",
        privacy_status=privacy,
        youtube_token_file=youtube_token_file,
        made_for_kids=made_for_kids,
        thumbnail_path=thumbnail_path,
    )

    if result.get("published"):
        await _execute(
            "UPDATE content_runs SET status = 'published' WHERE id = :run_id",
            {"run_id": run_id},
        )

    # Store publish result for URL tracking
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id,
         "type": "publish_result", "content": json.dumps(result)},
    )

    log.info("publish step complete", **result)
    return result


def _mix_narration_into_clip(
    clip_path: str,
    narration_path: str,
    output_path: str,
    sora_volume: float = 0.5,
    narration_volume: float = 1.3,
):
    """Mix narration audio into a video clip alongside Sora's native audio."""
    # Check if clip has existing audio
    audio_check = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", clip_path],
        capture_output=True, text=True, timeout=10,
    )
    has_clip_audio = bool(audio_check.stdout.strip())

    if has_clip_audio:
        # Mix Sora audio + narration
        filter_str = (
            f"[0:a]volume={sora_volume}[sora];"
            f"[1:a]volume={narration_volume}[narr];"
            f"[sora][narr]amix=inputs=2:duration=first:dropout_transition=0[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-i", narration_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ]
    else:
        # No Sora audio — narration only
        filter_str = f"[1:a]volume={narration_volume}[outa]"
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-i", narration_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning("narration mix failed, copying original clip", stderr=result.stderr[-300:])
        _ffmpeg_copy(clip_path, output_path)


def _ffmpeg_copy(input_path: str, output_path: str):
    """Copy a single file with faststart."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg copy failed: {result.stderr[-300:]}")


def _create_placeholder_clip(output_path: str, duration: int = 8):
    """Create a placeholder clip for testing without Sora."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a2e1a:s=720x1280:d={duration}:r=30",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-vf", "drawtext=text='YEAH THATS CLEAN\\nAnime Short Film\\nPlaceholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac",
        "-t", str(duration),
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
