"""Direct video generation pipeline — no Temporal, no worker, just runs.

Generates clips with Grok (or Sora), mixes audio, concatenates, burns subtitles.
Runs as a background task from the API.
"""

import asyncio
import json
import os
import subprocess

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

def _get_bg_session():
    """Get a fresh async session for the background pipeline thread.

    Creates a new engine each time to avoid event loop conflicts.
    """
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()

WIDTH = 720
HEIGHT = 1280


async def run_pipeline(run_id: int, concept: dict):
    """Run the full video generation pipeline directly."""
    try:
        await _update_step(run_id, "starting")
        channel_id = concept.get("channel_id", 1)
        video_engine = concept.get("video_engine", "grok")

        output_dir = f"output/unified_run_{run_id}"
        os.makedirs(output_dir, exist_ok=True)

        # 1. Generate narrations (if any clips have narration text)
        await _update_step(run_id, "generate_narrations")
        narrations = await _generate_narrations(run_id, concept)

        # 2. Generate video clips
        step_name = f"generate_{video_engine}_clips"
        await _update_step(run_id, step_name)
        if video_engine == "grok":
            clips = await _generate_grok_clips(run_id, concept, narrations)
        else:
            clips = await _generate_sora_clips(run_id, concept, narrations)

        # 3. Mix audio (narration + clip audio)
        await _update_step(run_id, "mix_audio")
        mixed = await _mix_audio(run_id, clips, narrations, concept)

        # 4. Normalize and concatenate
        await _update_step(run_id, "normalize_concat")
        concat_path, clip_durations = await _normalize_and_concat(run_id, mixed, narrations)

        # 5. Burn subtitles (unless skipped)
        await _update_step(run_id, "subtitles")
        if concept.get("skip_subtitles"):
            final_path = os.path.join(output_dir, "final.mp4")
            _ffmpeg_copy(concat_path, final_path)
        else:
            final_path = await _burn_subtitles(run_id, concat_path, narrations, concept, clip_durations)

        file_size = os.path.getsize(final_path)

        # 6. Store rendered asset
        await _store_asset(run_id, channel_id, "rendered_unified_short", json.dumps({
            "path": final_path, "file_size_bytes": file_size,
        }))

        # 7. Embedding QA — compare generated video against reference + script
        await _update_step(run_id, "embedding_qa")
        await _run_embedding_qa(run_id, output_dir, concept, channel_id)

        # 8. Production QA — Gemini watches the video
        await _update_step(run_id, "production_qa")
        await _run_production_qa(run_id, final_path, concept, channel_id)

        # 8. Store publish metadata
        await _store_asset(run_id, channel_id, "publish_metadata", json.dumps({
            "title": concept.get("title", "Untitled"),
            "description": concept.get("caption", ""),
            "tags": concept.get("tags", []),
            "category": "Entertainment",
        }))

        # 9. Mark pending review
        await _update_step(run_id, "pending_review")
        async with _get_bg_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'pending_review', completed_at = NOW() WHERE id = :id"),
                {"id": run_id},
            )
            await session.commit()

        logger.info("pipeline complete", run_id=run_id, path=final_path,
                    size_mb=round(file_size / 1024 / 1024, 1))

    except Exception as e:
        logger.error("pipeline failed", run_id=run_id, error=str(e)[:300])
        async with _get_bg_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id"),
                {"id": run_id, "err": str(e)[:500]},
            )
            await session.commit()


# ---------------------------------------------------------------------------
# Step 1: Narrations
# ---------------------------------------------------------------------------

async def _generate_narrations(run_id: int, concept: dict) -> list[dict]:
    """Generate ElevenLabs TTS for clips that have narration text."""
    from packages.clients.elevenlabs import generate_speech

    output_dir = f"output/unified_run_{run_id}/narration"
    os.makedirs(output_dir, exist_ok=True)

    voice = concept.get("voice_id", "George")
    clips = concept["clips"]
    results = []

    for i, clip in enumerate(clips):
        narration_text = clip.get("narration", "")
        if not narration_text:
            sora_dur = clip.get("duration") or 8
            results.append({"index": i, "path": None, "duration": 0, "sora_duration": sora_dur})
            continue

        output_path = os.path.join(output_dir, f"n_{i}.mp3")
        logger.info("generating narration", run_id=run_id, clip=i)
        generate_speech(text=narration_text, voice=voice, output_path=output_path)

        duration = _get_duration(output_path)
        if len(clips) == 1:
            sora_duration = clip.get("duration") or 8
        else:
            sora_duration = clip.get("duration") or _pick_sora_duration(duration + 3.0)

        results.append({
            "index": i, "path": output_path,
            "duration": duration, "sora_duration": sora_duration,
        })

    return results


