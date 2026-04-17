"""Shared video building functions used by all channel builders.

All common logic lives here — narration, intro hooks, audio mixing,
subtitle generation, teaser building, segment creation.
Channel-specific builders only define: character, voice, music, art style, prompts.
"""
import asyncio
import base64
import json
import math
import os
import subprocess
import wave

import numpy as np
import structlog

logger = structlog.get_logger()

# Shared constants
WIDTH, HEIGHT = 1080, 1920
SR = 44100
WHOOSH_SFX = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "sfx", "rising_whoosh.mp3")
SHUTTER_SFX = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "sfx", "camera_shutter.mp3")


def get_duration(path: str) -> float:
    """Get audio/video duration in seconds."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"File missing or empty: {path}")
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True,
    )
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (KeyError, json.JSONDecodeError):
        raise RuntimeError(f"Cannot read duration from {path} — file may be corrupt")


def get_clip_duration(narr_path: str) -> int:
    """Calculate how long to request from Grok for a narration line.

    Returns seconds (int). If the clip comes back slightly short,
    build_silent_segments will freeze the last frame (tpad) instead of looping.
    """
    narr_dur = get_duration(narr_path)
    return min(math.ceil(narr_dur + 0.5), 10)


async def run_tasks(coroutines: list, parallel: bool = True, max_concurrent: int = 5):
    """Run async coroutine-generating functions in parallel or sequentially.

    Args:
        coroutines: list of no-arg async functions (lambdas) to call
        parallel: True for concurrent (default), False for sequential
        max_concurrent: max simultaneous tasks when parallel

    Builders default to parallel for images/animations.
    Set parallel=False for steps that need order (chain-from-previous, etc).
    Adding sequential requirements later is just changing this flag.
    """
    if parallel:
        sem = asyncio.Semaphore(max_concurrent)
        async def limited(fn):
            async with sem:
                return await fn()
        return await asyncio.gather(*[limited(fn) for fn in coroutines])
    else:
        results = []
        for fn in coroutines:
            results.append(await fn())
        return results


def load_audio_samples(path: str) -> np.ndarray:
    """Load any audio file as mono float32 numpy array at 44100Hz."""
    path_hash = hash(path) & 0xFFFFFFFF
    tmp_raw = f"/tmp/_tmp_pcm_{os.getpid()}_{path_hash}.raw"
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-ar", str(SR), "-ac", "1", "-f", "s16le", tmp_raw],
        capture_output=True, timeout=30,
    )
    with open(tmp_raw, "rb") as f:
        return np.frombuffer(f.read(), dtype=np.int16).astype(np.float32)


async def generate_narration_with_timestamps(
    narration_lines: list[str],
    narr_dir: str,
    output_dir: str,
    voice_id: str,
    _update_step,
    voice_settings: dict | None = None,
) -> list[dict]:
    """Generate narration with ElevenLabs word-level timestamps.

    Returns list of word dicts: [{word, start, end, line}, ...]
    Skips lines that already have audio AND valid timestamps exist.
    """
    import requests
    from dotenv import load_dotenv
    load_dotenv()

    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    all_word_data = []

    # Check for existing valid timestamps
    word_ts_path = os.path.join(output_dir, "word_timestamps.json")
    has_valid_timestamps = False
    if os.path.exists(word_ts_path):
        with open(word_ts_path) as f:
            existing = json.load(f)
            if len(existing) > 0:
                # Validate that every expected mp3 file actually exists on disk.
                # A partial-failure retry may have timestamps but missing audio.
                all_mp3s_exist = all(
                    os.path.exists(os.path.join(narr_dir, f"line_{i:02d}.mp3"))
                    for i in range(len(narration_lines))
                )
                if all_mp3s_exist:
                    all_word_data = existing
                    has_valid_timestamps = True
                else:
                    logger.warning("timestamp cache exists but some mp3 files are missing — regenerating")

    if voice_settings is None:
        voice_settings = {"stability": 0.5, "similarity_boost": 0.8, "speed": 1.05}

    for i, line in enumerate(narration_lines):
        narr_path = os.path.join(narr_dir, f"line_{i:02d}.mp3")
        if os.path.exists(narr_path) and has_valid_timestamps:
            continue

        await _update_step(f"narrating {i + 1}/{len(narration_lines)}")
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": elevenlabs_key, "Content-Type": "application/json"},
            json={
                "text": line,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": voice_settings,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs failed line {i}: {resp.status_code}")

        data = resp.json()
        with open(narr_path, "wb") as f:
            f.write(base64.b64decode(data["audio_base64"]))

        # Parse word timestamps
        alignment = data.get("alignment", {})
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        current_word, word_start, word_end = "", None, None
        for c, cs, ce in zip(chars, starts, ends):
            if c == " ":
                if current_word:
                    all_word_data.append({"word": current_word, "start": word_start, "end": word_end, "line": i})
                    current_word, word_start = "", None
            else:
                if word_start is None:
                    word_start = cs
                current_word += c
                word_end = ce
        if current_word:
            all_word_data.append({"word": current_word, "start": word_start, "end": word_end, "line": i})

    with open(word_ts_path, "w") as f:
        json.dump(all_word_data, f)

    return all_word_data


async def generate_image_prompts(
    narration_lines: list[str],
    channel_rules: str,
    _update_step,
) -> list[str]:
    """Generate image prompts from narration lines using Claude.

    channel_rules: channel-specific instructions (character description, art style, etc.)
    """
    await _update_step("planning visuals")
    from packages.clients.claude import generate as claude_generate
    import re

    prompts_resp = claude_generate(
        prompt=f"""Write image prompts for each narration line.

NARRATION (each line is numbered):
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

ABSOLUTE RULES FOR EVERY IMAGE PROMPT:

1. LITERAL MATCH: Each image MUST show EXACTLY what the narrator says. Not something related — the LITERAL scene.

2. EVERY SCENE NEEDS A SETTING: Never write a prompt with just characters on a blank/white background. Every scene must have a specific location — a room, a street, an arena, a forest, etc. Describe the environment.

3. CHARACTER PROPORTIONS: All characters must be normal human proportions relative to each other unless the narration specifically says otherwise. A character should NOT appear giant or tiny compared to others unless that is the point.

4. CONSISTENCY: If the narration takes place in a specific location (arena, village, forest), keep using that SAME location across scenes that happen there. Dont randomly change settings between consecutive scenes in the same location.

5. SPECIFICITY: Describe exactly what each character is DOING, their EXPRESSION, their POSE, and WHERE they are standing in the scene. Vague prompts produce vague images.

6. ACTION MATCHING: If the narration says a character RUNS, show them MID-STRIDE with legs moving. If it says they FIGHT, show them mid-combat. If it says they HUNT, show them crouched and stalking or sprinting after prey. NEVER show a character calmly standing when the narration describes action. The character must be DOING the verb in the narration, not posing near it.

7. CHARACTER ACCURACY: If the narration mentions a specific character, creature, or famous person by name, describe them with their EXACT iconic features. Do not use vague descriptions — use their actual name and signature appearance. Pikachu is a yellow electric mouse with red cheeks, not "a small yellow creature."

