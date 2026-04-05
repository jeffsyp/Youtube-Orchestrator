"""Video generation pipeline — narrated shorts with Grok images and video clips.

Generates per-beat narration audio (ElevenLabs), Grok images/video clips,
stitches into a video with Ken Burns zoom effect and karaoke subtitles.
"""

import asyncio
import json
import os
import subprocess
import time

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

SHORT_WIDTH = 720
SHORT_HEIGHT = 1280
LONG_WIDTH = 1920
LONG_HEIGHT = 1080

# YouTube category per channel ID — used during upload
CHANNEL_CATEGORY = {
    14: "Entertainment",       # Deity Drama — mythology comedy
    15: "Education",           # Smooth Brain Academy — ELI5 explainers
    16: "Entertainment",       # Cold Case Cartoons — true crime
    17: "Pets & Animals",      # Nature Receipts — animal facts
    18: "Entertainment",       # Deep We Go — conspiracies/mysteries
    19: "Education",           # Historic Ls — history
    20: "Entertainment",       # SpookLand — horror
    21: "Education",           # Globe Thoughts — country comparisons
    22: "Gaming",              # Crab Rave Shorts — League of Legends
    23: "Entertainment",       # Toongunk — cartoon/pop culture
    24: "Entertainment",       # Night Night Shorts — anime
    25: "Entertainment",       # What If City — hypotheticals
    26: "Entertainment",       # One on Ones For Fun — who would win
    27: "Gaming",              # Munchlax Lore — Pokemon
    28: "Entertainment",       # Villanous Origins — villains
    30: "Education",           # Schmoney Facts — money facts
    31: "Entertainment",       # Hardcore Ranked — rankings
    32: "Entertainment",       # Oddly Satisfying
    33: "Entertainment",       # Plot Twist Shorts
    34: "Entertainment",       # What Happens Next
    35: "Entertainment",       # Infinite Zoom
    36: "Entertainment",       # Very Clean Very Good
    37: "Comedy",              # Thats A Meme
    38: "Entertainment",       # Blanket Fort Cartoons
    39: "Science & Technology", # Techognize — AI/tech education
}

# Channel-specific art styles for visual planning
_DEFAULT_STYLE = "Bold cartoon style, thick outlines, bright colors."
CHANNEL_ART_STYLE = {
    16: "Dark noir style, muted desaturated colors, dramatic shadows, moody lighting, heavy contrast.",  # Cold Case
    18: "Dark atmospheric surreal style, deep blues and purples, dreamlike distortion, conspiracy board energy.",  # Deep We Go
    19: "Vintage retro cartoon illustration style, aged parchment tones, warm sepia and muted colors with bold cartoon outlines, like an old editorial cartoon with humor.",  # Historic Ls
    20: "Dark eerie style, desaturated washed-out colors, creepy atmosphere, thick fog, long shadows, unsettling lighting.",  # SpookLand
    21: "Clean infographic illustration style, polished flat design, map-inspired color palette with blues greens and earth tones, clean lines.",  # Globe Thoughts
    22: "Vibrant gaming art style, dark background with neon blue and purple accents, dramatic lighting.",  # Crab Rave
    24: "Anime art style, sharp clean lines, anime color palette, dramatic shading, expressive eyes, dynamic composition.",  # Night Night
    26: "Fight poster art style, dramatic split composition, intense saturated colors, high contrast, boxing promo energy.",  # One on Ones
    27: "Cute cartoon style with soft rounded shapes and warm pastel colors, like a childrens storybook about friendly creatures.",  # Munchlax Lore
    28: "Dark dramatic cinematic style, high contrast, deep shadows with rim lighting, intense atmosphere.",  # Villanous Origins
    38: "Soft rounded kids cartoon style, warm pastel colors, gentle lighting, rounded shapes with no sharp edges, like Bluey or Peppa Pig animation.",  # Blanket Fort
    39: "Hand-drawn whiteboard sketch style, black marker on white background, simple doodles and stick figures, arrows and labels, like a draw-my-life video. Clean lines, minimal detail, the drawing should explain the concept not decorate it.",  # Techognize
}


async def run_deity_pipeline(run_id: int, concept: dict):
    """Run the full video generation pipeline."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    async def _update_step(step):
        try:
            engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
            async with AsyncSession(engine) as s:
                await s.execute(
                    text("UPDATE content_runs SET current_step = :step WHERE id = :id"),
                    {"step": step, "id": run_id},
                )
                await s.commit()
            await engine.dispose()
        except Exception as e:
            logger.warning("step update failed (non-fatal)", step=step, error=str(e)[:100])

    try:
        output_dir = f"output/run_{run_id}"
        os.makedirs(output_dir, exist_ok=True)

        # Route to narration-first pipeline (format_version 2) or legacy beat-based pipeline
        if concept.get("format_version") == 2:
            await _run_narration_first(run_id, concept, output_dir, _update_step, db_url)
            return

        beats = concept.get("beats", [])
        if not beats:
            raise ValueError("No beats in concept — nothing to generate")
        is_long_form = concept.get("long_form", False) or len(beats) >= 20
        WIDTH = LONG_WIDTH if is_long_form else SHORT_WIDTH
        HEIGHT = LONG_HEIGHT if is_long_form else SHORT_HEIGHT
        img_size = "1536x1024" if is_long_form else "1024x1536"
        logger.info("pipeline config", long_form=is_long_form, resolution=f"{WIDTH}x{HEIGHT}")
        voice_id = concept.get("voice_id", "56bWURjYFHyYyVf490Dp")
        narration_speed = concept.get("speed", 1.05)  # default 1.05x
        title = concept.get("title", "Untitled")
        channel_id = concept.get("channel_id", 14)

        # 1. Generate narration per beat
        await _update_step("generating narration")
        narration_dir = os.path.join(output_dir, "narration")
        os.makedirs(narration_dir, exist_ok=True)

        from packages.clients.elevenlabs import generate_speech

        beat_audio = []
        for i, beat in enumerate(beats):
            narr_path = os.path.join(narration_dir, f"beat_{i}.mp3")
            if os.path.exists(narr_path):
                duration = _get_duration(narr_path)
                beat_audio.append({"index": i, "path": narr_path, "duration": duration})
                logger.info("reusing existing narration", beat=i, duration=round(duration, 2))
                continue
            logger.info("generating beat narration", run_id=run_id, beat=i)
            for attempt in range(3):
                try:
                    generate_speech(
                        text=beat["narration"],
                        voice=voice_id,
                        output_path=narr_path,
                        speed=narration_speed,
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"ElevenLabs failed after 3 attempts for beat {i}: {e}") from e
                    logger.warning("narration attempt failed, retrying", beat=i, attempt=attempt, error=str(e)[:100])
                    import asyncio as _aio
                    await _aio.sleep(5 * (attempt + 1))
            duration = _get_duration(narr_path)
            beat_audio.append({"index": i, "path": narr_path, "duration": duration})
            logger.info("beat narration done", beat=i, duration=round(duration, 2))

        # Auto-split long image beats (>5s narration, no extra images provided)
        MAX_IMAGE_DURATION = 5.0
        for i, beat in enumerate(beats):
            if beat.get("type", "image") != "image":
                continue
            if beat.get("images"):
                continue  # already has multiple images
            dur = beat_audio[i]["duration"]
            if dur <= MAX_IMAGE_DURATION:
                continue
            # Need extra images — ask Claude to describe visuals for sub-sections
            num_images = max(2, int(dur / 4.0))
            logger.info("auto-splitting long beat", beat=i, duration=round(dur, 2), images_needed=num_images)
            try:
                from packages.clients.claude import generate
                split_prompt = f"""Split this narration into {num_images} visual scenes. For each scene, write an image prompt that shows exactly what is being described at that moment.

Narration: "{beat['narration']}"

