"""Deity Drama channel builder — mythology gods in absurd modern situations.

"What if Zeus got a 9-to-5 job" — gods dealing with modern life problems.
Classical oil painting style rendered photorealistically with Grok.
Uses shared functions for narration, intro, audio, subtitles.
"""
import asyncio
import base64
import json
import os
import re

import structlog

from apps.orchestrator.channel_builders.shared import (
    generate_narration_with_timestamps,
    generate_image_prompts,
    build_silent_segments,
    build_intro_teasers,
    concat_silent_video,
    build_numpy_audio,
    combine_video_audio,
    add_subtitles,
    update_database,
    get_duration,
    get_clip_duration,
    review_generated_images,
    run_tasks,
)

logger = structlog.get_logger()

# Channel-specific constants
CHANNEL_ID = 22
VOICE_ID = "tHX3st5GOLcIi8WJRtqa"  # Deity Drama voice
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "epic", "heroic_age.mp3")
TAGS = ["deity drama", "mythology", "gods", "what if", "comedy", "shorts", "viral"]

# Channel-specific image prompt rules
IMAGE_RULES = """ART STYLE:
- Classical oil painting aesthetic BUT in a modern setting — dramatic Baroque lighting, rich warm colors, canvas texture
- Gods should look GODLY — flowing robes, golden accessories, glowing auras, muscular/divine proportions
- BUT they are doing completely mundane modern things — that contrast IS the comedy
- The modern environment should be photorealistic (office, Walmart, traffic jam, DMV)
- The god is the only mythological element — everything else is normal modern life

GOD ACCURACY — CRITICAL:
- Use EXACT god names — Zeus, Hera, Poseidon, Hades, Thor, Loki, Odin, Anubis, etc.
- Grok knows what these gods look like — describe their signature features:
  - Zeus: white beard, lightning bolt, muscular, laurel crown
  - Hera: regal, peacock motifs, crown, judgmental expression
  - Poseidon: trident, sea-blue robes, seaweed in hair/beard
  - Hades: dark robes, pale skin, Cerberus, underworld flames
  - Thor: Mjolnir, red cape, Viking armor, blonde hair
  - Loki: green/gold, horned helmet, mischievous grin
- Each god should have their SIGNATURE WEAPON/ITEM even in modern settings

THE COMEDY:
- The humor comes from the CONTRAST — divine power meets mundane annoyance
- Zeus using a lightning bolt to charge his phone. Poseidon flooding the office bathroom. Hades stuck in traffic.
- Other humans in the scene should be reacting — terrified, confused, or completely unfazed

EVERY PROMPT MUST:
- Show the god with their iconic features and weapon/accessory
- Place them in a specific modern real-world setting
- Show the exact comedic situation from the narration
- End with "Classical painting lighting in a modern photorealistic setting. NO text anywhere." """


