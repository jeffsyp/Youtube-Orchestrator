"""NightNightShorts channel builder — anime crossover "what if" videos.

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

CHANNEL_ID = 28
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
TAGS = ["anime", "what if", "shorts", "viral", "nightnightshorts"]

ART_STYLE = "Anime art style with detailed expressive characters, warm colors, and clean linework. Characters drawn in recognizable anime proportions with large expressive eyes, detailed hair, and accurate costumes. Backgrounds are detailed and painterly."

IMAGE_RULES = """ANIME CHARACTERS:
- Use actual character names (Zoro from One Piece, Gon from Hunter x Hunter, etc.)
- gpt-image knows these characters by name — use names not descriptions
- Characters must be RECOGNIZABLE — signature hair, outfit, weapons

FIGHT SCENES — SHOW THE STARTING POINT:
- Each image shows the BEGINNING of the action, NOT the result
- The ANIMATION creates the impact/aftermath
- Both characters visible in every fight scene

COMEDY IN EVERY IMAGE:
- Characters should have EXAGGERATED expressions — bug eyes when shocked, sweat drops when nervous, smug grins when winning
- The visiting character should look out of place — confused by the world's rules, using their powers in stupid ways
- Background characters should be REACTING — jaw drops, pointing, running away, filming on phones
- Physical comedy: characters embedded in walls, crater-shaped holes, comically oversized attacks

MOOD MATCHING:
- Calm lines = calm scene. Only show fighting when narration describes a fight.
- BUT even calm scenes should be funny — the character doing something dumb, confused, or out of place
"""

SCRIPT_PROMPT = """Write a narration script for a NightNightShorts anime crossover video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the topic: "What if [character] was in [anime]?"
- Line 2 goes STRAIGHT into the action
- 6-8 narration lines, ~20-30 seconds. SHORTER IS BETTER.
- Each line UNDER 15 words
- Punchy, fast-paced, funny

THE COMEDY:
- The visiting character should be CONFUSED by the world's rules or do something DUMB with their powers
- Include at least one moment where the character fails hilariously before succeeding
- Background characters should react — the world notices this doesn't belong
- Physical comedy: someone gets sent through a wall, an attack is comically overpowered, someone uses the wrong move
- The punchline should be something ABSURD — banned from the anime, breaks the universe, the show gets cancelled
- Think of it like: what would ACTUALLY happen if this character showed up? The chaos, the confusion, the collateral damage

- The ending must GO COMPLETELY INSANE
- Reference specific attacks, abilities, and locations by name

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT TITLE"}}"""


async def build_nightnight(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full NightNightShorts video build using unified pipeline."""
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
        voice_settings={"stability": 0.4, "similarity_boost": 0.8, "speed": 1.1},
    )

    # ─── STEP 3: Unified pipeline — style anchor + sub-actions + chaining ───
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
    logger.info("nightnight complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
