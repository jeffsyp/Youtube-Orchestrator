"""Deep We Go channel builder — "What happens to your body if..." videos.

Glass person character that deteriorates over time.
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

CHANNEL_ID = 27
VOICE_ID = "TxGEqnHWrfWFTfGW9XjX"  # Josh (deep)
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
GLASS_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "deep_we_go_glass.png")
TAGS = ["deep we go", "what if", "body", "science", "health", "shorts", "viral"]

ART_STYLE = "Photorealistic environments with a stylized transparent glass person character. The glass person is an adult male made of clear blue-green glass with visible skeleton, organs, and blood vessels. Heart glows red, brain glows blue, kidneys glow orange. Cinematic dramatic lighting."

IMAGE_RULES = """THE CHARACTER:
- A transparent glass person — adult male, tall, made of clear blue-green glass
- A reference image of the glass person is provided — match this character exactly
- You can see the skeleton, organs, and blood vessels inside the glass body
- Heart glows red, brain glows blue, kidneys glow orange
- As deterioration progresses across scenes:
  - Early stages: glass still clear, organs bright, standing upright
  - Middle stages: small cracks in glass, some organs dimming, hunching over
  - Late stages: major cracks, glass cloudy, most organs dark, collapsing
  - Final stage: shattered glass, all organs dark, collapsed

REAL LIFE SITUATIONS:
- Do NOT just show the glass person standing in a dark room
- Put the glass person in REAL LIFE scenarios showing how the condition affects daily life
- The SETTING tells the HUMAN story, the GLASS BODY tells the MEDICAL story
- Photorealistic environments, stylized glass character

RULES:
- Every prompt MUST describe "this exact transparent glass person" with deterioration details
- Describe the glass condition (clear/cracked/cloudy/shattered)
- Describe which organs are affected (bright/dim/dark)
- Describe the posture and WHAT THEY ARE DOING in a real-life setting
- Each prompt must end with "Photorealistic environment. NO text." """

SCRIPT_PROMPT = """Write a narration script for a Deep We Go YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST state the topic as a question: "What happens to your body if [extreme scenario]?" — this IS the title. Shorts viewers don't see video titles so line 1 gives them context.
- Line 2 goes STRAIGHT into the first time period (Hour 12, etc.) — NO story intro, NO setup
- Hour-by-hour progression: Hour 12 → 24 → 48 → 72 → 96 → 120 → 168
- 6-8 narration lines, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line describes what happens to the BODY at that stage
- Include specific medical/biological details that sound shocking
- Each line UNDER 15 words
- Tone: dramatic, slightly scary, educational

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT TITLE"}}"""


async def build_deep_we_go(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Deep We Go video build using unified pipeline."""
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
        voice_settings={"stability": 0.6, "similarity_boost": 0.8, "speed": 0.95},
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
    logger.info("deep we go complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