async def build_deity_drama(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Deity Drama video build."""
    from packages.clients.grok import generate_image_dalle_async, generate_video_async

    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])

    narr_dir = os.path.join(output_dir, "narration")
    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, images_dir, clips_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Write script if not provided ───
    if not narration_lines:
        await _update_step("writing script")
        from packages.clients.claude import generate as claude_generate

        brief = concept.get("brief", title)
        structure = concept.get("structure", "")
        key_facts = concept.get("key_facts", "")

        resp = claude_generate(
            prompt=f"""Write a narration script for a Deity Drama video.

CONCEPT: {title}
BRIEF: {brief}
STRUCTURE: {structure}
KEY FACTS: {key_facts}

THE FORMAT:
- Line 1 MUST state the scenario: "What if [God] had to [mundane modern thing]?" — this IS the title. Shorts viewers don't see titles.
- Line 2 goes STRAIGHT into the situation — the god arrives at the modern location
- The humor comes from DIVINE POWER vs MUNDANE ANNOYANCE:
  - Zeus can't figure out self-checkout. Uses lightning bolt. Gets banned from Walmart.
  - Poseidon tries to take a bath. Floods the entire apartment complex.
  - Hades goes to a job interview. The interviewer is terrified. He gets the job anyway.
  - Thor goes through airport security. Mjolnir sets off every detector. TSA is powerless.
- Each line should escalate the chaos — the god keeps making it worse by using their powers for simple things
- Other people's reactions are part of the comedy — screaming, filming on phones, calling 911
- The ending must GO COMPLETELY INSANE — the god accidentally destroys the building, gets elected mayor, starts a religion at Costco, becomes a viral TikTok celebrity
- Use the god's SPECIFIC powers and weapons by name
- 8-10 narration lines total, ~30-40 seconds
- Each line = one scene = one image
- Each line UNDER 15 words
- Tone: epic narrator describing absurd mundane situations

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT FUNNY TITLE"}}""",
            max_tokens=1500,
        )

        json_match = re.search(r'\{.*\}', resp, re.DOTALL)
        if json_match:
            script_data = json.loads(json_match.group())
            narration_lines = script_data.get("narration", [])
            if script_data.get("title"):
                title = script_data["title"]

        if not narration_lines:
            raise ValueError("Failed to generate narration script")
        logger.info("script generated", title=title, lines=len(narration_lines))

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration (shared) — epic, dramatic, slightly comedic ───
    await _update_step("generating narration")
    all_word_data = await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
        voice_settings={"stability": 0.5, "similarity_boost": 0.8, "speed": 1.0},
    )

    # ─── STEP 3: Image prompts (shared + channel rules) ───
    image_prompts = await generate_image_prompts(narration_lines, IMAGE_RULES, _update_step)

    # ─── STEP 4: Generate images with GROK (accurate god depictions) ───
    await _update_step("generating images (parallel)")

    async def gen_image(i, prompt):
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        if os.path.exists(img_path):
            return
        await generate_image_dalle_async(prompt=prompt, output_path=img_path, size="1024x1536")
        logger.info("image generated", scene=i)

    await run_tasks(
        [lambda i=i, p=p: gen_image(i, p) for i, p in enumerate(image_prompts)],
        parallel=True, max_concurrent=5,
    )

    # ─── STEP 4b: Review generated images ───
    async def regen_image(i, prompt):
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        if os.path.exists(img_path):
            os.remove(img_path)
        await generate_image_dalle_async(prompt=prompt, output_path=img_path, size="1024x1536")

    await review_generated_images(
        narration_lines, image_prompts, images_dir, _update_step,
        regenerate_fn=regen_image,
    )

    # ─── STEP 5: Animation prompts + animate ───
    await _update_step("planning animations")
    from packages.clients.claude import generate as claude_gen
    anim_resp = claude_gen(
        prompt=f"""For each narration line, write a SHORT animation prompt (under 15 words) describing what MOVEMENT happens.

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

RULES:
- Gods should have DRAMATIC movement — lightning crackling, water swirling, fire flickering
- Modern people should react — flinching, running, dropping their coffee, filming on phones
- Divine powers interacting with mundane objects — electricity arcing, ground trembling, objects floating
- The contrast between epic godly movement and normal human panic is the comedy
- NEVER say "camera zooms" or "camera pans"

Return ONLY a JSON array of {n_lines} short strings.""",
        max_tokens=2000,
    )
    anim_match = re.search(r'\[.*\]', anim_resp, re.DOTALL)
    anim_prompts = json.loads(anim_match.group()) if anim_match else ["Divine energy crackling, mortals reacting." for _ in range(n_lines)]
    while len(anim_prompts) < n_lines:
        anim_prompts.append("Divine energy crackling, mortals reacting.")
    anim_prompts = anim_prompts[:n_lines]

    await _update_step("animating scenes (parallel)")

    async def animate_scene(i):
        clip_path = os.path.join(clips_dir, f"clip_{i:02d}.mp4")
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        if os.path.exists(clip_path):
            return
        dur = get_clip_duration(os.path.join(narr_dir, f"line_{i:02d}.mp3"))
        with open(img_path, "rb") as f:
            img_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        await generate_video_async(
            prompt=anim_prompts[i],
            output_path=clip_path, duration=dur, aspect_ratio="9:16",
            image_url=img_b64, timeout=600,
        )
        logger.info("scene animated", scene=i, prompt=anim_prompts[i])

    await run_tasks(
        [lambda i=i: animate_scene(i) for i in range(n_lines)],
        parallel=True, max_concurrent=5,
    )

    # ─── STEPS 6-10: All shared ───
    await _update_step("building video")
    seg_durations = build_silent_segments(n_lines, clips_dir, narr_dir, segments_dir)

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
