"""Skeletorinio channel builder — "What if you brought [item] to [era]" videos.

Toy skeletorinio character with googly eyes in historical scenarios.
Uses unified pipeline: style anchor → sub-actions → GPT images → Grok animation → chaining.
"""
import asyncio
import json
import os
import re

import structlog

from apps.orchestrator.channel_builders.shared import (
    generate_narration_with_timestamps,
    generate_and_animate_scenes,
    build_segments_from_clip_map,
    build_intro_teasers,
    concat_silent_video,
    build_numpy_audio,
    combine_video_audio,
    add_subtitles,
    update_database,
)

logger = structlog.get_logger()

# Channel-specific constants
CHANNEL_ID = 18
VOICE_ID = "TxGEqnHWrfWFTfGW9XjX"  # Josh
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "skeletorinio_theme.mp3")
SKELETON_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "skeletorinio.png")
TAGS = ["skeletorinio", "what if", "skeletorinio", "history", "shorts", "viral", "comedy"]

ART_STYLE = "Photorealistic world with cinematic golden hour lighting. The main character is a FULL-SIZE adult human-height 3D animated plastic skeletorinio with big googly cartoon eyes, gold chain necklace, and sunglasses pushed up on forehead. He is the same height as the humans around him — NOT a miniature toy. He looks like a stylized 3D cartoon character placed into a real photograph."

IMAGE_RULES = """RULES — FOLLOW THESE EXACTLY:
- The main character is a FULL-SIZE adult human-height 3D animated plastic skeletorinio with big googly cartoon eyes, gold chain necklace, and sunglasses on forehead. He is the SAME HEIGHT as real humans — NOT a miniature toy.
- A reference image of the skeletorinio is provided — match this character exactly but at HUMAN SCALE
- For EVERY scene with the skeletorinio, start the prompt with: "A full-size human-height 3D animated skeletorinio character with gold chain and sunglasses on forehead"
- The WORLD is PHOTOREALISTIC — real-looking buildings, landscapes, people, objects. Cinematic golden hour lighting.
- The skeletorinio is the ONLY non-realistic element. Everything else looks like a photograph.
- Other people (kings, soldiers, workers, merchants) must be described as PHOTOREALISTIC HUMANS, NOT cartoons, NOT skeletorinios
- Do NOT say "toy" or "miniature" or "figurine" — the skeletorinio is HUMAN-SIZED
- Every prompt must end with "Photorealistic world. NO text anywhere."
- Each prompt should describe ONE clear scene matching the narration line"""

