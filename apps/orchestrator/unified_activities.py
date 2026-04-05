"""Unified pipeline activities — single set of activities for all channels."""

import asyncio
import json
import math
import os
import subprocess

import structlog
from temporalio import activity

from packages.clients.db import async_session
from sqlalchemy import text

logger = structlog.get_logger()

WIDTH = 720
HEIGHT = 1280


# ---------------------------------------------------------------------------
# Activity 1: Generate narrations
# ---------------------------------------------------------------------------

@activity.defn
async def generate_narrations(run_id: int, concept: dict) -> dict:
    """Generate ElevenLabs TTS for each clip, measure durations, pick Sora durations."""
    from packages.clients.elevenlabs import generate_speech

    await _update_step(run_id, "generate_narrations")

    output_dir = f"output/unified_run_{run_id}/narration"
    os.makedirs(output_dir, exist_ok=True)

    voice = concept.get("voice_id", "George")
    clips = concept["clips"]
    results = []

    for i, clip in enumerate(clips):
        narration_text = clip.get("narration", "")
        if not narration_text:
            # No narration — Sora handles all audio (dialogue clips).
            # Give full 12s so dialogue has room to play out.
            sora_dur = clip.get("duration") or 12
            results.append({"index": i, "path": None, "duration": 0, "sora_duration": sora_dur})
            continue

        output_path = os.path.join(output_dir, f"n_{i}.mp3")
        log = logger.bind(run_id=run_id, clip=i, text_len=len(narration_text))
        log.info("generating narration")

        generate_speech(text=narration_text, voice=voice, output_path=output_path)

        # Measure duration with ffprobe
        duration = _get_audio_duration(output_path)
        # Auto-pick Sora duration: narration + 2.5s buffer so clip never cuts off speech
        # Single-clip videos default to 8s since that's enough for most actions.
        # Multi-clip videos use narration + buffer.
        # Concepts can override with "duration" per clip if needed.
        if len(clips) == 1:
            sora_duration = clip.get("duration") or 8
        else:
            sora_duration = clip.get("duration") or _pick_sora_duration(duration + 3.0)

        log.info("narration done", duration=duration, sora_duration=sora_duration)
        results.append({
            "index": i,
            "path": output_path,
            "duration": duration,
            "sora_duration": sora_duration,
        })

    return {"narrations": results, "output_dir": output_dir}


# ---------------------------------------------------------------------------
# Activity 2: Generate Sora clips
# ---------------------------------------------------------------------------

# Sora errors that should NOT be retried — the prompt itself is the problem
_SORA_NO_RETRY_PATTERNS = [
    "content policy", "moderation", "safety", "policy violation",
    "quota", "billing", "billing_hard_limit", "unauthorized", "authentication",
    "invalid_api_key", "permission",
]


def _is_retryable_sora_error(error: Exception) -> bool:
    """Check if a Sora error is transient and worth retrying."""
    msg = str(error).lower()
    return not any(pattern in msg for pattern in _SORA_NO_RETRY_PATTERNS)


