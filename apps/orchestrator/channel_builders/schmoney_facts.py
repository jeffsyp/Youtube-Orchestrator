"""Schmoney Facts channel builder — money, pricing, flex, and scam story shorts.

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

ART_STYLE = "GTA loading screen art style — bold illustrated characters, saturated colors, slightly exaggerated proportions, flashy commercial energy. Money is the star whether the scene is luxury, debt, pricing, gambling, banking, shopping, or pure flex."

IMAGE_RULES = """ART STYLE:
- Bold illustrated GTA loading screen energy — saturated colors, confident silhouettes, exaggerated expressions
- Money is the subject of every scene, but NOT every concept is a mansion/jet fantasy
- Use settings that fit the specific money idea: bank lobby, casino floor, grocery aisle, airport kiosk, private hangar, yacht dock, payday storefront, checkout counter, mansion driveway, vault room, gas station, trading floor

MONEY VISUALIZATION:
- Show the money mechanic physically and literally — cash bricks, vault stacks, grocery bags, poker chips, gold bars, supercars, fuel trucks, checkout counters, casino cages, tax piles, loan traps, yachts, jets
- Include one dominant proof prop that makes the cost or flex instantly legible on mute
- If the concept is about markup, fees, taxes, or profit, show both the payer and the winner whenever possible
- Do NOT default to the same house → supercar → yacht → jet escalation unless the narration is specifically a flex fantasy

EVERY PROMPT MUST:
- Start with "Bold illustrated GTA loading screen art style."
- Make the money idea instantly legible on mute
- Show the main subject interacting with the cost, profit, luxury item, trap, or payout
- Include SPECIFIC objects that match the narration (private jet stairs, grocery cart, popcorn bucket, ATM, casino chips, Rolex box, yacht deck, fuel hose, mansion gate, tax avalanche)
- End with "Illustrated not photographed. NO text anywhere." """

SCRIPT_PROMPT = """Write a narration script for a Schmoney Facts video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the exact money premise clearly. If there is a company, object, scam, salary, or dollar amount, say it immediately.
- Line 2 goes straight into the first concrete number or money mechanic — no slow setup.
- Follow the concept instead of forcing one template:
  - If it is a flex fantasy, escalate the spending.
  - If it is a trap, escalate the damage.
  - If it is a business reveal, escalate the profit or markup.
  - If it is a salary / luxury / tax video, escalate the real-world cost.
- Use SPECIFIC dollar amounts, percentages, salaries, hourly burn rates, taxes, fees, profits, or totals in as many lines as possible.
- Use SPECIFIC brands / objects when they help the visual: "a Gulfstream G650" not "a private jet", "movie theater popcorn" not "snacks", "a Rolex Daytona" not "a watch".
- Every line must add a NEW beat. No repeating the same mortgage / fee / loan point in slightly different words.
- Money topics can include: hidden fees, salaries, taxes, rich flexes, luxury operating costs, scams, business margins, pricing tricks, casinos, investing, or weird cash logistics.
- Tone depends on the concept: hype, disgust, disbelief, envy, admiration, or horror. Not every video should sound angry.
- The ending should hit the SHARPEST number, consequence, or reaction — the line people replay.
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place.
- Each line = one scene = one image
- Each line UNDER 15 words
- If the concept is about "you", use second person. Otherwise name the company, billionaire, or object directly.

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
    actual_teaser_dur = build_intro_teasers(
        n_lines, narr_dir, clips_dir, segments_dir, line_clip_map,
        channel_id=CHANNEL_ID, concept=concept,
    )

    await _update_step("concatenating")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, segments_dir, n_lines, output_dir)

    await _update_step("building audio")
    audio_path, seg_starts = build_numpy_audio(
        n_lines, narr_dir, MUSIC_PATH, actual_teaser_dur, seg_durations, total_dur, output_dir,
        channel_id=CHANNEL_ID, concept=concept,
    )

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, CHANNEL_ID, title, output_dir, db_url, TAGS)
    logger.info("schmoney facts complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
