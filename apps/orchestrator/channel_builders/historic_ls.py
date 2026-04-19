"""Historic Ls channel builder — history's biggest fails as dramatic stories.

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

CHANNEL_ID = 30
VOICE_ID = "EOVAuWqgSZN2Oel78Psj"  # Historic Ls voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "epic", "epic_unease.mp3")
TAGS = ["historic ls", "history", "fails", "comedy", "shorts", "viral"]

ART_STYLE = "Ink wash cartoon illustration with exaggerated caricature features — crosshatched shading, sepia and muted tones, hand-drawn editorial style. Characters with oversized heads and expressive faces. Historical scenes with a humorous twist."

IMAGE_RULES = """ART STYLE:
- Simple crude cartoon with thick black outlines and flat colors
- Characters with oversized heads, exaggerated bug-eyed expressions
- Historical figures should be RECOGNIZABLE caricatures — exaggerated but identifiable
- Period-appropriate clothing drawn in crude cartoon style
- Napoleon: short, bicorne hat, hand in jacket. Cleopatra: Egyptian headdress. Caesar: toga, laurel wreath.

THE COMEDY IN THE ART:
- Facial expressions tell the story — overconfident smirks that become wide-eyed horror
- Show the CONTRAST between confidence and failure visually
- The "L" moment should be the most exaggerated image — jaw dropped, eyes popping, sweat drops
- Other characters' reactions should be visible — shock, laughter, pointing

EVERY PROMPT MUST:
- Start with "Simple crude cartoon with thick black outlines and flat colors."
- Show the specific historical figure with exaggerated but recognizable features
- Match the exact moment described in the narration — overconfident OR devastated
- End with "Crude cartoon style. NO text anywhere." """

SCRIPT_PROMPT = """Write a narration script for a Historic Ls video — history's biggest fails.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST hook with the shocking outcome: "In 1999, a man was offered Google for one million dollars. He said no." — the L is revealed immediately. Shorts viewers don't see titles.
- Lines 2-4: The SETUP — everything was going great. The person was confident, powerful, on top of the world. Make the viewer understand WHY they made the decision.
- Lines 5-7: The ESCALATION — things start going wrong. The cracks appear. The consequences unfold.
- Lines 8-9: The DEVASTATING PUNCHLINE — the final result. How bad did it actually get?
- Last line: A one-liner that puts the L into perspective. "That company is now worth two trillion dollars." or "He spent the rest of his life pretending it never happened."
- This is a STORY, not a list of facts. Setup → escalation → punchline.
- Use REAL historical events and REAL people — not made up scenarios
- Include SPECIFIC numbers, dates, and names — they make it feel real and shocking
- The tone is dramatic comedy — the narrator can't believe this actually happened
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- The comedy comes from the SCALE of the L — how badly someone messed up

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_historic_ls(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Historic Ls video build using unified pipeline."""
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
        voice_settings={"stability": 0.5, "similarity_boost": 0.8, "speed": 1.05},
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
    actual_teaser_dur = build_intro_teasers(n_lines, narr_dir, clips_dir, segments_dir, line_clip_map)

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
    logger.info("historic ls complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
