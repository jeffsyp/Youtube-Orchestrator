"""Deity Drama channel builder — "What if [god] did [modern thing]" narrated videos.

Mythology gods in the modern world — divine powers collide with everyday situations.
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
CHANNEL_ID = 22
VOICE_ID = "tHX3st5GOLcIi8WJRtqa"  # Deity Drama voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "epic", "heroic_age.mp3")
TAGS = ["deity drama", "mythology", "gods", "what if", "comedy", "shorts", "viral"]

ART_STYLE = "Photorealistic with dramatic cinematic lighting. Gods look like real people in ancient clothing — muscular, divine, imposing — placed into real modern environments. The contrast between ancient divine beings and modern mundane settings IS the visual comedy. Golden hour or dramatic side-lighting."

IMAGE_RULES = """ART STYLE:
- PHOTOREALISTIC — gods and environments must look like real photographs
- Dramatic cinematic lighting — golden hour, rim lighting, volumetric light, lens flare from divine powers
- Gods look like REAL PEOPLE in ancient clothing — muscular, tall, imposing, divine aura
- Modern environments are completely normal and photorealistic (office, Walmart, traffic jam, DMV, kitchen)
- The ONLY mythological elements are the gods themselves and their power effects
- Divine power effects (lightning, water geysers, fire, glowing auras) must be DRAMATIC and VISIBLE

MYTHOLOGY CHARACTERS — MUST BE INSTANTLY RECOGNIZABLE:
- Zeus: white beard, muscular, white/gold toga, lightning bolt crackling in hand, laurel crown
- Poseidon: trident, flowing sea-blue/green robes, wet hair, seaweed, water swirling around him
- Hades: dark robes, pale skin, underworld flames flickering, skull motifs, Cerberus nearby
- Apollo: golden radiance, sun imagery, lyre or golden bow, blonde, glowing skin
- Dionysus: grape vine crown, ornate golden goblet, purple robes, flushed cheeks, wild hair
- Ares: blood-red armor, massive weapons, battle scars, aggressive stance, war paint
- Athena: silver owl on shoulder, aegis shield, plumed helmet, wise grey eyes
- Hermes: winged sandals glowing, caduceus staff, traveler's cloak, mischievous speed blur
- Aphrodite: ethereal beauty, pink/rose gold, doves, flowers blooming around her
- Thor: Mjolnir crackling with lightning, red cape, Viking armor, blonde braids
- Loki: green/gold armor, horned helmet, shape-shifting visual distortion, sly grin
- Gods keep their SIGNATURE WEAPON/ITEM even in modern settings — Zeus has his bolt at Walmart

THE COMEDY IS IN THE CONTRAST:
- A literal GOD — photorealistic, divine, glowing — standing in a completely mundane modern place
- Modern humans around them react realistically — terrified, filming on phones, running, frozen in shock
- Divine power effects collide with modern objects — lightning hitting a microwave, trident flooding a bathroom, fire melting a self-checkout
- Every prompt must end with "Photorealistic. NO text anywhere."
"""

SCRIPT_PROMPT = """Write a narration script for a Deity Drama YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 is the HOOK: "What if [god] [did modern thing]?" — name the specific god and situation.
  - GOOD: "What if Apollo became an Uber driver?"
  - GOOD: "What if Zeus and Poseidon shared an umbrella?"
- Escalation structure (3-5 beats):
  - Beat 1: God attempts the normal thing. Seems fine.
  - Beat 2: Divine power activates accidentally. Mild chaos.
  - Beat 3-4: Catastrophic escalation. Collateral destruction.
  - Final beat: GO COMPLETELY INSANE. God is unbothered. Everything is destroyed.
- The comedy is CONTRAST: divine power vs mundane situation. The god is CALM while everything burns.
- Reference specific divine powers by name (lightning bolt, trident, necromancy, etc.)
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER.
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, fast-paced, funny
- The LAST LINE must be a devastating punchline

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


async def build_deity_drama(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Deity Drama video build using unified pipeline."""
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
        voice_settings={"stability": 0.5, "similarity_boost": 0.8, "speed": 1.0},
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
    logger.info("deity drama complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
