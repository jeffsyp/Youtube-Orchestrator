"""Hardcore Ranked channel builder — visual comparison/ranking videos.

Frog character in astronaut helmet as the test subject.
Same visual anchor (camera angle, location) for every comparison.
gpt-4o edit to place frog into consistent scenes using reference images.
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
CHANNEL_ID = 26
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
FROG_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "hardcore_ranked_frog_v3.png")
TAGS = ["hardcore ranked", "comparison", "ranked", "shorts", "viral"]

# Channel-specific image prompt rules
IMAGE_RULES = """RULES:
- The main character is a HUMAN-SIZED PERSON wearing a green frog-themed astronaut suit with a frog-shaped helmet — NOT an actual frog. He is a human that looks like a frog because of his suit. Think of a human diver in a frog costume.
- PHOTOREALISTIC world, the character is a 3D animated character in a real world

THE SETTING DEPENDS ON THE CONCEPT — NOT ALWAYS A ROAD:
- Swimming comparison → BEHIND the character looking DOWN a single Olympic swimming lane, like a TV camera behind the starting blocks. You see the lane stretching away from camera so you can see how far the character swims.
- Vehicle comparison → a long straight road from behind the frog
- Climbing comparison → a tall wall/cliff from the side
- The setting should let you SEE the difference in speed/distance/progress between each item
- Choose the setting that makes the COMPARISON most visually obvious

SAME SETUP EVERY SCENE — THIS IS THE ENTIRE POINT:
- EVERY scene uses the EXACT SAME environment from the EXACT SAME camera angle
- The ONLY thing that changes is the VARIABLE (different liquid, vehicle, surface)
- The frog does the SAME action in every scene — only the variable differs
- Think of it like a science experiment: same test, one variable changed

EACH PROMPT MUST DESCRIBE ONLY WHAT CHANGES:
- Do NOT re-describe the entire scene in each prompt
- Just describe what is DIFFERENT: "The pool is now filled with thick golden honey. The frog is barely moving, stuck in the viscous liquid."
- The base scene handles everything else (setting, angle, frog position)