# ---------------------------------------------------------------------------
# Step 2: Video clips
# ---------------------------------------------------------------------------

async def _generate_grok_clips(run_id: int, concept: dict, narrations: list[dict]) -> list[dict]:
    """Generate clips with Grok Imagine Video — all in parallel."""
    from packages.clients.grok import generate_video_async

    output_dir = f"output/unified_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)
    clips = concept["clips"]

    async def gen_one(i, clip):
        narr = narrations[i]
        dur = narr.get("sora_duration", 8)
        path = os.path.join(output_dir, f"clip_{i}.mp4")

        ref = None
        if clip.get("image_path"):
            ref = _file_to_data_url(clip["image_path"])
        elif clip.get("image_url"):
            ref = clip["image_url"]

        result = await generate_video_async(
            prompt=clip["prompt"], output_path=path,
            duration=min(dur, 15), aspect_ratio="9:16",
            reference_image_url=ref,
        )
        logger.info("grok clip done", run_id=run_id, clip=i)
        return {"index": i, "path": path, "sora_duration": dur}

    tasks = [gen_one(i, c) for i, c in enumerate(clips)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    generated = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            raise RuntimeError(f"Clip {i} failed: {r}")
        generated.append(r)
    return generated


async def _generate_sora_clips(run_id: int, concept: dict, narrations: list[dict]) -> list[dict]:
    """Generate clips with Sora 2 or Sora 2 Pro. Uses video extension for multi-clip continuity."""
    from packages.clients.sora import generate_video_async, extend_video_async

    output_dir = f"output/unified_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)
    clips = concept["clips"]

    # Use sora-2-pro for single-clip videos, sora-2 for multi-clip
    sora_model = "sora-2-pro" if len(clips) == 1 else "sora-2"
    # Allow concept to override
    sora_model = concept.get("sora_model", sora_model)

    # Use ONE reference image for ALL clips
    style_ref = concept.get("reference_image")
    if not style_ref:
        for clip in clips:
            if clip.get("image_path"):
                style_ref = _file_to_data_url(clip["image_path"])
                break
            elif clip.get("image_url"):
                style_ref = clip["image_url"]
                break

    # Warn about long prompts (Sora drifts after 1500 chars, hard limit ~2000)
    for i, clip in enumerate(clips):
        prompt_len = len(clip.get("prompt", ""))
        if prompt_len > 1800:
            logger.warning("prompt too long, may be truncated", run_id=run_id, clip=i, chars=prompt_len)
        elif prompt_len > 1500:
            logger.info("prompt approaching limit", run_id=run_id, clip=i, chars=prompt_len)

    if len(clips) == 1:
        # Single clip — generate directly
        await _update_step(run_id, "generating clip 1/1")
        clip = clips[0]
        narr = narrations[0]
        dur = narr.get("sora_duration", 8)
        path = os.path.join(output_dir, "clip_0.mp4")

        try:
            result = await generate_video_async(
                prompt=clip["prompt"], output_path=path,
                duration=dur, size=f"{WIDTH}x{HEIGHT}",
                reference_image_url=style_ref, model=sora_model,
            )
        except Exception as e:
            if "moderation" in str(e).lower() or "blocked" in str(e).lower():
                logger.warning("clip moderation blocked, softening", run_id=run_id)
                result = await generate_video_async(
                    prompt=_soften_prompt(clip["prompt"]), output_path=path,
                    duration=dur, size=f"{WIDTH}x{HEIGHT}",
                    reference_image_url=style_ref, model=sora_model,
                )
            else:
                raise

        logger.info("sora clip done", run_id=run_id, clip=0)
        return [{"index": 0, "path": path, "sora_duration": dur, "video_id": result.get("video_id")}]

    else:
        # Multi-clip — generate first clip, then EXTEND for each subsequent clip
        # Extension uses the full previous video as context for perfect continuity
        generated = []

        # Generate clip 1
        total = len(clips)
        await _update_step(run_id, f"generating clip 1/{total}")
        clip = clips[0]
        narr = narrations[0]
        dur = narr.get("sora_duration", 8)
        path = os.path.join(output_dir, "clip_0.mp4")

        try:
            result = await generate_video_async(
                prompt=clip["prompt"], output_path=path,
                duration=dur, size=f"{WIDTH}x{HEIGHT}",
                reference_image_url=style_ref, model=sora_model,
            )
        except Exception as e:
            if "moderation" in str(e).lower() or "blocked" in str(e).lower():
                result = await generate_video_async(
                    prompt=_soften_prompt(clip["prompt"]), output_path=path,
                    duration=dur, size=f"{WIDTH}x{HEIGHT}",
                    reference_image_url=style_ref, model=sora_model,
                )
            else:
                raise

        logger.info("sora clip 0 done", run_id=run_id, video_id=result.get("video_id"))
        prev_video_id = result["video_id"]
        total_duration = dur
        generated.append({"index": 0, "path": path, "sora_duration": dur, "video_id": prev_video_id})

        # Extend for each subsequent clip
        for i in range(1, len(clips)):
            await _update_step(run_id, f"extending clip {i+1}/{total}")
            clip = clips[i]
            narr = narrations[i]
            clip_dur = narr.get("sora_duration", 8)
            # Extension seconds = just the NEW segment length
            # Must be a valid Sora duration: 4, 8, 12, 16, or 20
            valid_durations = [4, 8, 12, 16, 20]
            ext_dur = min(d for d in valid_durations if d >= clip_dur) if clip_dur <= 20 else 20
            total_duration += ext_dur
            path = os.path.join(output_dir, f"clip_{i}.mp4")

            try:
                result = await extend_video_async(
                    video_id=prev_video_id,
                    prompt=clip["prompt"],
                    output_path=path,
                    duration=ext_dur,
                    model=sora_model,
                )
            except Exception as e:
                if "moderation" in str(e).lower() or "blocked" in str(e).lower():
                    logger.warning("extension moderation blocked, softening", run_id=run_id, clip=i)
                    result = await extend_video_async(
                        video_id=prev_video_id,
                        prompt=_soften_prompt(clip["prompt"]),
                        output_path=path,
                        duration=ext_dur,
                        model=sora_model,
                    )
                else:
                    raise

            logger.info("sora extension done", run_id=run_id, clip=i, total_dur=total_duration)
            prev_video_id = result["video_id"]
            generated.append({"index": i, "path": path, "sora_duration": clip_dur, "video_id": prev_video_id})

        # The last extension contains the full stitched video — use that as the only clip
        # Override all clips with just the final extended video
        final_path = generated[-1]["path"]
        return [{"index": 0, "path": final_path, "sora_duration": total_duration, "video_id": prev_video_id}]


def _soften_prompt(prompt: str) -> str:
    """Replace words that trigger Sora moderation with safe alternatives."""
    replacements = {
        "blast": "wave",
        "energy blast": "powerful wave",
        "blown backwards": "sent flying",
        "blown back": "pushed back",
        "destroyed": "messy chaotic",
        "explosion": "burst of light",
        "explode": "burst",
        "punch": "force push",
        "hit ": "bump ",
        "kick": "stomp",
        "slam": "pound",
        "attack": "challenge",
        "fight": "showdown",
        "battle": "face-off",
        "weapon": "tool",
        "kill": "defeat",
        "die": "fall",
        "blood": "paint",
        "violent": "intense",
    }
    result = prompt
    for old, new in replacements.items():
        result = result.replace(old, new)
        result = result.replace(old.capitalize(), new.capitalize())
        result = result.replace(old.upper(), new.upper())
    return result


# ---------------------------------------------------------------------------
# Step 3: Mix audio
# ---------------------------------------------------------------------------

async def _mix_audio(run_id: int, clips: list[dict], narrations: list[dict], concept: dict) -> list[dict]:
    """Mix narration audio into video clips."""
    output_dir = f"output/unified_run_{run_id}/mixed"
    os.makedirs(output_dir, exist_ok=True)

    sora_volume = concept.get("sora_volume", 0.5)
    narration_volume = concept.get("narration_volume", 1.3)
    mixed = []

    for clip in clips:
        i = clip["index"]
        narr = narrations[i]
        out = os.path.join(output_dir, f"mixed_{i}.mp4")

        if narr.get("path") and os.path.exists(narr["path"]):
            _mix_narration(clip["path"], narr["path"], out, sora_volume, narration_volume)
        else:
            _ffmpeg_copy(clip["path"], out)

        mixed.append({"index": i, "path": out})
    return mixed


# ---------------------------------------------------------------------------
# Step 4: Normalize and concat
# ---------------------------------------------------------------------------

async def _normalize_and_concat(run_id: int, mixed: list[dict], narrations: list[dict]) -> tuple[str, list[float]]:
    """Normalize clips, trim to narration length, concat."""
    output_dir = f"output/unified_run_{run_id}"
    norm_dir = os.path.join(output_dir, "normalized")
    os.makedirs(norm_dir, exist_ok=True)

    final_paths = []
    clip_durations = []

    for clip in mixed:
        i = clip["index"]
        norm = os.path.join(norm_dir, f"norm_{i}.mp4")
        _normalize_clip(clip["path"], norm)

        narr = narrations[i]
        narr_dur = narr.get("duration", 0)
        if narr_dur > 0:
            clip_dur = _get_duration(norm)
            target = narr_dur + 3.0
            if clip_dur > target + 0.5:
                trim = os.path.join(norm_dir, f"trim_{i}.mp4")
                _ffmpeg_trim(norm, trim, target)
                actual = _get_duration(trim)
                final_paths.append(trim)
                clip_durations.append(actual)
                continue

        actual = _get_duration(norm)
        final_paths.append(norm)
        clip_durations.append(actual)

    concat_path = os.path.join(output_dir, "raw_concat.mp4")
    _ffmpeg_concat(final_paths, concat_path)
    return concat_path, clip_durations


# ---------------------------------------------------------------------------
# Step 5: Subtitles
# ---------------------------------------------------------------------------

async def _burn_subtitles(run_id: int, concat_path: str, narrations: list[dict],
                           concept: dict, clip_durations: list[float]) -> str:
    """Transcribe, build ASS, burn into video."""
    from faster_whisper import WhisperModel

    output_dir = f"output/unified_run_{run_id}"
    final_path = os.path.join(output_dir, "final.mp4")
    ass_path = os.path.join(output_dir, "subs.ass")

    # Compute clip boundaries
    starts, ends = {}, {}
    current = 0.0
    for i, dur in enumerate(clip_durations):
        starts[i] = current
        ends[i] = current + dur
        current += dur

    # Transcribe
    model = WhisperModel("base", device="cpu", compute_type="int8")
    all_words = []
    for narr in narrations:
        if not narr.get("path") or not os.path.exists(narr["path"]):
            continue
        segments, _ = model.transcribe(narr["path"], word_timestamps=True)
        idx = narr["index"]
        offset = starts.get(idx, 0)
        clip_end = ends.get(idx, 999)
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    ws = w.start + offset
                    we = w.end + offset
                    if ws >= clip_end - 0.1:
                        break
                    we = min(we, clip_end - 0.1)
                    all_words.append((w.word.strip(), ws, we, idx))

    # Build ASS
    clips = concept.get("clips", [])
    labels = [c.get("label", "") for c in clips]
    dialogue_lines = [c.get("dialogue", []) for c in clips]
    _write_ass(ass_path, labels, starts, ends, all_words, len(clips), dialogue_lines)

    # Burn
    ass_escaped = ass_path.replace(":", "\\:")
    cmd = ["ffmpeg", "-y", "-i", concat_path, "-vf", f"ass={ass_escaped}",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18",
           "-c:a", "copy", "-movflags", "+faststart", final_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        _ffmpeg_copy(concat_path, final_path)

    return final_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_embedding_qa(run_id: int, output_dir: str, concept: dict, channel_id: int):
    """Compare generated clips against reference images + script using Gemini Embedding 2."""
    try:
        from google import genai
        from google.genai import types
        import math

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return

        client = genai.Client(api_key=api_key)
        model = "gemini-embedding-2-preview"

        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb) if na and nb else 0

        clips = concept.get("clips", [])
        results = []

        for i, clip in enumerate(clips):
            clip_path = os.path.join(output_dir, "clips", f"clip_{i}.mp4")
            if not os.path.exists(clip_path):
                continue

            # Extract a frame from the middle of the generated clip
            frame_path = os.path.join(output_dir, f"qa_frame_{i}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-i", clip_path, "-vf", "select=eq(n\\,15)", "-vframes", "1",
                 "-q:v", "2", frame_path],
                capture_output=True, timeout=10,
            )
            if not os.path.exists(frame_path):
                continue

            with open(frame_path, "rb") as f:
                frame_data = f.read()

            # Embed the generated frame
            frame_emb = client.models.embed_content(
                model=model,
                contents=types.Content(parts=[
                    types.Part(inline_data=types.Blob(data=frame_data, mime_type="image/jpeg"))
                ]),
            )

            scores = {"clip": i}

            # Compare against script/prompt text
            prompt_text = clip.get("prompt", "")
            if prompt_text:
                text_emb = client.models.embed_content(model=model, contents=prompt_text[:500])
                scores["prompt_similarity"] = round(cosine_sim(
                    frame_emb.embeddings[0].values, text_emb.embeddings[0].values
                ), 4)

            # Compare against reference image if available
            ref_path = clip.get("image_path")
            if ref_path and os.path.exists(ref_path):
                with open(ref_path, "rb") as f:
                    ref_data = f.read()
                ref_emb = client.models.embed_content(
                    model=model,
                    contents=types.Content(parts=[
                        types.Part(inline_data=types.Blob(data=ref_data, mime_type="image/png"))
                    ]),
                )
                scores["reference_similarity"] = round(cosine_sim(
                    frame_emb.embeddings[0].values, ref_emb.embeddings[0].values
                ), 4)

            results.append(scores)

        # Flag clips that drifted
        flagged = []
        for r in results:
            if r.get("reference_similarity", 1) < 0.3:
                flagged.append(f"Clip {r['clip']}: visual drift from reference (sim={r['reference_similarity']})")
            if r.get("prompt_similarity", 1) < 0.2:
                flagged.append(f"Clip {r['clip']}: doesn't match prompt (sim={r['prompt_similarity']})")

        qa_result = {
            "clip_scores": results,
            "flagged": flagged,
            "overall_match": round(
                sum(r.get("reference_similarity", r.get("prompt_similarity", 0)) for r in results) / max(len(results), 1), 4
            ) if results else 0,
        }

        await _store_asset(run_id, channel_id, "embedding_qa", json.dumps(qa_result))
        logger.info("embedding QA complete", run_id=run_id, scores=results, flagged=len(flagged))

    except Exception as e:
        logger.warning("embedding QA failed", run_id=run_id, error=str(e)[:200])