Return JSON array of strings, each an image prompt starting with "Colorful cartoon style, thick outlines, bright colors. Vertical composition."
No markdown, just the JSON array."""
                # Try Sonnet with 3 retries + backoff, then Haiku as backup
                resp = None
                for sonnet_attempt in range(3):
                    try:
                        resp = generate(prompt=split_prompt, system="Return only a JSON array of image prompt strings.", model="claude-sonnet-4-20250514", max_tokens=800)
                        break
                    except Exception as model_err:
                        if "overloaded" in str(model_err).lower() or "529" in str(model_err):
                            logger.warning("auto-split sonnet overloaded, retrying", attempt=sonnet_attempt)
                            import asyncio as _aio2
                            await _aio2.sleep(5 * (sonnet_attempt + 1))
                            continue
                        raise
                if resp is None:
                    # Sonnet exhausted — try Haiku as genuine backup
                    logger.warning("sonnet exhausted for auto-split, trying haiku")
                    try:
                        resp = generate(prompt=split_prompt, system="Return only a JSON array of image prompt strings.", model="claude-haiku-4-5-20251001", max_tokens=800)
                    except Exception as haiku_err:
                        raise RuntimeError(f"All Claude models failed for auto-split: {haiku_err}") from haiku_err
                import re
                resp = resp.strip()
                if resp.startswith("```"):
                    resp = re.sub(r"^```(?:json)?\s*", "", resp)
                    resp = re.sub(r"\s*```$", "", resp)
                extra_prompts = json.loads(resp)
                if isinstance(extra_prompts, list) and len(extra_prompts) >= 2:
                    beat["_auto_image_prompts"] = extra_prompts[1:]  # first image uses the original
                    logger.info("auto-split generated prompts", beat=i, count=len(extra_prompts))
            except Exception as e:
                logger.warning("auto-split failed", beat=i, error=str(e)[:100])

        # 2. Generate visuals per beat — DALL-E images or Sora video clips
        await _update_step("generating visuals")
        images_dir = os.path.join(output_dir, "images")
        clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(clips_dir, exist_ok=True)

        import base64
        from concurrent.futures import ThreadPoolExecutor
        from packages.clients.grok import generate_image as grok_gen_image

        # Generate all images in parallel first
        image_beats = [(i, b) for i, b in enumerate(beats) if b.get("type", "image") == "image"]
        video_beats = [(i, b) for i, b in enumerate(beats) if b.get("type") == "video"]
        veo_beats = [(i, b) for i, b in enumerate(beats) if b.get("type") == "veo"]
        grok_beats = [(i, b) for i, b in enumerate(beats) if b.get("type") == "grok"]

        def _soften_image_prompt(prompt: str) -> str:
            """Ask Claude to rewrite an image prompt that was blocked by moderation."""
            try:
                from packages.clients.claude import generate
                resp = generate(
                    prompt=f"This image prompt was blocked by the safety system. Rewrite it to convey the same scene but with softer, family-friendly language. Remove any references to violence, blood, weapons, death, horror, or anything disturbing. Keep the visual description specific and detailed.\n\nBlocked prompt: {prompt}\n\nReturn ONLY the rewritten prompt, nothing else.",
                    system="Rewrite image prompts to pass content moderation. Keep the same visual concept but use safe language.",
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                )
                logger.info("softened image prompt", original=prompt[:80], softened=resp.strip()[:80])
                return resp.strip()
            except Exception as e:
                logger.warning("soften prompt failed", error=str(e)[:100])
                return prompt

        def gen_image(i, beat):
            img_path = os.path.join(images_dir, f"beat_{i}.png")
            if os.path.exists(img_path):
                return img_path
            prompt = beat["image"]
            for attempt in range(3):
                try:
                    grok_gen_image(prompt=prompt, output_path=img_path)
                    logger.info("image generated", beat=i, attempt=attempt)
                    return img_path
                except Exception as e:
                    if "moderation" in str(e).lower() or "safety" in str(e).lower() or "rejected" in str(e).lower():
                        logger.warning("image moderation blocked, softening", beat=i, attempt=attempt)
                        prompt = _soften_image_prompt(prompt)
                        continue
                    raise
            raise RuntimeError(f"Image generation blocked by moderation after 3 softening attempts for beat {i}")

        beat_visuals = {}  # i -> {"type": "image"|"video", "path": str}

        if image_beats:
            with ThreadPoolExecutor(max_workers=2) as ex:
                futures = {ex.submit(gen_image, i, beat): i for i, beat in image_beats}
                for f in futures:
                    idx = futures[f]
                    beat_visuals[idx] = {"type": "image", "path": f.result()}

        # Generate auto-split extra images for long beats
        auto_image_tasks = []
        for i, beat in enumerate(beats):
            auto_prompts = beat.get("_auto_image_prompts", [])
            for j, prompt in enumerate(auto_prompts):
                auto_image_tasks.append((i, j, prompt))

        if auto_image_tasks:
            def gen_auto_image(beat_idx, img_idx, prompt):
                path = os.path.join(images_dir, f"beat_{beat_idx}_auto_{img_idx}.png")
                if os.path.exists(path):
                    return beat_idx, path
                grok_gen_image(prompt=prompt, output_path=path)
                return beat_idx, path

            with ThreadPoolExecutor(max_workers=2) as ex:
                auto_futures = [ex.submit(gen_auto_image, bi, ji, p) for bi, ji, p in auto_image_tasks]
                for f in auto_futures:
                    beat_idx, path = f.result()
                    if "images" not in beats[beat_idx]:
                        beats[beat_idx]["images"] = []
                    beats[beat_idx]["images"].append(path)
            logger.info("auto-split images generated", count=len(auto_image_tasks))

        # Generate Sora video clips for video beats
        if video_beats:
            from packages.clients.sora import generate_video_async

            async def _sora_generate_one(i, beat):
                """Generate a single Sora video clip (no retries — caller handles that)."""
                clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                dur = min(int(beat_audio[i]["duration"]) + 1, 8)
                valid = [4, 8]
                sora_dur = min(d for d in valid if d >= dur) if dur <= 8 else 8
                ref_path = os.path.join(images_dir, f"beat_{i}_ref.png")
                if not os.path.exists(ref_path):
                    grok_gen_image(prompt=beat["image"], output_path=ref_path)
                sora_w, sora_h = (1280, 720) if is_long_form else (720, 1280)
                ref_resized = ref_path.replace(".png", "_sm.jpg")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", ref_path, "-vf", f"scale={sora_w}:{sora_h}",
                     "-q:v", "10", ref_resized],
                    capture_output=True, timeout=30,
                )
                if os.path.exists(ref_resized):
                    with open(ref_resized, "rb") as rf:
                        ref_url = f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}"
                else:
                    with open(ref_path, "rb") as rf:
                        ref_url = f"data:image/png;base64,{base64.b64encode(rf.read()).decode()}"
                await generate_video_async(
                    prompt=beat.get("video_prompt", beat["image"]),
                    output_path=clip_path,
                    duration=sora_dur,
                    size="1280x720" if is_long_form else "720x1280",
                    reference_image_url=ref_url,
                    model="sora-2",
                )
                return clip_path

            for i, beat in video_beats:
                await _update_step(f"generating video beat {i+1}")
                clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                if os.path.exists(clip_path):
                    beat_visuals[i] = {"type": "video", "path": clip_path}
                    logger.info("reusing existing sora clip", beat=i)
                    continue

                if i == 0:
                    # Hook beat — fail immediately, no retries
                    try:
                        result_path = await _sora_generate_one(i, beat)
                        beat_visuals[i] = {"type": "video", "path": result_path}
                        logger.info("video beat generated", beat=i)
                    except Exception as e:
                        raise RuntimeError(f"Sora failed on hook (beat 0) — cannot fall back to image: {e}") from e
                else:
                    # Non-hook beats — 3 retries with backoff
                    last_err = None
                    for attempt in range(3):
                        try:
                            result_path = await _sora_generate_one(i, beat)
                            beat_visuals[i] = {"type": "video", "path": result_path}
                            logger.info("video beat generated", beat=i, attempt=attempt)
                            last_err = None
                            break
                        except Exception as e:
                            last_err = e
                            logger.warning("sora retry failed", beat=i, attempt=attempt, error=str(e)[:100])
                            if attempt < 2:
                                await asyncio.sleep(5 * (attempt + 1))
                    if last_err:
                        raise RuntimeError(f"Sora failed after 3 retries on beat {i}: {last_err}") from last_err

        # Generate Veo video clips for veo beats (character dialogue)
        if veo_beats:
            from google import genai as _genai
            import time as _time
            veo_client = _genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            async def _veo_generate_one(i, beat):
                """Generate a single Veo clip (no retries — caller handles that)."""
                clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                veo_prompt = beat.get("video_prompt", beat.get("image", ""))
                aspect = "16:9" if is_long_form else "9:16"
                op = veo_client.models.generate_videos(
                    model="veo-3.1-fast-generate-preview",
                    prompt=veo_prompt,
                    config=_genai.types.GenerateVideosConfig(
                        aspect_ratio=aspect,
                        number_of_videos=1,
                    ),
                )
                logger.info("veo submitted", beat=i, operation=op.name)
                start_t = _time.time()
                while not op.done:
                    await asyncio.sleep(10)
                    op = veo_client.operations.get(op)
                    if _time.time() - start_t > 300:
                        raise RuntimeError("Veo generation timed out after 5 minutes")
                if op.result and op.result.generated_videos:
                    video = op.result.generated_videos[0]
                    resp = veo_client.files.download(file=video.video)
                    with open(clip_path, "wb") as f:
                        f.write(resp)
                    return clip_path
                else:
                    raise RuntimeError(f"Veo failed: {op.error}")

            for i, beat in veo_beats:
                await _update_step(f"generating veo beat {i+1}")
                clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                if os.path.exists(clip_path):
                    beat_visuals[i] = {"type": "video", "path": clip_path}
                    logger.info("reusing existing veo clip", beat=i)
                    continue

                if i == 0:
                    # Hook beat — fail immediately, no retries
                    try:
                        result_path = await _veo_generate_one(i, beat)
                        beat_visuals[i] = {"type": "video", "path": result_path}
                        logger.info("veo beat generated", beat=i)
                    except Exception as e:
                        raise RuntimeError(f"Veo failed on hook (beat 0): {e}") from e
                else:
                    # Non-hook beats — 3 retries with backoff
                    last_err = None
                    for attempt in range(3):
                        try:
                            result_path = await _veo_generate_one(i, beat)
                            beat_visuals[i] = {"type": "video", "path": result_path}
                            logger.info("veo beat generated", beat=i, attempt=attempt)
                            last_err = None
                            break
                        except Exception as e:
                            last_err = e
                            logger.warning("veo retry failed", beat=i, attempt=attempt, error=str(e)[:100])
                            if attempt < 2:
                                await asyncio.sleep(5 * (attempt + 1))
                    if last_err:
                        raise RuntimeError(f"Veo failed after 3 retries on beat {i}: {last_err}") from last_err

        # Generate Grok video clips
        if grok_beats:
            from packages.clients.grok import generate_video_async as grok_generate, extend_video_async as grok_extend
            grok_ref_frame = None  # reference frame for character consistency
            last_grok_result = None  # last grok result for video extensions
            aspect = "16:9" if is_long_form else "9:16"

            def _extract_grok_ref(clip_path):
                """Extract a reference frame from a Grok clip for character consistency."""
                ref_path = os.path.join(clips_dir, "grok_ref.jpg")
                subprocess.run([
                    "ffmpeg", "-y", "-ss", "2", "-i", clip_path,
                    "-map", "0:v:0", "-frames:v", "1", "-q:v", "3", ref_path,
                ], capture_output=True, text=True, timeout=15)
                if os.path.exists(ref_path):
                    with open(ref_path, "rb") as rf:
                        return f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}"
                return None

            # Check if any beats need character consistency or extensions
            needs_consistency = any(b.get("consistent_character") for _, b in grok_beats)
            has_extensions = any(b.get("extend_previous") for _, b in grok_beats)

            # If extensions needed, generate sequentially (each depends on previous)
            # If consistency needed, generate beat 0 first for ref frame, then rest concurrently
            # Otherwise, generate all concurrently
            if has_extensions:
                # Sequential generation with extension chaining
                await _update_step("generating grok beats (chained)")
                for i, beat in grok_beats:
                    clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                    if os.path.exists(clip_path):
                        beat_visuals[i] = {"type": "video", "path": clip_path, "source": "grok"}
                        logger.info("reusing existing grok clip", beat=i)
                        continue
                    try:
                        grok_prompt = beat.get("video_prompt", beat.get("image", ""))
                        dur = min(int(beat_audio[i]["duration"]) + 1, 15)
                        dur = max(dur, 1)

                        if beat.get("extend_previous") and last_grok_result and last_grok_result.get("video_url"):
                            # Extend from previous clip
                            ext_dur = min(dur, 10)
                            ext_dur = max(ext_dur, 2)
                            raw_path = os.path.join(clips_dir, f"beat_{i}_raw.mp4")
                            prev_duration = _get_duration(beat_visuals[grok_beats[grok_beats.index((i, beat)) - 1][0]]["path"])
                            result = await grok_extend(
                                video_url=last_grok_result["video_url"],
                                prompt=grok_prompt,
                                output_path=raw_path,
                                duration=ext_dur,
                            )
                            # Trim to just the new segment
                            subprocess.run([
                                "ffmpeg", "-y", "-ss", str(prev_duration),
                                "-i", raw_path, "-map", "0:v:0",
                                "-c:v", "copy", "-an", clip_path,
                            ], capture_output=True, text=True, timeout=30)
                            if not os.path.exists(clip_path):
                                import shutil
                                shutil.copy2(raw_path, clip_path)
                            last_grok_result = result
                        else:
                            # Fresh generation
                            ref = grok_ref_frame if beat.get("consistent_character") else None
                            result = await grok_generate(
                                prompt=grok_prompt, output_path=clip_path,
                                duration=dur, aspect_ratio=aspect,
                                reference_image_url=ref,
                            )
                            last_grok_result = result
                            if not grok_ref_frame:
                                grok_ref_frame = _extract_grok_ref(clip_path)

                        beat_visuals[i] = {"type": "video", "path": clip_path, "source": "grok"}
                        logger.info("grok beat generated", beat=i, extended=bool(beat.get("extend_previous")))
                    except Exception as e:
                        if i == grok_beats[0][0]:
                            raise RuntimeError(f"Grok failed on hook (beat {i}): {e}") from e
                        # Non-hook: retry with backoff
                        last_err = e
                        succeeded = False
                        for retry_attempt in range(3):
                            logger.warning("grok beat retry", beat=i, attempt=retry_attempt, error=str(last_err)[:150])
                            await asyncio.sleep(5 * (retry_attempt + 1))
                            try:
                                grok_prompt = beat.get("video_prompt", beat.get("image", ""))
                                dur = min(int(beat_audio[i]["duration"]) + 1, 15)
                                dur = max(dur, 1)
                                ref = grok_ref_frame if beat.get("consistent_character") else None
                                result = await grok_generate(
                                    prompt=grok_prompt, output_path=clip_path,
                                    duration=dur, aspect_ratio=aspect,
                                    reference_image_url=ref,
                                )
                                last_grok_result = result
                                beat_visuals[i] = {"type": "video", "path": clip_path, "source": "grok"}
                                logger.info("grok beat generated on retry", beat=i, attempt=retry_attempt)
                                succeeded = True
                                break
                            except Exception as retry_e:
                                last_err = retry_e
                        if not succeeded:
                            last_grok_result = None
                            raise RuntimeError(f"Grok failed after 3 retries on beat {i}: {last_err}") from last_err

            elif needs_consistency:
                # Beat 0 first for ref frame, then remaining concurrently with ref
                first_i, first_beat = grok_beats[0]
                first_clip = os.path.join(clips_dir, f"beat_{first_i}.mp4")
                if os.path.exists(first_clip):
                    beat_visuals[first_i] = {"type": "video", "path": first_clip, "source": "grok"}
                    grok_ref_frame = _extract_grok_ref(first_clip)
                else:
                    await _update_step(f"generating grok beat {first_i+1}")
                    try:
                        dur = min(int(beat_audio[first_i]["duration"]) + 1, 15)
                        dur = max(dur, 1)
                        await grok_generate(
                            prompt=first_beat.get("video_prompt", first_beat.get("image", "")),
                            output_path=first_clip, duration=dur, aspect_ratio=aspect,
                        )
                        beat_visuals[first_i] = {"type": "video", "path": first_clip, "source": "grok"}
                        grok_ref_frame = _extract_grok_ref(first_clip)
                    except Exception as e:
                        raise RuntimeError(f"Grok failed on hook (beat {first_i}): {e}") from e

                remaining_beats = grok_beats[1:]
                if remaining_beats:
                    await _update_step(f"generating {len(remaining_beats)} grok beats concurrently")

                    async def _gen_grok_beat_ref(i, beat):
                        clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                        if os.path.exists(clip_path):
                            return i, clip_path, None
                        last_err = None
                        for attempt in range(3):
                            try:
                                dur = min(int(beat_audio[i]["duration"]) + 1, 15)
                                dur = max(dur, 1)
                                if attempt == 0:
                                    delay = remaining_beats.index((i, beat)) * 1.5
                                    await asyncio.sleep(delay)
                                else:
                                    await asyncio.sleep(5 * (attempt + 1))
                                ref = grok_ref_frame if beat.get("consistent_character") else None
                                await grok_generate(
                                    prompt=beat.get("video_prompt", beat.get("image", "")),
                                    output_path=clip_path, duration=dur, aspect_ratio=aspect,
                                    reference_image_url=ref,
                                )
                                return i, clip_path, None
                            except Exception as e:
                                last_err = e
                                logger.warning("grok beat retry", beat=i, attempt=attempt, error=str(e)[:100])
                        return i, None, last_err

                    results = await asyncio.gather(*[_gen_grok_beat_ref(i, b) for i, b in remaining_beats])
                    for i, clip_path, err in results:
                        if clip_path and os.path.exists(clip_path):
                            beat_visuals[i] = {"type": "video", "path": clip_path, "source": "grok"}
                        else:
                            raise RuntimeError(f"Grok failed after 3 retries on beat {i}: {err}") from err

            else:
                # No consistency or extensions needed — all concurrent
                await _update_step(f"generating {len(grok_beats)} grok beats concurrently")

                async def _gen_grok_beat(i, beat):
                    clip_path = os.path.join(clips_dir, f"beat_{i}.mp4")
                    if os.path.exists(clip_path):
                        return i, clip_path, None
                    last_err = None
                    for attempt in range(3):
                        try:
                            dur = min(int(beat_audio[i]["duration"]) + 1, 15)
                            dur = max(dur, 1)
                            if attempt == 0:
                                delay = grok_beats.index((i, beat)) * 1.5
                                await asyncio.sleep(delay)
                            else:
                                await asyncio.sleep(5 * (attempt + 1))
                            await grok_generate(
                                prompt=beat.get("video_prompt", beat.get("image", "")),
                                output_path=clip_path, duration=dur, aspect_ratio=aspect,
                            )
                            return i, clip_path, None
                        except Exception as e:
                            last_err = e
                            logger.warning("grok beat retry", beat=i, attempt=attempt, error=str(e)[:100])
                    return i, None, last_err

                results = await asyncio.gather(*[_gen_grok_beat(i, b) for i, b in grok_beats])
                for i, clip_path, err in results:
                    if clip_path and os.path.exists(clip_path):
                        beat_visuals[i] = {"type": "video", "path": clip_path, "source": "grok"}
                    else:
                        if i == grok_beats[0][0]:
                            raise RuntimeError(f"Grok failed on hook (beat {grok_beats[0][0]}): {err}")
                        raise RuntimeError(f"Grok failed after 3 retries on beat {i}: {err}")

        # 3. Create video segments
        await _update_step("creating video segments")
        segments_dir = os.path.join(output_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)

        # SFX paths
        sfx_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sfx")
        sfx_whoosh = os.path.join(sfx_dir, "whoosh.mp3")
        sfx_impact = os.path.join(sfx_dir, "impact.mp3")
        sfx_transition = os.path.join(sfx_dir, "transition.mp3")

        segment_paths = []
        for i, audio in enumerate(beat_audio):
            seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")
            dur = audio["duration"] + 0.05  # tight padding
            beat = beats[i]
            visual = beat_visuals.get(i, {"type": "image", "path": os.path.join(images_dir, f"beat_{i}.png")})

            # Check for multiple images per beat
            extra_images = beat.get("images", [])

            if visual["type"] == "video":
                # Video beat — loop video, mix narration + SFX
                is_grok = visual.get("source") == "grok"
                sfx_file = sfx_impact if os.path.exists(sfx_impact) else None
                if sfx_file:
                    # Mix narration + sfx at start of video beat
                    mixed_audio = os.path.join(segments_dir, f"audio_sfx_{i}.mp3")
                    subprocess.run([
                        "ffmpeg", "-y", "-i", audio["path"], "-i", sfx_file,
                        "-filter_complex", "[1]volume=0.4[sfx];[0][sfx]amix=inputs=2:duration=first",
                        "-c:a", "libmp3lame", mixed_audio,
                    ], capture_output=True, text=True, timeout=30)
                    audio_for_video = mixed_audio if os.path.exists(mixed_audio) else audio["path"]
                else:
                    audio_for_video = audio["path"]

                # Grok videos have an embedded mjpeg thumbnail stream
                # Strip it first so -stream_loop works, then loop to cover narration
                if is_grok:
                    clean_clip = visual["path"].replace(".mp4", "_clean.mp4")
                    if not os.path.exists(clean_clip):
                        subprocess.run([
                            "ffmpeg", "-y", "-i", visual["path"],
                            "-map", "0:v:0", "-c:v", "copy", "-an", clean_clip,
                        ], capture_output=True, text=True, timeout=30)
                    clip_input = clean_clip if os.path.exists(clean_clip) else visual["path"]
                    video_map = "0:v"
                else:
                    clip_input = visual["path"]
                    video_map = "0:v"

                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", clip_input,
                    "-i", audio_for_video,
                    "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-map", video_map, "-map", "1:a",
                    "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart",
                    seg_path,
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            elif extra_images and len(extra_images) > 0:
                # Multi-image beat — cut between images evenly across duration
                all_imgs = [visual["path"]] + [
                    img_path for img_path in extra_images if os.path.exists(img_path)
                ]
                if len(all_imgs) < 2:
                    all_imgs = [visual["path"]]

                if len(all_imgs) >= 2:
                    # Generate sub-segments per image, then concat
                    sub_dur = dur / len(all_imgs)
                    sub_paths = []
                    for j, img_p in enumerate(all_imgs):
                        sub_path = os.path.join(segments_dir, f"sub_{i}_{j}.mp4")
                        subprocess.run([
                            "ffmpeg", "-y", "-loop", "1", "-i", img_p,
                            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                            "-t", str(sub_dur), "-an",
                            sub_path,
                        ], capture_output=True, text=True, timeout=60)
                        sub_paths.append(sub_path)

                    # Concat sub-segments
                    concat_file = os.path.join(segments_dir, f"multi_{i}.txt")
                    with open(concat_file, "w") as cf:
                        for sp in sub_paths:
                            cf.write(f"file '{os.path.abspath(sp)}'\n")
                    multi_video = os.path.join(segments_dir, f"multi_{i}.mp4")
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                        multi_video,
                    ], capture_output=True, text=True, timeout=60)

                    # Add transition SFX at each cut point, mix with narration
                    if os.path.exists(sfx_transition) and len(all_imgs) > 1:
                        # Build SFX mix with transition sounds at each cut
                        mixed = os.path.join(segments_dir, f"audio_trans_{i}.mp3")
                        cuts = [sub_dur * k for k in range(1, len(all_imgs))]
                        adelay_parts = ";".join(
                            f"[t{k}]adelay={int(t*1000)}|{int(t*1000)},volume=0.3[d{k}]"
                            for k, t in enumerate(cuts)
                        )
                        inputs = "".join(f"-i {sfx_transition} " for _ in cuts)
                        mix_labels = "".join(f"[d{k}]" for k in range(len(cuts)))
                        filter_parts = ";".join(
                            f"[{k+1}]adelay={int(t*1000)}|{int(t*1000)},volume=0.3[d{k}]"
                            for k, t in enumerate(cuts)
                        )
                        filter_str = f"{filter_parts};[0]{mix_labels}amix=inputs={len(cuts)+1}:duration=first"
                        mix_cmd = f"ffmpeg -y -i {audio['path']} {inputs}-filter_complex \"{filter_str}\" -c:a libmp3lame {mixed}"
                        subprocess.run(mix_cmd, shell=True, capture_output=True, text=True, timeout=30)
                        narr_audio = mixed if os.path.exists(mixed) else audio["path"]
                    else:
                        narr_audio = audio["path"]

                    # Combine multi-image video with narration audio
                    subprocess.run([
                        "ffmpeg", "-y", "-i", multi_video, "-i", narr_audio,
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart",
                        seg_path,
                    ], capture_output=True, text=True, timeout=60)
                else:
                    # Fallback to single image
                    extra_images = []  # reset, handle below

            if not os.path.exists(seg_path):
                # Static image — scale to output resolution, no zoom/shake
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", visual["path"],
                    "-i", audio["path"],
                    "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart",
                    seg_path,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    cmd_simple = [
                        "ffmpeg", "-y",
                        "-loop", "1", "-i", visual["path"],
                        "-i", audio["path"],
                        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart",
                        seg_path,
                    ]
                    subprocess.run(cmd_simple, capture_output=True, text=True, timeout=120)

            if not os.path.exists(seg_path):
                raise RuntimeError(f"Segment {i} failed to create at {seg_path}")
            segment_paths.append(seg_path)
            logger.info("segment created", beat=i, duration=round(dur, 2), type=visual["type"])

        # 4. Concatenate all segments
        await _update_step("concatenating")
        concat_path = os.path.join(output_dir, "raw_concat.mp4")
        concat_list = os.path.join(output_dir, "concat_list.txt")
        with open(concat_list, "w") as f:
            for seg in segment_paths:
                f.write(f"file '{os.path.abspath(seg)}'\n")

        sub_timeout = 600 if is_long_form else 300
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
             "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
             concat_path],
            capture_output=True, text=True, timeout=sub_timeout,
        )

        # 4b. Mix transition SFX at beat boundaries
        if os.path.exists(sfx_transition) and os.path.exists(concat_path):
            try:
                beat_boundaries = []
                cumulative = 0.0
                for audio in beat_audio[:-1]:  # no transition after last beat
                    cumulative += audio["duration"] + 0.05
                    beat_boundaries.append(cumulative)

                if beat_boundaries:
                    concat_with_sfx = os.path.join(output_dir, "raw_concat_sfx.mp4")
                    # Build adelay filter for each transition
                    inputs = " ".join(f"-i {sfx_transition}" for _ in beat_boundaries)
                    filter_parts = ";".join(
                        f"[{k+1}]adelay={int(t*1000)}|{int(t*1000)},volume=0.25[t{k}]"
                        for k, t in enumerate(beat_boundaries)
                    )
                    mix_labels = "".join(f"[t{k}]" for k in range(len(beat_boundaries)))
                    filter_str = f"{filter_parts};[0:a]{mix_labels}amix=inputs={len(beat_boundaries)+1}:duration=first[out]"
                    cmd = f'ffmpeg -y -i {concat_path} {inputs} -filter_complex "{filter_str}" -map 0:v -map "[out]" -c:v copy -c:a aac -b:a 192k -movflags +faststart {concat_with_sfx}'
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=sub_timeout)
                    if result.returncode == 0 and os.path.exists(concat_with_sfx):
                        os.replace(concat_with_sfx, concat_path)
                        logger.info("added transition SFX", boundaries=len(beat_boundaries))
                    else:
                        logger.warning("transition SFX failed, using original", stderr=result.stderr[:100])
            except Exception as e:
                logger.warning("transition SFX step failed (non-fatal)", error=str(e)[:100])

        # 5. Burn karaoke subtitles
        await _update_step("subtitles")
        final_path = os.path.join(output_dir, "final.mp4")

        # Longer timeout for long-form content
        sub_timeout = 600 if len(beats) >= 20 else 300

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(concat_path, word_timestamps=True)

            all_words = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        all_words.append((w.word.strip(), w.start, w.end))

            # Compute beat timing for labels
            beat_labels = []
            current_time = 0.0
            for i, audio in enumerate(beat_audio):
                label = beats[i].get("label", "")
                start = current_time
                end = current_time + audio["duration"] + 0.05
                if label:
                    beat_labels.append((label, start, end))
                current_time = end

            ass_path = os.path.join(output_dir, "subs.ass")
            _write_karaoke_ass(ass_path, all_words, beat_labels, is_long_form=is_long_form)

            ass_escaped = ass_path.replace(":", "\\:")
            cmd = [
                "ffmpeg", "-y", "-i", concat_path,
                "-vf", f"ass={ass_escaped}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart",
                final_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=sub_timeout)
            if result.returncode != 0:
                logger.warning("subtitle burn failed, using concat as final", stderr=result.stderr[:300])
                import shutil
                shutil.copy2(concat_path, final_path)
        except Exception as e:
            # If subtitles fail entirely, just use the concat video
            logger.warning("subtitle step failed entirely, using concat", error=str(e)[:200])
            import shutil
            shutil.copy2(concat_path, final_path)

        if not os.path.exists(final_path):
            raise RuntimeError(f"No final video after subtitle step. concat exists: {os.path.exists(concat_path)}")

        file_size = os.path.getsize(final_path)

        # 6. Store publish metadata FIRST (so uploads always have titles)
        metadata = json.dumps({
            "title": title,
            "description": concept.get("caption", ""),
            "tags": concept.get("tags", []),
            "category": CHANNEL_CATEGORY.get(channel_id, "Entertainment"),
        })

        # 7. Update DB — step + status + assets in one transaction
        engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
        async with AsyncSession(engine) as s:
            await s.execute(
                text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :id"),
                {"id": run_id},
            )
            await s.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
                {"rid": run_id, "cid": channel_id, "type": "rendered_unified_short",
                 "content": json.dumps({"path": final_path, "file_size_bytes": file_size})},
            )
            # Check if publish_metadata already exists (avoid duplicates on retries)
            existing = await s.execute(
                text("SELECT id FROM assets WHERE run_id = :rid AND asset_type = 'publish_metadata'"),
                {"rid": run_id},
            )
            if not existing.fetchone():
                await s.execute(
                    text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
                    {"rid": run_id, "cid": channel_id, "type": "publish_metadata", "content": metadata},
                )
            await s.commit()
        await engine.dispose()

        # Copy to channel folder with title as filename
        _copy_to_channel_folder(final_path, title, channel_id, db_url)
        logger.info("pipeline complete", run_id=run_id, path=final_path, size_mb=round(file_size/1024/1024, 1))

    except Exception as e:
        logger.error("pipeline failed", run_id=run_id, error=str(e)[:300])
        try:
            engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
            async with AsyncSession(engine) as s:
                await s.execute(
                    text("UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id"),
                    {"id": run_id, "err": str(e)[:500]},
                )
                await s.commit()
            await engine.dispose()
        except Exception as db_err:
            logger.error("failed to update DB after pipeline failure", run_id=run_id, db_error=str(db_err)[:100])


async def _batched_visual_planning(
    line_audio: list[dict],
    title: str,
    channel_name: str,
    niche: str,
    is_long_form: bool,
    output_dir: str,
    batch_size: int = 12,
    channel_id: int = 0,
) -> list[dict]:
    """Plan visuals in batches of ~12 lines for long-form content.

    Returns a flat list of visuals, one per narration line.
    """
    import re as _re
    from packages.clients.claude import generate
    from packages.prompts.long_form import build_longform_visual_batch_prompt

    total_lines = len(line_audio)
    batches = []
    for start in range(0, total_lines, batch_size):
        end = min(start + batch_size, total_lines)
        batches.append(line_audio[start:end])

    logger.info("batched visual planning", total_lines=total_lines, batches=len(batches))

    all_visuals = [None] * total_lines
    style_summary = ""

    loop = asyncio.get_event_loop()

    for batch_idx, batch in enumerate(batches):
        batch_lines = [
            {"index": a["index"], "duration": a["duration"], "text": a["text"]}
            for a in batch
        ]

        system, user = build_longform_visual_batch_prompt(
            channel_name=channel_name,
            niche=niche,
            title=title,
            batch_lines=batch_lines,
            batch_index=batch_idx,
            total_batches=len(batches),
            previous_batch_summary=style_summary,
            is_long_form=is_long_form,
            channel_id=channel_id,
        )

        resp = await loop.run_in_executor(
            None, lambda s=system, u=user: generate(prompt=u, system=s, model="claude-sonnet-4-6", max_tokens=4000)
        )
        resp = resp.strip()
        if resp.startswith("```"):
            resp = _re.sub(r"^```(?:json)?\s*", "", resp)
            resp = _re.sub(r"\s*```$", "", resp)

        batch_plan = json.loads(resp)
        batch_visuals = batch_plan.get("visuals", [])
        style_summary = batch_plan.get("style_summary", style_summary)

        # Map visuals back to their line indices
        for v in batch_visuals:
            idx = v.get("line_index", None)
            if idx is not None and 0 <= idx < total_lines:
                all_visuals[idx] = v
            else:
                # Fallback: assign sequentially within batch
                for a in batch:
                    if all_visuals[a["index"]] is None:
                        all_visuals[a["index"]] = v
                        break

        logger.info("batch visual plan complete", batch=batch_idx + 1, of=len(batches),
                     visuals_planned=sum(1 for v in batch_visuals))

        # Small delay between batches
        if batch_idx < len(batches) - 1:
            await asyncio.sleep(2)

    # Fill any gaps with default image visuals
    for i in range(total_lines):
        if all_visuals[i] is None:
            all_visuals[i] = {
                "type": "image",
                "prompt": "Cinematic style, dramatic scene, landscape 16:9 composition." if is_long_form
                          else "Colorful cartoon style, dramatic scene, vertical composition.",
            }

    # Save the full plan
    with open(os.path.join(output_dir, "visual_plan.json"), "w") as f:
        json.dump({"visuals": all_visuals, "style_summary": style_summary}, f, indent=2)

    logger.info("batched visual planning complete", total_visuals=len(all_visuals),
                grok=sum(1 for v in all_visuals if v.get("type") == "grok"),
                image=sum(1 for v in all_visuals if v.get("type") == "image"))

    return all_visuals


async def _run_no_narration(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """No-narration pipeline for memes and satisfying videos.

    Scenes have text baked into images, Grok animates with native audio.
    No TTS, no subtitles.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text
    import base64

    scenes = concept.get("scenes", [])
    title = concept.get("title", "Untitled")
    channel_id = concept.get("channel_id", 14)
    WIDTH, HEIGHT = SHORT_WIDTH, SHORT_HEIGHT

    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [images_dir, clips_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    from packages.clients.grok import generate_image as grok_gen_image, generate_video_async

    # 1. Generate images + animate each scene
    await _update_step("generating scenes")
    segment_paths = []

    for i, scene in enumerate(scenes):
        img_path = os.path.join(images_dir, f"scene_{i}.png")
        clip_path = os.path.join(clips_dir, f"scene_{i}.mp4")
        seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")

        scene_prompt = scene.get("image_prompt", "")
        motion_prompt = scene.get("video_prompt", "subtle movement")
        duration = scene.get("duration", 5)

        # Generate image (with text baked in if provided)
        if not os.path.exists(img_path):
            await _update_step(f"generating scene {i + 1}/{len(scenes)}")
            grok_gen_image(
                prompt=scene_prompt,
                output_path=img_path,
            )
            logger.info("scene image generated", scene=i)

        # Animate
        if not os.path.exists(clip_path):
            await _update_step(f"animating scene {i + 1}/{len(scenes)}")
            compressed = img_path.replace(".png", "_hq.jpg")
            if not os.path.exists(compressed):
                subprocess.run(["ffmpeg", "-y", "-i", img_path, "-q:v", "2", compressed],
                    capture_output=True, timeout=10)
            with open(compressed if os.path.exists(compressed) else img_path, "rb") as rf:
                img_b64 = f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}"

            await generate_video_async(
                prompt=motion_prompt,
                output_path=clip_path,
                duration=min(duration, 10),
                aspect_ratio="9:16",
                image_url=img_b64,
            )
            logger.info("scene animated", scene=i)

        # Create segment — keep Grok native audio
        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-i", clip_path,
            "-t", str(duration),
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
            "-movflags", "+faststart",
            seg_path,
        ], capture_output=True, timeout=120)

        if os.path.exists(seg_path):
            segment_paths.append(seg_path)
            logger.info("scene segment created", scene=i, duration=duration)

    if not segment_paths:
        raise RuntimeError("No scene segments created")

    # 2. Concatenate
    await _update_step("concatenating")
    concat_path = os.path.join(output_dir, "raw_concat.mp4")
    concat_list = os.path.join(output_dir, "concat_list.txt")
    with open(concat_list, "w") as f:
        for seg in segment_paths:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
        concat_path,
    ], capture_output=True, timeout=300)

    # 3. Add background music if specified
    bg_music = concept.get("background_music")
    if bg_music:
        music_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")
        bg_path = os.path.join(music_dir, f"{bg_music}.mp3")
        if os.path.exists(bg_path):
            video_dur = _get_duration(concat_path)
            with_music = os.path.join(output_dir, "with_music.mp4")
            cmd = f'ffmpeg -y -i {concat_path} -stream_loop -1 -i {bg_path} -filter_complex "[1:a]volume=0.15,atrim=0:{video_dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first:weights=3 1,loudnorm=I=-16:TP=-1.5:LRA=11[out]" -map 0:v -map "[out]" -c:v copy -c:a aac -ar 44100 -b:a 192k -movflags +faststart {with_music}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and os.path.exists(with_music):
                os.replace(with_music, concat_path)

    # No subtitles for no-narration content
    final_path = os.path.join(output_dir, "final.mp4")
    import shutil
    shutil.copy2(concat_path, final_path)

    if not os.path.exists(final_path):
        raise RuntimeError("No final video")

    file_size = os.path.getsize(final_path)

    # Update DB
    metadata_dict = {
        "title": title,
        "description": concept.get("caption", ""),
        "tags": concept.get("tags", []),
        "category": CHANNEL_CATEGORY.get(channel_id, "Entertainment"),
    }
    metadata = json.dumps(metadata_dict)

    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    async with AsyncSession(engine) as s:
        await s.execute(
            text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await s.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": "rendered_unified_short",
             "content": json.dumps({"path": final_path, "file_size_bytes": file_size})},
        )
        existing = await s.execute(
            text("SELECT id FROM assets WHERE run_id = :rid AND asset_type = 'publish_metadata'"),
            {"rid": run_id},
        )
        if not existing.fetchone():
            await s.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
                {"rid": run_id, "cid": channel_id, "type": "publish_metadata", "content": metadata},
            )
        await s.commit()
    await engine.dispose()

    _copy_to_channel_folder(final_path, title, channel_id, db_url)
    logger.info("no-narration pipeline complete", run_id=run_id, path=final_path,
                scenes=len(scenes), size_mb=round(file_size/1024/1024, 1))


