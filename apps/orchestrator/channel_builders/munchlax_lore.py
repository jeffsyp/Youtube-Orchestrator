"""Munchlax Lore channel builder — POV Pokemon IRL videos.

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

CHANNEL_ID = 13
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam (energetic)
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "epic", "hero_theme.mp3")
TAGS = ["pokemon", "pov", "what if", "pokemon irl", "shorts", "viral"]

ART_STYLE = "Simple crude cartoon with thick black outlines and flat colors, like Cyanide and Happiness webcomic style. Stubby proportions, simple round eyes, flat color fills."

IMAGE_RULES = """ART STYLE:
- Simple crude cartoon with thick wobbly outlines and flat colors
- Like a funny webcomic or doodle — deliberately simple and charming
- POV first-person perspective — the viewer's hands should be visible when it makes sense
- The ENVIRONMENT must be a real-world location (backyard, street, highway, bathroom, kitchen) but drawn in crude cartoon style

POKEMON ACCURACY — CRUDE DOES NOT MEAN INACCURATE:
- Use the EXACT Pokemon name (Pikachu, Charizard, Snorlax, Gyarados, etc.)
- EVERY Pokemon must have ALL of its signature features even in crude style:
  - Pikachu: yellow body, red circle cheeks, black-tipped pointy ears, lightning bolt shaped tail, small and round
  - Charizard: orange body, blue inner wings, flame on tail tip, horn on head, dragon-like
  - Snorlax: massive round body, dark blue-green, cream belly, closed sleepy eyes
  - Gyarados: blue serpentine body, whiskers, fanged mouth, spiky crown, massive
  - Magikarp: orange fish, big dumb round eyes, yellow fins, whiskers, useless expression
- A viewer must INSTANTLY know which Pokemon it is from the silhouette alone
- Scale matters: Charizard towers over people, Pikachu fits in your hands, Snorlax fills a room
- Crude style = wobbly lines and flat colors, NOT missing features or wrong colors

EVERY PROMPT MUST:
- Start with "Simple crude cartoon with thick wobbly outlines and flat colors."
- Include a specific real-world setting drawn in crude cartoon style
- Show the Pokemon DOING the action described in the narration — not just standing there
- End with "Crude cartoon style. NO text anywhere."
- Describe the human reaction in the scene (people running, screaming, staring) with exaggerated cartoon expressions"""

SCRIPT_PROMPT = """Write a narration script for a Munchlax Lore POV Pokemon IRL video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the scenario: "POV: You find a [Pokemon] in your [location]" — this IS the title. Shorts viewers don't see video titles so line 1 gives them context.
- Line 2 goes STRAIGHT into the action — what happens next
- Second person narration — "You reach for it...", "It looks at you...", "You call 911..."
- The Pokemon acts like it WOULD in real life — Charizard sets things on fire, Snorlax blocks traffic, Gyarados destroys the lake, Pikachu shorts out your electronics
- ESCALATION is everything — each line makes it worse/crazier
- Include REAL-WORLD consequences — neighbors call police, news crews show up, the military arrives, the president gets involved
- If the Pokemon EVOLVES or TRANSFORMS, dedicate a line to the moment itself: "It starts glowing." or "It evolves." — a short dramatic beat before the reveal. The transformation is the payoff, give it space.
- Every line must show a DIFFERENT angle or location — never two consecutive lines with the same person in the same pose from the same angle. Move through rooms, switch perspectives, show different people reacting.
- The ending must GO COMPLETELY INSANE — you ride it to work, it becomes a city mascot, the government tries to capture it, you become a real Pokemon trainer, you accidentally start a Pokemon uprising
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, dramatic, funny
- Reference SPECIFIC Pokemon moves and abilities by name (Thunderbolt, Flamethrower, Hyper Beam, etc.)

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_munchlax_lore(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Munchlax Lore video build using unified pipeline."""
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
    logger.info("munchlax lore complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
