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
from packages.clients.channel_profiles import (
    get_channel_anchor_policy as get_profile_anchor_policy,
    get_channel_art_style as get_profile_art_style,
    get_channel_audio_policy as get_profile_audio_policy,
    get_channel_category as get_profile_category,
    get_channel_intro_policy as get_profile_intro_policy,
    get_channel_provider_strategy as get_profile_provider_strategy,
    get_channel_video_model as get_profile_video_model,
    get_channel_video_provider as get_profile_video_provider,
    get_channel_video_resolution as get_profile_video_resolution,
    should_skip_image_review as get_profile_skip_image_review,
)
from packages.clients.workflow_state import (
    append_run_event,
    create_review_task,
    ensure_run_bundle,
    get_pending_review_task,
    resolve_review_task,
    update_concept_status,
    update_run_manifest,
)

load_dotenv(override=True)
logger = structlog.get_logger()

SHORT_WIDTH = 720
SHORT_HEIGHT = 1280
LONG_WIDTH = 1920
LONG_HEIGHT = 1080

# YouTube category per channel ID — used during upload
CHANNEL_CATEGORY = {
    # 9: deleted (was Techognize)
    # 10: deleted (was Mathognize)
    34: "Science & Technology",   # Ctrl Z The Time
    12: "News & Politics",        # Globe Dump
    13: "Gaming",                 # Munchlax Lore
    14: "Entertainment",          # ToonGunk
    15: "Entertainment",          # Very Clean Very Good
    16: "Gaming",                 # CrabRaveShorts
    17: "Education",              # Smooth Brain Academy
    18: "Entertainment",          # What If City
    19: "Entertainment",          # SpookLand
    20: "Entertainment",          # ColdCaseCartoons
    21: "Entertainment",          # One on Ones For Fun
    22: "Entertainment",          # Deity Drama
    23: "Science & Technology",    # Techognizer
    24: "Entertainment",          # Blanket Fort Cartoons
    25: "Pets & Animals",         # Nature Receipts
    26: "Entertainment",          # Hardcore Ranked
    27: "Entertainment",          # Deep We Go
    28: "Entertainment",          # NightNightShorts
    29: "Education",              # Globe Thoughts
    30: "Education",              # Historic Ls
    31: "Education",              # Schmoney Facts
    32: "Education",              # Mathematicious
    33: "Comedy",                 # Thats A Meme
}

# Channel-specific art styles for visual planning
_DEFAULT_STYLE = "Bold cartoon illustration style, thick outlines, bright colors. NEVER photorealistic — always illustrated."
# IMPORTANT: Every style must be ILLUSTRATED, never photorealistic.
# Add "NEVER photorealistic" to any style that could drift toward realism.
CHANNEL_ART_STYLE = {
    # 9: deleted (was Techognize)
    # 10: deleted (was Mathognize)
    34: "Clean flat vector infographic, like Vox or Bloomberg Quicktake graphics. White background, bold blue accents, clean icons, data-driven layout.",  # Ctrl Z The Time
    13: "Simple crude cartoon with thick wobbly outlines and flat colors. Like a funny webcomic or doodle. Pokemon should be recognizable by their signature features (Pikachu's red cheeks, Charizard's wings and tail flame, Snorlax's round belly) but drawn in crude doodle style. Exaggerated expressions, stubby proportions. Game elements like HP bars, pokeballs, and battle screens drawn in crude cartoon style. NOT realistic, NOT official Pokemon art — crude and funny.",  # Munchlax Lore
    14: "In the visual style of actual 1990s-2000s cartoon show frames — like paused frames from Dexter's Lab, Powerpuff Girls, SpongeBob, or Fairly OddParents. Scenes should look like real cartoon screenshots with the show's backgrounds, character animations mid-action, classic cartoon expressions. NOT modern reinterpretation — actual retro cartoon frames.",  # ToonGunk
    15: "Clean flat lay illustration, birds-eye view, objects arranged symmetrically on white surface. Like an IKEA instruction manual meets Marie Kondo aesthetic. Vector art.",  # Very Clean Very Good
    16: "Simple crude cartoon with thick wobbly outlines and flat colors. Like a funny webcomic or doodle. Game characters should be recognizable — use their actual names (Yasuo from League of Legends, Master Chief from Halo, Steve from Minecraft, etc.) and draw them in crude doodle style. Exaggerated expressions, stubby proportions, big heads. Game elements like health bars, chat boxes, kill feeds, minimaps, and lane/turret/jungle props should be drawn in crude cartoon style too. League of Legends scenes must still look like Summoner's Rift with lane stones, brush, jungle entrances, and turret bases — never generic fantasy filler. NOT realistic, NOT official game art — crude and funny.",  # CrabRaveShorts
    17: "In the style of a child's crayon drawing on lined notebook paper — wobbly circles, stick figures, misspelled labels, colorful and messy but charming. Like Diary of a Wimpy Kid illustrations.",  # Smooth Brain Academy
    18: "In the style of Kurzgesagt — clean flat vector illustration, simple bold shapes, vibrant saturated colors on dark backgrounds, tiny detailed characters in massive sci-fi environments, cosmic scale. Educational but visually stunning.",  # What If City
    19: "Detailed black and white manga illustration with intricate crosshatching and linework. Stark monochrome with occasional red accents. Unsettling atmosphere with spiral motifs and exaggerated expressions. Japanese horror manga aesthetic.",  # SpookLand
    20: "High contrast black and white graphic novel illustration with bold ink linework. Almost entirely monochrome with selective pops of red or yellow for emphasis. Noir mystery aesthetic with dramatic shadows and silhouettes.",  # ColdCaseCartoons
    21: "Simple colorful cartoon illustration — bright colors, clean lines, expressive characters, solid backgrounds. Fun and friendly. Illustrated not photographed.",  # One on Ones For Fun
    22: "Photorealistic cinematic scene with dramatic lighting. Gods depicted as powerful muscular humans with divine features — glowing eyes, golden armor, supernatural auras. Like a scene from a Marvel or God of War movie. Characters must be recognizable by their iconic attributes (Zeus with lightning, Poseidon with trident, Ares in red armor). Photorealistic world, NOT cartoon, NOT illustrated.",  # Deity Drama
    23: "Actual dry-erase marker drawing on a real white whiteboard with visible marker streaks and slightly smudged edges. Messy handwritten text, wobbly arrows, imperfect circles drawn by hand. Looks like a real photo of a whiteboard in a classroom. NOT digital art, NOT clean vector graphics — real messy human handwriting on a real whiteboard.",  # Techognizer
    24: "In the style of Bluey or Peppa Pig animation — soft rounded shapes, warm pastel colors, simple faces, gentle lighting, no sharp edges. Children's TV animation cel style.",  # Blanket Fort Cartoons
    25: "Photorealistic editorial wildlife photography — absurd animal scenarios rendered like real high-end press or documentary photos. Real feathers, fur, scales, anatomy, and lighting. Naturalistic textures, believable shadows, real camera depth of field, subtle lens imperfections. Human environments and props may be absurd, but the final image must still look like a real photograph. NOT cartoon, NOT illustrated, NOT cel-shaded.",  # Nature Receipts
    26: "Bold colorful digital illustration matching the topic — anime style for anime topics, game art style for gaming topics, cinematic poster style for movie topics. Vibrant, high energy, clear subjects. Each image should look like it belongs in the world of whatever is being ranked.",  # Hardcore Ranked
    27: "Conspiracy theory evidence board — cork board covered in red string connecting photographs, newspaper clippings, post-it notes, and handwritten arrows. Charlie Day Pepe Silvia energy.",  # Deep We Go
    28: "Clean anime-cartoon hybrid — bold clean outlines, flat cel shading, crisp anime silhouettes, simplified but recognizable faces, expressive webtoon energy. Characters stay recognizable by signature hair, outfit, makeup, weapons, and colors, but rendered like a polished 2D parody frame rather than a painterly anime screenshot. NOT photoreal, NOT plush chibi, NOT storybook soft, NOT grimy doodle, NOT glossy 3D mobile-game art.",  # NightNightShorts
    29: "In the style of 1950s airline travel posters — bold flat colors, stylized landscapes, art deco typography influence, vintage tourism illustration aesthetic.",  # Globe Thoughts
    30: "Ink wash cartoon illustration with exaggerated caricature features — crosshatched shading, sepia and muted tones, hand-drawn editorial style. Characters with oversized heads and expressive faces. Historical scenes with a humorous twist. Illustrated not photographed.",  # Historic Ls
    31: "In the style of GTA loading screen art — bold illustrated characters, saturated colors, slightly exaggerated proportions, urban and flashy. Money, luxury, and hustle energy. Illustrated not photographed.",  # Schmoney Facts
    32: "Actual dry-erase marker drawing on a real white whiteboard with visible marker streaks and slightly smudged edges. Messy handwritten text, wobbly arrows, imperfect circles, equations and graphs drawn by hand. Looks like a real photo of a math teacher's whiteboard after a lecture. NOT digital art, NOT clean vector graphics — real messy human handwriting on a real whiteboard.",  # Mathematicious
    33: "Simple 2D cartoon style like TheOdd1sOut or Jaiden Animations — clean lines, flat colors, expressive round-headed characters with big eyes, white or solid color backgrounds. Looks hand-drawn but clean. NOT AI-looking, NOT photorealistic, NOT over-detailed.",  # Thats A Meme
}


def get_channel_category(channel_id: int) -> str:
    return get_profile_category(
        channel_id,
        fallback_map=CHANNEL_CATEGORY,
        default="Entertainment",
    )