async def _run_narration_first(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Narration-first pipeline: generate audio → plan one visual per line → assemble.

    Each narration line gets exactly one visual. The visual's duration matches the audio
    exactly — no timestamp slicing, no drift, perfect sync.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text
    import base64
    import re as _re

    narration_lines = concept.get("narration", [])
    no_narration = concept.get("narration_style") == "none" or not narration_lines

    # For no-narration content (memes, satisfying), use scenes list instead
    scenes = concept.get("scenes", [])
    if no_narration and not scenes and not narration_lines:
        raise ValueError("No narration lines or scenes in concept")

    is_long_form = concept.get("long_form", False) or len(narration_lines) >= 20
    WIDTH = LONG_WIDTH if is_long_form else SHORT_WIDTH
    HEIGHT = LONG_HEIGHT if is_long_form else SHORT_HEIGHT
    voice_id = concept.get("voice_id", "56bWURjYFHyYyVf490Dp")
    narration_speed = concept.get("speed", None)
    title = concept.get("title", "Untitled")
    channel_id = concept.get("channel_id", 14)

    # No-narration pipeline (memes, satisfying videos)
    if no_narration:
        await _run_no_narration(run_id, concept, output_dir, _update_step, db_url)
        return

    narr_dir = os.path.join(output_dir, "narration")
    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, images_dir, clips_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # Strip emojis
    _emoji_pattern = _re.compile("[\U00010000-\U0010ffff]", flags=_re.UNICODE)
    narration_lines = [_emoji_pattern.sub("", line) for line in narration_lines]

    # 1. Generate narration per line
    await _update_step("generating narration")
    from packages.clients.elevenlabs import generate_speech

    line_audio = []  # [{index, path, duration, text}]
    for i, line in enumerate(narration_lines):
        narr_path = os.path.join(narr_dir, f"line_{i}.mp3")
        if not os.path.exists(narr_path):
            for attempt in range(3):
                try:
                    generate_speech(text=line, voice=voice_id, output_path=narr_path, speed=narration_speed)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"ElevenLabs failed after 3 attempts for line {i}: {e}") from e
                    await asyncio.sleep(5 * (attempt + 1))
        dur = _get_duration(narr_path)
        line_audio.append({"index": i, "path": narr_path, "duration": dur, "text": line})
        logger.info("narration generated", line=i, duration=round(dur, 2))

    total_duration = sum(a["duration"] for a in line_audio)

    # 2. Claude visual planning — one visual per narration line
    await _update_step("planning visuals")
    from packages.clients.claude import generate

    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    async with AsyncSession(engine) as s:
        ch_row = await s.execute(text("SELECT name, niche FROM channels WHERE id = :id"), {"id": channel_id})
        ch = ch_row.fetchone()
        channel_name = ch[0] if ch else "Unknown"
        niche = ch[1] if ch else "general"
    await engine.dispose()

    # Use batched visual planning for long-form, single call for shorts
    if is_long_form and len(line_audio) > 20:
        visuals = await _batched_visual_planning(
            line_audio, title, channel_name, niche, is_long_form, output_dir,
            channel_id=channel_id,
        )
    else:
        # Build the narration block with durations
        narr_block = "\n".join(
            f"  Line {a['index']} ({a['duration']:.1f}s): \"{a['text']}\""
            for a in line_audio
        )

        aspect = "16:9 landscape" if is_long_form else "9:16 vertical portrait"
        art_style = CHANNEL_ART_STYLE.get(channel_id, _DEFAULT_STYLE)
        visual_system = f"""You write DALL-E image prompts for YouTube videos. Channel: "{channel_name}" ({niche}).

One prompt per narration line. Every prompt starts with "{art_style}"

RULES:
- ONE scene per prompt. 1-2 sentences max.
- Think like a comedy editor — exaggerate everything. Absurd scale, extreme reactions, visual gags. The image should be funny or dramatic on its own even without narration.
- Named characters/animals/people: just use their name + what they're doing. Do NOT describe their appearance. DALL-E knows them.
- CRITICAL: Every term must be grounded in the video's universe. If the video is about League of Legends, "minions" means LEAGUE OF LEGENDS minions — write "League of Legends minions" not just "minions". If the video is about Pokemon, "evolution" means POKEMON evolution. Always prefix ambiguous terms with the franchise/universe name so DALL-E generates the right thing.
- If the video is about a specific character, that character should be in most images.
- DALL-E CANNOT draw: UIs, screens, menus, websites, game interfaces, text-heavy scenes, split panels
- DALL-E CANNOT understand: game jargon like "skins", "RP", "champion icons", "mana bar", "capsules"
- If narration mentions a screen/store/interface, show a person or character reacting instead
- Never show generic office workers when the topic is about a specific character/thing

BORING: "A Riot Games employee handing a gift box to a player"
FUNNY: "A Riot Games employee on his knees begging forgiveness while a smug gamer sits on a throne of gold coins"

SAFETY: The image generator will BLOCK prompts with combat/violence words. NEVER use: battle, fight, attack, fierce, intimidating, terrified, horror, destroy, death, kill, weapon, blood, evil, menacing, threatening, war. Instead show characters posing, reacting, celebrating, looking confused — not fighting.

TYPES:
- "grok": animated video clip. DEFAULT — use for almost every line. The image is generated first, then animated.
  "video_prompt": describe the motion/animation. GOOD: "camera slowly pulls back", "character turns head", "coins rain down"
- "image": static still. ONLY use for things that should not move: charts, numbers, graphs, documents, text displays. Everything else should be "grok". Everything else.

If a character appears in multiple lines, tag with "character": "name".
If the narration mentions a number/rank (like "#5", "Number 3"), add "label": "#5" or "label": "#3" to show the rank on screen.

Aspect ratio: {aspect}

OUTPUT — JSON:
{{
  "visuals": [
    {{"type": "grok", "prompt": "{art_style} Gangplank from League of Legends buried in gold coins, looking shocked", "video_prompt": "coins rain down burying him", "character": "Gangplank"}},
    {{"type": "image", "prompt": "{art_style} A gamer holding a single penny with a huge grin"}},
    ...
  ]
}}

Return exactly {len(line_audio)} visuals — one per narration line. Order matches narration order.
Return ONLY valid JSON, no markdown."""

        visual_user = f"""Plan visuals for "{title}"

NARRATION LINES WITH DURATIONS:
{narr_block}

Total: {total_duration:.1f}s, {len(line_audio)} lines

One visual per line. Make each visual perfectly match what's being said."""

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: generate(prompt=visual_user, system=visual_system, model="claude-sonnet-4-6", max_tokens=4000))
        resp = resp.strip()
        if resp.startswith("```"):
            resp = _re.sub(r"^```(?:json)?\s*", "", resp)
            resp = _re.sub(r"\s*```$", "", resp)

        visual_plan = json.loads(resp)
        visuals = visual_plan.get("visuals", [])

        with open(os.path.join(output_dir, "visual_plan.json"), "w") as f:
            json.dump(visual_plan, f, indent=2)

    # Ensure we have one visual per line (pad or trim)
    while len(visuals) < len(line_audio):
        visuals.append({"type": "image", "prompt": "Colorful cartoon style, dramatic scene, vertical composition."})
    visuals = visuals[:len(line_audio)]

    logger.info("visual plan complete", visuals=len(visuals),
                grok=sum(1 for v in visuals if v["type"] == "grok"),
                image=sum(1 for v in visuals if v["type"] == "image"))

    # 3. Generate visuals
    await _update_step("generating visuals")
    art_style = CHANNEL_ART_STYLE.get(channel_id, _DEFAULT_STYLE)
    from packages.clients.grok import generate_image as grok_gen_image
    from packages.clients.grok import generate_image_dalle as dalle_gen_image
    from packages.clients.grok import generate_video_async as grok_generate

    # Grok for all images — no safety filter issues, good character knowledge
    def _gen_still_image(prompt, output_path, reference_image_url=None):
        return grok_gen_image(prompt=prompt, output_path=output_path, reference_image_url=reference_image_url)

    visual_paths = {}  # i -> {type, path, source?}
    grok_ref_frame = None
    character_refs = {}  # character_name -> {"path": str, "b64": str} reference image
    character_descriptions = {}  # character_name -> text description for prompt consistency

    # Separate image, diagram, and grok visuals
    image_indices = [i for i, v in enumerate(visuals) if v["type"] == "image"]
    diagram_indices = [i for i, v in enumerate(visuals) if v["type"] == "diagram"]
    grok_indices = [i for i, v in enumerate(visuals) if v["type"] == "grok"]

    # Generate reference portraits for each unique character
    unique_characters = set()
    for v in visuals:
        char = v.get("character")
        if char:
            unique_characters.add(char)

    if unique_characters:
        await _update_step(f"generating {len(unique_characters)} character references")
        ref_dir = os.path.join(output_dir, "character_refs")
        os.makedirs(ref_dir, exist_ok=True)

        for char_name in unique_characters:
            ref_path = os.path.join(ref_dir, f"{char_name.replace(' ', '_')}.png")
            if not os.path.exists(ref_path):
                ref_prompt = f"{art_style} Family-friendly full body portrait of {char_name}, facing the viewer, simple background, character centered."
                _gen_still_image(prompt=ref_prompt, output_path=ref_path)
                logger.info("character reference generated", character=char_name)

            # Get Claude to describe the character from the image for prompt consistency
            if os.path.exists(ref_path):
                try:
                    import base64 as _b64ref
                    with open(ref_path, "rb") as rf:
                        ref_b64 = _b64ref.b64encode(rf.read()).decode()

                    from anthropic import Anthropic
                    desc_client = Anthropic()
                    desc_resp = desc_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=150,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ref_b64}},
                                {"type": "text", "text": "Describe this character's visual appearance in ONE sentence — colors, outfit, key features. Be specific. Start with the character name."},
                            ],
                        }],
                    )
                    desc = desc_resp.content[0].text.strip()
                    character_descriptions[char_name] = desc
                    logger.info("character described", character=char_name, description=desc[:80])
                except Exception as e:
                    logger.warning("character description failed", character=char_name, error=str(e)[:80])

                # Store compressed reference for Grok video
                compressed_ref = ref_path.replace(".png", "_hq.jpg")
                if not os.path.exists(compressed_ref):
                    subprocess.run(["ffmpeg", "-y", "-i", ref_path, "-q:v", "2", compressed_ref],
                        capture_output=True, timeout=10)
                with open(compressed_ref if os.path.exists(compressed_ref) else ref_path, "rb") as rf:
                    character_refs[char_name] = {
                        "path": ref_path,
                        "b64": f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}",
                    }

    def _validate_prompt(i, prompt, narration_text):
        """Pre-generation check: rewrite prompt with accurate visual descriptions.

        Uses web search to look up what specific characters/things actually look like,
        so the image prompt describes the real appearance instead of just a name.
        """
        try:
            from anthropic import Anthropic
            client = Anthropic()
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                messages=[{
                    "role": "user",
                    "content": f"""Narration line: "{narration_text}"
Image prompt: "{prompt}"

Your job: make sure this image prompt will produce an accurate image. Keep it SIMPLE.

If the prompt references a specific character, creature, or thing by name — search the web to find its key visual traits. Add ONLY the 2-3 most distinctive visual features (e.g. color, shape, key accessory). Do NOT write a paragraph.

Rules:
- Keep the prompt to 1-2 sentences max. Short prompts render better.
- ONE subject per image. Do not add extra elements.
- Start with "{art_style}"
- If the prompt is already good, return it unchanged.

Return ONLY the final image prompt text, nothing else.""",
                }],
            )
            # Extract text from response (may have tool use blocks)
            new_prompt = ""
            for block in resp.content:
                if block.type == "text":
                    new_prompt = block.text.strip().strip('"')
            if new_prompt and len(new_prompt) > 10:
                if new_prompt != prompt:
                    logger.info("prompt improved via search", line=i, old=prompt[:60], new=new_prompt[:60])
                return new_prompt
        except Exception as e:
            logger.warning("prompt validation failed (using original)", line=i, error=str(e)[:80])
        return prompt

    def _validate_image(i, img_path, narration_text, prompt_used):
        """Post-generation check: does the image match the narration?

        Uses web search to verify character/subject accuracy.
        """
        try:
            import base64 as _b64
            with open(img_path, "rb") as f:
                img_b64 = _b64.b64encode(f.read()).decode()

            from anthropic import Anthropic
            client = Anthropic()
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                        {"type": "text", "text": f"""The narrator is saying: "{narration_text}"
The image was generated from this prompt: "{prompt_used}"

Does this image accurately show what the narration describes? If it references a specific character, creature, or thing — search the web to verify the image matches the real appearance.

For example, if the narration mentions "Kindred from League of Legends" — search what Kindred looks like, then check if the image shows a lamb creature with a wolf mask (correct) or a human girl (wrong).

Format:
MATCH: YES or NO
PROMPT: (only if NO) a corrected image prompt with detailed visual description of what it should actually look like"""},
                    ],
                }],
            )
            result = ""
            for block in resp.content:
                if block.type == "text":
                    result += block.text
            result = result.strip()
            if "MATCH: NO" in result or "MATCH:NO" in result:
                for line in result.split("\n"):
                    if line.strip().startswith("PROMPT:"):
                        new_prompt = line.split("PROMPT:", 1)[1].strip()
                        if new_prompt and len(new_prompt) > 10:
                            logger.info("image rejected, regenerating", line=i, new_prompt=new_prompt[:60])
                            return False, new_prompt
            return True, None
        except Exception as e:
            logger.warning("image validation failed (keeping image)", line=i, error=str(e)[:80])
            return True, None

    # Generate images with validation
    if image_indices:
        from concurrent.futures import ThreadPoolExecutor

        def _gen_img_validated(i):
            p = os.path.join(images_dir, f"line_{i}.png")
            if os.path.exists(p):
                # Still register as character ref if applicable
                char_name = visuals[i].get("character")
                if char_name and char_name not in character_refs:
                    import base64 as _b64
                    with open(p, "rb") as rf:
                        character_refs[char_name] = f"data:image/png;base64,{_b64.b64encode(rf.read()).decode()}"
                return i, p

            narr_text = line_audio[i]["text"]
            prompt = visuals[i].get("prompt") or visuals[i].get("image_prompt", "")
            char_name = visuals[i].get("character")

            # Inject character description for visual consistency
            if char_name and char_name in character_descriptions:
                char_desc = character_descriptions[char_name]
                # Replace generic character name with specific description
                prompt = prompt + f" The character {char_name} looks like: {char_desc}"

            # Step 1: Validate prompt before generating
            prompt = _validate_prompt(i, prompt, narr_text)

            # Step 2: Generate image (pass character reference for consistency)
            ref_url = character_refs.get(char_name, {}).get("b64") if char_name else None
            for attempt in range(5):
                try:
                    _gen_still_image(prompt=prompt, output_path=p, reference_image_url=ref_url)
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "Too Many Requests" in err:
                        import time as _t
                        wait = 15 * (attempt + 1)
                        logger.warning("rate limited, waiting", line=i, wait=wait)
                        _t.sleep(wait)
                    elif attempt < 4:
                        import time as _t
                        _t.sleep(5 * (attempt + 1))
                        logger.warning("image retry", line=i, attempt=attempt, error=err[:100])
                    else:
                        raise

            # Step 3: Validate image matches narration (up to 2 retries)
            for retry in range(2):
                matches, better_prompt = _validate_image(i, p, narr_text, prompt)
                if matches:
                    break
                if better_prompt:
                    os.remove(p)
                    prompt = better_prompt
                    _gen_still_image(prompt=prompt, output_path=p)
                    logger.info("image regenerated after validation", line=i, retry=retry + 1)
                else:
                    break

            return i, p

        # Character refs already generated above — all images can go in parallel
        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(_gen_img_validated, i) for i in image_indices]
            for f in futures:
                i, path = f.result()
                visual_paths[i] = {"type": "image", "path": path}

    # Generate diagram visuals with gpt-image-1.5 (handles text/charts well)
    if diagram_indices:
        from concurrent.futures import ThreadPoolExecutor as _DiagramTPE

        def _gen_diagram(i):
            p = os.path.join(images_dir, f"line_{i}.png")
            if os.path.exists(p):
                return i, p
            prompt = visuals[i].get("prompt") or visuals[i].get("image_prompt", "")
            for attempt in range(3):
                try:
                    dalle_gen_image(
                        prompt=prompt,
                        output_path=p,
                        size="1536x1024",  # landscape
                        quality="high",
                    )
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "Too Many Requests" in err:
                        import time as _t
                        _t.sleep(15 * (attempt + 1))
                    elif attempt < 2:
                        import time as _t
                        _t.sleep(5 * (attempt + 1))
                        logger.warning("diagram retry", line=i, attempt=attempt, error=err[:100])
                    else:
                        raise
            return i, p

        with _DiagramTPE(max_workers=2) as ex:
            futures = [ex.submit(_gen_diagram, i) for i in diagram_indices]
            for f in futures:
                i, path = f.result()
                visual_paths[i] = {"type": "image", "path": path}
        logger.info("diagrams generated", count=len(diagram_indices))

    # Generate grok video clips
    if grok_indices:
        aspect_ratio = "16:9" if is_long_form else "9:16"
        needs_consistency = any(visuals[i].get("consistent_character") for i in grok_indices)


        async def _gen_grok_with_retries(i, max_attempts=3):
            """Generate a grok video clip: image first, then animate.

            1. Generate image with detailed scene prompt
            2. Animate image to video with short motion-only prompt
            Grok already has the image as context, so the video prompt
            just needs to describe motion, camera movement, and mood.
            """
            clip_path = os.path.join(clips_dir, f"line_{i}.mp4")
            if os.path.exists(clip_path):
                return i, clip_path
            dur = max(1, min(int(line_audio[i]["duration"]) + 1, 10))  # Grok max 10s for image-to-video

            # Step 1: Generate the image with Grok (pass reference image for character consistency)
            img_path = os.path.join(images_dir, f"line_{i}.png")
            if not os.path.exists(img_path):
                char_name = visuals[i].get("character")
                ref_url = character_refs.get(char_name, {}).get("b64") if char_name else None
                _gen_still_image(
                    prompt=visuals[i].get("prompt") or visuals[i].get("image_prompt", ""),
                    output_path=img_path,
                    reference_image_url=ref_url,
                )
            # Compress to high-quality JPEG for Grok video (PNG too large)
            img_compressed = img_path.replace(".png", "_hq.jpg")
            if not os.path.exists(img_compressed):
                subprocess.run(
                    ["ffmpeg", "-y", "-i", img_path, "-q:v", "2", img_compressed],
                    capture_output=True, timeout=10,
                )
            source_img = img_compressed if os.path.exists(img_compressed) else img_path
            with open(source_img, "rb") as rf:
                img_data_url = f"data:image/{('jpeg' if source_img.endswith('.jpg') else 'png')};base64,{base64.b64encode(rf.read()).decode()}"

            # Step 2: Animate with short motion prompt
            motion_prompt = visuals[i].get("video_prompt", "Slow cinematic movement, dramatic mood")

            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        await asyncio.sleep(5 * attempt)
                        logger.info("retrying grok clip", line=i, attempt=attempt)
                    await grok_generate(
                        prompt=motion_prompt,
                        output_path=clip_path, duration=dur, aspect_ratio=aspect_ratio,
                        image_url=img_data_url,
                    )
                    return i, clip_path
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise RuntimeError(f"Grok video failed for line {i} after {max_attempts} attempts: {e}") from e
                    logger.warning("grok clip attempt failed", line=i, attempt=attempt, error=str(e)[:100])

        # If consistency, generate first for ref frame
        if needs_consistency:
            first_gi = grok_indices[0]
            first_clip = os.path.join(clips_dir, f"line_{first_gi}.mp4")
            dur = max(1, min(int(line_audio[first_gi]["duration"]) + 1, 10))

            # Generate image first, then animate
            first_img = os.path.join(images_dir, f"line_{first_gi}.png")
            if not os.path.exists(first_img):
                _gen_still_image(prompt=visuals[first_gi]["prompt"], output_path=first_img)
            with open(first_img, "rb") as rf:
                first_img_url = f"data:image/png;base64,{base64.b64encode(rf.read()).decode()}"

            motion_prompt = visuals[first_gi].get("video_prompt", "Slow cinematic movement, dramatic mood")
            for attempt in range(3):
                try:
                    if attempt > 0:
                        await asyncio.sleep(5 * attempt)
                    await grok_generate(
                        prompt=motion_prompt,
                        output_path=first_clip, duration=dur, aspect_ratio=aspect_ratio,
                        image_url=first_img_url,
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"Grok failed on first clip (line {first_gi}) after 3 attempts: {e}") from e
                    logger.warning("first grok clip retry", attempt=attempt, error=str(e)[:100])

            visual_paths[first_gi] = {"type": "video", "path": first_clip, "source": "grok"}
            ref_path = os.path.join(clips_dir, "grok_ref.jpg")
            subprocess.run([
                "ffmpeg", "-y", "-ss", "1", "-i", first_clip,
                "-map", "0:v:0", "-frames:v", "1", "-q:v", "3", ref_path,
            ], capture_output=True, text=True, timeout=15)
            if os.path.exists(ref_path):
                with open(ref_path, "rb") as rf:
                    grok_ref_frame = f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}"
            remaining = grok_indices[1:]
        else:
            remaining = grok_indices

        if remaining:
            await _update_step(f"generating {len(remaining)} video clips")
            # Stagger launches to avoid rate limits
            tasks = []
            for idx, i in enumerate(remaining):
                async def _launch(i=i, delay=idx * 1.5):
                    await asyncio.sleep(delay)
                    return await _gen_grok_with_retries(i)
                tasks.append(_launch())
            results = await asyncio.gather(*tasks)
            for i, clip_path in results:
                visual_paths[i] = {"type": "video", "path": clip_path, "source": "grok"}

    # 4. Create segments — each line's audio paired directly with its visual
    await _update_step("creating segments")

    segment_paths = []
    for i, audio in enumerate(line_audio):
        seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")
        dur = audio["duration"]
        vp = visual_paths.get(i)
        # Landscape: scale down + pad. Portrait: scale up + crop to fill (no black bars).
        if is_long_form:
            scale_filter = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2"
        else:
            scale_filter = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}"

        if not vp:
            logger.warning("no visual for line", line=i)
            continue

        if vp["type"] == "video":
            is_grok = vp.get("source") == "grok"
            if is_grok:
                # Strip mjpeg thumbnail but KEEP audio for mixing
                clean_clip = vp["path"].replace(".mp4", "_clean.mp4")
                if not os.path.exists(clean_clip):
                    subprocess.run([
                        "ffmpeg", "-y", "-i", vp["path"],
                        "-map", "0:v:0", "-map", "0:a?", "-c:v", "copy", "-c:a", "copy", clean_clip,
                    ], capture_output=True, text=True, timeout=30)
                clip_input = clean_clip if os.path.exists(clean_clip) else vp["path"]

                # Strip video to video-only (remove grok's audio track entirely)
                # Narration is the audio — grok clip audio is just ambient noise
                video_only = clip_input.replace("_clean.mp4", "_vidonly.mp4")
                if not os.path.exists(video_only):
                    subprocess.run([
                        "ffmpeg", "-y", "-i", clip_input,
                        "-map", "0:v:0", "-c:v", "copy", "-an", video_only,
                    ], capture_output=True, text=True, timeout=30)
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", video_only if os.path.exists(video_only) else clip_input,
                    "-i", audio["path"],
                    "-vf", scale_filter,
                    "-map", "0:v", "-map", "1:a",
                    "-t", str(dur),
                    "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-movflags", "+faststart",
                    seg_path,
                ]
            else:
                clip_input = vp["path"]
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", clip_input,
                    "-i", audio["path"],
                    "-vf", scale_filter,
                    "-map", "0:v", "-map", "1:a",
                    "-t", str(dur),
                    "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-movflags", "+faststart",
                    seg_path,
                ]
        else:
            # Static image — scale to output resolution
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", vp["path"],
                "-i", audio["path"],
                "-vf", scale_filter,
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                seg_path,
            ]

        seg_timeout = 180 if is_long_form else 120
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=seg_timeout)
        if result.returncode != 0:
            logger.warning("segment failed", line=i, stderr=result.stderr[:200])
            continue

        if os.path.exists(seg_path):
            segment_paths.append(seg_path)
            logger.info("segment created", line=i, dur=round(dur, 2), type=vp["type"])

    if not segment_paths:
        raise RuntimeError("No segments created")

    # 5. Assemble with visual transitions + SFX + background music
    await _update_step("assembling")
    concat_path = os.path.join(output_dir, "raw_concat.mp4")
    sub_timeout = 1200 if is_long_form else 300
    sfx_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "sfx")

    FADE_DUR = 0.3  # crossfade duration between segments

    # Step 5a: Crossfade segments together with visual wipe transitions
    if len(segment_paths) >= 2:
        # Get each segment's duration for offset calculation
        seg_durations = []
        for seg in segment_paths:
            d = float(subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", seg],
                capture_output=True, text=True, timeout=10).stdout.strip())
            seg_durations.append(d)

        # Calculate xfade offsets
        offsets = []
        cumulative = 0.0
        for i, d in enumerate(seg_durations):
            if i > 0:
                offsets.append(cumulative - FADE_DUR)
            cumulative += d - (FADE_DUR if i < len(seg_durations) - 1 else 0)

        # Build xfade filter chain
        n = len(segment_paths)
        inputs_str = " ".join(f"-i {seg}" for seg in segment_paths)
        vf_parts = []
        af_parts = []
        prev_v = "[0:v]"
        prev_a = "[0:a]"
        for i in range(1, n):
            out_v = f"[v{i}]" if i < n - 1 else "[vout]"
            out_a = f"[a{i}]" if i < n - 1 else "[aout]"
            vf_parts.append(f"{prev_v}[{i}:v]xfade=transition=wipeleft:duration={FADE_DUR}:offset={offsets[i-1]:.3f}{out_v}")
            af_parts.append(f"{prev_a}[{i}:a]acrossfade=d={FADE_DUR}{out_a}")
            prev_v = out_v
            prev_a = out_a

        filter_str = ";".join(vf_parts + af_parts)
        xfade_cmd = f'ffmpeg -y {inputs_str} -filter_complex "{filter_str}" -map "[vout]" -map "[aout]" -c:v libx264 -preset fast -crf 14 -c:a aac -ar 44100 -b:a 192k -movflags +faststart {concat_path}'
        result = subprocess.run(xfade_cmd, shell=True, capture_output=True, text=True, timeout=sub_timeout)
        if result.returncode != 0:
            logger.warning("crossfade failed, falling back to simple concat", stderr=result.stderr[:200])
            # Fallback to simple concat
            concat_list_path = os.path.join(output_dir, "concat_list.txt")
            with open(concat_list_path, "w") as f:
                for seg in segment_paths:
                    f.write(f"file '{os.path.abspath(seg)}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
                 "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
                 concat_path],
                capture_output=True, text=True, timeout=sub_timeout,
            )
    else:
        # Single segment — just copy
        import shutil
        shutil.copy2(segment_paths[0], concat_path)

    # Step 5b: Add page turn SFX at transitions + background music
    sfx_page_turn = os.path.join(sfx_dir, "el_page_turn.mp3")
    # Pick background music based on channel niche
    # Select background music based on channel vibe
    music_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")
    channel_music_map = {
        # Intense/dramatic
        "SpookLand": "epic", "Cold Case Cartoons": "epic", "Deep We Go": "epic",
        "Villanous Origins": "epic",
        # Fun/upbeat
        "Deity Drama": "comical", "Toongunk": "comical", "Munchlax Lore": "epic",
        "Crab Rave Shorts": "epic", "Night Night Shorts": "epic",
        "One on Ones For Fun": "epic",
        # Chill/informative
        "Smooth Brain Academy": "chill", "Globe Thoughts": "chill",
        "What If City": "chill", "Stays Unwritten": "chill",
        # Energetic
        "Nature Receipts": "feel_alive", "Historic Ls": "comical",
        "Schmoney Facts": "feel_alive", "Hardcore Ranked": "epic",
    }
    music_name = channel_music_map.get(channel_name, "chill")
    bg_music_path = os.path.join(music_dir, f"{music_name}.mp3")
    if not os.path.exists(bg_music_path):
        bg_music_path = None

    if os.path.exists(concat_path) and os.path.exists(sfx_page_turn):
        try:
            video_dur = float(subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", concat_path],
                capture_output=True, text=True, timeout=10).stdout.strip())

            # Calculate transition points from segment durations
            boundaries = []
            cumulative = 0.0
            for audio in line_audio[:-1]:
                cumulative += audio["duration"] - FADE_DUR  # adjusted for crossfade
                boundaries.append(max(0, cumulative))

            if boundaries:
                concat_with_audio = os.path.join(output_dir, "raw_concat_audio.mp4")
                sfx_inputs = " ".join(f"-i {sfx_page_turn}" for _ in boundaries)
                delays = ";".join(
                    f"[{k+1}]adelay={int(t*1000)}|{int(t*1000)},volume=1.5[s{k}]"
                    for k, t in enumerate(boundaries)
                )
                sfx_labels = "".join(f"[s{k}]" for k in range(len(boundaries)))

                if bg_music_path:
                    bg_idx = len(boundaries) + 1
                    filter_str = f"{delays};[{bg_idx}]volume=0.12,atrim=0:{video_dur}[bgm];[0:a]{sfx_labels}[bgm]amix=inputs={len(boundaries)+2}:duration=first:weights={' '.join(['5'] + ['1']*len(boundaries) + ['1'])},loudnorm=I=-16:TP=-1.5:LRA=11[out]"
                    cmd = f'ffmpeg -y -i {concat_path} {sfx_inputs} -stream_loop -1 -i {bg_music_path} -filter_complex "{filter_str}" -map 0:v -map "[out]" -c:v copy -c:a aac -ar 44100 -b:a 192k -movflags +faststart {concat_with_audio}'
                else:
                    filter_str = f"{delays};[0:a]{sfx_labels}amix=inputs={len(boundaries)+1}:duration=first:weights={' '.join(['5'] + ['1']*len(boundaries))},loudnorm=I=-16:TP=-1.5:LRA=11[out]"
                    cmd = f'ffmpeg -y -i {concat_path} {sfx_inputs} -filter_complex "{filter_str}" -map 0:v -map "[out]" -c:v copy -c:a aac -ar 44100 -b:a 192k -movflags +faststart {concat_with_audio}'

                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=sub_timeout)
                if result.returncode == 0 and os.path.exists(concat_with_audio):
                    os.replace(concat_with_audio, concat_path)
                    logger.info("added transitions + SFX + background music")
                else:
                    logger.warning("audio mixing failed, using video without SFX", stderr=result.stderr[:200] if result.stderr else "")
        except Exception as e:
            logger.warning("audio post-processing failed", error=str(e)[:100])

    # 6. Burn karaoke subtitles
    await _update_step("subtitles")
    final_path = os.path.join(output_dir, "final.mp4")

    try:
        from faster_whisper import WhisperModel
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        whisper_segs, _ = whisper_model.transcribe(concat_path, word_timestamps=True)

        all_words = []
        for seg in whisper_segs:
            if seg.words:
                for w in seg.words:
                    all_words.append((w.word.strip(), w.start, w.end))

        # Build labels from visual plan
        visual_labels = []
        cumulative = 0.0
        for i, v in enumerate(visuals):
            if v.get("label"):
                visual_labels.append((v["label"], cumulative, cumulative + line_audio[i]["duration"]))
            cumulative += line_audio[i]["duration"]

        ass_path = os.path.join(output_dir, "subs.ass")
        _write_karaoke_ass(ass_path, all_words, visual_labels, is_long_form=is_long_form)

        ass_escaped = ass_path.replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y", "-i", concat_path,
            "-vf", f"ass={ass_escaped}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart",
            final_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=sub_timeout)
        if result.returncode != 0:
            import shutil
            shutil.copy2(concat_path, final_path)
    except Exception as e:
        logger.warning("subtitle step failed, using concat", error=str(e)[:200])
        import shutil
        shutil.copy2(concat_path, final_path)

    if not os.path.exists(final_path):
        raise RuntimeError(f"No final video. concat exists: {os.path.exists(concat_path)}")

    file_size = os.path.getsize(final_path)

    # 7. Update DB IMMEDIATELY after video is confirmed — before thumbnail or any optional step
    #    This prevents orphaned videos where the file exists but the DB doesn't know about it.
    metadata_dict = {
        "title": title,
        "description": concept.get("caption", ""),
        "tags": concept.get("tags", []),
        "category": CHANNEL_CATEGORY.get(channel_id, "Entertainment"),
    }
    metadata = json.dumps(metadata_dict)

    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    async with AsyncSession(engine) as s:
        await s.execute(
            text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await s.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": "rendered_unified_short",
             "content": json.dumps({"path": final_path, "file_size_bytes": file_size})},
        )
        existing = await s.execute(
            text("SELECT id FROM assets WHERE run_id = :rid AND asset_type = 'publish_metadata'"),
            {"rid": run_id},
        )
        if not existing.fetchone():
            await s.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
                {"rid": run_id, "cid": channel_id, "type": "publish_metadata", "content": metadata},
            )
        await s.commit()
    await engine.dispose()

    # 7b. Generate thumbnail for long-form (optional — DB is already updated)
    if is_long_form:
        try:
            await _update_step("generating thumbnail")
            thumbnail_path = await _generate_longform_thumbnail(
                concept, output_dir, title, channel_name,
            )
            if thumbnail_path:
                # Update metadata with thumbnail path
                metadata_dict["thumbnail_path"] = thumbnail_path
                engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
                async with AsyncSession(engine) as s:
                    await s.execute(
                        text("UPDATE assets SET content = :content WHERE run_id = :rid AND asset_type = 'publish_metadata'"),
                        {"rid": run_id, "content": json.dumps(metadata_dict)},
                    )
                    await s.commit()
                await engine.dispose()
        except Exception as e:
            logger.warning("thumbnail generation failed (non-fatal, video is already saved)", error=str(e)[:200])
        finally:
            await _update_step("pending_review")

    # Copy to channel folder with title as filename
    _copy_to_channel_folder(final_path, title, channel_id, db_url)
    logger.info("pipeline complete", run_id=run_id, path=final_path, size_mb=round(file_size/1024/1024, 1),
                lines=len(line_audio), duration=round(total_duration, 1))


