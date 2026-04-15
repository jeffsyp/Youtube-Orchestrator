"""SpookLand channel builder — POV horror "What if you..." videos.

COLD OPEN — no intro teasers, narration starts immediately.
Uses unified pipeline: style anchor → sub-actions → GPT images → Grok animation → chaining.
"""
import asyncio
import json
import os
import re
import subprocess
import wave

import numpy as np
import structlog

from apps.orchestrator.channel_builders.shared import (
    generate_narration_with_timestamps,
    generate_and_animate_scenes,
    build_segments_from_clip_map,
    combine_video_audio,
    add_subtitles,
    update_database,
    get_duration,
    load_audio_samples,
    SR,
)

logger = structlog.get_logger()

CHANNEL_ID = 19
VOICE_ID = "jtE6dbPUTt2kchN89Uej"  # SpookLand voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "unseen_horrors.mp3")
TAGS = ["spookland", "horror", "creepy", "pov", "scary", "shorts", "viral"]

ART_STYLE = "Detailed black and white manga illustration with intricate crosshatching and linework. Stark monochrome with occasional red accents. Unsettling atmosphere with spiral motifs and exaggerated expressions. Japanese horror manga aesthetic like Junji Ito."

IMAGE_RULES = """ART STYLE:
- Simple crude cartoon with thick black outlines and flat colors — horror drawn in a deliberately crude, unsettling style
- POV first-person perspective — the viewer IS the character. Show what THEY would see.
- Dark, desaturated colors with heavy shadows
- The crude style makes the horror MORE unsettling, not less

VISUAL STORYTELLING — THE VIEWER SHOULD UNDERSTAND THE STORY WITHOUT NARRATION:
- Each scene must show a DIFFERENT part of the house/location — bedroom, hallway, kitchen, front door, stairs, bathroom. NOT the same staircase over and over.
- The scene must show EXACTLY what the narration describes — if it says "shoes facing outward," the image must clearly show shoes facing outward. If it says "phone screen," show the phone screen.
- The viewer should be able to follow the story just from the images: wake up → see something wrong → investigate → discover more wrong things → the reveal
- Movement through the house should be logical: bedroom → hallway → stairs → downstairs → front door

HORROR PACING — DO NOT SPOIL THE REVEAL:
- Scenes 1-4: NO figure, NO creature, NO shadow person. Just empty rooms with subtle wrongness — a door ajar, shoes facing wrong, a light that shouldn't be on. The horror is that things are SLIGHTLY OFF.
- Scenes 5-6: HINTS only — a sound implied by the scene (dark staircase with dust falling), a shadow that MIGHT be something. Still ambiguous.
- Scenes 7-8: THE REVEAL — now you can show the figure/creature/horror. This is the payoff.
- Final scene: The consequence — door closing, trapped, something approaching.
- NEVER show the scary thing in the first half. The dread of NOT seeing it is scarier.

EVERY PROMPT MUST:
- Start with "Simple crude cartoon with thick black outlines, dark desaturated colors."
- Show a SPECIFIC room or location that advances the story spatially
- Match EXACTLY what the narration line describes — show the specific object/detail mentioned
- End with "Crude cartoon horror style. NO text anywhere." """

SCRIPT_PROMPT = """Write a narration script for a SpookLand horror short.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 MUST set the scene with a hook: "You wake up at 3am. Your front door is wide open." — immediate dread. Shorts viewers don't see titles so line 1 IS the hook.
- Second person narration — "You hear it...", "You turn around...", "Your phone dies..."
- SLOW BUILD — don't reveal the scary thing immediately. Build unease first.
  - Lines 1-3: Something is wrong but you can't tell what
  - Lines 4-6: It gets worse — details that don't add up, sounds that shouldn't be there
  - Lines 7-8: The reveal — what's actually happening. This should be TERRIFYING.
- The horror should be SPECIFIC — not "something scary" but "your bedroom door is now six inches to the left of where it was yesterday"
- Each line should make the viewer more uncomfortable
- The ending must be CLEAR and OBVIOUS — the viewer should instantly understand what just happened. No puzzles, no "figure it out" moments. The last 2 lines should:
  - Line 9: The REALIZATION — you understand what's actually happening. One sentence that reframes everything.
  - Line 10: The CONSEQUENCE — something happens. The door slams shut, the lights go out, something grabs you.
- NOT gore, NOT jumpscares — but the horror must be CLEAR, not subtle or ambiguous.

VISUAL STORYTELLING IS CRITICAL:
- Each line MUST describe a DIFFERENT location or object — bedroom, hallway, stairs, front door, kitchen, phone screen. NOT the same room twice in a row.
- Each line must describe something VISUALLY SPECIFIC that can be shown in an image
- The viewer should be able to follow the story just from the images even without audio

- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image = one SPECIFIC visual
- Each line UNDER 15 words
- Whispered, tense delivery

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT CREEPY TITLE"}}"""


async def build_spookland(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full SpookLand video build using unified pipeline. COLD OPEN — no intro teasers."""
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
        voice_settings={"stability": 0.7, "similarity_boost": 0.9, "speed": 0.85},
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

    # ─── STEP 5: COLD OPEN — no intro teasers, concat ALL segments directly ───
    await _update_step("concatenating")
    all_video_path = os.path.join(output_dir, "all_video_silent.mp4")
    avl = os.path.join(output_dir, "all_video_list.txt")
    with open(avl, "w") as f:
        for i in range(n_lines):
            f.write(f"file '{os.path.abspath(os.path.join(segments_dir, f'seg_{i:02d}.mp4'))}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", avl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p", "-an",
        all_video_path,
    ], capture_output=True, timeout=300)
    total_dur = get_duration(all_video_path)

    # ─── STEP 6: Build audio without intro — narration starts at t=0 ───
    await _update_step("building audio")
    total_samples = int(total_dur * SR) + SR
    output = np.zeros(total_samples, dtype=np.float32)

    seg_starts = []
    cursor = 0.0
    for i in range(n_lines):
        seg_starts.append(cursor)
        narr = load_audio_samples(os.path.join(narr_dir, f"line_{i:02d}.mp3"))
        start_sample = int(cursor * SR)
        end_sample = min(start_sample + len(narr), total_samples)
        output[start_sample:end_sample] += narr[:end_sample - start_sample]
        cursor += seg_durations[i]

    # Quiet background music for horror
    music = load_audio_samples(MUSIC_PATH)
    music_vol = 0.08
    music_tiled = np.tile(music, (total_samples // len(music)) + 1)[:total_samples] * music_vol
    output += music_tiled

    peak = np.max(np.abs(output))
    if peak > 0:
        output = output / peak * 0.95

    audio_path = os.path.join(output_dir, "full_audio.wav")
    output_16 = (output * 32767).astype(np.int16)
    with wave.open(audio_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(output_16.tobytes())

    await _update_step("combining")
    combined = combine_video_audio(all_video_path, audio_path, output_dir)

    await _update_step("adding subtitles")
    with open(os.path.join(output_dir, "word_timestamps.json")) as f:
        word_data = json.load(f)
    add_subtitles(combined, word_data, seg_starts, output_dir)

    await update_database(run_id, CHANNEL_ID, title, output_dir, db_url, TAGS)
    logger.info("spookland complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