@activity.defn
async def generate_sora_clips(run_id: int, concept: dict, narration_result: dict) -> dict:
    """Generate video clips — uses Grok or Sora based on concept config."""
    video_engine = concept.get("video_engine", "sora")

    if video_engine == "grok":
        return await _generate_grok_clips(run_id, concept, narration_result)

    from packages.clients.sora import generate_video_async, _extract_last_frame

    await _update_step(run_id, "generate_sora_clips")

    output_dir = f"output/unified_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    clips = concept["clips"]
    narrations = narration_result["narrations"]
    use_chaining = concept.get("frame_chain", False)

    # Concept-level reference image for character/style consistency
    style_ref = concept.get("reference_image")

    if use_chaining:
        # Sequential with frame chaining
        generated = []
        prev_frame_url = None
        for i, clip in enumerate(clips):
            narr = narrations[i]
            sora_duration = narr.get("sora_duration", 8)
            output_path = os.path.join(output_dir, f"clip_{i}.mp4")

            # Frame chain takes priority, then per-clip image, then style ref
            clip_img = clip.get("image_url") or (
                _file_to_data_url(clip["image_path"]) if clip.get("image_path") else None
            )
            ref = prev_frame_url or clip_img or style_ref
            result = await _generate_clip_with_retry(
                clip["prompt"], output_path, sora_duration, ref, run_id, i,
            )
            prev_frame_url = _extract_last_frame(output_path)
            generated.append({
                "index": i, "path": output_path,
                "sora_duration": sora_duration, "video_id": result.get("video_id"),
            })
    else:
        # Parallel — all clips fire at once, ~5x faster
        logger.info("generating clips in parallel", run_id=run_id, count=len(clips))

        async def _gen_one(i: int, clip: dict) -> dict:
            narr = narrations[i]
            sora_duration = narr.get("sora_duration", 8)
            output_path = os.path.join(output_dir, f"clip_{i}.mp4")
            # Per-clip reference: image_url (inline) or image_path (file to convert)
            clip_ref = clip.get("image_url") or style_ref
            if not clip_ref and clip.get("image_path"):
                clip_ref = _file_to_data_url(clip["image_path"])
            result = await _generate_clip_with_retry(
                clip["prompt"], output_path, sora_duration, clip_ref, run_id, i,
            )
            return {
                "index": i, "path": output_path,
                "sora_duration": sora_duration, "video_id": result.get("video_id"),
            }

        tasks = [_gen_one(i, clip) for i, clip in enumerate(clips)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        generated = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                raise RuntimeError(f"Clip {i} failed: {r}") from r
            generated.append(r)

    return {"clips": generated, "output_dir": output_dir}


async def _generate_grok_clips(run_id: int, concept: dict, narration_result: dict) -> dict:
    """Generate video clips using Grok Imagine Video — parallel, fast, no audio."""
    from packages.clients.grok import generate_video_async as grok_generate

    await _update_step(run_id, "generate_grok_clips")

    output_dir = f"output/unified_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    clips = concept["clips"]
    narrations = narration_result["narrations"]

    async def _gen_one(i: int, clip: dict) -> dict:
        narr = narrations[i]
        sora_duration = narr.get("sora_duration", 8)
        output_path = os.path.join(output_dir, f"clip_{i}.mp4")

        # Per-clip reference image
        ref = clip.get("image_url")
        if not ref and clip.get("image_path"):
            ref = _file_to_data_url(clip["image_path"])

        try:
            result = await grok_generate(
                prompt=clip["prompt"],
                output_path=output_path,
                duration=min(sora_duration, 15),  # Grok max is 15s
                aspect_ratio="9:16",
                reference_image_url=ref,
            )
            logger.info("grok clip done", run_id=run_id, clip=i, path=output_path)
            return {
                "index": i, "path": output_path,
                "sora_duration": sora_duration, "video_id": result.get("video_id"),
            }
        except Exception as e:
            logger.error("grok clip failed", run_id=run_id, clip=i, error=str(e)[:200])
            raise

    logger.info("generating grok clips in parallel", run_id=run_id, count=len(clips))
    tasks = [_gen_one(i, clip) for i, clip in enumerate(clips)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    generated = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            raise RuntimeError(f"Grok clip {i} failed: {r}") from r
        generated.append(r)

    return {"clips": generated, "output_dir": output_dir}


async def _generate_clip_with_retry(prompt: str, output_path: str, duration: int,
                                      reference_url: str | None, run_id: int, clip_idx: int,
                                      max_retries: int = 2) -> dict:
    """Generate a single Sora clip with retry on transient errors only."""
    from packages.clients.sora import generate_video_async

    for attempt in range(1, max_retries + 1):
        try:
            result = await generate_video_async(
                prompt=prompt,
                output_path=output_path,
                duration=duration,
                size=f"{WIDTH}x{HEIGHT}",
                timeout=1200,
                reference_image_url=reference_url,
            )
            logger.info("sora clip done", run_id=run_id, clip=clip_idx, path=output_path)
            return result
        except Exception as e:
            if not _is_retryable_sora_error(e) or attempt == max_retries:
                logger.error("sora clip failed permanently", run_id=run_id, clip=clip_idx,
                            error=str(e)[:200], retryable=_is_retryable_sora_error(e))
                raise
            logger.warning("sora clip failed, retrying", run_id=run_id, clip=clip_idx,
                          attempt=attempt, error=str(e)[:200])
            await asyncio.sleep(15 * attempt)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# Activity 3: Mix clip audio (Sora audio + narration)
# ---------------------------------------------------------------------------

@activity.defn
async def mix_clip_audio(run_id: int, clips_result: dict, narration_result: dict, concept: dict) -> dict:
    """Mix Sora native audio with narration per clip."""
    await _update_step(run_id, "mix_clip_audio")

    output_dir = f"output/unified_run_{run_id}/mixed"
    os.makedirs(output_dir, exist_ok=True)

    sora_volume = concept.get("sora_volume", 0.4)
    narration_volume = concept.get("narration_volume", 1.3)
    clips = clips_result["clips"]
    narrations = narration_result["narrations"]
    mixed = []

    for clip in clips:
        i = clip["index"]
        narr = narrations[i]
        output_path = os.path.join(output_dir, f"mixed_{i}.mp4")

        if narr.get("path") and os.path.exists(narr["path"]):
            _mix_narration_into_clip(
                clip_path=clip["path"],
                narration_path=narr["path"],
                output_path=output_path,
                sora_volume=sora_volume,
                narration_volume=narration_volume,
            )
        else:
            _ffmpeg_copy(clip["path"], output_path)

        mixed.append({"index": i, "path": output_path})

    return {"mixed_clips": mixed, "output_dir": output_dir}


# ---------------------------------------------------------------------------
# Activity 4: Normalize and concatenate
# ---------------------------------------------------------------------------

@activity.defn
async def normalize_and_concat(run_id: int, mixed_result: dict, narration_result: dict) -> dict:
    """Normalize clips, trim each to narration length + buffer, then hard-cut concat.

    Returns actual measured duration of each clip so subtitles sync perfectly.
    """
    await _update_step(run_id, "normalize_and_concat")

    output_dir = f"output/unified_run_{run_id}"
    norm_dir = os.path.join(output_dir, "normalized")
    trim_dir = os.path.join(output_dir, "trimmed")
    os.makedirs(norm_dir, exist_ok=True)
    os.makedirs(trim_dir, exist_ok=True)

    mixed_clips = mixed_result["mixed_clips"]
    narrations = narration_result["narrations"]
    final_paths = []
    clip_durations = []  # Actual measured duration of each final clip

    for clip in mixed_clips:
        i = clip["index"]
        norm_path = os.path.join(norm_dir, f"norm_{i}.mp4")
        _normalize_clip(clip["path"], norm_path)

        # Trim each clip to narration duration + 2.0s buffer.
        # This ensures narration finishes completely before the cut.
        narr = narrations[i]
        narr_dur = narr.get("duration", 0)
        if narr_dur > 0:
            clip_dur = _get_video_duration(norm_path)
            target_dur = narr_dur + 3.0
            if clip_dur > target_dur + 0.5:
                trim_path = os.path.join(trim_dir, f"trim_{i}.mp4")
                _ffmpeg_trim(norm_path, trim_path, target_dur)
                actual_dur = _get_video_duration(trim_path)
                final_paths.append(trim_path)
                clip_durations.append(actual_dur)
                logger.info("trimmed clip", clip=i, from_dur=round(clip_dur, 1),
                           to_dur=round(actual_dur, 1))
                continue

        # No trim needed — use as-is
        actual_dur = _get_video_duration(norm_path)
        final_paths.append(norm_path)
        clip_durations.append(actual_dur)

    # Hard-cut concat
    raw_path = os.path.join(output_dir, "raw_concat.mp4")
    _ffmpeg_concat(final_paths, raw_path)

    duration = _get_video_duration(raw_path)

    logger.info("concat complete", duration=round(duration, 1), clips=len(final_paths),
               clip_durations=[round(d, 2) for d in clip_durations])
    return {"raw_video": raw_path, "duration": duration, "clip_durations": clip_durations}


# ---------------------------------------------------------------------------
# Activity 5: Generate karaoke subtitles
# ---------------------------------------------------------------------------

@activity.defn
async def generate_karaoke_subtitles(run_id: int, concat_result: dict, narration_result: dict, concept: dict) -> dict:
    """Transcribe narrations, build karaoke ASS, burn into video."""
    await _update_step(run_id, "generate_karaoke_subtitles")

    raw_video = concat_result["raw_video"]
    output_dir = f"output/unified_run_{run_id}"
    final_path = os.path.join(output_dir, "final.mp4")
    ass_path = os.path.join(output_dir, "subs.ass")

    # Skip subtitles if concept says so (e.g. kids content, dialogue-only videos)
    if concept.get("skip_subtitles"):
        _ffmpeg_copy(raw_video, final_path)
        file_size = os.path.getsize(final_path)
        await _store_asset(run_id, concept.get("channel_id", 1), "rendered_unified_short", json.dumps({
            "path": final_path, "file_size_bytes": file_size,
        }))
        return {"video_path": final_path, "file_size": file_size}

    narrations = narration_result["narrations"]
    clips = concept["clips"]

    # Phase A: Compute real clip boundaries from measured durations
    clip_starts, clip_ends = _compute_clip_offsets(narrations, concat_result)

    # Phase B: Transcribe each narration with Faster-Whisper
    all_words = []  # List of (word, start, end, clip_index)
    for narr in narrations:
        if not narr.get("path") or not os.path.exists(narr["path"]):
            continue
        words = _transcribe_words(narr["path"])
        idx = narr["index"]
        offset = clip_starts[idx]
        clip_end = clip_ends[idx]
        for w in words:
            w_start = w["start"] + offset
            w_end = w["end"] + offset
            # Clamp words to within their clip boundary — prevents bleed into next clip
            if w_start >= clip_end:
                break
            w_end = min(w_end, clip_end - 0.05)
            all_words.append((w["word"], w_start, w_end, idx))

    # Phase C: Generate ASS file
    clip_labels = [c.get("label", "") for c in clips]
    clip_start_list = [clip_starts.get(i, 0) for i in range(len(clips))]
    clip_end_list = [clip_ends.get(i, concat_result["duration"]) for i in range(len(clips))]

    _write_karaoke_ass(ass_path, clip_labels, clip_start_list, clip_end_list, all_words)

    # Phase D: Burn subtitles into video
    # Escape backslashes and colons in ass_path for ffmpeg on Linux
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", raw_video,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        "-movflags", "+faststart",
        final_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("subtitle burn failed", stderr=result.stderr[-500:])
        # Fallback: copy raw as final
        _ffmpeg_copy(raw_video, final_path)

    file_size = os.path.getsize(final_path)
    logger.info("karaoke subtitles complete", path=final_path, size_mb=round(file_size / 1024 / 1024, 1))

    # Store rendered video asset
    await _store_asset(run_id, concept.get("channel_id", 1), "rendered_unified_short", json.dumps({
        "path": final_path,
        "file_size_bytes": file_size,
    }))

    return {"video_path": final_path, "file_size": file_size, "ass_path": ass_path}


# ---------------------------------------------------------------------------
# Activity 6: QA check
# ---------------------------------------------------------------------------

@activity.defn
async def unified_qa_check(run_id: int, rendered: dict) -> dict:
    """FFprobe checks: vertical, 8-59s, 1-500MB, audio present."""
    await _update_step(run_id, "qa_check")

    video_path = rendered["video_path"]
    issues = []

    # Resolution check
    w, h = _get_video_dimensions(video_path)
    if w != WIDTH or h != HEIGHT:
        issues.append(f"Resolution {w}x{h}, expected {WIDTH}x{HEIGHT}")

    # Duration check
    duration = _get_video_duration(video_path)
    if duration < 8:
        issues.append(f"Too short: {duration:.1f}s (min 8s)")
    if duration > 180:
        issues.append(f"Over 3min Shorts limit: {duration:.1f}s")

    # File size check
    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    if size_mb < 1:
        issues.append(f"Too small: {size_mb:.1f}MB (min 1MB)")
    if size_mb > 500:
        issues.append(f"Too large: {size_mb:.1f}MB (max 500MB)")

    # Audio check
    if not _has_audio(video_path):
        issues.append("No audio stream detected")

    passed = len(issues) == 0
    logger.info("qa check", passed=passed, issues=issues)

    return {"passed": passed, "issues": issues, "duration": duration, "size_mb": round(size_mb, 1)}


# ---------------------------------------------------------------------------
# Activity 7: Gemini review
# ---------------------------------------------------------------------------

@activity.defn
async def gemini_review(run_id: int, rendered: dict, concept: dict) -> dict:
    """Review the rendered video with Gemini."""
    await _update_step(run_id, "gemini_review")

    from packages.clients.gemini import review_video
    from packages.prompts.video_review import build_review_prompt

    video_path = rendered["video_path"]
    prompt = build_review_prompt(concept)

    try:
        response_text = review_video(video_path, prompt)
        # Parse JSON from response
        review = _parse_review_json(response_text)
        review["reviewed"] = True
    except Exception as e:
        logger.warning("gemini review failed", error=str(e)[:200])
        review = {"reviewed": False, "error": str(e)[:200]}

    # Store review asset
    await _store_asset(run_id, concept.get("channel_id", 1), "video_review", json.dumps(review))

    return review


# ---------------------------------------------------------------------------
# Activity 8: Production QA (Gemini watches the video like a human editor)
# ---------------------------------------------------------------------------

@activity.defn
async def gemini_production_qa(run_id: int, rendered: dict, concept: dict) -> dict:
    """Gemini watches the video and flags production issues a human editor would catch."""
    await _update_step(run_id, "production_qa")

    from packages.clients.gemini import review_video

    video_path = rendered["video_path"]
    clips = concept.get("clips", [])

    # Build clip descriptions for Gemini to check against
    clip_descriptions = ""
    for i, clip in enumerate(clips):
        clip_descriptions += f"\nClip {i+1}: {clip.get('label', '')} — Prompt: {clip.get('prompt', '')[:150]}"
        clip_descriptions += f"\n  Narration: {clip.get('narration', '')[:100]}"

    prompt = f"""You are a video editor doing a final quality check on a YouTube Short before publishing.
Watch this video carefully and check for these specific production issues:

CONCEPT: {concept.get('title', '')}
CLIPS:{clip_descriptions}

Check each of these and be specific about timestamps:

1. **TEXT READABILITY**: Are any on-screen text overlays hard to read? Do they overlap each other? Are they too small? Cut off by the edges?

2. **NARRATION SYNC**: Does the narration ever get cut off mid-sentence when a clip transitions? Is there dead silence where narration should be playing? Does the audio feel rushed or too slow?

3. **VISUAL MATCH**: For each clip, does the visual actually match what was described in the prompt? If clip 2 should show a Megalodon but shows something else, flag it. Note any clips that start showing the wrong subject before switching.

4. **PACING**: Are there awkward pauses, dead time at the end of clips, or abrupt cuts? Does the video feel too long or too short? Does it end cleanly or cut off mid-action?

5. **CLIP TRANSITIONS**: Do the transitions between clips feel natural or jarring? Any visual glitches at cut points?

6. **OVERALL WATCHABILITY**: If you saw this while scrolling YouTube Shorts, would you keep watching? What is the single biggest issue that needs fixing?

Return JSON (no markdown):
{{
  "text_issues": ["list of specific text/overlay problems"],
  "narration_issues": ["list of specific audio/narration sync problems"],
  "visual_match_issues": ["list of clips that don't match their prompt"],
  "pacing_issues": ["list of pacing/timing problems"],
  "transition_issues": ["list of transition problems"],
  "biggest_issue": "the single most important thing to fix",
  "verdict": "pass" or "needs_fixes",
  "fix_suggestions": ["ordered list of what to change, most important first"]
}}"""

    try:
        response_text = review_video(video_path, prompt)
        qa = _parse_review_json(response_text)
        qa["reviewed"] = True
    except Exception as e:
        logger.warning("production QA failed", error=str(e)[:200])
        qa = {"reviewed": False, "error": str(e)[:200]}

    await _store_asset(run_id, concept.get("channel_id", 1), "production_qa", json.dumps(qa))
    logger.info("production QA complete", verdict=qa.get("verdict"), biggest_issue=qa.get("biggest_issue", "")[:80])

    return qa


# ---------------------------------------------------------------------------
# Activity 9: Auto-fix subtitle issues flagged by production QA
# ---------------------------------------------------------------------------

@activity.defn
async def auto_fix_subtitles(run_id: int, rendered: dict, production_qa_result: dict,
                              concat_result: dict, narration_result: dict, concept: dict) -> dict:
    """If production QA flagged text/timing issues, regenerate subtitles and re-burn.

    Only fixes subtitle-related issues (free — just FFmpeg). Does NOT re-generate
    Sora clips (expensive). Returns the new rendered path or the original if no fix needed.
    """
    if not production_qa_result.get("reviewed"):
        return rendered

    text_issues = production_qa_result.get("text_issues", [])
    narration_issues = production_qa_result.get("narration_issues", [])

    # Only auto-fix if there are text/narration timing issues
    has_text_issues = len(text_issues) > 0
    has_timing_issues = any(
        "cut off" in issue.lower() or "overlap" in issue.lower() or
        "linger" in issue.lower() or "sync" in issue.lower() or
        "timing" in issue.lower()
        for issue in narration_issues
    )

    if not has_text_issues and not has_timing_issues:
        logger.info("auto-fix: no subtitle issues to fix", run_id=run_id)
        return rendered

    await _update_step(run_id, "auto_fix_subtitles")
    logger.info("auto-fix: regenerating subtitles", run_id=run_id,
               text_issues=len(text_issues), timing_issues=has_timing_issues)

    output_dir = f"output/unified_run_{run_id}"
    raw_video = concat_result["raw_video"]
    fixed_path = os.path.join(output_dir, "final_fixed.mp4")
    ass_path = os.path.join(output_dir, "subs_fixed.ass")

    narrations = narration_result["narrations"]
    clips = concept["clips"]

    # Recompute clip boundaries from actual durations
    clip_starts, clip_ends = _compute_clip_offsets(narrations, concat_result)

    # Re-transcribe and rebuild subtitles with tighter clamping
    all_words = []
    for narr in narrations:
        if not narr.get("path") or not os.path.exists(narr["path"]):
            continue
        words = _transcribe_words(narr["path"])
        idx = narr["index"]
        offset = clip_starts[idx]
        clip_end = clip_ends[idx]
        for w in words:
            w_start = w["start"] + offset
            w_end = w["end"] + offset
            if w_start >= clip_end - 0.1:
                break
            w_end = min(w_end, clip_end - 0.1)
            all_words.append((w["word"], w_start, w_end, idx))

    clip_labels = [c.get("label", "") for c in clips]
    clip_start_list = [clip_starts.get(i, 0) for i in range(len(clips))]
    clip_end_list = [clip_ends.get(i, concat_result["duration"]) for i in range(len(clips))]

    _write_karaoke_ass(ass_path, clip_labels, clip_start_list, clip_end_list, all_words)

    # Re-burn subtitles
    ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y",
        "-i", raw_video,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        "-movflags", "+faststart",
        fixed_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.warning("auto-fix burn failed, keeping original", stderr=result.stderr[-300:])
        return rendered

    file_size = os.path.getsize(fixed_path)
    logger.info("auto-fix complete", run_id=run_id, path=fixed_path,
               size_mb=round(file_size / 1024 / 1024, 1))

    # Update the rendered asset to point to the fixed version
    await _store_asset(run_id, concept.get("channel_id", 1), "rendered_unified_short", json.dumps({
        "path": fixed_path,
        "file_size_bytes": file_size,
        "auto_fixed": True,
    }))

    return {"video_path": fixed_path, "file_size": file_size, "auto_fixed": True}


# ---------------------------------------------------------------------------
# Activity 10: Mark pending review
# ---------------------------------------------------------------------------

@activity.defn
async def unified_mark_pending_review(run_id: int, concept: dict) -> dict:
    """Update DB status and store publish metadata."""
    await _update_step(run_id, "pending_review")

    channel_id = concept.get("channel_id", 1)

    # Store publish_metadata asset
    metadata = {
        "title": concept.get("title", "Untitled"),
        "description": concept.get("caption", ""),
        "tags": concept.get("tags", []),
        "category": "Entertainment",
    }
    await _store_asset(run_id, channel_id, "publish_metadata", json.dumps(metadata))

    # Update run status
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'pending_review', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    logger.info("marked pending review", run_id=run_id)
    return {"status": "pending_review"}


# ===========================================================================
# Helper functions
# ===========================================================================

async def _update_step(run_id: int, step: str):
    """Update current_step in DB."""
    try:
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET current_step = :step WHERE id = :id"),
                {"id": run_id, "step": step},
            )
            await session.commit()
    except Exception as e:
        logger.warning("failed to update step", run_id=run_id, step=step, error=str(e))


async def _store_asset(run_id: int, channel_id: int, asset_type: str, content: str):
    """Store an asset in the DB."""
    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": asset_type, "content": content},
        )
        await session.commit()