async def _generate_longform_thumbnail(
    concept: dict,
    output_dir: str,
    title: str,
    channel_name: str,
) -> str | None:
    """Generate a custom thumbnail for long-form video.

    Uses the concept's thumbnail spec (visual + text + emotion) to create
    a 1920x1080 image with text overlay burned in.
    """
    from packages.clients.grok import generate_image as grok_gen_image

    thumb_spec = concept.get("thumbnail", {})
    if not thumb_spec:
        # No thumbnail spec — generate one from the title
        thumb_visual = f"Dramatic cinematic scene related to: {title}. Dark moody lighting, high contrast, landscape 16:9."
        thumb_text = title[:30]
    else:
        thumb_visual = thumb_spec.get("visual", f"Dramatic scene: {title}")
        thumb_text = thumb_spec.get("text", "")
        emotion = thumb_spec.get("emotion", "mystery")
        thumb_visual = f"{thumb_visual}. Mood: {emotion}. Cinematic, high contrast, landscape 16:9 composition. YouTube thumbnail style — bold, eye-catching, readable at small size."

    thumb_img = os.path.join(output_dir, "thumbnail_raw.png")
    thumb_final = os.path.join(output_dir, "thumbnail.jpg")  # JPEG to stay under YouTube's 2MB limit

    try:
        # Generate the base thumbnail image
        for attempt in range(3):
            try:
                grok_gen_image(prompt=thumb_visual, output_path=thumb_img)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning("thumbnail image retry", attempt=attempt, error=str(e)[:100])
                import asyncio as _aio
                await _aio.sleep(3 * (attempt + 1))

        if thumb_text:
            # Burn text overlay onto thumbnail using ffmpeg
            # White text with black outline, bottom-left, large bold font
            safe_text = thumb_text.replace("'", "\\'").replace('"', '\\"').replace(":", "\\:")
            result = subprocess.run([
                "ffmpeg", "-y", "-i", thumb_img,
                "-vf", (
                    f"scale=1920:1080:force_original_aspect_ratio=decrease,"
                    f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                    f"drawtext=text='{safe_text}'"
                    f":fontsize=80:fontcolor=white:borderw=4:bordercolor=black"
                    f":x=60:y=h-th-60:font=Impact"
                ),
                "-q:v", "4",
                thumb_final,
            ], capture_output=True, text=True, timeout=30)
            if result.returncode != 0 or not os.path.exists(thumb_final):
                subprocess.run([
                    "ffmpeg", "-y", "-i", thumb_img,
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "4",
                    thumb_final,
                ], capture_output=True, text=True, timeout=30)
        else:
            subprocess.run([
                "ffmpeg", "-y", "-i", thumb_img,
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-q:v", "4",
                thumb_final,
            ], capture_output=True, text=True, timeout=30)

        if os.path.exists(thumb_final):
            logger.info("thumbnail generated", path=thumb_final, text=thumb_text)
            return thumb_final
        elif os.path.exists(thumb_img):
            logger.info("thumbnail generated (no text overlay)", path=thumb_img)
            return thumb_img
        return None

    except Exception as e:
        logger.warning("thumbnail generation failed (non-fatal)", error=str(e)[:200])
        return None