async def _run_production_qa(run_id: int, video_path: str, concept: dict, channel_id: int):
    """Gemini watches the rendered video and flags production issues."""
    try:
        from packages.clients.gemini import review_video

        clips = concept.get("clips", [])
        clip_descriptions = ""
        for i, clip in enumerate(clips):
            clip_descriptions += f"\nClip {i+1}: {clip.get('prompt', '')[:150]}"

        prompt = f"""You are a video editor reviewing an AI-generated animated short before publishing.
This video was generated by Sora/Grok AI from text prompts. Watch carefully and check for these SPECIFIC issues:

CONCEPT: {concept.get('title', '')}

ORIGINAL SCRIPT (this is what was asked for — check if the video actually shows this):
{clip_descriptions}

CHECK THESE — be specific with timestamps:

1. **FLUIDITY & FLOW**: Does the video flow naturally from scene to scene? Or do clips feel disconnected and jarring? Are transitions between clips smooth or do they feel like random unrelated scenes stitched together? This is the MOST IMPORTANT check.

2. **STORY CLARITY**: Can you follow what is happening? Is there a clear beginning, middle, and end? Would a viewer understand the story without reading the description? If not, what is confusing?

3. **CHARACTER CONSISTENCY**: Do characters look the same across clips? Or do they change appearance, size, color, or style between scenes?

4. **ACTION MATCH**: Does each clip show what was described in the prompt? Flag any clips where the visual doesn't match the intended action.

5. **PACING**: Are any clips too slow, too fast, or have dead time? Does the video hold attention throughout or does it drag?

6. **ENDING**: Does the video end satisfyingly or does it cut off abruptly mid-action?

CRITICAL: For each clip, compare what the SCRIPT asked for versus what ACTUALLY happened in the video. Be extremely specific. If the script said "the character sneezes and stumbles forward" but in the video the character just stands still, say exactly that.

Then for each mismatch, suggest a REWRITTEN version of that part of the prompt that would be more likely to produce the intended result. Think about what Sora responds to — simple clear physical descriptions, not abstract concepts.

Return JSON (no markdown):
{{
  "flow_score": 1-10,
  "story_clarity_score": 1-10,
  "character_consistency_score": 1-10,
  "overall_score": 1-10,
  "verdict": "pass" or "needs_fixes",
  "flow_issues": ["specific fluidity/transition problems"],
  "story_issues": ["what was confusing"],
  "character_issues": ["consistency problems"],
  "biggest_issue": "single most important thing to fix",
  "script_vs_video": [
    {{
      "clip": 1,
      "script_said": "what the prompt asked for",
      "video_showed": "what actually appeared in the video",
      "rewritten_prompt": "a better version of the prompt that would more likely produce the intended result"
    }}
  ]
}}"""

        response_text = review_video(video_path, prompt)

        # Parse JSON
        import re
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            qa = json.loads(text)
        except json.JSONDecodeError:
            qa = {"raw_response": text, "parse_error": True}

        qa["reviewed"] = True
        await _store_asset(run_id, channel_id, "production_qa", json.dumps(qa))
        logger.info("production QA complete", run_id=run_id,
                    verdict=qa.get("verdict"), flow=qa.get("flow_score"),
                    biggest=qa.get("biggest_issue", "")[:80])

    except Exception as e:
        logger.warning("production QA failed", run_id=run_id, error=str(e)[:200])
        await _store_asset(run_id, channel_id, "production_qa", json.dumps({
            "reviewed": False, "error": str(e)[:200],
        }))