8. NO REPETITIVE ANGLES: Never describe two consecutive scenes with the same character in the same pose from the same camera angle in the same location. Each scene must change at least ONE of: camera angle, location, character pose, or which characters are visible. If two lines happen in the same room, show different parts of it or different perspectives.

{channel_rules}

Return ONLY a JSON array of {len(narration_lines)} strings.""",
        max_tokens=4000,
    )

    json_match = re.search(r'\[.*\]', prompts_resp, re.DOTALL)
    if json_match:
        image_prompts = json.loads(json_match.group())
    else:
        image_prompts = json.loads(prompts_resp)

    # Pad or trim to match narration count
    while len(image_prompts) < len(narration_lines):
        image_prompts.append(image_prompts[-1])
    image_prompts = image_prompts[:len(narration_lines)]

    # ─── VISUAL PLAN REVIEW — catch problems before spending on image gen ───
    await _update_step("reviewing visual plan")
    review_resp = claude_generate(
        prompt=f"""You are a visual story editor. Review this visual plan and FIX any problems.

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

IMAGE PROMPTS:
{chr(10).join(f'{i}: "{p}"' for i, p in enumerate(image_prompts))}

CHECK FOR THESE PROBLEMS AND FIX THEM:

1. DUPLICATE SCENES: Are any two prompts describing essentially the same image? (same setting, same pose, same composition). If so, rewrite one to show a DIFFERENT angle, location, or moment.

2. VISUAL FLOW: Would a viewer understand the story just from the images alone, without narration? Each image should advance the story visually — moving to a new location, showing a new action, revealing new information. If the story doesn't flow visually, fix it.

3. NARRATION MISMATCH: Does each prompt show EXACTLY what its narration line says? If the narration mentions a specific object (shoes, phone, door), that object MUST be the focus of the image. Fix any that don't match.

4. PREMATURE REVEAL: If this is a horror/mystery/surprise video, does any early scene spoil the reveal? The scary thing, the punchline, or the twist should NOT appear until the narration reveals it. Fix any that spoil it.

5. VARIETY: Are the scenes visually diverse enough? Different rooms, angles, compositions, lighting? A video where every scene is the same hallway from the same angle is boring. Fix repetitive scenes.

Return the FIXED array of {len(image_prompts)} prompts. If a prompt is fine, keep it unchanged. Only rewrite the ones with problems.

Return ONLY a JSON array of {len(image_prompts)} strings.""",
        max_tokens=4000,
    )

    review_match = re.search(r'\[.*\]', review_resp, re.DOTALL)
    if review_match:
        try:
            reviewed = json.loads(review_match.group())
            if len(reviewed) == len(image_prompts):
                changes = sum(1 for a, b in zip(image_prompts, reviewed) if a != b)
                if changes > 0:
                    logger.info("visual plan reviewed", changes=changes, total=len(image_prompts))
                    image_prompts = reviewed
                else:
                    logger.info("visual plan approved — no changes needed")
            else:
                logger.warning("visual review returned wrong count, keeping originals",
                             expected=len(image_prompts), got=len(reviewed))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("visual review parse failed, keeping originals", error=str(e)[:100])
    else:
        logger.warning("visual review returned no JSON, keeping originals")

    return image_prompts


async def generate_and_animate_scenes(
    narration_lines: list[str],
    concept: dict,
    channel_rules: str,
    art_style_prompt: str,
    output_dir: str,
    _update_step,
    run_id: int = 0,
    prefer_grok_images: bool = False,
    character_ref_path: str | None = None,
) -> tuple[str, list[str], int, dict[int, list[str]]]:
    """Unified scene generation + animation pipeline.

    Implements: style anchor → sub-actions → GPT images → Grok animation → chaining.
    Returns (clips_dir, clip_paths_in_order, n_clips, line_clip_map) where
    line_clip_map maps narration line index → list of clip filenames for that line.

    Args:
        prefer_grok_images: Skip gpt-image entirely and use Grok Imagine for all images.
            Use for channels with IP/licensed characters that gpt-image always refuses.

    Args:
        narration_lines: the narration script
        concept: full concept dict (for brief, etc.)
        channel_rules: IMAGE_RULES from the channel builder
        art_style_prompt: the art style description for GPT (e.g. "Simple cartoon with thick outlines...")
        output_dir: base output directory
        _update_step: status callback
    """
    from packages.clients.grok import generate_image_dalle_async, generate_image_grok_async, generate_video_async
    # Pick image generator based on channel preference
    _gen_image = generate_image_grok_async if prefer_grok_images else generate_image_dalle_async
    from packages.clients.claude import generate as claude_generate
    from openai import AsyncOpenAI
    import re as _re

    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
    brief = concept.get("brief", "")
    extra_rules = f"\n\nCONCEPT-SPECIFIC INSTRUCTIONS:\n{brief}" if brief else ""

    # Era enforcement — ALL image prompts and reviews must specify this era
    era = concept.get("era", "")
    era_prefix = ""
    if era:
        era_prefix = f"STRICT ERA: {era}. All humans in period-accurate clothing. NO modern clothing (no T-shirts, jeans, suits, polo shirts, casual wear). NO modern vehicles, NO modern technology, NO modern buildings. "

    n_lines = len(narration_lines)

    # ─── STEP 1: Generate style anchor ───
    await _update_step("generating style anchor")
    style_anchor_path = os.path.join(images_dir, "style_anchor.png")
    if not os.path.exists(style_anchor_path):
        await _gen_image(
            prompt=f"{art_style_prompt} A simple establishing shot for the video. {narration_lines[0] if narration_lines else 'A character in a scene.'}. NO text anywhere.",
            output_path=style_anchor_path, size="1024x1536",
        )
    else:
        # Anchor was reused from previous run — validate size and fix if wrong
        from packages.clients.grok import _crop_to_size as _crop
        _crop(style_anchor_path, "1024x1536")
    logger.info("style anchor generated")

    # ─── STEP 2: Plan sub-actions ───
    await _update_step("planning sub-actions")
    # Get narration durations so planner can match clip count to narration length
    _narr_durs = []
    for _ni in range(len(narration_lines)):
        _np = os.path.join(output_dir, "narration", f"line_{_ni:02d}.mp3")
        if os.path.exists(_np):
            _narr_durs.append(get_duration(_np))
        else:
            _narr_durs.append(3.0)

    plan_resp = claude_generate(
        prompt=f"""Break this narration into animation sub-actions. Each sub-action is ONE simple movement (2-3 seconds for Grok to animate).

CHANNEL RULES (HIGHEST PRIORITY — every image_prompt must follow these exactly):
{channel_rules}

NARRATION (with durations):
{chr(10).join(f'{i}: "{line}" ({_narr_durs[i]:.1f}s)' for i, line in enumerate(narration_lines))}