- Every prompt must end with "Photorealistic. NO text anywhere."
- CONSISTENCY IS KEY — same camera angle, same frog, same environment, ONLY the variable changes"""


async def build_hardcore_ranked(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Hardcore Ranked video build."""
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
            prompt=f"""Write a narration script for a Hardcore Ranked comparison video.

CONCEPT: {title}
BRIEF: {brief}
STRUCTURE: {structure}
KEY FACTS: {key_facts}

THE FORMAT:
- Line 1 MUST state the topic: "How fast can frog swim across a pool in every liquid?" — this IS the title. Shorts viewers don't see video titles.
- Line 2 onwards: NUMBERED ranked list. Each line starts with the rank number. Example:
  - "Number 1: Water. Four seconds. Built for this."
  - "Number 2: Honey. Three hours. Basically a statue."
  - "Number 3: Rocket fuel. Instant explosion. Never seen again."
- ONLY 4-5 items total (lines 2-5 or 2-6). Pick the most DIFFERENT and INTERESTING ones — skip boring/similar items (saltwater is too close to water, skip it)
- CRITICAL: ONE item PER LINE. NEVER combine multiple items in one line. Each line = one surface/liquid/vehicle/planet = one scene = one image.
  BAD: "Grass gets him six feet. Dirt path, eight. Asphalt, fifteen." (3 items crammed into 1 line — impossible to visualize)
  GOOD: "Number 2: Grass. Six feet. Barely counts."
  GOOD: "Number 3: Dirt path. Eight feet. Getting somewhere."
- The character in a frog-themed astronaut suit is the test subject in EVERY scene
- The character does the EXACT SAME THING in every scene — only the VARIABLE changes
- Start with the most normal, escalate to the most insane
- The LAST item should be absurd and break the format (explosion, launch into space, instant destruction)
- 6-8 narration lines, ~20-30 seconds. SHORTER IS BETTER.
- Each line = one scene, each under 15 words. ONE variable per line, no exceptions.
- Include specific numbers/facts for each item — the numbers ARE the comparison

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT TITLE"}}""",
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

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration (shared) ───
    await _update_step("generating narration")
    all_word_data = await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
    )

    # ─── STEP 3: Image prompts (shared + channel rules) ───
    brief = concept.get("brief", "")
    extra_rules = f"\n\nCONCEPT-SPECIFIC INSTRUCTIONS:\n{brief}" if brief else ""
    image_prompts = await generate_image_prompts(narration_lines, IMAGE_RULES + extra_rules, _update_step)

    # ─── STEP 4: Generate base scene → edit per liquid → animate ───
    await _update_step("generating base scene")
    import shutil
    from openai import AsyncOpenAI
    edit_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)

    brief = concept.get("brief", "")
    if brief:
        # Brief describes the exact setup — use it directly as the base prompt
        # Split on various markers to extract only the base scene description
        _base_text = brief
        for _marker in ['For edits', 'For every edit', 'For animation', 'For each edit']:
            _base_text = _base_text.split(_marker)[0]
        base_prompt = f"Photorealistic. SINGLE IMAGE only — NOT a comic panel layout, NOT multiple panels, NOT a grid. One continuous scene. CAMERA: Behind-view, looking over the character's shoulder down the path/slope/track ahead. The character is a HUMAN-SIZED PERSON in a green frog-themed astronaut suit with a frog-shaped helmet — NOT an actual frog, NOT a cartoon frog, a HUMAN wearing a frog costume. {_base_text.strip()} NO text anywhere. ONE single frame only."
    else:
        from packages.clients.claude import generate as claude_gen_base
        base_prompt_resp = claude_gen_base(
            prompt=f"""Based on this concept, describe the BASE SCENE for the comparison.

CONCEPT: {title}

THE CHARACTER: A HUMAN-SIZED PERSON wearing a green frog-themed astronaut suit with a frog-shaped helmet. NOT an actual frog. A human in a frog costume.

CAMERA: Always BEHIND the character, looking over their shoulder down the path/slope/track ahead. Like a TV camera behind a starting line.

ACTION: The character must be performing the EXACT ACTION from the title:
- "roll" = curled up in a ball, mid-tumble, body tucked
- "swim" = arms mid-stroke, body horizontal in water
- "run" = mid-stride, one leg forward, arms pumping
- "jump" = legs coiled or mid-launch, leaving the ground
Match the specific physical action. The character must be MID-ACTION, not standing still.

Start with "Photorealistic." End with "NO text anywhere."
Return ONLY the prompt.""",
            max_tokens=300,
        )
        base_prompt = base_prompt_resp.strip().strip('"')
    logger.info("base prompt", prompt=base_prompt[:100])

    base_scene_path = os.path.join(images_dir, "base_scene.png")
    if not os.path.exists(base_scene_path):
        # Use frog reference image as input for consistent character
        if os.path.exists(FROG_REF):
            frog_file = open(FROG_REF, "rb")
            try:
                resp = await edit_client.images.edit(
                    model="gpt-image-1.5",
                    image=frog_file,
                    prompt=f"Place this exact character into the scene. {base_prompt}",
                    size="1024x1536",
                    quality="medium",
                    input_fidelity="high",
                )
                frog_file.close()
                if resp.data and resp.data[0].b64_json:
                    img_data = base64.b64decode(resp.data[0].b64_json)
                    with open(base_scene_path, "wb") as f:
                        f.write(img_data)
            except Exception as e:
                try: frog_file.close()
                except: pass
                logger.warning("frog ref edit failed, generating fresh", error=str(e)[:80])
                await generate_image_dalle_async(
                    prompt=base_prompt,
                    output_path=base_scene_path, size="1024x1536",
                )
        else:
            await generate_image_dalle_async(
                prompt=base_prompt,
                output_path=base_scene_path, size="1024x1536",
            )
        logger.info("base scene generated", prompt=base_prompt[:100])

    # Scene 0 = base scene (hook/title)
    scene_00 = os.path.join(images_dir, "scene_00.png")
    if not os.path.exists(scene_00):
        shutil.copy2(base_scene_path, scene_00)

    # Edit base scene for each liquid/variable — gpt-image-1.5 edit with input_fidelity=high
    await _update_step("creating scene variants")

    from packages.clients.claude import generate as claude_gen_edits
    edits_resp = claude_gen_edits(
        prompt=f"""For each narration line (except line 0), write a SHORT edit instruction. The base scene shows: {base_prompt}

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

CRITICAL — THE STORY IS "FROG LOSES":
Grok's video model cannot show subjects pulling ahead and shrinking into distance. So we must BAKE THE LOSS INTO THE IMAGE. The dinosaur must ALREADY be far ahead of the frog in every image — we are capturing the moment AFTER the dinosaur has pulled ahead, not the start of the race.

EACH SCENE'S IMAGE MUST SHOW:
- Frog in foreground at the bottom of the frame, visibly exhausted (hunched, gasping, struggling)
- The dinosaur ALREADY FAR AHEAD down the road — smaller in the frame due to distance
- Motion blur / dust trail STRETCHING from the dinosaur back toward the frog, showing it has already been running and pulling away
- The gap between them increases with each scene:
  * Triceratops: 50 yards ahead (medium-sized in frame)
  * T-Rex: 100 yards ahead (smaller in frame, running away)
  * Velociraptor: 200 yards ahead (tiny, almost at horizon)
  * Pterodactyl: flies DOWN to grab frog from above (different — no distance gap needed)

Examples:
- "Add a Triceratops that is ALREADY 50 YARDS AHEAD of the frog on the road, visible in the middle distance, mid-gallop with dust trail extending back toward the frog. The frog in foreground is hunched over, gasping. The Triceratops is SMALLER in the frame because it's further away. Everything else stays identical."
- "Add a Velociraptor that is ALREADY 200 YARDS AHEAD — a tiny silhouette at the horizon, running away at top speed, huge dust trail extending back toward the frog. The frog in foreground looks defeated, tiny raptor visible in the distance down the road. Make the dinosaur LOOK TINY to show how far ahead it is."

Return ONLY a JSON array of {n_lines} strings. Line 0 should be "No changes — use base scene as is." """,
        max_tokens=1000,
    )
    edits_match = re.search(r'\[.*\]', edits_resp, re.DOTALL)
    edit_prompts = json.loads(edits_match.group()) if edits_match else ["No changes." for _ in range(n_lines)]
    while len(edit_prompts) < n_lines:
        edit_prompts.append("No changes.")
    edit_prompts = edit_prompts[:n_lines]

    for i in range(1, n_lines):
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        if os.path.exists(img_path):
            continue
        for attempt in range(4):
            try:
                base_file = open(base_scene_path, "rb")
                resp = await edit_client.images.edit(
                    model="gpt-image-1.5",
                    image=base_file,
                    prompt=f"Same exact scene, same camera angle, same character position. The character must look IDENTICAL to the input image — same suit, same helmet, same body proportions, same colors. ONLY change: {edit_prompts[i]} Everything else stays pixel-identical. NO text anywhere.",
                    size="1024x1536",
                    quality="medium",
                    input_fidelity="high",
                )
                base_file.close()
                if resp.data and resp.data[0].b64_json:
                    img_data = base64.b64decode(resp.data[0].b64_json)
                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    logger.info("scene variant created", scene=i, edit=edit_prompts[i][:60])
                    break
            except Exception as e:
                logger.warning("edit failed", scene=i, attempt=attempt, error=str(e)[:80])
                try: base_file.close()
                except: pass
                await asyncio.sleep(3)
        if not os.path.exists(img_path):
            raise RuntimeError(f"Failed to create scene {i} variant after 4 attempts")

        # Review: verify the edited image still matches the base scene
        try:
            import anthropic
            review_client = anthropic.Anthropic()
            with open(img_path, "rb") as rf:
                img_b64_review = base64.b64encode(rf.read()).decode()
            with open(base_scene_path, "rb") as rf:
                base_b64_review = base64.b64encode(rf.read()).decode()
            review = review_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base_b64_review}},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64_review}},
                        {"type": "text", "text": f"Image 1 is the base scene. Image 2 is an edited version. Does image 2 keep the SAME camera angle, same character position, same setting as image 1? Only the liquid/variable should change. Answer PASS or FAIL with reason."},
                    ],
                }],
            )
            review_text = review.content[0].text
            if "FAIL" in review_text:
                logger.warning("scene edit review FAILED", scene=i, reason=review_text[:100])
            else:
                logger.info("scene edit review passed", scene=i)
        except Exception as e:
            logger.warning("scene edit review skipped", error=str(e)[:80])

    # ─── STEP 4c: Wait for user approval via file ───
    # Skip if clips already exist (images were approved in a previous run)
    _existing_clips = [f for f in os.listdir(clips_dir) if f.endswith('.mp4')] if os.path.isdir(clips_dir) else []
    _approval_file = os.path.join(output_dir, ".images_approved")
    _deny_file = os.path.join(output_dir, ".images_denied")
    if _existing_clips:
        logger.info("skipping image approval — clips exist from previous run", count=len(_existing_clips))
    elif os.path.exists(_approval_file):
        logger.info("skipping image approval — already approved (carried forward from previous run)")
        os.remove(_approval_file)
    else:
        await _update_step("images ready for review")
        if os.path.exists(_deny_file):
            os.remove(_deny_file)
        while True:
            await asyncio.sleep(3)
            if os.path.exists(_approval_file):
                logger.info("user approved images")
                os.remove(_approval_file)
                break
            if os.path.exists(_deny_file):
                logger.info("user denied images — regenerating with feedback")
                os.remove(_deny_file)
                for i in range(n_lines):
                    fb_path = os.path.join(images_dir, f"scene_{i:02d}_feedback.txt")
                    img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
                    if os.path.exists(fb_path):
                        fb_text = open(fb_path).read().strip()
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        if i == 0:
                            if os.path.exists(base_scene_path):
                                os.remove(base_scene_path)
                            await generate_image_dalle_async(
                                prompt=f"{base_prompt} User feedback: {fb_text}. NO text anywhere.",
                                output_path=base_scene_path, size="1024x1536",
                            )
                            shutil.copy2(base_scene_path, img_path)
                        else:
                            base_file = open(base_scene_path, "rb")
                            try:
                                resp = await edit_client.images.edit(
                                    model="gpt-image-1.5",
                                    image=base_file,
                                    prompt=f"Same scene, same camera angle. {edit_prompts[i]} User feedback: {fb_text}. NO text anywhere.",
                                    size="1024x1536", quality="medium", input_fidelity="high",
                                )
                                base_file.close()
                                if resp.data and resp.data[0].b64_json:
                                    img_data = base64.b64decode(resp.data[0].b64_json)
                                    with open(img_path, "wb") as wf:
                                        wf.write(img_data)
                            except Exception as regen_err:
                                try: base_file.close()
                                except: pass
                                await generate_image_dalle_async(
                                    prompt=f"{base_prompt} {edit_prompts[i]} User feedback: {fb_text}. NO text anywhere.",
                                    output_path=img_path, size="1024x1536",
                                )
                        os.remove(fb_path)
                        logger.info("regenerated from feedback", scene=i, feedback=fb_text[:60])
                # Also handle base_scene feedback
                base_fb = os.path.join(images_dir, "base_scene_feedback.txt")
                if os.path.exists(base_fb):
                    fb_text = open(base_fb).read().strip()
                    if os.path.exists(base_scene_path):
                        os.remove(base_scene_path)
                    await generate_image_dalle_async(
                        prompt=f"{base_prompt} User feedback: {fb_text}. NO text anywhere.",
                        output_path=base_scene_path, size="1024x1536",
                    )
                    shutil.copy2(base_scene_path, os.path.join(images_dir, "scene_00.png"))
                    os.remove(base_fb)
                    logger.info("regenerated base scene from feedback", feedback=fb_text[:60])
                await _update_step("images ready for review")

    # ─── STEP 5: Animation prompts — speed/movement per scene ───
    await _update_step("planning animations")
    from packages.clients.claude import generate as claude_gen
    anim_resp = claude_gen(
        prompt=f"""For each narration line, write an EXTREMELY AGGRESSIVE animation prompt. Grok defaults to slow zooms — we must FORCE it to animate full-body motion.

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

THE PROBLEM: Grok makes static slideshows unless the prompt is extremely specific about physical motion. EVERY word of the prompt must describe what's moving RIGHT NOW.

REQUIRED PATTERN FOR EVERY PROMPT:
1. Character A's specific limb motion: "Frog's legs pump up and down in a full running stride, knees driving to chest, feet slapping the ground rapidly"
2. Character B's specific limb motion: "Triceratops gallops forward, all four legs cycling through a full run, tail whipping side to side"
3. Environmental speed cues: "Dust clouds explode from every footstep, the road streaks past underneath, desert brush blurs as they sprint, air currents push back their hair/scales"
4. Expression/state changes: "Frog's mouth opens gasping for air, tongue flops out, eyes widen in panic"
5. Relative motion: "Triceratops PULLS AHEAD, gap widens every second, frog falls further behind"

RULES:
- Line 0 (hook): camera subject stares into camera, breath visible, nervous energy, shifting weight foot to foot preparing to sprint
- Lines 1+: FULL SPRINT MOTION. Both characters running. Specific leg cycles.
- Use words like: pumping, driving, slapping, cycling, whipping, thundering, exploding, blurring, streaking, gasping, panting
- NEVER: "runs", "races", "moves" (too vague). Say EXACTLY how the legs move.
- NEVER say "camera zooms" or "camera pans" — describe character motion only.
- Each prompt should be 3-4 sentences packed with motion verbs.

Return ONLY a JSON array of {n_lines} strings.""",
        max_tokens=2500,
    )
    anim_match = re.search(r'\[.*\]', anim_resp, re.DOTALL)
    anim_prompts = json.loads(anim_match.group()) if anim_match else ["Subtle idle movement." for _ in range(n_lines)]
    while len(anim_prompts) < n_lines:
        anim_prompts.append("Subtle idle movement.")
    anim_prompts = anim_prompts[:n_lines]
    logger.info("animation prompts generated", count=len(anim_prompts))

    await _update_step("animating scenes (parallel)")

    async def animate_scene(i):
        clip_path = os.path.join(clips_dir, f"clip_{i:02d}.mp4")
        if os.path.exists(clip_path):
            return
        dur = get_clip_duration(os.path.join(narr_dir, f"line_{i:02d}.mp3"))
        # Each scene uses its OWN edited image (not the base)
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        with open(img_path, "rb") as f:
            img_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        await generate_video_async(
            prompt=anim_prompts[i],
            output_path=clip_path, duration=dur, aspect_ratio="9:16",
            image_url=img_b64, timeout=600,
        )
        logger.info("scene animated", scene=i)

    await run_tasks(
        [lambda i=i: animate_scene(i) for i in range(n_lines)],
        parallel=True, max_concurrent=5,  # Rate limiter handles throttling
    )

    # ─── STEPS 6-10: All shared ───
    await _update_step("building video")
    seg_durations = build_silent_segments(n_lines, clips_dir, narr_dir, segments_dir)

    await _update_step("building intro")
    teasers_path = os.path.join(segments_dir, "teasers.mp4")
    actual_teaser_dur = build_intro_teasers(n_lines, narr_dir, clips_dir, segments_dir)

    await _update_step("concatenating")
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
    logger.info("hardcore ranked complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