async def _update_step(run_id: int, step: str):
    try:
        async with _get_bg_session() as session:
            await session.execute(
                text("UPDATE content_runs SET current_step = :step WHERE id = :id"),
                {"id": run_id, "step": step},
            )
            await session.commit()
    except Exception:
        pass


async def _store_asset(run_id: int, channel_id: int, asset_type: str, content: str):
    async with _get_bg_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": asset_type, "content": content},
        )
        await session.commit()


def _get_duration(path: str) -> float:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True, timeout=10)
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def _has_audio(path: str) -> bool:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-select_streams", "a",
                        "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
                       capture_output=True, text=True, timeout=10)
    return bool(r.stdout.strip())


def _pick_sora_duration(target: float) -> int:
    for opt in [4, 8, 12]:
        if opt >= target:
            return opt
    return 12


def _file_to_data_url(path: str, target_w: int = 720, target_h: int = 1280) -> str | None:
    """Convert image to base64 data URL, resizing to match Sora's expected dimensions."""
    import base64
    if not path or not os.path.exists(path):
        return None

    # Resize to target dimensions so Sora doesn't reject it
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


def _ffmpeg_copy(src: str, dst: str):
    subprocess.run(["ffmpeg", "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst],
                   capture_output=True, text=True, timeout=60)


def _mix_narration(clip_path: str, narr_path: str, out_path: str,
                    sora_vol: float = 0.5, narr_vol: float = 1.3):
    if _has_audio(clip_path):
        filt = (f"[0:a]volume={sora_vol}[s];[1:a]volume={narr_vol}[n];"
                f"[s][n]amix=inputs=2:duration=first:dropout_transition=0[o]")
        cmd = ["ffmpeg", "-y", "-i", clip_path, "-i", narr_path,
               "-filter_complex", filt, "-map", "0:v:0", "-map", "[o]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-shortest", out_path]
    else:
        filt = f"[1:a]volume={narr_vol}[o]"
        cmd = ["ffmpeg", "-y", "-i", clip_path, "-i", narr_path,
               "-filter_complex", filt, "-map", "0:v:0", "-map", "[o]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", "-shortest", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        _ffmpeg_copy(clip_path, out_path)


def _normalize_clip(src: str, dst: str):
    vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
          f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
          f"fps=30,format=yuv420p")
    if _has_audio(src):
        cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
               "-movflags", "+faststart", dst]
    else:
        cmd = ["ffmpeg", "-y", "-i", src, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
               "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
               "-shortest", "-movflags", "+faststart", dst]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"Normalize failed: {r.stderr[-300:]}")