CRITICAL — CHARACTER CONSISTENCY: If the CHANNEL RULES above describe a specific main character (e.g. a skeletorinio, a frog, a mascot), that exact character MUST appear in EVERY image_prompt as the subject. Do NOT substitute with generic humans, tourists, or other characters. The named main character is the star of every single scene unless the narration explicitly focuses on someone else.

CRITICAL — CLIP COVERAGE: The total duration of sub-action clips for each narration line MUST cover the narration duration. A 6-second narration line needs 2-3 sub-actions (2x3s or 3x2s), NOT one 3s clip. A 4-second line needs at least 2 sub-actions. Only lines under 3.5s can have a single sub-action.

CRITICAL — SHOT VARIETY: Across the full set of image_prompts, vary camera angle, distance, and composition aggressively. Never more than 2 consecutive scenes with the same framing. Mix: close-up, medium, wide, bird's-eye, low-angle, over-the-shoulder, dutch-angle. Mix tight/loose framing. Vary lighting when the scene changes (golden hour, overcast, night, torchlit). Repeating "wide shot at eye level" across most scenes is a FAIL — the video will look static and boring.

CRITICAL — NO STATIC ANIMATION PROMPTS: Every animation_prompt must describe CONTINUOUS VISIBLE motion. Banned words: "motionless", "still", "sits", "stands", "peaceful", "calm", "slowly blinks", "half-closed", "unchanging". If the beat is inherently quiet, describe subject motion (twitching, breathing hard, shifting weight) OR camera motion (fast push-in, pull-back, dolly, whip-pan). A clip where nothing moves reads as a freeze.

CRITICAL — LINE 0 IS THE HOOK (SHOW THE PAYOFF, NOT THE SETUP):
Line 0's narration is the "what if" question, but the image_prompt for line 0 must show the MOST EXCITING / CLIMACTIC moment of the video — the payoff the viewer is being teased with. NOT the setup, NOT the protagonist holding an object, NOT "about to do" something. SHOW THE ACTUAL COOL THING HAPPENING.
- BAD: "Skeletorinio stands holding a tiny red canister at the entrance of a jousting arena, knights charging in the distance." (This is setup — viewer swipes away.)
- GOOD: "Skeletorinio in the center of the jousting arena, laughing, spraying orange pepper mist directly into the faces of two armored knights who are simultaneously falling off their galloping horses with tears streaming, crowd erupting. Dust exploding."
- The viewer should hear "What if you brought pepper spray to medieval jousting" while SEEING the knights already wiping out. That's how hooks work on shorts.
- Applies to ALL videos regardless of channel. The hook visual is the #1 determinant of watch time.
- Lines 1+ still follow temporal alignment (below) — only line 0 gets the "show the payoff" privilege.

CRITICAL — EVERY IMAGE MUST SHOW ACTION IN PROGRESS (NO STANDING/POSING):
Every `image_prompt` must depict a MOMENT OF ACTION — something physically happening RIGHT NOW. Never "character standing in a location" or "character surrounded by people watching." The character must be MID-MOTION: swinging, crashing, falling, running, grabbing, throwing, reacting with their whole body.
- BAD: "Skeletorinio stands in front of a crowd in a medieval courtyard" (boring — nothing happening)
- BAD: "Two thousand people kneel before the skeleton" (static tableau — no action)
- GOOD: "Skeletorinio mid-swing pulling a glowing sword from a cracking stone, sparks flying, crowd behind him diving out of the way"
- GOOD: "Skeletorinio crashing a bicycle through castle gates, wood splintering, guards tumbling"
If a scene is inherently about people REACTING (crowd cheering, king giving award), show the MOMENT OF the reaction with physical motion — confetti mid-air, arms mid-throw, crown tumbling off a head — not the static aftermath.

CRITICAL — TEMPORAL ALIGNMENT (DO NOT FORESHADOW):
Each sub-action's `image_prompt` and `animation_prompt` MUST depict ONLY the specific event the narration describes for THAT exact line. Do NOT pre-stage events from later lines. Do NOT show aftermath from earlier lines. Do NOT combine beats.
- If narration line N says "you pull out a canister", the animation shows the canister being pulled out — NOT a spray, NOT an impact, NOT a crash.
- If narration line N+1 says "spray hits", THAT is where the spray animation belongs.
- If narration line N+2 says "they crash", THAT is where the crash animation belongs.
The visible action on screen must match WHAT THE VIEWER IS HEARING AT THAT MOMENT. Front-loading dramatic action into earlier scenes (because the planner is excited about the climax) breaks narration sync and makes the video feel buggy. Every line gets its own beat — no more, no less.

For each sub-action, decide:
- "new_scene": true if this needs a fresh GPT-generated image (new setting, new character entering). false if it chains from the previous clip's last frame.
- "image_prompt": what the starting image should show (BEFORE the action happens). Only needed if new_scene=true.
- "animation_prompt": ONE simple action for Grok (2-3 seconds). One verb. e.g. "opens door and walks through", "swings sword hitting opponent", "energy builds in fist"
- "line": which narration line (0-indexed) this belongs to
- "duration": seconds (2-3)
- "chain_rule": if chaining, what must be in the last frame for the chain to work (e.g. "Zoro visible in hallway")

CRITICAL RULES FOR IMAGE PROMPTS:

1. VISUAL SPECIFICITY: Every image_prompt must describe the EXACT visual that a viewer would understand WITHOUT narration.
   BAD: "Luffy copies hand signs" — too vague, viewer won't know what's happening
   GOOD: "Luffy from One Piece and Naruto from Naruto standing side by side. Both are forming the same cross-shaped hand sign. Luffy has one red Sharingan eye and looks confused. Naruto looks surprised that Luffy is copying him. Hidden Leaf Village training ground background."

2. SHOW THE ACTION LITERALLY: If the narration says "bouncing off walls," the image must show a character PHYSICALLY embedded in or bouncing off a wall with cracks. If it says "stretches an arm," the image must show a visibly stretched rubber arm going across the scene.
   BAD: "clones causing chaos in the village" — vague, could be anything
   GOOD: "Five Luffy clones — one embedded in a stone wall with cracks radiating out, one stretched between two buildings like a rubber band, one eating from a food cart while the vendor screams. Hidden Leaf Village street."

3. THE VIEWER MUST UNDERSTAND THE SCENE ON MUTE: Ask yourself — if someone saw ONLY this image with no text, would they understand what's happening? If not, add more visual detail.

4. CAMERA ANGLE AND POSITIONING: Every prompt must specify:
   - CAMERA ANGLE: "Close-up", "Wide shot from behind", "Side view at eye level", "Bird's eye view"
   - CHARACTER POSITION: Where each character is in frame — "left of frame", "center", "facing each other"
   - SPATIAL RELATIONSHIPS: "standing next to", "towering over", "side by side" — be explicit about how characters relate to each other physically
   BAD: "Kakashi and Luffy fight" — where are they? What angle?
   GOOD: "Side view at eye level. Kakashi on the left punches Luffy on the right in the belly. Luffy's rubber belly stretches toward camera."