def _get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def _get_video_duration(path: str) -> float:
    """Get video duration in seconds."""
    return _get_audio_duration(path)


def _get_video_dimensions(path: str) -> tuple[int, int]:
    """Get video width and height."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        parts = result.stdout.strip().split(",")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def _file_to_data_url(path: str, target_w: int = 720, target_h: int = 1280) -> str | None:
    """Convert image to base64 data URL, resizing to match Sora's expected dimensions."""
    import base64
    if not path or not os.path.exists(path):
        return None

    resized_path = path.replace(".png", "_resized.jpg").replace(".jpg", "_resized.jpg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-vf",
         f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
         f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black",
         "-q:v", "2", resized_path],
        capture_output=True, text=True, timeout=10,
    )
    use_path = resized_path if result.returncode == 0 and os.path.exists(resized_path) else path

    ext = os.path.splitext(use_path)[1].lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "image/jpeg")
    with open(use_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def _has_audio(path: str) -> bool:
    """Check if a file has an audio stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return bool(result.stdout.strip())


def _pick_sora_duration(target: float) -> int:
    """Pick nearest Sora duration (4, 8, or 12) that fits the narration."""
    options = [4, 8, 12]
    # Pick the smallest option >= target, or 12 if target > 12
    for opt in options:
        if opt >= target:
            return opt
    return 12


def _mix_narration_into_clip(clip_path: str, narration_path: str, output_path: str,
                              sora_volume: float = 0.4, narration_volume: float = 1.3):
    """Mix narration audio into a video clip alongside Sora's native audio."""
    has_clip_audio = _has_audio(clip_path)

    if has_clip_audio:
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
        logger.warning("narration mix failed, copying original", stderr=result.stderr[-300:])
        _ffmpeg_copy(clip_path, output_path)


def _ffmpeg_copy(input_path: str, output_path: str):
    """Copy a single file with faststart."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c", "copy", "-movflags", "+faststart",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def _normalize_clip(input_path: str, output_path: str):
    """Normalize a clip to consistent resolution, frame rate, color, and audio."""
    vf_filters = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"colorlevels=rimin=0.02:gimin=0.02:bimin=0.02:rimax=0.98:gimax=0.98:bimax=0.98,"
        f"eq=contrast=1.05:saturation=1.1,"
        f"fps=30,"
        f"format=yuv420p"
    )

    has_audio = _has_audio(input_path)

    if has_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf_filters,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", vf_filters,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Normalize failed: {result.stderr[-300:]}")


def _ffmpeg_concat(clip_paths: list[str], output_path: str):
    """Hard-cut concatenation using concat demuxer."""
    concat_file = output_path.replace(".mp4", "_concat.txt")
    with open(concat_file, "w") as f:
        for path in clip_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Concat failed: {result.stderr[-300:]}")

    # Clean up concat file
    try:
        os.remove(concat_file)
    except OSError:
        pass


def _ffmpeg_trim(input_path: str, output_path: str, max_seconds: float):
    """Trim a video to max_seconds."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-t", str(max_seconds),
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Trim failed: {result.stderr[-300:]}")


def _transcribe_words(audio_path: str) -> list[dict]:
    """Transcribe audio file and return word-level timestamps."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    words = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                words.append({
                    "word": w.word.strip(),
                    "start": w.start,
                    "end": w.end,
                })
    return words


def _compute_clip_offsets(narrations: list[dict], concat_result: dict) -> tuple[dict[int, float], dict[int, float]]:
    """Compute clip start/end offsets using ACTUAL measured durations from concat.

    Returns (start_offsets, end_offsets) dicts keyed by clip index.
    """
    clip_durations = concat_result.get("clip_durations", [])
    starts = {}
    ends = {}
    current = 0.0

    for i, narr in enumerate(narrations):
        idx = narr["index"]
        starts[idx] = current
        if i < len(clip_durations):
            dur = clip_durations[i]
        else:
            # Fallback if clip_durations not available
            narr_dur = narr.get("duration", 0)
            dur = (narr_dur + 3.0) if narr_dur > 0 else narr.get("sora_duration", 8)
        ends[idx] = current + dur
        current += dur

    return starts, ends


def _format_ass_time(seconds: float) -> str:
    """Format seconds to ASS time format: H:MM:SS.CC"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _write_karaoke_ass(ass_path: str, clip_labels: list[str],
                        clip_starts: list[float], clip_ends: list[float],
                        all_words: list[tuple]):
    """Write ASS subtitle file with karaoke-style word highlighting."""
    header = """[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Label,Impact,32,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,8,60,60,100,1
Style: Word,Impact,56,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header.strip()]

    # Labels on each clip (shown at top of screen)
    for i, label in enumerate(clip_labels):
        if label and i < len(clip_starts):
            l_start = _format_ass_time(clip_starts[i])
            l_end = _format_ass_time(clip_ends[i])
            lines.append(f"Dialogue: 0,{l_start},{l_end},Label,,0,0,0,,{label}")

    # Karaoke word groups (3 words per group, never spanning clip boundaries)
    if all_words:
        # Split words by clip first, then group within each clip
        from itertools import groupby
        for _clip_idx, clip_words_iter in groupby(all_words, key=lambda w: w[3]):
            clip_words = list(clip_words_iter)

            for gi in range(0, len(clip_words), 3):
                group = clip_words[gi:gi + 3]
                words_text = [w[0] for w in group]
                word_count = len(group)

                # Calculate per-word timing within the group
                word_times = []
                for j, (word, ws, we, _ci) in enumerate(group):
                    if j + 1 < word_count:
                        word_times.append((ws, group[j + 1][1]))
                    else:
                        word_times.append((ws, we))

                # Emit a dialogue line per word-highlight position
                for active_idx in range(word_count):
                    w_start = word_times[active_idx][0]
                    w_end = word_times[active_idx][1]

                    parts = []
                    for j, wt in enumerate(words_text):
                        if j == active_idx:
                            parts.append("{\\1c&H00FFFF&}" + wt)
                        else:
                            parts.append("{\\1c&HFFFFFF&}" + wt)
                    styled = " ".join(parts)

                    t1 = _format_ass_time(w_start)
                    t2 = _format_ass_time(w_end)
                    lines.append(f"Dialogue: 1,{t1},{t2},Word,,0,0,0,,{styled}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info("karaoke ASS written", path=ass_path, word_groups=len(all_words) // 3)


def _parse_review_json(text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown code blocks."""
    import re
    # Strip markdown code blocks if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}