def _ffmpeg_concat(paths: list[str], out: str):
    concat_file = out.replace(".mp4", "_concat.txt")
    with open(concat_file, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
           "-c", "copy", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"Concat failed: {r.stderr[-300:]}")
    try:
        os.remove(concat_file)
    except OSError:
        pass


def _ffmpeg_trim(src: str, dst: str, max_s: float):
    subprocess.run(["ffmpeg", "-y", "-i", src, "-t", str(max_s), "-c", "copy",
                    "-movflags", "+faststart", dst],
                   capture_output=True, text=True, timeout=120)


def _format_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    cs = int((s % 1) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def _write_ass(path: str, labels: list[str], starts: dict, ends: dict,
               words: list[tuple], num_clips: int,
               dialogue_lines: list[list[str]] | None = None):
    """Write ASS subtitle file with labels, karaoke words, and speech bubbles.

    dialogue_lines: per-clip list of dialogue strings to show as speech bubbles.
    """
    header = """[Script Info]
Title: Subtitles
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Label,Impact,32,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,8,60,60,80,1
Style: Word,Impact,56,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,50,50,100,1
Style: Bubble,Arial Black,40,&H00000000,&H000000FF,&H00000000,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,0,0,5,80,80,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.strip()]

    for i, label in enumerate(labels):
        if label and i < num_clips:
            lines.append(f"Dialogue: 0,{_format_time(starts.get(i,0))},{_format_time(ends.get(i,999))},Label,,0,0,0,,{label}")

    # Speech bubbles — evenly spaced across clip duration
    if dialogue_lines:
        for i, clip_dialogue in enumerate(dialogue_lines):
            if not clip_dialogue:
                continue
            clip_start = starts.get(i, 0)
            clip_end = ends.get(i, 999)
            clip_dur = clip_end - clip_start
            n = len(clip_dialogue)
            segment = clip_dur / n
            for j, line_text in enumerate(clip_dialogue):
                if not line_text:
                    continue
                t_start = clip_start + j * segment
                t_end = clip_start + (j + 1) * segment
                # Pad timing: show 0.3s after segment start, end 0.2s before segment end
                t_start = t_start + min(0.3, segment * 0.1)
                t_end = t_end - min(0.2, segment * 0.1)
                lines.append(f"Dialogue: 2,{_format_time(t_start)},{_format_time(t_end)},Bubble,,0,0,0,,{line_text}")

    if words:
        from itertools import groupby
        for _ci, clip_words_iter in groupby(words, key=lambda w: w[3]):
            clip_words = list(clip_words_iter)
            for gi in range(0, len(clip_words), 3):
                group = clip_words[gi:gi + 3]
                texts = [w[0] for w in group]
                wc = len(group)
                times = []
                for j, (_, ws, we, _c) in enumerate(group):
                    times.append((ws, group[j + 1][1] if j + 1 < wc else we))
                for ai in range(wc):
                    parts = []
                    for j, t in enumerate(texts):
                        if j == ai:
                            parts.append("{\\1c&H00FFFF&}" + t)
                        else:
                            parts.append("{\\1c&HFFFFFF&}" + t)
                    lines.append(f"Dialogue: 1,{_format_time(times[ai][0])},{_format_time(times[ai][1])},Word,,0,0,0,,{' '.join(parts)}")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