5. EVERY image_prompt MUST include:
   - A SPECIFIC BACKGROUND SETTING (arena, village, forest, ramen shop)
   - Character NAMES with franchise ("Luffy from One Piece", "Kakashi from Naruto")
   - The SPECIFIC PHYSICAL ACTION happening (not just "fighting" but "fist connecting with face, opponent flying backward")
   - Character EXPRESSIONS (confused, shocked, angry, smirking)
   - NEVER just characters on a blank/white background
   - NEVER comic panel layouts or manga grids — ONE single scene per image
   - NEVER split-images / before-and-after combos in a single frame (no top-half/bottom-half showing two moments)
   - The image_prompt describes ONLY the FIRST MOMENT of the action — the starting point. The animation and chaining handle everything after that. Do NOT try to show the whole sequence in one image.

6. WHEN A NARRATION LINE DESCRIBES TWO EVENTS, USE TWO SUB-ACTIONS:
   - If narration says "X, then Y" or "X and then Y" — that's TWO sub-actions for the same line, not one image showing both.
   - BAD: narration "Goku Instant Transmissions to the exit, then back" → ONE image with split-screen showing both
   - GOOD: narration "Goku Instant Transmissions to the exit, then back" → sub-action A: Goku flashing in at the exit (light burst, examiners shocked) + sub-action B: Goku flashing back at the start (chained from A's last frame, examinees gasping)
   - Multiple sub-actions for the same `line` index is fully supported — use it whenever the narration has multiple beats.

5. For fight/action scenes: show the MOMENT OF IMPACT or the STARTING POINT of the action, with both characters visible and the result beginning to happen.

OTHER RULES:
- Line 0 (the hook) is always new_scene=true
- When characters/setting change, it's new_scene=true
- Within the same fight or location, chain from last frame
- Keep animations SIMPLE — one action per clip

Return ONLY a JSON array of objects.""",
        max_tokens=4000,
    )

    plan_match = _re.search(r'\[.*\]', plan_resp, _re.DOTALL)
    if plan_match:
        sub_actions = json.loads(plan_match.group())
    else:
        sub_actions = [
            {"new_scene": True, "image_prompt": f"Scene for: {line}", "animation_prompt": "Subtle movement.", "line": i, "duration": 3}
            for i, line in enumerate(narration_lines)
        ]
    # Save plan to disk so the API can read it for narration mapping
    with open(os.path.join(images_dir, "plan.json"), "w") as pf:
        json.dump(sub_actions, pf, indent=2)
    logger.info("sub-actions planned", count=len(sub_actions))

    # ─── STEP 3a: Generate all NEW scene images first (reviewable) ───
    await _update_step("generating scene images")
    import anthropic
    review_client = anthropic.Anthropic()
    for sa_idx, sa in enumerate(sub_actions):
        if not sa.get("new_scene", True):
            continue  # chained clips get images later
        img_prompt = sa.get("image_prompt", "")
        img_path = os.path.join(images_dir, f"sub_{sa_idx:03d}.png")
        if os.path.exists(img_path):
            continue

        # Use character reference if provided (more consistent than style anchor)
        _edit_ref_path = character_ref_path if character_ref_path and os.path.exists(character_ref_path) else style_anchor_path

        if prefer_grok_images:
            await _gen_image(
                prompt=f"{era_prefix}{art_style_prompt} {img_prompt} NO text anywhere.",
                output_path=img_path, size="1024x1536",
            )
        else:
            style_ref = open(_edit_ref_path, "rb")
            try:
                # Keep edit prompt SHORT — the reference image handles character/style.
                # Long prompts (art_style + channel_rules) cause gpt-image to override the reference.
                resp = await client.images.edit(
                    model="gpt-image-1.5",
                    image=style_ref,
                    prompt=f"{era_prefix}MATCH THE EXACT ART STYLE OF THE REFERENCE IMAGE. Same photographic look, same level of detail, same character design. NOT a cartoon, NOT cel-shaded, NOT a sketch — identical rendering style to the reference. {img_prompt} NO text anywhere.",
                    size="1024x1536",
                    quality="medium",
                    input_fidelity="high",
                )
                style_ref.close()
                if resp.data and resp.data[0].b64_json:
                    img_data = base64.b64decode(resp.data[0].b64_json)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
            except Exception as e:
                style_ref.close()
                # Re-attempt edit with reference instead of falling back to text-only
                for _retry in range(2):
                    try:
                        style_ref_retry = open(_edit_ref_path, "rb")
                        resp = await client.images.edit(
                            model="gpt-image-1.5",
                            image=style_ref_retry,
                            prompt=f"{era_prefix}MATCH THE EXACT ART STYLE OF THE REFERENCE IMAGE. Same photographic look, same level of detail, same character design. NOT a cartoon, NOT cel-shaded, NOT a sketch — identical rendering style to the reference. {img_prompt} NO text anywhere.",
                            size="1024x1536",
                            quality="medium",
                            input_fidelity="high",
                        )
                        style_ref_retry.close()
                        if resp.data and resp.data[0].b64_json:
                            img_data = base64.b64decode(resp.data[0].b64_json)
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                            break
                    except Exception:
                        try: style_ref_retry.close()
                        except: pass
                else:
                    # All edit retries exhausted — last resort text-only
                    await _gen_image(
                        prompt=f"{era_prefix}{art_style_prompt} {img_prompt} NO text anywhere.",
                        output_path=img_path, size="1024x1536",
                    )
        logger.info("new scene image", sub_action=sa_idx, prompt=img_prompt[:60])

        # Auto-review
        try:
            with open(img_path, "rb") as rf:
                img_b64_review = base64.b64encode(rf.read()).decode()
            line_idx = sa.get("line", 0)
            narr_text = narration_lines[line_idx] if line_idx < len(narration_lines) else ""
            review = review_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64_review}},
                    {"type": "text", "text": f"""Review this image against the narration and rules. Be STRICT.

NARRATION: '{narr_text}'

ART STYLE EXPECTED: {art_style_prompt}

ERA REQUIRED: {era if era else 'any'}

CHANNEL RULES: {channel_rules[:500]}

IMAGE PROMPT USED: {img_prompt[:300]}

Check ALL of these:
1. Does the image show the SPECIFIC ACTION described in the narration? Not just the right characters — the actual action happening.
2. Is it a SINGLE SCENE? Comic panel layouts, manga grids, split panels = automatic FAIL.
3. Are the characters recognizable as who they should be?
4. Does the art style match what's expected? (crude cartoon should be crude cartoon, not anime)
5. ERA CHECK: If an era is required above, ALL humans must be in period-accurate clothing. Modern clothing (T-shirts, jeans, suits, casual wear), modern vehicles, or modern objects in a historical-era video = automatic FAIL.
5. Does the image show the STARTING POINT of the action (before the result)? Images showing the aftermath instead of the moment = FAIL.
6. Is there anything that contradicts the narration?

Answer PASS or FAIL with specific reason."""},
                ]}],
            )
            if "FAIL" in review.content[0].text:
                logger.warning("image review FAILED — regenerating with reference", sub_action=sa_idx, reason=review.content[0].text[:100])
                os.remove(img_path)
                # Use the SAME short-prompt + reference pattern as first-pass to avoid style drift.
                # Long prompts with art_style_prompt cause gpt-image to ignore the reference image.
                if prefer_grok_images:
                    await _gen_image(
                        prompt=f"{era_prefix}{art_style_prompt} {img_prompt} Make sure this EXACTLY matches: {narr_text}. NO text anywhere.",
                        output_path=img_path, size="1024x1536",
                    )
                else:
                    _regen_prompt = f"{era_prefix}MATCH THE EXACT ART STYLE OF THE REFERENCE IMAGE. Same photographic look, same level of detail, same character design. NOT a cartoon, NOT cel-shaded, NOT a sketch — identical rendering style to the reference. {img_prompt} Make sure this EXACTLY matches: {narr_text}. NO text anywhere."
                    # Retry the edit up to 3 times with the reference before giving up
                    for _retry in range(3):
                        try:
                            style_ref2 = open(_edit_ref_path, "rb")
                            resp2 = await client.images.edit(
                                model="gpt-image-1.5",
                                image=style_ref2,
                                prompt=_regen_prompt,
                                size="1024x1536",
                                quality="medium",
                                input_fidelity="high",
                            )
                            style_ref2.close()
                            if resp2.data and resp2.data[0].b64_json:
                                with open(img_path, "wb") as f2:
                                    f2.write(base64.b64decode(resp2.data[0].b64_json))
                                break
                        except Exception:
                            try: style_ref2.close()
                            except: pass
                    # Only fall to text-only if all edit retries failed — last resort
                    if not os.path.exists(img_path):
                        logger.warning("review regen: all edit retries failed, falling to text-only (will drift style)", sub_action=sa_idx)
                        await _gen_image(
                            prompt=f"{era_prefix}{art_style_prompt} {img_prompt} Make sure this EXACTLY matches: {narr_text}. NO text anywhere.",
                            output_path=img_path, size="1024x1536",
                        )
        except Exception as e:
            logger.error("image review ERROR", error=str(e)[:200], sub_action=sa_idx)

    # ─── STEP 3b: Wait for user approval via file watch ───
    # Skip approval if clips already exist (means images were already approved in a previous run)
    existing_clips = [f for f in os.listdir(clips_dir) if f.endswith('.mp4')] if os.path.isdir(clips_dir) else []
    approval_file = os.path.join(output_dir, ".images_approved")
    deny_file = os.path.join(output_dir, ".images_denied")
    if existing_clips:
        logger.info("skipping image approval — clips already exist from previous run", count=len(existing_clips))
    elif os.path.exists(approval_file):
        logger.info("skipping image approval — already approved (carried forward from previous run)")
        os.remove(approval_file)
    else:
        await _update_step("images ready for review")

        # Clean up stale deny file only (approval was checked above)
        if os.path.exists(deny_file):
            os.remove(deny_file)

        while True:
            await asyncio.sleep(3)

            if os.path.exists(approval_file):
                logger.info("user approved images — continuing to animation")
                os.remove(approval_file)
                break

            if os.path.exists(deny_file):
                logger.info("user denied images — checking feedback")
                os.remove(deny_file)
                # Regenerate images that have feedback files — use edit-with-reference, not text-only,
                # to maintain style consistency with other scenes.
                for sa_idx, sa in enumerate(sub_actions):
                    if not sa.get("new_scene", True):
                        continue
                    feedback_path = os.path.join(images_dir, f"sub_{sa_idx:03d}_feedback.txt")
                    img_path = os.path.join(images_dir, f"sub_{sa_idx:03d}.png")
                    if os.path.exists(feedback_path):
                        feedback_text = open(feedback_path).read().strip()
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        _deny_prompt = f"{era_prefix}MATCH THE EXACT ART STYLE OF THE REFERENCE IMAGE. Same photographic look, same level of detail, same character design. NOT a cartoon, NOT cel-shaded, NOT a sketch — identical rendering style to the reference. {sa.get('image_prompt', '')} User feedback: {feedback_text}. NO text anywhere."
                        if prefer_grok_images:
                            await _gen_image(
                                prompt=f"{art_style_prompt} {sa.get('image_prompt', '')} User feedback: {feedback_text}. NO text anywhere.",
                                output_path=img_path, size="1024x1536",
                            )
                        else:
                            for _retry in range(3):
                                try:
                                    ref_file = open(_edit_ref_path, "rb")
                                    resp = await client.images.edit(
                                        model="gpt-image-1.5",
                                        image=ref_file,
                                        prompt=_deny_prompt,
                                        size="1024x1536",
                                        quality="medium",
                                        input_fidelity="high",
                                    )
                                    ref_file.close()
                                    if resp.data and resp.data[0].b64_json:
                                        with open(img_path, "wb") as f2:
                                            f2.write(base64.b64decode(resp.data[0].b64_json))
                                        break
                                except Exception:
                                    try: ref_file.close()
                                    except: pass
                            if not os.path.exists(img_path):
                                logger.warning("deny regen: all edit retries failed, falling to text-only (will drift style)", sub_action=sa_idx)
                                await _gen_image(
                                    prompt=f"{art_style_prompt} {sa.get('image_prompt', '')} User feedback: {feedback_text}. NO text anywhere.",
                                    output_path=img_path, size="1024x1536",
                                )
                        os.remove(feedback_path)
                        logger.info("regenerated from feedback", sub_action=sa_idx, feedback=feedback_text[:60])
                await _update_step("images ready for review")


    # ─── STEP 3c: Animate with chaining ───
    await _update_step("animating")
    clip_paths = []
    last_frame_path = None

    for sa_idx, sa in enumerate(sub_actions):
        is_new = sa.get("new_scene", True)
        img_prompt = sa.get("image_prompt", "")
        anim_prompt = sa.get("animation_prompt", "Subtle movement.")
        duration = min(sa.get("duration", 3), 4)  # cap at 4 seconds
        line_idx = sa.get("line", 0)

        img_path = os.path.join(images_dir, f"sub_{sa_idx:03d}.png")
        clip_path = os.path.join(clips_dir, f"sub_{sa_idx:03d}.mp4")
        clip_paths.append(clip_path)

        if os.path.exists(clip_path):
            # Extract last frame for potential chaining
            lf = os.path.join(images_dir, f"sub_{sa_idx:03d}_lastframe.png")
            if not os.path.exists(lf):
                subprocess.run([
                    "ffmpeg", "-y", "-sseof", "-0.1", "-i", clip_path,
                    "-frames:v", "1", "-update", "1", lf,
                ], capture_output=True, timeout=10)
            last_frame_path = lf
            continue

        await _update_step(f"scene {sa_idx+1}/{len(sub_actions)}")

        # Get starting image
        if is_new or last_frame_path is None:
            # Image already generated in step 3a — just verify it exists
            if not os.path.exists(img_path):
                raise RuntimeError(f"Missing image for new scene sub-action {sa_idx}")
        else:
            # Chain — use last frame from previous clip
            import shutil
            shutil.copy2(last_frame_path, img_path)
            logger.info("chained from last frame", sub_action=sa_idx)

        # Animate
        with open(img_path, "rb") as f:
            img_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

        await generate_video_async(
            prompt=anim_prompt,
            output_path=clip_path,
            duration=duration,
            aspect_ratio="9:16",
            image_url=img_b64,
            timeout=600,
        )
        logger.info("animated", sub_action=sa_idx, prompt=anim_prompt[:60])

        # Extract last frame for potential chaining
        lf = os.path.join(images_dir, f"sub_{sa_idx:03d}_lastframe.png")
        subprocess.run([
            "ffmpeg", "-y", "-sseof", "-0.1", "-i", clip_path,
            "-frames:v", "1", "-update", "1", lf,
        ], capture_output=True, timeout=10)
        last_frame_path = lf

    # Build line → clip mapping from the sub-action plan
    line_clip_map = {}
    for sa_idx, sa in enumerate(sub_actions):
        line_idx = sa.get("line", 0)
        clip_path = clip_paths[sa_idx] if sa_idx < len(clip_paths) else None
        if clip_path:
            line_clip_map.setdefault(line_idx, []).append(os.path.basename(clip_path))

    return clips_dir, clip_paths, len(sub_actions), line_clip_map


def build_segments_from_clip_map(
    n_lines: int,
    line_clip_map: dict[int, list[str]],
    clips_dir: str,
    narr_dir: str,
    segments_dir: str,
    style_anchor_path: str | None = None,
) -> list[float]:
    """Build video segments by mapping clips to narration lines explicitly.

    Each narration line gets a segment composed of its specific clips,
    trimmed or padded to match narration duration.
    """
    seg_durations = []
    for i in range(n_lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:02d}.mp4")
        if os.path.exists(seg_path):
            seg_durations.append(get_duration(seg_path))
            continue

        try:
            narr_dur = get_duration(os.path.join(narr_dir, f"line_{i:02d}.mp3")) + 0.05
        except Exception:
            narr_dur = 3.0  # fallback
        # Pad the LAST segment by 0.6s so the final narration has room to play out
        # before the video ends — prevents the cutoff-at-end issue.
        if i == n_lines - 1:
            narr_dur += 0.6
        clips = line_clip_map.get(i, [])

        if not clips:
            # No clips for this line — use style anchor as static image or first available clip
            src = style_anchor_path or os.path.join(clips_dir, "sub_000.png")
            if src and os.path.exists(src):
                subprocess.run([
                    "ffmpeg", "-y", "-loop", "1", "-i", src, "-t", str(narr_dur),
                    "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                    seg_path,
                ], capture_output=True, timeout=30)
        elif len(clips) == 1:
            clip_path = os.path.join(clips_dir, clips[0])
            clip_dur = get_duration(clip_path)
            if clip_dur >= narr_dur:
                subprocess.run([
                    "ffmpeg", "-y", "-i", clip_path, "-t", str(narr_dur),
                    "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                    seg_path,
                ], capture_output=True, timeout=60)
            else:
                subprocess.run([
                    "ffmpeg", "-y", "-i", clip_path,
                    "-vf", f"tpad=stop_mode=clone:stop_duration={narr_dur - clip_dur},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-t", str(narr_dur),
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                    seg_path,
                ], capture_output=True, timeout=60)
        else:
            # Multiple clips — trim static warmup AND crossfade between them for smooth transitions
            # Shorter xfade = snappier transitions, less "pause" feel and less risk of freeze-pad at segment end.
            TRIM_START = 0.5  # trim Grok's static warmup + any boundary mismatch
            XFADE_DUR = 0.5   # short crossfade — still visibly smooth, no perceived pause

            # First, trim the start of chained clips (2nd+)
            trimmed_paths = []
            for idx, c in enumerate(clips):
                if idx == 0:
                    trimmed_paths.append(os.path.join(clips_dir, c))
                else:
                    trimmed_path = os.path.join(segments_dir, f"trimmed_{i:02d}_{idx}.mp4")
                    subprocess.run([
                        "ffmpeg", "-y", "-ss", str(TRIM_START), "-i", os.path.join(clips_dir, c),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
                        "-r", "30",
                        trimmed_path,
                    ], capture_output=True, timeout=30)
                    trimmed_paths.append(trimmed_path)

            # Build xfade filter chain: each transition overlaps XFADE_DUR seconds
            tmp = os.path.join(segments_dir, f"tmp_{i:02d}.mp4")
            if len(trimmed_paths) == 2:
                d0 = get_duration(trimmed_paths[0])
                cmd = ["ffmpeg", "-y",
                    "-i", trimmed_paths[0], "-i", trimmed_paths[1],
                    "-filter_complex",
                    f"[0:v]settb=AVTB,fps=30[v0];[1:v]settb=AVTB,fps=30[v1];"
                    f"[v0][v1]xfade=transition=fade:duration={XFADE_DUR}:offset={d0 - XFADE_DUR}[out]",
                    "-map", "[out]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
                    tmp]
            else:
                # 3+ clips: chain xfades
                inputs = []
                for p in trimmed_paths:
                    inputs.extend(["-i", p])

                filter_parts = []
                for idx in range(len(trimmed_paths)):
                    filter_parts.append(f"[{idx}:v]settb=AVTB,fps=30[v{idx}]")

                cumulative_dur = 0
                prev_label = "v0"
                for idx in range(1, len(trimmed_paths)):
                    d_prev = get_duration(trimmed_paths[idx-1]) if idx == 1 else None
                    if idx == 1:
                        cumulative_dur = d_prev - XFADE_DUR
                        out_label = f"x{idx}"
                        filter_parts.append(f"[{prev_label}][v{idx}]xfade=transition=fade:duration={XFADE_DUR}:offset={cumulative_dur}[{out_label}]")
                    else:
                        d_clip = get_duration(trimmed_paths[idx-1]) - (XFADE_DUR if idx > 1 else 0)
                        cumulative_dur += d_clip - XFADE_DUR if idx > 2 else d_clip
                        out_label = f"x{idx}" if idx < len(trimmed_paths) - 1 else "out"
                        filter_parts.append(f"[{prev_label}][v{idx}]xfade=transition=fade:duration={XFADE_DUR}:offset={cumulative_dur}[{out_label}]")
                    prev_label = out_label

                # If last label isn't "out" rename
                last_out = prev_label if prev_label == "out" else f"x{len(trimmed_paths)-1}"
                if last_out != "out":
                    # Rewrite last filter to use "out"
                    filter_parts[-1] = filter_parts[-1].replace(f"[{last_out}]", "[out]")

                cmd = ["ffmpeg", "-y"] + inputs + [
                    "-filter_complex", ";".join(filter_parts),
                    "-map", "[out]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
                    tmp,
                ]
            subprocess.run(cmd, capture_output=True, timeout=120)
            concat_dur = get_duration(tmp)
            if concat_dur >= narr_dur:
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp, "-t", str(narr_dur),
                    "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                    seg_path,
                ], capture_output=True, timeout=60)
            else:
                subprocess.run([
                    "ffmpeg", "-y", "-i", tmp,
                    "-vf", f"tpad=stop_mode=clone:stop_duration={narr_dur - concat_dur},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                    "-t", str(narr_dur),
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                    seg_path,
                ], capture_output=True, timeout=60)
            try:
                os.remove(tmp)
                # Clean up trimmed clip temp files
                for idx in range(1, len(clips)):
                    tp = os.path.join(segments_dir, f"trimmed_{i:02d}_{idx}.mp4")
                    if os.path.exists(tp):
                        os.remove(tp)
            except:
                pass

        seg_durations.append(get_duration(seg_path) if os.path.exists(seg_path) else narr_dur)
    return seg_durations


def build_silent_segments(
    n_lines: int, clips_dir: str, narr_dir: str, segments_dir: str,
) -> list[float]:
    """Build silent video segments (no audio). Returns list of segment durations."""
    seg_durations = []
    for i in range(n_lines):
        seg_path = os.path.join(segments_dir, f"seg_{i:02d}.mp4")
        clip_path = os.path.join(clips_dir, f"clip_{i:02d}.mp4")
        narr_dur = get_duration(os.path.join(narr_dir, f"line_{i:02d}.mp3")) + 0.05
        clip_dur = get_duration(clip_path)

        if clip_dur >= narr_dur:
            # Clip long enough — trim to narration duration
            subprocess.run([
                "ffmpeg", "-y", "-i", clip_path, "-t", str(narr_dur),
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                seg_path,
            ], capture_output=True, timeout=60)
        else:
            # Clip too short — freeze last frame to fill remaining time (no loop/replay)
            subprocess.run([
                "ffmpeg", "-y", "-i", clip_path,
                "-vf", f"tpad=stop_mode=clone:stop_duration={narr_dur - clip_dur},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-t", str(narr_dur),
                "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
                seg_path,
            ], capture_output=True, timeout=60)

        seg_durations.append(get_duration(seg_path))
    return seg_durations


def build_intro_teasers(
    n_lines: int, narr_dir: str, clips_dir: str, segments_dir: str,
) -> float:
    """Build intro teaser clips — ONE teaser per scene (one shutter per scene).

    If there are fewer scenes than needed to fill narration duration, pause on
    the last teaser until narration finishes.
    """
    title_narr_dur = get_duration(os.path.join(narr_dir, "line_00.mp3"))
    teaser_clip_dur = 0.6  # matches shutter sfx interval

    # Pick ONE teaser per scene (exclude scene 0 which is the hook itself)
    all_clips = sorted([f for f in os.listdir(clips_dir) if f.endswith('.mp4') and not f.startswith('.')])
    if not all_clips:
        raise RuntimeError(f"No clips found in {clips_dir}")

    # One teaser per scene (use every clip, one per)
    n_teasers = len(all_clips)

    for j in range(n_teasers):
        tp = os.path.join(segments_dir, f"teaser_{j:02d}.mp4")
        clip_path = os.path.join(clips_dir, all_clips[j])
        subprocess.run([
            "ffmpeg", "-y", "-ss", "0.4",  # grab a mid-clip moment
            "-i", clip_path,
            "-t", str(teaser_clip_dur),
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an",
            tp,
        ], capture_output=True, timeout=10)

    # Concat teasers
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    tl = os.path.join(segments_dir, "teaser_list.txt")
    with open(tl, "w") as f:
        for j in range(n_teasers):
            tp = os.path.join(segments_dir, f"teaser_{j:02d}.mp4")
            if os.path.exists(tp):
                f.write(f"file '{os.path.abspath(tp)}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", tl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        teasers_path,
    ], capture_output=True, timeout=30)

    actual_teaser_dur = get_duration(teasers_path)

    # Trim teasers if they're longer than narration
    if actual_teaser_dur > title_narr_dur + 0.1:
        trimmed = teasers_path.replace(".mp4", "_trimmed.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", teasers_path, "-t", str(title_narr_dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
            trimmed,
        ], capture_output=True, timeout=30)
        if os.path.exists(trimmed):
            os.replace(trimmed, teasers_path)
            actual_teaser_dur = get_duration(teasers_path)
    # Pad teasers if they're shorter than narration — freeze on last teaser's last frame
    elif actual_teaser_dur < title_narr_dur - 0.1:
        pad_dur = title_narr_dur - actual_teaser_dur
        padded = teasers_path.replace(".mp4", "_padded.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-i", teasers_path,
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad_dur},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-t", str(title_narr_dur),
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            padded,
        ], capture_output=True, timeout=30)
        if os.path.exists(padded):
            os.replace(padded, teasers_path)
            actual_teaser_dur = get_duration(teasers_path)

    return actual_teaser_dur


def concat_silent_video(
    teasers_path: str, segments_dir: str, n_lines: int, output_dir: str,
) -> tuple[str, float]:
    """Concat teasers + segments 1-N.

    - teasers → seg_01: HARD CUT (no transition)
    - seg_N → seg_(N+1): CROSSFADE (visible blend, preserves total duration)

    Xfades happen over real content on BOTH sides — no freeze-frame extension. This means
    the tail of segment N blends with the head of segment N+1 during XFADE_DUR seconds of
    real motion. Total video shrinks by (n_transitions * XFADE_DUR) vs sum-of-segments, but
    this avoids the frozen-last-frame-before-transition artifact.
    """
    XFADE_DUR = 0.4
    XFADE_INTO_CONTENT = XFADE_DUR  # xfade entirely over real content, no freeze extension
    EXT_DUR = XFADE_DUR - XFADE_INTO_CONTENT  # 0 — no freeze extension

    all_video_path = os.path.join(output_dir, "all_video_silent.mp4")

    # List segments (skip seg_00 — line 0 is in intro)
    segs = []
    for i in range(1, n_lines):
        p = os.path.join(segments_dir, f"seg_{i:02d}.mp4")
        if os.path.exists(p):
            segs.append(p)

    if not segs:
        import shutil as _sh
        _sh.copy2(teasers_path, all_video_path)
        return all_video_path, get_duration(all_video_path)

    # Extension step — only runs if EXT_DUR > 0. With the current config (EXT_DUR = 0),
    # xfades happen entirely over real content on both sides and no freeze is inserted.
    extended_segs = []
    for idx, seg in enumerate(segs):
        if idx < len(segs) - 1 and EXT_DUR > 0:
            ext_path = os.path.join(segments_dir, f"ext_{idx:02d}.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", seg,
                "-vf", f"tpad=stop_mode=clone:stop_duration={EXT_DUR}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
                "-r", "30",
                ext_path,
            ], capture_output=True, timeout=60)
            extended_segs.append(ext_path)
        else:
            extended_segs.append(seg)

    # Step 1: Build the xfaded portion from extended segments
    if len(extended_segs) == 1:
        xfaded_path = extended_segs[0]
    else:
        inputs = []
        for vf in extended_segs:
            inputs.extend(["-i", vf])

        filter_parts = []
        for idx in range(len(extended_segs)):
            filter_parts.append(f"[{idx}:v]settb=AVTB,fps=30,format=yuv420p[v{idx}]")

        cumulative_offset = 0.0
        prev_label = "v0"
        for idx in range(1, len(extended_segs)):
            prev_dur = get_duration(extended_segs[idx - 1])
            if idx == 1:
                cumulative_offset = prev_dur - XFADE_DUR
            else:
                cumulative_offset += prev_dur - XFADE_DUR
            out_label = f"x{idx}" if idx < len(extended_segs) - 1 else "segs_out"
            filter_parts.append(
                f"[{prev_label}][v{idx}]xfade=transition=fade:duration={XFADE_DUR}:offset={cumulative_offset}[{out_label}]"
            )
            prev_label = out_label

        xfaded_path = os.path.join(output_dir, "_segs_xfaded.mp4")
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[segs_out]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
            xfaded_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=600)

    # Step 2: Hard-concat teasers + xfaded segments (no transition at teaser→seg01 boundary)
    avl = os.path.join(output_dir, "all_video_list.txt")
    with open(avl, "w") as f:
        f.write(f"file '{os.path.abspath(teasers_path)}'\n")
        f.write(f"file '{os.path.abspath(xfaded_path)}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", avl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
        all_video_path,
    ], capture_output=True, timeout=300)

    # Cleanup temps
    for p in extended_segs:
        if p != segs[-1] and os.path.exists(p):
            try: os.remove(p)
            except: pass
    if xfaded_path != extended_segs[-1] and os.path.exists(xfaded_path):
        try: os.remove(xfaded_path)
        except: pass

    return all_video_path, get_duration(all_video_path)


def build_numpy_audio(
    n_lines: int,
    narr_dir: str,
    music_path: str,
    actual_teaser_dur: float,
    seg_durations: list[float],
    total_dur: float,
    output_dir: str,
) -> tuple[str, list[float]]:
    """Build entire audio as one WAV using numpy. Returns (audio_path, seg_starts)."""
    total_samples = int(total_dur * SR) + SR
    output = np.zeros(total_samples, dtype=np.float32)

    whoosh = load_audio_samples(WHOOSH_SFX)
    shutter = load_audio_samples(SHUTTER_SFX)[:int(0.3 * SR)] * 1.2
    title_narr = load_audio_samples(os.path.join(narr_dir, "line_00.mp3"))

    # Whoosh stretched to teaser duration
    whoosh_resampled = np.interp(
        np.linspace(0, len(whoosh) - 1, int(actual_teaser_dur * SR)),
        np.arange(len(whoosh)), whoosh,
    ) * 0.3
    output[:len(whoosh_resampled)] += whoosh_resampled

    # Camera shutter clicks at 0.6s intervals
    n_teasers = max(4, int(actual_teaser_dur / 0.6))
    for j in range(n_teasers):
        pos = int(j * 0.6 * SR)
        end = min(pos + len(shutter), int(actual_teaser_dur * SR))
        output[pos:end] += shutter[:end - pos]

    # Title narration over intro
    narr_len = min(len(title_narr), int(actual_teaser_dur * SR))
    output[:narr_len] += title_narr[:narr_len] * 1.0

    # Narration lines placed at segment positions
    # Xfade between segments is 0.4s (matches concat_silent_video's XFADE_DUR) —
    # each transition shrinks timeline by 0.4s so we subtract that from cumulative position
    XFADE_INTO_CONTENT = 0.4
    intro_end = int(actual_teaser_dur * SR)
    current_pos = intro_end
    seg_starts = [0.0]  # line 0 at position 0 (in intro)
    for i in range(1, n_lines):
        seg_starts.append(current_pos / SR)
        narr = load_audio_samples(os.path.join(narr_dir, f"line_{i:02d}.mp3"))
        end_pos = min(current_pos + len(narr), total_samples)
        output[current_pos:end_pos] += narr[:end_pos - current_pos] * 1.0
        # Subtract overlap for non-last segments (those have xfade into next)
        overlap = XFADE_INTO_CONTENT if i < n_lines - 1 else 0
        current_pos += int((seg_durations[i] - overlap) * SR)

    # Background music (starts after intro)
    music = load_audio_samples(music_path)
    ml = min(len(music), total_samples - intro_end)
    output[intro_end:intro_end + ml] += music[:ml] * 0.05

    # Normalize and write
    max_val = np.max(np.abs(output))
    if max_val > 32000:
        output = output * (32000 / max_val)
    output = np.clip(output, -32768, 32767).astype(np.int16)

    audio_path = os.path.join(output_dir, "full_audio.wav")
    with wave.open(audio_path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(output[:int(total_dur * SR)].tobytes())

    return audio_path, seg_starts


def combine_video_audio(video_path: str, audio_path: str, output_dir: str) -> str:
    """Combine silent video + WAV audio into one MP4."""
    combined = os.path.join(output_dir, "combined.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
        "-map", "0:v", "-map", "1:a", "-movflags", "+faststart",
        combined,
    ], capture_output=True, timeout=300)
    return combined


def add_subtitles(
    combined_path: str,
    word_data: list[dict],
    seg_starts: list[float],
    output_dir: str,
) -> str:
    """Add karaoke subtitles. Returns final video path."""
    from apps.orchestrator.pipeline import _write_karaoke_ass

    all_words = [
        (w["word"], seg_starts[w["line"]] + w["start"], seg_starts[w["line"]] + w["end"])
        for w in word_data
        if w["line"] < len(seg_starts)
    ]

    ass_path = os.path.join(output_dir, "karaoke.ass")
    _write_karaoke_ass(ass_path, all_words, is_long_form=False)

    final_path = os.path.join(output_dir, "final.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", combined_path,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart",
        final_path,
    ], capture_output=True, timeout=300)

    if not os.path.exists(final_path):
        raise RuntimeError("No final video produced")

    return final_path


async def update_database(
    run_id: int, channel_id: int, title: str, output_dir: str, db_url: str,
    tags: list[str] | None = None,
):
    """Update database with completed video."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sql_text

    if tags is None:
        tags = ["shorts", "viral"]

    caption = f"{title}\n\n" + " ".join(f"#{t}" for t in tags)
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.execute(
            sql_text("UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review' WHERE id = :rid"),
            {"rid": run_id},
        )
        await conn.execute(
            sql_text("UPDATE content_bank SET status = 'generated' WHERE run_id = :rid"),
            {"rid": run_id},
        )
        await conn.execute(
            sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, 'rendered_video', :c)"),
            {"rid": run_id, "cid": channel_id, "c": json.dumps({"path": f"output/run_{run_id}/final.mp4"})},
        )
        await conn.execute(
            sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, 'publish_metadata', :c)"),
            {"rid": run_id, "cid": channel_id, "c": json.dumps({"title": title, "description": caption, "tags": tags, "privacy": "private"})},
        )
    await engine.dispose()