def _copy_to_channel_folder(final_path: str, title: str, channel_id: int, db_url: str):
    """Copy final video to output/videos/{Channel Name}/{Title}.mp4"""
    try:
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy import text
        import shutil
        import re

        async def _get_channel_name():
            engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
            async with AsyncSession(engine) as s:
                row = await s.execute(text("SELECT name FROM channels WHERE id = :id"), {"id": channel_id})
                result = row.scalar()
            await engine.dispose()
            return result

        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't await in sync context — use a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                channel_name = ex.submit(lambda: asyncio.run(_get_channel_name())).result()
        else:
            channel_name = asyncio.run(_get_channel_name())

        if not channel_name:
            return

        # Sanitize title for filename
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:80]
        channel_dir = os.path.join("output", "videos", channel_name)
        os.makedirs(channel_dir, exist_ok=True)
        dest = os.path.join(channel_dir, f"{safe_title}.mp4")
        shutil.copy2(final_path, dest)
        logger.info("copied to channel folder", dest=dest)
    except Exception as e:
        logger.warning("channel folder copy failed (non-fatal)", error=str(e)[:100])


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr[:100]}")
    return float(result.stdout.strip())


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _write_karaoke_ass(path: str, words: list[tuple], beat_labels: list[tuple] | None = None,
                       is_long_form: bool = False):
    """Write ASS file with karaoke-style word highlighting and optional beat labels."""
    if is_long_form:
        play_res_x, play_res_y = 1920, 1080
        font_size = 42
        label_size = 42
        subtitle_margin_v = 60  # bottom margin fine for landscape
        label_margin_v = 80
    else:
        play_res_x, play_res_y = 720, 1280
        font_size = 52
        label_size = 52
        subtitle_margin_v = 350  # push up above YouTube Shorts UI (~bottom 25%)
        label_margin_v = 400

    header = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Impact,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,50,50,{subtitle_margin_v},1
Style: Label,Impact,{label_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,8,60,60,{label_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.strip()]

    # Strip emojis from all text
    import re as _re
    _emoji_pat = _re.compile("[\U00010000-\U0010ffff]", flags=_re.UNICODE)

    # Beat labels (persistent top text)
    if beat_labels:
        for label, start, end in beat_labels:
            clean_label = _emoji_pat.sub("", label).strip()
            if clean_label:
                lines.append(f"Dialogue: 0,{_format_time(start)},{_format_time(end)},Label,,0,0,0,,{clean_label}")

    if words:
        # Group words into chunks of 3
        for gi in range(0, len(words), 3):
            group = words[gi:gi + 3]
            texts = [_emoji_pat.sub("", w[0]) for w in group]
            wc = len(group)
            times = []
            for j, (_, ws, we) in enumerate(group):
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
