"""Schmoney Facts channel builder — "What if you had X money" escalation videos.

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

CHANNEL_ID = 31
VOICE_ID = "EOVAuWqgSZN2Oel78Psj"  # Schmoney Facts voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "upbeat", "retrofuture_clean.mp3")
TAGS = ["schmoney facts", "money", "finance", "what if", "rich", "shorts", "viral"]

ART_STYLE = "GTA loading screen art style — bold illustrated characters, saturated colors, slightly exaggerated proportions, urban and flashy. Money, luxury, and hustle energy."

IMAGE_RULES = """ART STYLE:
- Simple crude cartoon with thick black outlines and flat colors
- Urban, flashy, money energy — gold chains, stacks of cash, luxury cars, mansions, private jets
- Characters with exaggerated expressions — jaw drops, dollar sign eyes, flexing poses
- Backgrounds should show wealth escalation — apartment → penthouse → mansion → private island → space station

MONEY VISUALIZATION:
- SHOW the money and luxury items specifically — don't just describe them
- Stacks of cash, gold bars, diamond jewelry, supercars, yachts, private jets should be visible
- The spending should be VISUALLY escalating — each scene more extravagant than the last

EVERY PROMPT MUST:
- Start with "Simple crude cartoon with thick black outlines and flat colors."
- Show the main character spending money or surrounded by wealth
- Include SPECIFIC luxury items that match the narration (Lamborghini, Rolex, yacht, etc.)
- Show the escalation visually — early scenes modest, later scenes insane
- End with "Crude cartoon style. NO text anywhere." """

SCRIPT_PROMPT = """Write a narration script for a Schmoney Facts video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the scenario with a specific dollar amount: "What if you had 200 billion dollars for 24 hours?" — this IS the title. Shorts viewers don't see titles.
- Line 2 goes STRAIGHT into spending — no setup, no "imagine this"
- ESCALATING SPENDING — each line is a bigger, crazier purchase:
  - Start modest: pay off student loans, buy a house ($500K)
  - Then flex: buy a Lamborghini, a yacht, a private jet ($1M-$50M)
  - Then insane: buy an NFL team, an island, a country's GDP ($1B+)
  - Then completely unhinged: buy the moon, fund a Mars colony, purchase the entire stock market
- SPECIFIC dollar amounts in every line — "$47 million for a private island" not "you buy an island"
- SPECIFIC brand names — "a Bugatti Chiron" not "a fancy car", "a Patek Philippe" not "a nice watch"
- The spending must be mathematically reasonable for the starting amount
- The ending must GO COMPLETELY INSANE — you run out of money and realize you still owe taxes, or you bought so much you accidentally crashed the economy, or you own so much real estate you're technically a country
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- Tone: excited, flexing, "I can't believe I'm doing this"

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_schmoney_facts(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Schmoney Facts video build using unified pipeline."""
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
    logger.info("schmoney facts complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