def get_channel_art_style(channel_id: int) -> str:
    return get_profile_art_style(
        channel_id,
        fallback_map=CHANNEL_ART_STYLE,
        default=_DEFAULT_STYLE,
    )


def should_skip_image_review(channel_id: int) -> bool:
    return get_profile_skip_image_review(channel_id)


def get_channel_runtime_policy(channel_id: int, concept: dict | None = None) -> dict[str, str | None]:
    concept = concept or {}
    provider_strategy = str(
        concept.get("provider_strategy") or get_profile_provider_strategy(channel_id)
    ).strip().lower()
    explicit_provider = str(
        concept.get("video_provider") or get_profile_video_provider(channel_id, default="")
    ).strip().lower()
    video_provider = explicit_provider or ("veo" if provider_strategy == "veo" else "grok")
    return {
        "provider_strategy": provider_strategy,
        "video_provider": video_provider,
        "video_model": concept.get("video_model") or get_profile_video_model(channel_id),
        "video_resolution": concept.get("video_resolution") or get_profile_video_resolution(channel_id),
        "audio_policy": str(
            concept.get("audio_policy") or get_profile_audio_policy(channel_id)
        ).strip().lower(),
        "intro_policy": str(
            concept.get("intro_policy") or get_profile_intro_policy(channel_id)
        ).strip().lower(),
        "anchor_policy": str(
            concept.get("anchor_policy") or get_profile_anchor_policy(channel_id)
        ).strip().lower(),
    }


def build_anchor_policy_instruction(anchor_policy: str) -> str:
    policy = (anchor_policy or "none").strip().lower()
    if policy == "recurring_character":
        return """
- RECURRING ANCHOR: keep the same main character design across the whole video. If a line can stay on the main character, keep them on screen instead of swapping to generic observers.
"""
    if policy == "recurring_pair":
        return """
- RECURRING ANCHOR: keep the same core pair across the whole video. Default to scenes that feature the pair together unless the narration explicitly isolates one character.
"""
    if policy == "recurring_host":
        return """
- RECURRING ANCHOR: keep the same host/presenter design across all host-led scenes. Prefer host-centered framing when the narration is explanatory.
"""
    if policy == "proof_props":
        return """
- RECURRING ANCHOR: keep recurring proof objects visible across scenes where possible — receipts, bills, price tags, calculators, charts, meters, or cash props.
"""
    return ""


