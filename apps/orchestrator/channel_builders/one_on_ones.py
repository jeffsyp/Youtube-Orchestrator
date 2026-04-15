"""One on Ones For Fun channel builder — cross-franchise "Who would win" battles.

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

CHANNEL_ID = 21
VOICE_ID = "JjsQrIrIBD6TZ656NQfi"  # One on Ones voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "epic", "five_armies.mp3")
TAGS = ["who would win", "vs", "battle", "one on one", "shorts", "viral"]

ART_STYLE = "Simple colorful cartoon illustration — bright colors, clean lines, expressive characters, solid backgrounds. Fun and friendly."

IMAGE_RULES = """ART STYLE:
- Simple crude cartoon with thick wobbly BLACK outlines and flat solid colors
- Like a funny webcomic — NO gradients, NO shading, NO glow effects
- Flat color fills only. Stubby proportions. Exaggerated expressions.
- The crude style keeps characters CONSISTENT across scenes — same simple design every time
- NOT photorealistic, NOT detailed — crude and fun

CHARACTER ACCURACY — CRUDE DOES NOT MEAN UNRECOGNIZABLE:
- Use EXACT character names (Link from Zelda, Cloud from Final Fantasy, Iron Man from Marvel, etc.)
- Characters must be INSTANTLY recognizable even in crude style — signature weapons, colors, silhouettes
- Each character must look the SAME in every single scene — same proportions, same outfit, same weapon
- gpt-image knows these characters by name — use names not descriptions

BATTLE COMPOSITION:
- Show BOTH fighters in every battle scene — never just one
- The fighters should be actively FIGHTING — mid-punch, dodging, using signature moves
- Show environmental destruction as collateral damage (craters, broken buildings, debris)
- SHOW THE IMPACT: When an attack lands, show the fist/sword/blast connecting AND the opponent flying back, crashing, or reacting. Characters don't just disappear — they get sent flying with spiral eyes, embedded in walls, or knocked across the scene.

SCENE FLOW — EACH SCENE MUST CONNECT TO THE NEXT:
- If scene N shows Character A charging an attack, scene N+1 MUST show that attack landing or being blocked — not a completely new composition
- The defeated character must be VISIBLE in the defeat scene — not just gone
- Think of it like a comic strip: each panel follows from the last

EVERY PROMPT MUST:
- Start with "Simple crude cartoon with thick black outlines and flat colors."
- Show both characters clearly identifiable by name
- Describe the SPECIFIC action with the RESULT visible
- End with "NO text anywhere." """

SCRIPT_PROMPT = """Write a narration script for a One on Ones For Fun battle video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST announce the matchup: "What if [Character A] fought [Character B]?" — this IS the title. Shorts viewers don't see titles.
- Line 2: Brief intro of Fighter A — ONE signature ability or feat that makes them dangerous
- Line 3: Brief intro of Fighter B — ONE signature ability or feat
- Lines 4-7: The fight plays out blow by blow — each line is a specific exchange
  - Show each fighter using their SIGNATURE MOVES by name (Kamehameha, Repulsor Blast, Mjolnir throw, etc.)
  - One fighter gains an advantage, then the other counters
  - Include collateral damage to the environment (buildings falling, craters forming)
- Lines 8-9: The climax — one fighter pulls out their ULTIMATE move
- Line 10: Clear winner declared with a devastating final line
- You MUST declare a winner — no cop-out "they'd tie" endings
- The winner should win in a dramatic, satisfying way — not just "they punch harder"
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line UNDER 15 words
- Hype energy — like a sports commentator calling the fight of the century
- Cross-franchise ONLY — NOT anime vs anime

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT VS TITLE"}}"""


async def build_one_on_ones(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full One on Ones For Fun video build using unified pipeline."""
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
        voice_settings={"stability": 0.3, "similarity_boost": 0.8, "speed": 1.15},
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
    logger.info("one on ones complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
