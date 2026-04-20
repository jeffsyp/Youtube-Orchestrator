"""Deity Drama channel builder.

Supports two lanes:
1. modern divine-chaos comedy ("What if Poseidon became a plumber?")
2. mythic cinematic POV / retelling ("What it felt like when Poseidon came for you")

Uses unified pipeline: style anchor → sub-actions → GPT images → animation → chaining.
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

MYTHIC_ART_STYLE = "Photorealistic mythic cinema. Ancient Greece and the open sea rendered like a prestige historical epic: stormlight, huge skies, violent water, bronze ships, temples, cliffs, torchlight, sea spray, divine scale. Gods look like real divine beings in their own world — imposing, supernatural, terrifying. Not comic-book glossy, not cartoon, not painterly fantasy illustration."

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

MYTHIC_IMAGE_RULES = """ART STYLE:
- PHOTOREALISTIC MYTHIC CINEMA — scenes should look like live-action epic mythology, not cartoons or paintings
- Ancient and mythic environments only unless the concept explicitly says modern
- Big weather, sea spray, stormclouds, torch smoke, crashing surf, bronze ships, cliffs, temples, palace halls
- The scale should feel terrifying and divine, not sitcom-like

MYTHOLOGY CHARACTERS — MUST BE INSTANTLY RECOGNIZABLE:
- Zeus: white beard, muscular, white/gold toga or armor, lightning crackling in hand, laurel crown
- Poseidon: trident, flowing sea-blue/green robes or bronze armor, wet hair, salt spray, water surging around him
- Hades: dark robes or armor, pale skin, underworld fire, skull motifs, dread-heavy stillness
- Athena: plumed helmet, silver owl, aegis shield, cold intelligent gaze
- Apollo: golden radiance, lyre or golden bow, sunlit skin, immaculate beauty
- Ares: blood-red armor, scars, brutal posture, battle haze
- Hermes: winged sandals, caduceus, swift blur, messenger cloak

FOR MYTHIC POV / RETELLING:
- The point is FEAR, AWE, and STORY — not office comedy
- Every image must show a concrete escalating moment: sea going flat, wave rising, mast snapping, ship tilting vertical, temple doors blowing open
- Keep scenes visually literal and easy to parse on mute
- Show the god's power affecting the world directly
- Background humans should react realistically: kneeling, screaming, gripping ropes, praying, fleeing, staring upward in shock
- If the concept is POV or \"what it felt like\", frame scenes like lived moments inside the disaster, not a detached infographic
- End every prompt with "Photorealistic. NO text anywhere."
"""

SCRIPT_PROMPT = """Write a narration script for a Deity Drama YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 is the HOOK: "What if [god] [did modern thing]?" — name the specific god and situation.
  - GOOD: "What if Apollo became an Uber driver?"
  - GOOD: "What if Zeus and Poseidon shared an umbrella?"
- CHOOSE THE RIGHT STRUCTURE for the concept:
  A) DAY-BY-DAY — use when the god enters a new situation over time (new job, new world, living among mortals):
     - Lines include "Day 1:", "Day 2:", "Week 2:" as part of narration
     - Time jumps accelerate to show spiraling consequences
     - GOOD fit: "What if Zeus moved to New York" → Day 1: apartment hunting, Day 3: neighborhood destroyed
  B) REAL-TIME — use when it's a single interaction or event (one task, one attempt):
     - No day markers, rapid beat-by-beat escalation within one moment
     - GOOD fit: "What if Poseidon became a plumber" → touches pipe, floods room, floods building, floods city
  Pick whichever fits naturally.
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

SCRIPT_PROMPT_MYTHIC = """Write a narration script for a Deity Drama mythology short.

CONCEPT: {title}
BRIEF: {brief}

THIS IS NOT DEFAULT MODERN COMEDY.
Treat this as one of:
- cinematic POV mythology
- mythic retelling
- informative but visceral divine-story short

RULES:
- 5-7 lines total, ~20-30 seconds
- Each line under 15 words
- Line 1 must say exactly what the viewer is about to experience
- Every line must be visually literal and drawable in one image
- Escalate through specific physical events, not abstractions
- Use the god's domain directly: storms, sea walls, lightning, temple fire, plague, prophecy, monsters
- Ancient/mythic environments by default unless the concept explicitly says modern
- End on the most devastating image or consequence, not a joke unless the concept clearly wants one

GOOD SHAPE:
- Hook
- omen / warning sign
- first impossible display of divine power
- catastrophic escalation
- overwhelming final consequence

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


def _infer_deity_mode(concept: dict) -> str:
    explicit = str(concept.get("deity_mode") or "").strip().lower()
    if explicit:
        return explicit
    text = f"{concept.get('title', '')} {concept.get('brief', '')}".lower()
    mythic_signals = (
        "what it felt like",
        "came for you",
        "pov",
        "the day",
        "how ",
        "why ",
        "retelling",
        "actually happened",
        "real story",
        "prophecy",
        "curse",
    )
    if any(token in text for token in mythic_signals):
        return "mythic_pov"
    return "modern_chaos"


async def build_deity_drama(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Deity Drama video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])
    deity_mode = _infer_deity_mode(concept)
    art_style = MYTHIC_ART_STYLE if deity_mode != "modern_chaos" else ART_STYLE
    image_rules = MYTHIC_IMAGE_RULES if deity_mode != "modern_chaos" else IMAGE_RULES
    script_prompt = SCRIPT_PROMPT_MYTHIC if deity_mode != "modern_chaos" else SCRIPT_PROMPT

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
            prompt=script_prompt.format(title=title, brief=brief),
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
        narration_lines, concept, image_rules, art_style, output_dir, _update_step, run_id=run_id,
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
    logger.info("deity drama complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