SCRIPT_PROMPT = """Write a narration script for a Skeletorinio YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 is the HOOK — it MUST state the concept directly so a viewer with ZERO title context knows what the video is about. Shorts viewers don't see the title.
  - THE HOOK SHOULD BASICALLY MIRROR THE TITLE AS A "What if..." QUESTION.
  - TITLE: "WHAT IF YOU ACCIDENTALLY SUMMONED A DEMON YOU COULDN'T SEND BACK" → HOOK: "What if you accidentally summoned a demon you couldn't send back?"
  - TITLE: "WHAT IF YOU ACCIDENTALLY BECAME THE CHOSEN ONE" → HOOK: "What if you accidentally pulled a sword from a stone?" (close paraphrase — the sword-from-stone IS the becoming-chosen-one moment)
  - TITLE: "WHAT IF YOU BROUGHT A JETPACK TO ANCIENT ROME" → HOOK: "What if you brought a jetpack to Ancient Rome?"
- BAD HOOK (skips the concept): TITLE is "SUMMONED A DEMON" but line 1 says "What if you read one line from an old book out loud?" — a viewer has no idea what this is about, no context for the demon that appears in line 2
- The hook must LABEL the concept — use the specific noun from the title (demon, sword, jetpack, dragon, time portal, genie, etc.) in line 1, not a vague setup
- If the title says "ACCIDENTALLY X" — the hook must include "accidentally" and name what X is
- The story is about the SITUATION — the skeletorinio is the person doing it. The situation is the star.
- CHOOSE THE RIGHT STRUCTURE for the concept:
  A) DAY-BY-DAY ESCALATION — use when the concept spans time (arriving somewhere new, starting a job, entering a new world):
     - Lines include "Day 1:", "Day 2:", "Week 2:", "Month 3:" as part of the narration
     - Time jumps ACCELERATE — Day 1, Day 2, Day 3, then suddenly "Week 2" or "Year 5" to show things spiraling
     - Each time jump shows a BIGGER consequence
     - GOOD fit: "What if you brought a lighter to the Ice Age" → Day 1: discovery, Day 3: worshipped, Month 2: civilization built
     - GOOD fit: "What if you accidentally became the chosen one" → Day 1: sword pull, Week 2: crowned king, Month 3: abolished feudalism
  B) REAL-TIME ESCALATION — use when the concept is a single moment that spirals (one interaction, one event, one attempt):
     - No day markers, just rapid beat-by-beat escalation within one scene/event
     - GOOD fit: "What if Poseidon became a plumber" → shows up, touches pipe, bathroom floods, building floods, city floods
     - GOOD fit: "What if you tried to return something on Black Friday" → walk in, line is insane, chaos erupts
  Pick whichever structure fits the concept naturally. Day-by-day is the default for concepts that span time. Real-time is for single-moment chaos.
- The ending must GO ABSOLUTELY INSANE:
  - NOT "people get mad" or "the authorities arrive" — that's boring
  - YES: you become president, you buy an island, you accidentally start a religion, you get launched into space, you break reality, the simulation crashes, the gods revolt
  - The ending should make viewers replay the video. Realistic endings are BORING — go full absurd comedy.
- The LAST LINE should be a punchline that lands hard — funny, unexpected, satisfying. Often a callback to something mundane from the premise.
- Second person narration ("You walk in...", "You show...", "You realize...")
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, fast-paced, funny
- Do NOT mention skeletorinio, bones, or the character's appearance — just tell the story

REFERENCE EXAMPLE (the Chosen One — this was a hit, study its shape):
Title: WHAT IF YOU ACCIDENTALLY BECAME THE CHOSEN ONE
Narration:
  0: What if you accidentally pulled a sword from a stone?
  1: Day 1: You were just curious. The sword slides out with a hum.
  2: Day 2: A dragon lands in front of you and bows. You did not ask for this.
  3: Day 3: Wizards appear from thin air. They are all weeping.
  4: Week 1: You are crowned king of a realm you cannot pronounce.
  5: Month 2: The dragon is your ride now. You sleep in a floating castle.
  6: Year 1: Prophecies about you are carved into mountains.
  7: You still don't know what the sword does.

Why this worked:
- Universal mythology (Excalibur) — zero-context entry
- "You" is a REACTOR — things happen TO you (dragon bows, wizards weep, prophecies carve themselves)
- Time jumps ACCELERATE: Day 1, Day 2, Day 3, Week 1, Month 2, Year 1
- CONCRETE visuals only (sword, dragon, crown, castle, mountains) — never abstract
- Anticlimactic punchline: "You still don't know what the sword does" — leaves mystery
- 8 lines, each under 15 words

Aim for this shape. Match it in structure and energy.

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_skeletorinio(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Skeletorinio video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])

    narr_dir = os.path.join(output_dir, "narration")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Write script if not provided ───
    if not narration_lines:
        await _update_step("writing script")
        from packages.clients.claude import generate as claude_generate
        brief = concept.get("brief", title)
        resp = claude_generate(
            prompt=SCRIPT_PROMPT.format(title=title, brief=brief),
            max_tokens=2000,
        )
        json_match = re.search(r'\{.*\}', resp, re.DOTALL)
        if json_match:
            script_data = json.loads(json_match.group())
            narration_lines = script_data.get("narration", [])
            if script_data.get("title"):
                title = script_data["title"]
        if not narration_lines:
            raise ValueError("Failed to generate narration script")

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
    )

    # ─── STEP 3: Generate style anchor using skeletorinio reference IN the scene ───
    from openai import AsyncOpenAI
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    anchor_path = os.path.join(images_dir, "style_anchor.png")
    if not os.path.exists(anchor_path) and os.path.exists(SKELETON_REF):
        # Generate the skeletorinio IN the first scene — this becomes the style anchor
        # so all subsequent scenes share the same era, lighting, and character scale
        _oai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
        brief = concept.get("brief", title)
        era = concept.get("era", "")
        era_part = f"STRICT ERA: {era}. All humans in period-accurate clothing. NO modern clothing, NO modern objects. " if era else "Historical time period — NOT modern day. "
        _ref = open(SKELETON_REF, "rb")
        try:
            _resp = await _oai.images.edit(
                model="gpt-image-1.5",
                image=_ref,
                prompt=f"{era_part}Place this exact skeletorinio character (same size, same gold chain, same sunglasses, same googly eyes) into the scene for this video: {title}. {brief[:200]}. {narration_lines[0] if narration_lines else ''}. The skeletorinio is FULL ADULT HUMAN HEIGHT — same size as real people around him. Photorealistic world with cinematic golden hour lighting. NO text anywhere.",
                size="1024x1536",
                quality="medium",
                input_fidelity="high",
            )
            _ref.close()
            if _resp.data and _resp.data[0].b64_json:
                import base64 as _b64
                with open(anchor_path, "wb") as _f:
                    _f.write(_b64.b64decode(_resp.data[0].b64_json))
                logger.info("style anchor generated from skeletorinio ref in scene")
        except Exception as _e:
            try: _ref.close()
            except: pass
            import shutil
            shutil.copy2(SKELETON_REF, anchor_path)
            logger.warning("style anchor fallback to bare skeletorinio ref", error=str(_e)[:80])

    # ─── STEP 4: Unified pipeline — uses style anchor (skeleton IN scene) for all edits ───
    clips_dir, clip_paths, n_clips, line_clip_map = await generate_and_animate_scenes(
        narration_lines, concept, IMAGE_RULES, ART_STYLE, output_dir, _update_step, run_id=run_id,
    )

    # ─── STEP 4: Build segments from clip map ───
    await _update_step("building video")
    style_anchor = os.path.join(output_dir, "images", "style_anchor.png")
    seg_durations = build_segments_from_clip_map(
        n_lines, line_clip_map, clips_dir, narr_dir, segments_dir, style_anchor,
    )

    # ─── STEP 5: Intro, audio, subtitles ───
    await _update_step("building intro")
    actual_teaser_dur = build_intro_teasers(n_lines, narr_dir, clips_dir, segments_dir)

    await _update_step("concatenating")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, segments_dir, n_lines, output_dir)

    await _update_step("building audio")
    audio_path, seg_starts = build_numpy_audio(
        n_lines, narr_dir, MUSIC_PATH, actual_teaser_dur, seg_durations, total_dur, output_dir,
    )

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, CHANNEL_ID, title, output_dir, db_url, TAGS)
    logger.info("skeletorinio complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
