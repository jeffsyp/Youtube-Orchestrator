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

ART_STYLE = "Photorealistic with dramatic cinematic lighting. Real-world environments (suburban backyard, highway, office, kitchen) shot like a news/documentary photo. Pokemon rendered as if they were actually there — detailed, textured, correctly proportioned. Golden hour or natural daylight."

IMAGE_RULES = """ART STYLE:
- PHOTOREALISTIC — environments and humans must look like real photographs
- Real-world settings: suburban backyards, highways, offices, kitchens, streets, parks, etc.
- Dramatic natural lighting — golden hour, daylight, news-helicopter shots
- The POKEMON is rendered with full detail as if it really existed in the real world (real fur/scales/feathers texture, real shadow, real mass)
- Human bystanders look like real people — terrified, confused, filming on phones, news crews

POKEMON ACCURACY — MUST BE INSTANTLY RECOGNIZABLE:
- Use the EXACT Pokemon name (Pikachu, Charizard, Snorlax, Gyarados, etc.)
- EVERY Pokemon must have ALL of its signature features rendered realistically:
  - Pikachu: yellow body, red circle cheeks, black-tipped pointy ears, lightning bolt shaped tail, small and round
  - Charizard: orange body, blue inner wings, flame on tail tip, horn on head, dragon-like
  - Snorlax: massive round body, dark blue-green, cream belly, closed sleepy eyes
  - Gyarados: blue serpentine body, whiskers, fanged mouth, spiky crown, massive
  - Magikarp: orange fish, big dumb round eyes, yellow fins, whiskers, useless expression
- A viewer must INSTANTLY know which Pokemon it is
- Scale matters dramatically in photorealistic style: Charizard towers over buildings, Pikachu fits in your hands, Snorlax fills an entire room

EVERY PROMPT MUST:
- Start with "Photorealistic cinematic photograph."
- Include a specific real-world setting rendered photorealistically
- Show the Pokemon DOING the action described in the narration — using its actual signature ability
- End with "Photorealistic. NO text anywhere."
- Describe the human reaction in the scene (people running, screaming, filming, news crews) with real-world realism"""

SCRIPT_PROMPT = """Write a narration script for a Munchlax Lore "What If" Pokemon video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 is the HOOK: "What if [Pokemon scenario]?" — name the specific Pokemon and situation.
  - GOOD: "What if Snorlax blocked the highway during rush hour?"
  - GOOD: "What if Charizard was your Uber driver?"
  - GOOD: "What if Mewtwo showed up to your job interview?"
- CHOOSE THE RIGHT STRUCTURE:
  A) DAY-BY-DAY — use when the Pokemon situation spans time:
     - "Day 1:", "Day 2:", "Week 2:" as part of narration
     - GOOD fit: "What if Snorlax blocked the highway" → Day 1: traffic stops, Day 3: news crews, Month 1: new landmark
  B) REAL-TIME — use when it's a single Pokemon encounter/moment:
     - No day markers, rapid escalation
     - GOOD fit: "What if Charizard sneezed in a library" → sneeze, fire, sprinklers, everything destroyed
  Pick whichever fits.
- Escalation structure (3-5 beats):
  - Beat 1: The Pokemon appears / the situation begins. Seems manageable.
  - Beat 2: The Pokemon uses its abilities. Things escalate.
  - Beat 3-4: Real-world consequences — police, news crews, military, the president.
  - Final beat: GO COMPLETELY INSANE. The Pokemon takes over, you become a trainer, a new region is declared.
- The comedy is CONTRAST: a powerful mythical creature in a completely mundane setting
- The Pokemon uses its ACTUAL moves and abilities — Thunderbolt, Flamethrower, Hyper Beam, etc.
- Second person narration ("You see...", "It looks at you...", "You realize...")
- The Pokemon acts like it WOULD in real life — Charizard sets things on fire, Snorlax blocks everything, Gyarados destroys water features, Pikachu shorts out electronics
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER.
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, dramatic, funny
- The LAST LINE must be a devastating punchline

AVOID DRAGGING ENDINGS — END AT THE PUNCHLINE:
- Stop adding lines after the punchline lands. Aftermath beats that explain consequences AFTER the absurd climax kill pacing.
- BAD sequence: "Line 5: gym is destroyed. Line 6: FEMA arrives. Line 7: Machamp is certified. Line 8: you are jacked but broken." — four aftermath beats dilute the impact.
- GOOD sequence: "Line 5: he used Dynamic Punch to motivate you off the treadmill. Line 6: you have never felt better. You have also never felt worse." — two lines max after climax.
- If a line feels like it's just describing the aftermath of the previous line, cut it. The next line should introduce NEW action or the punchline.
- TEST: if you can remove a line and the story still works, remove it.

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