async def run_pipeline(run_id: int, concept: dict):
    """Run the full video generation pipeline."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from packages.clients.workflow_state import (
        append_run_event,
        create_review_task,
        ensure_run_bundle,
        get_pending_review_task,
        resolve_review_task,
        update_concept_status,
        update_run_manifest,
    )

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    _log_engine = create_async_engine(db_url, pool_size=1, max_overflow=1)
    _pipeline_start = time.time()
    await ensure_run_bundle(
        run_id,
        concept=concept,
        channel_id=concept.get("channel_id"),
        pipeline_mode="default",
        stage="starting",
        status="running",
    )

    async def _update_step(step):
        """Update current_step and append to log. Use for major phase changes."""
        try:
            from datetime import datetime as _dt
            elapsed = int(time.time() - _pipeline_start)
            m, s = divmod(elapsed, 60)
            timestamp = _dt.now().strftime("%H:%M:%S")
            elapsed_str = f"{m}m{s:02d}s" if elapsed >= 1 else "cached"
            log_line = f"[{timestamp}] [{elapsed_str}] {step}"
            async with AsyncSession(_log_engine) as sess:
                await sess.execute(
                    text("""UPDATE content_runs
                        SET current_step = :step,
                            log_entries = CASE
                                WHEN log_entries IS NULL OR log_entries = '' OR log_entries = '[]'
                                THEN :line
                                ELSE log_entries || E'\n' || :line
                            END
                        WHERE id = :id"""),
                    {"step": step, "line": log_line, "id": run_id},
                )
                await sess.commit()
            await append_run_event(
                run_id,
                event_type="stage_started",
                message=step,
                stage=step,
                data={"log_line": log_line},
            )
            await update_run_manifest(run_id, {"stage": step, "last_log_line": log_line})
        except Exception as e:
            logger.warning("step update failed (non-fatal)", step=step, error=str(e)[:100])

    async def _log(msg):
        """Append a log line without changing current_step. Use for progress within a phase."""
        try:
            from datetime import datetime as _dt
            elapsed = int(time.time() - _pipeline_start)
            m, s = divmod(elapsed, 60)
            timestamp = _dt.now().strftime("%H:%M:%S")
            elapsed_str = f"{m}m{s:02d}s" if elapsed >= 1 else "cached"
            log_line = f"[{timestamp}] [{elapsed_str}]   {msg}"
            async with AsyncSession(_log_engine) as sess:
                await sess.execute(
                    text("""UPDATE content_runs
                        SET log_entries = CASE
                                WHEN log_entries IS NULL OR log_entries = '' OR log_entries = '[]'
                                THEN :line
                                ELSE log_entries || E'\n' || :line
                            END
                        WHERE id = :id"""),
                    {"line": log_line, "id": run_id},
                )
                await sess.commit()
            await append_run_event(
                run_id,
                event_type="log",
                message=msg,
                stage=None,
                data={"log_line": log_line},
            )
        except Exception:
            pass

    _pending_logs = []  # Thread-safe accumulator for sync log calls
    import threading
    _log_lock = threading.Lock()

    def _log_sync(msg):
        """Sync version of _log for use inside thread pool workers. Accumulates logs to flush later."""
        from datetime import datetime as _dt
        elapsed = int(time.time() - _pipeline_start)
        m, s = divmod(elapsed, 60)
        timestamp = _dt.now().strftime("%H:%M:%S")
        elapsed_str = f"{m}m{s:02d}s" if elapsed >= 1 else "cached"
        log_line = f"[{timestamp}] [{elapsed_str}]   {msg}"
        with _log_lock:
            _pending_logs.append(log_line)

    async def _flush_logs():
        """Flush accumulated sync logs to the database."""
        with _log_lock:
            if not _pending_logs:
                return
            lines = list(_pending_logs)
            _pending_logs.clear()
        try:
            combined = "\n".join(lines)
            async with AsyncSession(_log_engine) as sess:
                await sess.execute(
                    text("""UPDATE content_runs
                        SET log_entries = CASE
                                WHEN log_entries IS NULL OR log_entries = '' OR log_entries = '[]'
                                THEN :lines
                                ELSE log_entries || E'\n' || :lines
                            END
                        WHERE id = :id"""),
                    {"lines": combined, "id": run_id},
                )
                await sess.commit()
            for line in lines:
                await append_run_event(
                    run_id,
                    event_type="log",
                    message=line,
                    data={"log_line": line},
                )
        except Exception:
            pass

    try:
        output_dir = f"output/run_{run_id}"
        os.makedirs(output_dir, exist_ok=True)

        # Route to channel-specific builder if one exists
        from apps.orchestrator.channel_builders import get_channel_builder
        channel_id = concept.get("channel_id", 0)
        custom_builder = get_channel_builder(channel_id)
        if custom_builder:
            await custom_builder(run_id, concept, output_dir, _update_step, db_url)
            return

        # Route to narration-first pipeline (format_version 2 OR has scenes/narration)
        if concept.get("format_version") == 2 or concept.get("scenes") or concept.get("narration"):
            await _run_narration_first(run_id, concept, output_dir, _update_step, _log, _log_sync, _flush_logs, _pipeline_start, db_url)
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

        # 2. Generate visuals per beat — gpt-image-1.5 images + Grok video clips
        await _update_step("generating visuals")
        images_dir = os.path.join(output_dir, "images")
        clips_dir = os.path.join(output_dir, "clips")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(clips_dir, exist_ok=True)

        import base64
        from concurrent.futures import ThreadPoolExecutor
        from packages.clients.grok import generate_image as grok_gen_image
        from packages.clients.grok import generate_image_dalle

        # Generate all images in parallel first
        image_beats = [(i, b) for i, b in enumerate(beats) if b.get("type", "image") == "image"]
        veo_beats = [(i, b) for i, b in enumerate(beats) if b.get("type") == "veo"]
        grok_beats = [(i, b) for i, b in enumerate(beats) if b.get("type") in ("grok", "video")]  # treat legacy "video" as grok

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
                    if is_long_form:
                        # Landscape — Grok 2K is fine, gets scaled to 1920x1080
                        grok_gen_image(prompt=prompt, output_path=img_path)
                    else:
                        # Portrait/shorts — use gpt-image-1.5 at native 1024x1536
                        # to avoid quality loss from stretching/cropping Grok's 2K images
                        generate_image_dalle(prompt=prompt, output_path=img_path, size="1024x1536")
                    logger.info("image generated", beat=i, attempt=attempt, portrait=not is_long_form)
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
            with ThreadPoolExecutor(max_workers=8) as ex:
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

            with ThreadPoolExecutor(max_workers=8) as ex:
                auto_futures = [ex.submit(gen_auto_image, bi, ji, p) for bi, ji, p in auto_image_tasks]
                for f in auto_futures:
                    beat_idx, path = f.result()
                    if "images" not in beats[beat_idx]:
                        beats[beat_idx]["images"] = []
                    beats[beat_idx]["images"].append(path)
            logger.info("auto-split images generated", count=len(auto_image_tasks))

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
            # Pad LAST segment more so final narration isn't cut by xfade
            if i == len(beat_audio) - 1:
                dur += 0.6
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
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
                            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
             "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
        await _update_step("adding subtitles")
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

            # Subtitles only — no label overlays (AI generates all text in images)
            ass_path = os.path.join(output_dir, "subs.ass")
            _write_karaoke_ass(ass_path, all_words, None, is_long_form=is_long_form)

            ass_escaped = ass_path.replace(":", "\\:")
            cmd = [
                "ffmpeg", "-y", "-i", concat_path,
                "-vf", f"ass={ass_escaped}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
            "category": get_channel_category(channel_id),
        })

        # 7. Update DB — step + status + assets in one transaction
        engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
        async with AsyncSession(engine) as s:
            concept_id = (
                await s.execute(text("SELECT concept_id FROM content_runs WHERE id = :id"), {"id": run_id})
            ).scalar_one_or_none()
            await s.execute(
                text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :id"),
                {"id": run_id},
            )
            await s.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
                {"rid": run_id, "cid": channel_id, "type": "rendered_video",
                 "content": json.dumps({"path": final_path, "file_size_bytes": file_size})},
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
            if concept_id:
                await update_concept_status(concept_id, status="ready", latest_run_id=run_id, session=s)
            await s.commit()
        await engine.dispose()
        await update_run_manifest(run_id, {"status": "pending_review", "stage": "pending_review", "final_video": final_path})

        # Copy to channel folder with title as filename
        _copy_to_channel_folder(final_path, title, channel_id, db_url)
        logger.info("pipeline complete", run_id=run_id, path=final_path, size_mb=round(file_size/1024/1024, 1))

    except Exception as e:
        logger.error("pipeline failed", run_id=run_id, error=str(e)[:300])
        try:
            engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
            async with AsyncSession(engine) as s:
                concept_id = (
                    await s.execute(text("SELECT concept_id FROM content_runs WHERE id = :id"), {"id": run_id})
                ).scalar_one_or_none()
                await s.execute(
                    text("UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id"),
                    {"id": run_id, "err": str(e)[:500]},
                )
                if concept_id:
                    await update_concept_status(concept_id, status="failed", latest_run_id=run_id, session=s)
                await s.commit()
            await engine.dispose()
            await update_run_manifest(run_id, {"status": "failed", "error": str(e)[:500]})
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

        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000)
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
    channel_id = int(concept.get("channel_id", 14))
    runtime_policy = get_channel_runtime_policy(channel_id, concept)
    video_provider = str(runtime_policy["video_provider"] or "grok").strip().lower()
    video_model = runtime_policy["video_model"]
    video_resolution = runtime_policy["video_resolution"] or "720p"
    audio_policy = str(runtime_policy["audio_policy"] or "native_sfx").strip().lower()
    use_native_video_audio = audio_policy in {"native_sfx", "native_dialogue"}
    WIDTH, HEIGHT = SHORT_WIDTH, SHORT_HEIGHT

    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [images_dir, clips_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    from packages.clients.grok import generate_image as grok_gen_image, generate_video_async
    from packages.clients.veo import generate_video_async as veo_generate_video_async
    from apps.orchestrator.channel_builders.shared import get_veo_duration

    # 0. Build character reference descriptions for consistent characters
    character_descriptions = {}  # character_name -> text description
    unique_characters = set()
    for scene in scenes:
        chars = scene.get("characters", [])
        if isinstance(chars, str):
            chars = [chars]
        for c in chars:
            unique_characters.add(c)

    if unique_characters:
        await _update_step(f"fetching {len(unique_characters)} character references")
        ref_dir = os.path.join(output_dir, "character_refs")
        os.makedirs(ref_dir, exist_ok=True)

        GLOBAL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "character_cache")
        os.makedirs(GLOBAL_CACHE_DIR, exist_ok=True)

        for char_name in unique_characters:
            safe_name = char_name.replace(' ', '_').replace("'", "").lower()
            ref_path = os.path.join(ref_dir, f"{safe_name}.png")
            global_path = os.path.join(GLOBAL_CACHE_DIR, f"{safe_name}.png")

            # Check global cache → web search
            if not os.path.exists(ref_path):
                if os.path.exists(global_path):
                    import shutil
                    shutil.copy2(global_path, ref_path)
                    logger.info("character ref from cache", character=char_name)
                else:
                    import requests as _req
                    serper_key = os.getenv("SERPER_API_KEY")
                    if serper_key:
                        try:
                            resp = _req.post("https://google.serper.dev/images",
                                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                                json={"q": f"{char_name} full body character reference clear", "num": 10},
                                timeout=15)
                            for img in resp.json().get("images", []):
                                url = img.get("imageUrl", "")
                                if not url:
                                    continue
                                try:
                                    r = _req.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                                    is_image = r.content[:4] in [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'RIFF']
                                    if is_image and len(r.content) > 10000:
                                        with open(ref_path, "wb") as f:
                                            f.write(r.content)
                                        import shutil
                                        shutil.copy2(ref_path, global_path)
                                        logger.info("character ref downloaded", character=char_name)
                                        break
                                except Exception:
                                    continue
                        except Exception as e:
                            logger.warning("character ref search failed", character=char_name, error=str(e)[:100])

            # Describe the character with Claude Vision
            if os.path.exists(ref_path):
                try:
                    # Convert WebP to PNG if needed
                    with open(ref_path, "rb") as _check:
                        if _check.read(4) == b'RIFF':
                            png_path = ref_path + ".converted.png"
                            subprocess.run(["ffmpeg", "-y", "-i", ref_path, png_path],
                                capture_output=True, timeout=10)
                            if os.path.exists(png_path):
                                import shutil
                                shutil.move(png_path, ref_path)
                                # Update global cache too
                                shutil.copy2(ref_path, os.path.join(GLOBAL_CACHE_DIR, f"{safe_name}.png"))
                                logger.info("converted WebP to PNG", character=char_name)

                    import base64 as _b64ref
                    with open(ref_path, "rb") as rf:
                        ref_b64 = _b64ref.b64encode(rf.read()).decode()
                    import httpx
                    from anthropic import Anthropic
                    desc_client = Anthropic(http_client=httpx.Client(timeout=20))
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
                    logger.info("character described", character=char_name, description=desc[:100])
                except Exception as e:
                    logger.warning("character description failed", character=char_name, error=str(e)[:100])

    # 1. Generate images, then wait for approval, then animate
    await _update_step("generating scene images")
    segment_paths = []

    # --- PASS 1: Generate all images ---
    for i, scene in enumerate(scenes):
        img_path = os.path.join(images_dir, f"scene_{i}.png")
        clip_path = os.path.join(clips_dir, f"scene_{i}.mp4")
        seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")

        scene_prompt = scene.get("image_prompt", "")
        motion_prompt = scene.get("video_prompt", "subtle movement")
        duration = scene.get("duration", 5)

        # Build reference image URL from first character ref for this scene
        scene_chars = scene.get("characters", [])
        if isinstance(scene_chars, str):
            scene_chars = [scene_chars]
        scene_ref_url = None
        for char_name in scene_chars:
            safe_name = char_name.replace(' ', '_').replace("'", "").lower()
            char_ref_path = os.path.join(output_dir, "character_refs", f"{safe_name}.png")
            if os.path.exists(char_ref_path):
                with open(char_ref_path, "rb") as rf:
                    scene_ref_url = f"data:image/png;base64,{base64.b64encode(rf.read()).decode()}"
                logger.info("using character ref for image gen", character=char_name, scene=i)
                break  # Use first available ref

        # Text-to-video mode: skip image gen, generate video directly from prompt
        text_to_video = not scene_prompt

        if not text_to_video:
            # Generate image — edit from previous frame if chaining, otherwise fresh generation
            if not os.path.exists(img_path):
                import time as _scene_t
                _scene_start = _scene_t.time()
                img_size = "1536x1024" if concept.get("long_form") else "1024x1536"

                prev_last_frame = os.path.join(images_dir, f"scene_{i - 1}_lastframe.png") if i > 0 else None
                if scene.get("chain_from_previous") and prev_last_frame and os.path.exists(prev_last_frame):
                    await _update_step(f"generating scene {i + 1}/{len(scenes)} — editing previous frame")
                    from packages.clients.grok import edit_image_dalle_async
                    edit_prompt = f"Edit this image: {scene_prompt}. Keep the same art style and setting."
                    await edit_image_dalle_async(prompt=edit_prompt, input_image_path=prev_last_frame, output_path=img_path, size=img_size)
                else:
                    await _update_step(f"generating scene {i + 1}/{len(scenes)} — calling gpt-image-1.5")
                    from packages.clients.grok import generate_image_dalle_async
                    await generate_image_dalle_async(prompt=scene_prompt, output_path=img_path, size=img_size)
                await _update_step(f"scene {i + 1}/{len(scenes)} image done ({_scene_t.time()-_scene_start:.0f}s)")

    # --- APPROVAL GATE: wait for user to review images before animating ---
    # Skip if clips already exist (images were approved in a previous run that failed during animation)
    _existing_clips = [f for f in os.listdir(clips_dir) if f.endswith('.mp4')] if os.path.isdir(clips_dir) else []
    if _existing_clips:
        logger.info("skipping image approval — clips exist from previous run", count=len(_existing_clips))
    elif not should_skip_image_review(channel_id):
        all_images_exist = all(
            os.path.exists(os.path.join(images_dir, f"scene_{i}.png"))
            for i in range(len(scenes))
        )
        if all_images_exist:
            await _update_step("images ready for review")
            approval_file = os.path.join(output_dir, ".images_approved")
            deny_file = os.path.join(output_dir, ".images_denied")
            review_task_id = await create_review_task(
                run_id=run_id,
                kind="images",
                concept_id=concept.get("concept_id"),
                channel_id=channel_id,
                stage="images ready for review",
                payload={
                    "expected_images": len(scenes),
                    "images_dir": os.path.abspath(images_dir),
                    "image_names": [f"scene_{i}.png" for i in range(len(scenes))],
                },
            )
            await update_run_manifest(run_id, {"review_task_id": review_task_id, "stage": "images ready for review"})
            for _f in [approval_file, deny_file]:
                if os.path.exists(_f):
                    os.remove(_f)
            while True:
                await asyncio.sleep(3)
                if os.path.exists(approval_file):
                    logger.info("user approved images")
                    os.remove(approval_file)
                    await resolve_review_task(
                        run_id=run_id,
                        kind="images",
                        status="approved",
                        resolution={"source": "file_fallback"},
                    )
                    break
                if os.path.exists(deny_file):
                    logger.info("user denied images — stopping")
                    os.remove(deny_file)
                    await resolve_review_task(
                        run_id=run_id,
                        kind="images",
                        status="rejected",
                        resolution={"source": "file_fallback"},
                    )
                    raise RuntimeError("Images denied by user")
                pending_task = await get_pending_review_task(run_id, "images")
                if pending_task is None:
                    logger.info("image review resolved via review task")
                    break

    # --- PASS 2: Animate each scene ---
    for i, scene in enumerate(scenes):
        img_path = os.path.join(images_dir, f"scene_{i}.png")
        clip_path = os.path.join(clips_dir, f"scene_{i}.mp4")
        seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")
        scene_prompt = scene.get("image_prompt", "")
        motion_prompt = scene.get("video_prompt", "subtle movement")
        duration = scene.get("duration", 5)
        scene_chars = scene.get("characters", [])
        if isinstance(scene_chars, str):
            scene_chars = [scene_chars]
        scene_ref_url = None
        text_to_video = scene.get("text_to_video", False)

        # Animate
        if not os.path.exists(clip_path):
            img_b64 = None
            if not text_to_video:
                await _update_step(f"animating scene {i + 1}/{len(scenes)}")
                # Compress for Grok video upload
                compressed = img_path.replace(".png", "_hq.jpg")
                if not os.path.exists(compressed):
                    subprocess.run(["ffmpeg", "-y", "-i", img_path, "-q:v", "1", compressed],
                        capture_output=True, timeout=10)
                with open(compressed if os.path.exists(compressed) else img_path, "rb") as rf:
                    ext = "jpeg" if compressed and os.path.exists(compressed) else "png"
                    img_b64 = f"data:image/{ext};base64,{base64.b64encode(rf.read()).decode()}"
            else:
                await _update_step(f"generating scene {i + 1}/{len(scenes)} — text-to-video" + (" (with ref)" if scene_ref_url else ""))

            if video_provider == "veo":
                veo_kwargs = {
                    "prompt": motion_prompt,
                    "output_path": clip_path,
                    "model": video_model or "veo-3.1-lite-generate-001",
                    "duration_seconds": get_veo_duration(duration),
                    "aspect_ratio": "9:16",
                    "resolution": video_resolution,
                    "generate_audio": use_native_video_audio,
                    "timeout_seconds": 600,
                }
                if not text_to_video and img_path:
                    veo_kwargs["image_path"] = img_path
                await veo_generate_video_async(**veo_kwargs)
            else:
                await generate_video_async(
                    prompt=motion_prompt,
                    output_path=clip_path,
                    duration=min(duration, 10),
                    aspect_ratio="9:16",
                    image_url=img_b64,
                    reference_image_url=scene_ref_url if text_to_video else None,
                    resolution=video_resolution,
                )
            logger.info("scene animated", scene=i)

        # Extract last frame for seamless chaining to next scene
        last_frame_path = os.path.join(images_dir, f"scene_{i}_lastframe.png")
        if not os.path.exists(last_frame_path) and os.path.exists(clip_path):
            await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run([
                "ffmpeg", "-y", "-sseof", "-0.1", "-i", clip_path,
                "-frames:v", "1", last_frame_path,
            ], capture_output=True, timeout=10))
            if os.path.exists(last_frame_path):
                logger.info("extracted last frame for chaining", scene=i)

        # If next scene exists and wants to chain, set its image to this last frame
        if i + 1 < len(scenes):
            next_img_path = os.path.join(images_dir, f"scene_{i + 1}.png")
            next_scene = scenes[i + 1]
            if next_scene.get("chain_from_previous") and not os.path.exists(next_img_path) and os.path.exists(last_frame_path):
                import shutil as _shutil
                _shutil.copy2(last_frame_path, next_img_path)
                logger.info("chained last frame to next scene", from_scene=i, to_scene=i + 1)

        # Create segment — keep Grok native audio (run in executor to avoid blocking)
        # Do not pad the final segment; the extra cloned tail reads like a repeated beat.
        seg_duration = duration
        def _render_scene_segment(d=seg_duration):
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", clip_path,
                "-t", str(d),
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
            ]
            if audio_policy == "none":
                cmd.extend(["-an", seg_path])
            else:
                cmd.extend(["-map", "0:v:0", "-map", "0:a?", "-c:a", "aac", "-ar", "44100", "-b:a", "192k", seg_path])
            return subprocess.run(cmd, capture_output=True, timeout=120)

        await asyncio.get_event_loop().run_in_executor(None, _render_scene_segment)

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

    # Use crossfade transitions between scenes (0.5s each)
    if len(segment_paths) >= 2:
        # Build xfade filter chain for video and acrossfade for audio
        fade_dur = 0.5
        inputs = " ".join(f"-i '{os.path.abspath(s)}'" for s in segment_paths)

        # Video xfade chain
        vfilters = []
        afilters = []
        n = len(segment_paths)

        # Get durations of each segment
        seg_durations = []
        for sp in segment_paths:
            d = _get_duration(sp)
            seg_durations.append(d)

        if n == 2:
            offset = seg_durations[0] - fade_dur
            vfilters.append(f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset}[vout]")
            afilters.append(f"[0:a][1:a]acrossfade=d={fade_dur}[aout]")
            map_v, map_a = "[vout]", "[aout]"
        elif n == 3:
            offset1 = seg_durations[0] - fade_dur
            vfilters.append(f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset1}[v01]")
            offset2 = offset1 + seg_durations[1] - fade_dur
            vfilters.append(f"[v01][2:v]xfade=transition=fade:duration={fade_dur}:offset={offset2}[vout]")
            afilters.append(f"[0:a][1:a]acrossfade=d={fade_dur}[a01]")
            afilters.append(f"[a01][2:a]acrossfade=d={fade_dur}[aout]")
            map_v, map_a = "[vout]", "[aout]"
        else:
            # 4+ scenes — build chain dynamically
            prev_v = "0:v"
            prev_a = "0:a"
            cumulative_offset = 0
            for idx in range(1, n):
                cumulative_offset += seg_durations[idx - 1] - fade_dur
                out_v = "vout" if idx == n - 1 else f"v{idx:02d}"
                out_a = "aout" if idx == n - 1 else f"a{idx:02d}"
                vfilters.append(f"[{prev_v}][{idx}:v]xfade=transition=fade:duration={fade_dur}:offset={cumulative_offset}[{out_v}]")
                afilters.append(f"[{prev_a}][{idx}:a]acrossfade=d={fade_dur}[{out_a}]")
                prev_v = out_v
                prev_a = out_a
            map_v, map_a = f"[{prev_v}]", f"[{prev_a}]"

        filter_complex = ";".join(vfilters + afilters)
        xfade_cmd = f"ffmpeg -y {inputs} -filter_complex \"{filter_complex}\" -map \"{map_v}\" -map \"{map_a}\" -c:v libx264 -preset fast -crf 23 -pix_fmt yuv420p -c:a aac -ar 44100 -b:a 192k -movflags +faststart {concat_path}"

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(xfade_cmd, shell=True, capture_output=True, text=True, timeout=300)
        )

        if result.returncode != 0 or not os.path.exists(concat_path):
            logger.warning("xfade failed, falling back to hard cut", stderr=result.stderr[:200] if result.stderr else "")
            # Fallback to simple concat
            await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
                concat_path,
            ], capture_output=True, timeout=300))
    else:
        await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
            concat_path,
        ], capture_output=True, timeout=300))

    # 3. Add background music — use mood folder or concept-specified mood
    import random as _random
    music_base = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")
    # Background music disabled — Grok SFX handles audio atmosphere
    bg_music_path = None

    if False:  # music disabled
        video_dur = _get_duration(concat_path)
        with_music = os.path.join(output_dir, "with_music.mp4")
        cmd = f'ffmpeg -y -i {concat_path} -stream_loop -1 -i {bg_music_path} -filter_complex "[1:a]volume=0.15,atrim=0:{video_dur}[bgm];[0:a][bgm]amix=inputs=2:duration=first:weights=3 1,loudnorm=I=-16:TP=-1.5:LRA=11[out]" -map 0:v -map "[out]" -c:v copy -c:a aac -ar 44100 -b:a 192k -movflags +faststart {with_music}'
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        )
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
        "category": get_channel_category(channel_id),
    }
    metadata = json.dumps(metadata_dict)

    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    async with AsyncSession(engine) as s:
        concept_id = (
            await s.execute(text("SELECT concept_id FROM content_runs WHERE id = :id"), {"id": run_id})
        ).scalar_one_or_none()
        await s.execute(
            text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await s.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": "rendered_video",
             "content": json.dumps({"path": final_path, "file_size_bytes": file_size})},
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
        if concept_id:
            await update_concept_status(concept_id, status="ready", latest_run_id=run_id, session=s)
        await s.commit()
    await engine.dispose()
    await update_run_manifest(run_id, {"status": "pending_review", "stage": "pending_review", "final_video": final_path})

    _copy_to_channel_folder(final_path, title, channel_id, db_url)
    logger.info("no-narration pipeline complete", run_id=run_id, path=final_path,
                scenes=len(scenes), size_mb=round(file_size/1024/1024, 1))


async def _run_narration_first(run_id: int, concept: dict, output_dir: str, _update_step, _log, _log_sync, _flush_logs, _pipeline_start, db_url: str):
    """Narration-first pipeline: generate audio → plan one visual per line → assemble.

    Each narration line gets exactly one visual. The visual's duration matches the audio
    exactly — no timestamp slicing, no drift, perfect sync.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text
    from packages.clients.workflow_state import (
        create_review_task,
        get_pending_review_task,
        resolve_review_task,
        update_concept_status,
        update_run_manifest,
    )
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
    channel_id = int(concept.get("channel_id", 14))
    runtime_policy = get_channel_runtime_policy(channel_id, concept)
    video_provider = str(runtime_policy["video_provider"] or "grok").strip().lower()
    video_model = runtime_policy["video_model"]
    video_resolution = runtime_policy["video_resolution"] or ("1080p" if is_long_form else "720p")
    anchor_policy = str(runtime_policy["anchor_policy"] or "none").strip().lower()
    anchor_policy_block = build_anchor_policy_instruction(anchor_policy)

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

    # 1. Generate narration per line — PARALLEL
    await _update_step(f"generating narration — {len(narration_lines)} lines")
    from packages.clients.elevenlabs import generate_speech
    from concurrent.futures import ThreadPoolExecutor

    _narr_done = 0
    _narr_total = len(narration_lines)

    def _gen_narration(i, line):
        nonlocal _narr_done
        narr_path = os.path.join(narr_dir, f"line_{i}.mp3")
        cached = os.path.exists(narr_path)
        if not cached:
            import time as _t
            # Pass adjacent lines for natural intonation continuity
            prev_text = narration_lines[i - 1] if i > 0 else None
            next_text = narration_lines[i + 1] if i < len(narration_lines) - 1 else None
            for attempt in range(3):
                try:
                    generate_speech(text=line, voice=voice_id, output_path=narr_path, speed=narration_speed, previous_text=prev_text, next_text=next_text)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"ElevenLabs failed after 3 attempts for line {i}: {e}") from e
                    _log_sync(f"narration line {i} retry {attempt+1} — {str(e)[:80]}")
                    _t.sleep(5 * (attempt + 1))
        dur = _get_duration(narr_path)
        _narr_done += 1
        _log_sync(f"narration {_narr_done}/{_narr_total} done ({dur:.1f}s){' [cached]' if cached else ''}")
        return {"index": i, "path": narr_path, "duration": dur, "text": line}

    loop = asyncio.get_event_loop()
    narr_tasks = [
        loop.run_in_executor(None, _gen_narration, i, line)
        for i, line in enumerate(narration_lines)
    ]
    line_audio = await asyncio.gather(*narr_tasks)
    await _flush_logs()
    line_audio = sorted(line_audio, key=lambda a: a["index"])

    # Trim leading silence from first narration line — shorts only (long-form can breathe)
    if not is_long_form:
        first_audio = line_audio[0]["path"]
        trimmed = first_audio.replace(".mp3", "_trimmed.mp3")
        if not os.path.exists(trimmed):
            trim_result = subprocess.run([
                "ffmpeg", "-y", "-i", first_audio,
                "-af", "silenceremove=start_periods=1:start_threshold=-40dB:start_duration=0.05",
                trimmed,
            ], capture_output=True, text=True, timeout=15)
            if trim_result.returncode == 0 and os.path.exists(trimmed):
                os.replace(trimmed, first_audio)
                line_audio[0]["duration"] = _get_duration(first_audio)

    total_duration = sum(a["duration"] for a in line_audio)
    await _update_step(f"narration done — {len(line_audio)} lines, {total_duration:.0f}s total")

    # 2. Claude visual planning — one visual per narration line
    await _update_step("planning visuals — calling Claude")
    from packages.clients.claude import generate

    engine = create_async_engine(db_url, pool_size=1, max_overflow=0)
    async with AsyncSession(engine) as s:
        ch_row = await s.execute(text("SELECT name, niche FROM channels WHERE id = :id"), {"id": channel_id})
        ch = ch_row.fetchone()
        channel_name = ch[0] if ch else "Unknown"
        niche = ch[1] if ch else "general"
    await engine.dispose()

    # Check for cached visual plan from a previous run
    visual_plan_path = os.path.join(output_dir, "visual_plan.json")
    if os.path.exists(visual_plan_path):
        try:
            with open(visual_plan_path) as f:
                cached_plan = json.load(f)
            cached_visuals = cached_plan.get("visuals", [])
            if len(cached_visuals) >= len(line_audio):
                visuals = cached_visuals[:len(line_audio)]
                await _update_step(f"visual plan loaded from cache — {len(visuals)} visuals")
                await _log("skipped visual planning (cached from previous run)")
            else:
                cached_plan = None  # Wrong size, regenerate
        except Exception:
            cached_plan = None
    else:
        cached_plan = None

    if cached_plan is None:
        pass  # Fall through to visual planning below

    # Use batched visual planning for long-form, single call for shorts
    if cached_plan is None and is_long_form and len(line_audio) > 20:
        visuals = await _batched_visual_planning(
            line_audio, title, channel_name, niche, is_long_form, output_dir,
            channel_id=channel_id,
        )
    elif cached_plan is None:
        # Build the narration block with durations
        narr_block = "\n".join(
            f"  Line {a['index']} ({a['duration']:.1f}s): \"{a['text']}\""
            for a in line_audio
        )

        aspect = "16:9 landscape" if is_long_form else "9:16 vertical portrait"
        art_style = concept.get("art_style") or get_channel_art_style(channel_id)
        visual_system = f"""You write image prompts for YouTube videos. Channel: "{channel_name}" ({niche}).

One prompt per narration line. Every prompt starts with "{art_style}"

CRITICAL RULE: ALL images must be ILLUSTRATED, never photorealistic. No photographs, no 3D renders, no CGI. Every image should look hand-drawn, painted, or stylized. If the art style says "illustration" or "cartoon" — follow that strictly.

RULES:
- ONE scene per prompt. 1-2 sentences max.
- Each visual must LITERALLY DEPICT what the narrator is saying at that moment. NOT a thematic mood image — the ACTUAL thing being described. If they say "your skin would peel off" show skin peeling. If they say "a coin worth $7 million" show a specific coin. The viewer should understand the video on mute.
- Think like a comedy editor — exaggerate everything. Absurd scale, extreme reactions, visual gags. The image should be funny or dramatic on its own even without narration.
- EVERY scene must look like it belongs IN the universe of the content. Think about what a real fan would expect to see:
  - For League of Legends: the scene should look like the actual game — characters as their in-game 3D models on Summoner's Rift with the game's lanes, turrets, jungle camps, river, brushes. When describing gameplay scenes, say "in the art style of League of Legends in-game graphics" NOT "splash art". Use splash art style only for dramatic character reveals or title cards.
  - For Pokemon: scenes should look like the actual Pokemon games — characters as 3D models in game environments (routes, tall grass, Pokemon Centers, gyms). Say "in the art style of Pokemon Scarlet/Violet" for gameplay scenes. Use concept art style only for dramatic reveals.
  - For anime: scenes should look like paused frames from the actual anime episode — with the show's backgrounds, mid-action poses, dramatic camera angles. Say "in the visual style of [show name] anime frames." NOT fan art, NOT static character poses.
  - For mythology: scenes should look like classical paintings of mythological events.
  - For true crime: scenes should look like graphic novel recreations of real events.
  GOOD: "Amumu from League of Legends standing next to the Blue Buff camp on Summoner's Rift, crying while his team pings him"
  BAD: "Amumu standing in a dark forest looking sad" (this is generic fantasy, not League of Legends)
- NEVER use generic descriptions like "a champion", "a character", "a jungler". ALWAYS pick a SPECIFIC named character.
- For franchise content: EVERY image must name a specific character AND place them in a recognizable location from that franchise.
- NEVER use in-game jargon without the franchise name. "League of Legends jungle camp" not just "jungle camp". "Pokemon evolution" not just "evolution".
- The image generator CANNOT draw: UIs, screens, menus, websites, game interfaces, text-heavy scenes, split panels
- The image generator CANNOT understand: game jargon like "skins", "RP", "champion icons", "mana bar", "capsules"
- TRANSLATE ALL GAME JARGON into literal visual descriptions for the image generator. It does NOT know gaming terms:
  BAD: "Yasuo knocking up the enemy team" (generator will show something inappropriate)
  GOOD: "Yasuo from League of Legends launching enemies into the air with a tornado"
  BAD: "Yasuo diving under tower" (generator doesn't know what a tower is in LoL)
  GOOD: "Yasuo from League of Legends charging past a stone defense turret recklessly"
  BAD: "feeding the enemy team" (generator will show literal food)
  GOOD: "Yasuo from League of Legends lying defeated on the ground while enemy champions celebrate"
  Always describe the VISUAL RESULT of the game action, never the game mechanic itself.
- If narration mentions a screen/store/interface, show a named character reacting instead
- Never show generic office workers when the topic is about a specific character/thing

BORING: "A Riot Games employee handing a gift box to a player"
FUNNY: "A Riot Games employee on his knees begging forgiveness while a smug gamer sits on a throne of gold coins"

FIRST FRAME IS EVERYTHING (the hook):
- Line 1's visual is the FIRST thing the viewer sees. It must STOP THE SCROLL in under 1 second.
- Make it the most dramatic, shocking, or visually striking image of the whole video. NOT a title card. NOT a calm establishing shot. The most extreme, eye-catching moment.
- GOOD first frame: A massive explosion of rabbits charging at a terrified Napoleon. (dramatic, unexpected, makes you stay)
- BAD first frame: A portrait of Napoleon standing calmly. (boring, looks like a history lesson, instant swipe)
- The video_prompt for line 1 should have immediate motion — camera zoom, dramatic reveal, something moving from second 0. No slow fades.

SAFETY: The image generator will BLOCK prompts with combat/violence words. NEVER use: battle, fight, attack, fierce, intimidating, terrified, horror, destroy, death, kill, weapon, blood, evil, menacing, threatening, war. Instead show characters posing, reacting, celebrating, looking confused — not fighting.

SPEAKING/DIALOGUE (CRITICAL — violations look terrible):
- When 2+ characters are in the scene: ONLY ONE character may speak/have mouth movement. The other characters must be reacting (nodding, gesturing, looking confused) — NOT talking. Specify clearly WHICH character is speaking in the video_prompt: "the mom character speaks while the teen stares in disbelief" NOT "both characters talk."
- The AI video generator animates ALL mouths if you say "characters talking" — you MUST specify which single character's mouth moves.
- Make sure the speaking character matches who the text/narration attributes the dialogue to. If the text says "mom:" then the mom character speaks, not the teen.
- Character gender must match: "your mom" = woman, "your dad" = man, "the teacher" = match context.
{anchor_policy_block}

TYPES:
- "grok": animated video clip. DEFAULT — use for almost every line. The image is generated first, then animated.
  "video_prompt": describe the DRAMATIC END STATE the scene transforms into, plus SOUND EFFECTS. The video generator animates by cutting between the starting image and the end state you describe — like comic book panels. It CANNOT do smooth continuous animation. ONE big dramatic change works best.
  GOOD: "The person collapses face-first onto the keyboard, energy cans scatter and fall to the floor, monitor shows blue error screen. Loud crash sound."
  GOOD: "The character jumps up from chair with arms raised in victory, headset flies off, drink spills everywhere. Loud celebration cheer."
  GOOD: "The villain is now lying defeated on the ground, the hero stands over him arms crossed. Massive impact boom sound."
  BAD: "camera slowly pulls back" (boring zoom on still image — nothing actually moves)
  BAD: "character nods slightly" (too subtle — generator ignores small movements)
  BAD: "person clicks mouse rapidly" (invisible micro-action — generator cannot do this)
  BAD: "camera zooms into face" (just a zoom — describe what the FACE CHANGES TO instead)
  RULE: The image prompt is the BEFORE. The video_prompt describes the AFTER. The bigger and more dramatic the change between them, the better the animation. Think: standing→collapsed, calm→explosion, together→scattered.
- "image": static still. Use for things that should not move: charts, numbers, graphs, documents, text displays, code snippets, diagrams explaining HOW something works. When the narration is explaining a specific technical detail (a bug, a formula, a mechanism), use an "image" with a clear diagram showing it — the viewer needs to SEE what's being explained, not just hear it.
- "diagram": infographic or data visualization with text. Use when the narration presents data, comparisons, or step-by-step explanations that need text labels.

IMPORTANT — tag ANY recognizable person, character, animal, or entity with "character": "name" AND "consistent_character": true on EVERY line they appear in. This includes:
- Game characters: "Amumu from League of Legends"
- Real people: "Donald Trump", "Elon Musk", "Taylor Swift"
- Mythological figures: "Zeus", "Thor"
- Animals by species: "mantis shrimp", "red panda"
- Anime characters: "Gojo from Jujutsu Kaisen"
The pipeline will search the web for their real appearance and use it as a reference image. If you DON'T tag them, the AI will generate a generic person/character that looks nothing like the real thing.
If the narration mentions a number/rank (like "#5", "Number 3"), bake the number directly into the image prompt so gpt-image generates it as part of the scene. Do NOT use a "label" field — all text must be generated by the AI image model, not overlaid by the pipeline.

Aspect ratio: {aspect}

OUTPUT — JSON:
{{
  "visuals": [
    {{"type": "grok", "prompt": "{art_style} Gangplank from League of Legends buried in gold coins, looking shocked", "video_prompt": "coins rain down burying him, metallic clinking sounds and a heavy thud", "character": "Gangplank", "consistent_character": true}},
    {{"type": "image", "prompt": "{art_style} A gamer holding a single penny with a huge grin"}},
    ...
  ]
}}

Return exactly {len(line_audio)} visuals — one per narration line. Order matches narration order. Each visual should show a DIFFERENT scene or angle — never the same pose twice even for the same character.
Return ONLY valid JSON, no markdown."""

        # VS channels get a forced title card instruction
        from packages.prompts.concept_drafts import VS_CHANNELS, RANKING_CHANNELS
        vs_visual_block = ""
        if channel_id in VS_CHANNELS:
            vs_visual_block = """
VS CHANNEL — MANDATORY STRUCTURE:
- Line 1 visual MUST be a dramatic split-screen VS title card: both characters facing each other from opposite sides, "VS" energy between them. Like a fighting game character select screen or UFC promo poster. Tag BOTH characters with consistent_character: true.
- Middle lines: show each fighter's signature ability or most impressive moment. Make it look like the actual fight is happening.
- Final line: show the WINNER in a victory pose, the loser defeated. Make it obvious who won.
"""

        ranking_visual_block = ""
        if channel_id in RANKING_CHANNELS:
            ranking_visual_block = """
RANKING CHANNEL — MANDATORY STRUCTURE:
Each narration line gets ONE visual. The narration drives the structure — the visuals just illustrate it. Do NOT add extra number card scenes.

- Title line visual: The image itself should show bold text with the ranking title (e.g. "TOP 5 MOST BROKEN ABILITIES") baked into the image by gpt-image. Dramatic background related to the topic.
- Number lines (e.g. "Number 5: X"): The image shows the thing being ranked in action, with a large bold number baked into the corner of the image by gpt-image (e.g. a big "5" in the corner). Do NOT make separate number card scenes — the number is part of the image.
- Use the art style that matches each entry's world — anime for anime, game art for games, cinematic for movies.
- #1 should be the most dramatic image — bigger, bolder.
- Do NOT overlay text via the pipeline — ALL text must be baked into the image prompt for gpt-image to generate.
- Do NOT use the "label" field — bake all text directly into the image prompt.
"""

        visual_user = f"""Plan visuals for "{title}"
{vs_visual_block}{ranking_visual_block}
NARRATION LINES WITH DURATIONS:
{narr_block}

Total: {total_duration:.1f}s, {len(line_audio)} lines

One visual per line. Each visual must LITERALLY SHOW what the narrator is describing — not just look thematically cool.

CRITICAL: The viewer should be able to understand the video on MUTE just from the visuals. If the narrator says "your body would stretch like spaghetti" — show a body stretching into a long thin strand, NOT a generic swirling black hole. If the narrator says "light bends around the event horizon" — show light rays curving around a sphere, NOT just a pretty space scene. Every image must ILLUSTRATE the specific concept being explained, like a diagram or demonstration, not just set the mood."""

        # Claude visual planning — run in executor to avoid blocking event loop
        await _update_step("calling claude for visual plan")
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: generate(prompt=visual_user, system=visual_system, model="claude-sonnet-4-6", max_tokens=4000)
        )
        await _log("claude visual plan response received")
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

    n_grok = sum(1 for v in visuals if v["type"] == "grok")
    n_image = sum(1 for v in visuals if v["type"] == "image")
    n_diagram = sum(1 for v in visuals if v["type"] == "diagram")
    logger.info("visual plan complete", visuals=len(visuals), grok=n_grok, image=n_image, diagram=n_diagram)
    await _update_step(f"visual plan done — {n_grok} videos, {n_image} images, {n_diagram} diagrams")

    # 3. Generate visuals
    parts = []
    if n_image: parts.append(f"{n_image} images")
    if n_diagram: parts.append(f"{n_diagram} diagrams")
    if n_grok: parts.append(f"{n_grok} video clips")
    await _update_step(f"generating {', '.join(parts)}")
    art_style = get_channel_art_style(channel_id)
    from packages.clients.grok import generate_image as grok_gen_image
    from packages.clients.grok import generate_image_dalle as dalle_gen_image
    from packages.clients.grok import generate_video_async as grok_generate, extend_video_async as grok_extend
    from packages.clients.veo import generate_video_async as veo_generate_video_async
    from apps.orchestrator.channel_builders.shared import get_veo_duration

    from packages.clients.grok import generate_image_dalle_async

    # Image size based on format
    _img_size = "1536x1024" if is_long_form else "1024x1536"

    async def _gen_video_image_async(prompt, output_path):
        """Generate image for video clips — fully async."""
        return await generate_image_dalle_async(prompt=prompt, output_path=output_path, size=_img_size)

    async def _gen_still_image_async(prompt, output_path, size=None):
        """Generate still image — fully async."""
        return await generate_image_dalle_async(prompt=prompt, output_path=output_path, size=size or _img_size)

    # Sync wrappers
    def _gen_video_image(prompt, output_path, reference_image_url=None):
        return dalle_gen_image(prompt=prompt, output_path=output_path, size=_img_size)

    def _gen_still_image(prompt, output_path, size=None):
        return dalle_gen_image(prompt=prompt, output_path=output_path, size=size or _img_size)

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

        def _search_character_image(char_name, save_path):
            """Search for a clear reference image using Serper.dev image search."""
            import requests as _requests

            serper_key = os.getenv("SERPER_API_KEY")
            if not serper_key:
                logger.warning("SERPER_API_KEY not set, skipping web image search")
                return False

            try:
                query = f"{char_name} full body character reference clear"
                resp = _requests.post("https://google.serper.dev/images",
                    headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                    json={"q": query, "num": 10},
                    timeout=15,
                )
                images = resp.json().get("images", [])

                for img in images:
                    url = img.get("imageUrl", "")
                    if not url:
                        continue
                    try:
                        r = _requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                        # Verify it's actually an image by checking magic bytes
                        is_image = r.content[:4] in [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'RIFF']
                        if is_image and len(r.content) > 10000:
                            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                            # Convert WebP to PNG if needed
                            if r.content[:4] == b'RIFF':
                                tmp = save_path + ".webp"
                                with open(tmp, "wb") as f:
                                    f.write(r.content)
                                subprocess.run(["ffmpeg", "-y", "-i", tmp, save_path], capture_output=True, timeout=10)
                                os.remove(tmp)
                            else:
                                with open(save_path, "wb") as f:
                                    f.write(r.content)
                            logger.info("character ref downloaded via Serper", character=char_name,
                                       url=url[:80], size=len(r.content))
                            return True
                    except Exception:
                        continue

                logger.warning("Serper found no downloadable image", character=char_name)
                return False

            except Exception as e:
                logger.warning("Serper image search failed", character=char_name, error=str(e)[:150])
                return False

        # Global character cache — search once, reuse forever
        GLOBAL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "character_cache")
        os.makedirs(GLOBAL_CACHE_DIR, exist_ok=True)

        # Get character refs: check global cache → web search → AI generation
        async def _gen_char_ref(char_name):
            ref_path = os.path.join(ref_dir, f"{char_name.replace(' ', '_')}.png")
            safe_name = char_name.replace(' ', '_').replace("'", "").lower()
            global_path = os.path.join(GLOBAL_CACHE_DIR, f"{safe_name}.png")

            if not os.path.exists(ref_path):
                # Check global cache first
                if os.path.exists(global_path):
                    import shutil
                    shutil.copy2(global_path, ref_path)
                    await _log(f"character ref '{char_name}' — from global cache")
                else:
                    # Web search
                    found = await asyncio.get_event_loop().run_in_executor(
                        None, lambda cn=char_name, sp=ref_path: _search_character_image(cn, sp)
                    )
                    if found:
                        # Save to global cache for future runs
                        import shutil
                        shutil.copy2(ref_path, global_path)
                        await _log(f"character ref '{char_name}' — downloaded from web (cached globally)")
                    else:
                        # Fall back to AI generation
                        await _log(f"character ref '{char_name}' — web search failed, generating with AI instead")
                    ref_prompt = f"{art_style} Family-friendly full body portrait of {char_name}, facing the viewer, simple background, character centered."
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda p=ref_prompt, o=ref_path: _gen_video_image(prompt=p, output_path=o)
                    )
            return char_name, ref_path

        char_results = await asyncio.gather(*[_gen_char_ref(cn) for cn in unique_characters])

        def _describe_character(char_name, ref_path):
            """Describe a character from its reference image using Claude Vision."""
            try:
                import base64 as _b64ref
                with open(ref_path, "rb") as rf:
                    ref_b64 = _b64ref.b64encode(rf.read()).decode()
                import httpx
                from anthropic import Anthropic
                desc_client = Anthropic(http_client=httpx.Client(timeout=20))
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
                return desc_resp.content[0].text.strip()
            except Exception:
                return None

        # Describe all characters in parallel
        desc_tasks = []
        for char_name, ref_path in char_results:
            if os.path.exists(ref_path):
                desc_tasks.append((char_name, ref_path))

        # Character description via Claude Vision disabled — causes hangs and is not essential
        # The character reference image is still used for visual consistency

        for char_name, ref_path in char_results:
            if not os.path.exists(ref_path):
                continue

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

        _img_done = 0

        def _gen_img_validated(i):
            nonlocal _img_done
            p = os.path.join(images_dir, f"line_{i}.png")
            if os.path.exists(p):
                char_name = visuals[i].get("character")
                if char_name and char_name not in character_refs:
                    import base64 as _b64
                    with open(p, "rb") as rf:
                        character_refs[char_name] = f"data:image/png;base64,{_b64.b64encode(rf.read()).decode()}"
                _img_done += 1
                _log_sync(f"image {_img_done}/{len(image_indices)} line {i} [cached]")
                return i, p

            narr_text = line_audio[i]["text"]
            prompt = visuals[i].get("prompt") or visuals[i].get("image_prompt", "")
            char_name = visuals[i].get("character")

            # Inject character description for visual consistency
            if char_name and char_name in character_descriptions:
                char_desc = character_descriptions[char_name]
                # Replace generic character name with specific description
                prompt = prompt + f" The character {char_name} looks like: {char_desc}"

            # Generate image (pass character reference for consistency)
            ref_url = character_refs.get(char_name, {}).get("b64") if char_name else None
            for attempt in range(5):
                try:
                    _gen_video_image(prompt=prompt, output_path=p, reference_image_url=ref_url)
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

            _img_done += 1
            _log_sync(f"image {_img_done}/{len(image_indices)} line {i} generated")

            return i, p

        # Character refs already generated above — all images can go in parallel
        img_loop = asyncio.get_event_loop()
        img_results = await asyncio.gather(*[
            img_loop.run_in_executor(None, _gen_img_validated, i) for i in image_indices
        ])
        await _flush_logs()
        for i, path in img_results:
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
                        size=_img_size,
                        quality="medium",
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

        diag_loop = asyncio.get_event_loop()
        diag_results = await asyncio.gather(*[
            diag_loop.run_in_executor(None, _gen_diagram, i) for i in diagram_indices
        ])
        for i, path in diag_results:
            visual_paths[i] = {"type": "image", "path": path}
        logger.info("diagrams generated", count=len(diagram_indices))

    # Generate grok video clips
    if grok_indices:
        aspect_ratio = "16:9" if is_long_form else "9:16"
        needs_consistency = video_provider == "grok" and any(visuals[i].get("consistent_character") for i in grok_indices)


        async def _gen_animated_clip_with_retries(i, max_attempts=3):
            """Generate an animated clip: image first, then animate.

            1. Generate image with detailed scene prompt
            2. Animate image to video with short motion-only prompt
            Grok already has the image as context, so the video prompt
            just needs to describe motion, camera movement, and mood.
            """
            clip_path = os.path.join(clips_dir, f"line_{i}.mp4")
            if os.path.exists(clip_path):
                await _log(f"{video_provider} clip line {i} [cached]")
                return i, clip_path
            dur = max(1, min(int(line_audio[i]["duration"]) + 1, 10))

            # Step 1: Generate the image
            await _log(f"{video_provider} clip line {i} — calling gpt-image-1.5 ({dur}s target)")
            img_path = os.path.join(images_dir, f"line_{i}.png")
            if not os.path.exists(img_path):
                _prompt = visuals[i].get("prompt") or visuals[i].get("image_prompt", "")
                try:
                    import time as _img_t
                    _img_start = _img_t.time()
                    await _gen_video_image_async(prompt=_prompt, output_path=img_path)
                    await _log(f"{video_provider} clip line {i} — image generated ({_img_t.time()-_img_start:.0f}s)")
                except Exception as img_err:
                    await _log(f"{video_provider} clip line {i} — image FAILED: {str(img_err)[:150]}")
                    raise

                if not os.path.exists(img_path):
                    raise RuntimeError(f"Image generation produced no file for line {i}: {img_path}")

            # Pass image to Grok video — Grok handles aspect ratio framing internally
            # Compress to high-quality JPEG to reduce upload size (2.5MB PNG → ~300KB JPEG)
            img_for_video = img_path.replace(".png", "_hq.jpg")
            if not os.path.exists(img_for_video):
                subprocess.run(["ffmpeg", "-y", "-i", img_path, "-q:v", "1", img_for_video],
                               capture_output=True, timeout=10)
            source = img_for_video if os.path.exists(img_for_video) else img_path
            with open(source, "rb") as rf:
                ext = "jpeg" if source.endswith(".jpg") else "png"
                img_data_url = f"data:image/{ext};base64,{base64.b64encode(rf.read()).decode()}"

            # Step 2: Animate with Grok video
            motion_prompt = visuals[i].get("video_prompt", "Slow cinematic movement, dramatic mood")
            await _log(f"{video_provider} clip line {i} — animating image to video")

            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        await asyncio.sleep(5 * attempt)
                        await _log(f"{video_provider} clip line {i} — retry {attempt}")
                    if video_provider == "veo":
                        await veo_generate_video_async(
                            prompt=motion_prompt,
                            output_path=clip_path,
                            model=video_model or "veo-3.1-lite-generate-001",
                            duration_seconds=get_veo_duration(dur),
                            aspect_ratio=aspect_ratio,
                            resolution=video_resolution,
                            image_path=img_path,
                            timeout_seconds=600,
                        )
                    else:
                        async def _grok_progress(progress, elapsed, _i=i):
                            await _log(f"grok clip line {_i} — {progress}% ({elapsed}s)")

                        await grok_generate(
                            prompt=motion_prompt,
                            output_path=clip_path, duration=dur, aspect_ratio=aspect_ratio,
                            image_url=img_data_url,
                            resolution=video_resolution,
                            progress_callback=_grok_progress,
                        )

                    await _log(f"{video_provider} clip line {i} — done")
                    return i, clip_path
                except Exception as e:
                    if attempt == max_attempts - 1:
                        await _log(f"{video_provider} clip line {i} — FAILED after {max_attempts} attempts: {str(e)[:100]}")
                        raise RuntimeError(f"{video_provider} video failed for line {i} after {max_attempts} attempts: {e}") from e
                    await _log(f"{video_provider} clip line {i} — attempt {attempt} failed: {str(e)[:80]}")

        # If consistency, generate first for ref frame
        if needs_consistency:
            first_gi = grok_indices[0]
            first_clip = os.path.join(clips_dir, f"line_{first_gi}.mp4")
            dur = max(1, min(int(line_audio[first_gi]["duration"]) + 1, 10))

            # Generate image first, then animate
            first_img = os.path.join(images_dir, f"line_{first_gi}.png")
            if not os.path.exists(first_img):
                await _gen_video_image_async(prompt=visuals[first_gi]["prompt"], output_path=first_img)
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
                        resolution=video_resolution,
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        raise RuntimeError(f"Grok failed on first clip (line {first_gi}) after 3 attempts: {e}") from e
                    logger.warning("first grok clip retry", attempt=attempt, error=str(e)[:100])

            visual_paths[first_gi] = {"type": "video", "path": first_clip, "source": video_provider}
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
            await _update_step(f"generating {len(remaining)} {video_provider} video clips")
            # Launch all concurrently with minimal stagger
            tasks = []
            for idx, i in enumerate(remaining):
                async def _launch(i=i, delay=idx * 0.3):
                    await asyncio.sleep(delay)
                    return await _gen_animated_clip_with_retries(i)
                tasks.append(_launch())
            results = await asyncio.gather(*tasks)
            for i, clip_path in results:
                visual_paths[i] = {"type": "video", "path": clip_path, "source": video_provider}

    # 4. Create segments — each line's audio paired directly with its visual — PARALLEL
    await _update_step(f"visuals done — creating {len(line_audio)} segments")

    # Always pad to fit — never crop/squish. Black bars are better than cut-off content.
    scale_filter = f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"

    _seg_done = 0

    _n_lines_total = len(line_audio)

    def _create_segment(i, audio):
        nonlocal _seg_done
        seg_path = os.path.join(segments_dir, f"seg_{i}.mp4")
        if os.path.exists(seg_path):
            _seg_done += 1
            return i, seg_path
        dur = audio["duration"]
        # Pad the LAST segment by 0.6s so the final narration has room to play
        # before the video ends — acrossfade blends the last 0.3s otherwise.
        if i == _n_lines_total - 1:
            dur += 0.6
        vp = visual_paths.get(i)

        if not vp:
            logger.warning("no visual for line", line=i)
            return i, None

        if vp["type"] == "video":
            is_grok = vp.get("source") == "grok"
            if is_grok:
                clean_clip = vp["path"].replace(".mp4", "_clean.mp4")
                if not os.path.exists(clean_clip):
                    subprocess.run([
                        "ffmpeg", "-y", "-i", vp["path"],
                        "-map", "0:v:0", "-map", "0:a?", "-c:v", "copy", "-c:a", "copy", clean_clip,
                    ], capture_output=True, text=True, timeout=30)
                clip_input = clean_clip if os.path.exists(clean_clip) else vp["path"]

                # Mix Grok's generated SFX audio under the narration
                # Grok audio at -12dB, narration at full volume
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", clip_input,
                    "-i", audio["path"],
                    "-vf", scale_filter,
                    "-filter_complex",
                    "[0:a]volume=-12dB[groksfx];[1:a]volume=0dB[narr];[narr][groksfx]amix=inputs=2:duration=first:dropout_transition=0[aout]",
                    "-map", "0:v", "-map", "[aout]",
                    "-t", str(dur),
                    "-r", "30", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
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
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-movflags", "+faststart",
                    seg_path,
                ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", vp["path"],
                "-i", audio["path"],
                "-vf", scale_filter,
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart",
                seg_path,
            ]

        seg_timeout = 180 if is_long_form else 120
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=seg_timeout)
        if result.returncode != 0:
            logger.warning("segment failed", line=i, stderr=result.stderr[:200])
            return i, None

        if os.path.exists(seg_path):
            _seg_done += 1
            _log_sync(f"segment {_seg_done}/{len(line_audio)} line {i} ({dur:.1f}s, {vp['type']})")
            return i, seg_path
        return i, None

    seg_loop = asyncio.get_event_loop()
    seg_tasks = [
        seg_loop.run_in_executor(None, _create_segment, i, audio)
        for i, audio in enumerate(line_audio)
    ]
    seg_results = await asyncio.gather(*seg_tasks)
    await _flush_logs()

    # Sort by index and filter out failures
    seg_results = sorted(seg_results, key=lambda x: x[0])
    segment_paths = [path for _, path in seg_results if path]

    if not segment_paths:
        raise RuntimeError("No segments created")

    # 5. Assemble with visual transitions + SFX + background music
    await _update_step(f"segments done ({len(segment_paths)}) — assembling final video")
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
        xfade_cmd = f'ffmpeg -y {inputs_str} -filter_complex "{filter_str}" -map "[vout]" -map "[aout]" -c:v libx264 -preset fast -crf 23 -c:a aac -ar 44100 -b:a 192k -movflags +faststart {concat_path}'
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
                 "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
    # Pick background music based on channel mood
    import random as _random
    music_base = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")

    # Map channels to mood folders
    channel_mood_map = {
        # Dark/suspense
        "SpookLand": "dark", "ColdCaseCartoons": "dark", "Deep We Go": "dark",
        "Mathematicious": "chill", "Techognizer": "chill",
        # Epic/dramatic
        "Deity Drama": "epic", "One on Ones For Fun": "epic",
        "NightNightShorts": "epic", "CrabRaveShorts": "epic",
        # Upbeat/fun
        "Munchlax Lore": "upbeat", "ToonGunk": "upbeat",
        "Hardcore Ranked": "upbeat", "Nature Receipts": "upbeat",
        "Schmoney Facts": "upbeat", "Historic Ls": "upbeat",
        # Quirky/comedy
        "Thats A Meme": "quirky",
        # Chill/educational
        # Techognize/Mathognize deleted — now Techognizer/Mathematicious (mapped above)
        "Smooth Brain Academy": "chill", "Globe Thoughts": "chill",
        "What If City": "chill",
        # News
        "Ctrl Z The Time": "news",
        # Kids
        "Blanket Fort Cartoons": "kids",
    }

    # Background music disabled — Grok SFX handles audio atmosphere
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
    await _update_step("adding subtitles")
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

        # Subtitles only — no label overlays (AI generates all text in images)
        ass_path = os.path.join(output_dir, "subs.ass")
        _write_karaoke_ass(ass_path, all_words, None, is_long_form=is_long_form)

        # FFmpeg ASS filter needs special escaping for path separators
        ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        cmd = [
            "ffmpeg", "-y", "-i", concat_path,
            "-vf", f"ass='{ass_path}'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
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
        "category": get_channel_category(channel_id),
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

    # 7b. Thumbnail generation disabled — YouTube auto-generates one, saves 1 gpt-image call per video
    if False and is_long_form:
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

        # No text overlay — AI generates all text in the thumbnail image itself
        if True:
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
        font_size = 64
        label_size = 58
        subtitle_margin_v = 80
        label_margin_v = 100
    else:
        play_res_x, play_res_y = 720, 1280
        font_size = 62
        label_size = 58
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
        # Split into line groups. Prefer explicit line ids when available so we never
        # mix words across narration lines like "smile? He". Fall back to gap-based
        # grouping for older callers that pass 3-tuples only.
        line_groups = []
        if len(words[0]) >= 4:
            current_line_id = words[0][3]
            current_group = [words[0]]
            for word in words[1:]:
                if word[3] != current_line_id:
                    line_groups.append(current_group)
                    current_group = [word]
                    current_line_id = word[3]
                else:
                    current_group.append(word)
            if current_group:
                line_groups.append(current_group)
        else:
            current_group = [words[0]]
            for k in range(1, len(words)):
                prev_end = words[k - 1][2]
                curr_start = words[k][1]
                if curr_start - prev_end > 0.25:
                    line_groups.append(current_group)
                    current_group = []
                current_group.append(words[k])
            if current_group:
                line_groups.append(current_group)

        # Now group words into chunks of 3 WITHIN each line group
        for group_idx, line_words in enumerate(line_groups):
            next_group_start = None
            if group_idx + 1 < len(line_groups):
                next_group_start = line_groups[group_idx + 1][0][1]
            for gi in range(0, len(line_words), 3):
                group = line_words[gi:gi + 3]
                texts = [_emoji_pat.sub("", w[0]) for w in group]
                wc = len(group)
                times = []
                for j, word_entry in enumerate(group):
                    _, ws, we = word_entry[:3]
                    next_boundary = group[j + 1][1] if j + 1 < wc else we
                    if j == wc - 1 and next_group_start is not None:
                        next_boundary = min(next_boundary, max(next_group_start - 0.01, ws))
                    times.append((ws, next_boundary))
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
