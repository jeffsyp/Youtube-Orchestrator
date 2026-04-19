"""Hardcore Ranked channel builder — visual comparison/ranking videos.

Uses a consistent humanlike frog protagonist with concept-specific accessories.
Same visual anchor (camera angle, location) for every comparison.
Uses shared functions for narration, intro, audio, subtitles.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess

import structlog
from packages.clients.channel_profiles import (
    get_channel_video_model,
    get_channel_video_provider,
    get_channel_video_resolution,
)

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
    run_tasks,
)

logger = structlog.get_logger()

# Channel-specific constants
CHANNEL_ID = 26
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"  # Liam
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "dark", "rising.mp3")
FROG_BASE_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "hardcore_ranked_frog_base.png")
FROG_LEGACY_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "hardcore_ranked_frog_v3.png")
MANUAL_PLANET_REF_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "assets",
    "reference",
    "hardcore_ranked_worlds",
)
TAGS = ["hardcore ranked", "comparison", "ranked", "shorts", "viral"]

BASE_CHARACTER_IDENTITY = (
    "The core Hardcore Ranked identity never changes: a human-sized athletic green frog person with glossy smooth skin, "
    "big expressive orange-and-black frog eyes, a friendly confident face, long frog feet, upright human posture, and a stylized but believable 3D character look. "
    "He is not a person in a frog suit and not a literal small animal. "
    "He stays the same character in every scene; only video-specific accessories or gear may change."
)

# Channel-specific image prompt rules
IMAGE_RULES = """RULES:
- The main character is a HUMAN-SIZED ATHLETIC GREEN FROG PERSON with big expressive frog eyes, upright human posture, long frog feet, and glossy stylized 3D skin. NOT a person in a frog suit. NOT a tiny frog.
- The core identity stays the same in every scene. Only concept-specific accessories or gear can change.
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


def _heuristic_character_variant(title: str, brief: str) -> dict:
    text = f"{title} {brief}".lower()
    variant_name = "default athlete"
    traits: list[str]

    if any(term in text for term in ["planet", "space", "moon", "mars", "jupiter", "pluto", "ceres", "uranus", "neptune", "saturn", "mercury"]):
        variant_name = "space athlete"
        traits = [
            "a glossy black astronaut helmet framing the frog head",
            "clean athletic tank top and fitted training shorts",
            "very light space-training styling only, while keeping the frog body fully recognizable",
        ]
    elif any(term in text for term in ["swim", "pool", "ocean", "water", "underwater"]):
        variant_name = "swim athlete"
        traits = [
            "sleek swim goggles or a swim cap suited to a frog athlete",
            "minimal competitive swim gear",
        ]
    elif any(term in text for term in ["cook", "kitchen", "grill", "bake", "oven", "chef"]):
        variant_name = "kitchen tester"
        traits = [
            "a simple apron or chef accessory",
            "practical kitchen-safe outfit details",
        ]
    elif any(term in text for term in ["bike", "cycle", "motorcycle", "vehicle", "racecar", "car"]):
        variant_name = "racer"
        traits = [
            "streamlined racing helmet or goggles",
            "light performance gear matched to a racing test",
        ]
    else:
        traits = [
            "simple athletic outfit matched to the test",
            "no unnecessary accessories unless the concept needs them",
        ]

    return {
        "variant_name": variant_name,
        "must_keep": BASE_CHARACTER_IDENTITY,
        "traits": traits,
        "negative_traits": [
            "do not turn him into a person in a frog costume",
            "do not change the head shape or eye style",
            "do not replace the frog body with generic human skin",
            "do not add logos, patches, printed words, backpacks, or bulky sci-fi gadgets unless the concept truly requires them",
        ],
    }


def _variant_rules_text(character_variant: dict) -> str:
    traits = character_variant.get("traits") or []
    negatives = character_variant.get("negative_traits") or []
    traits_text = "; ".join(traits) if traits else "no extra accessories"
    negatives_text = "; ".join(negatives) if negatives else "no off-model redesigns"
    return (
        "\n\nCONCEPT-SPECIFIC FROG VARIANT:\n"
        f"- {character_variant.get('must_keep', BASE_CHARACTER_IDENTITY)}\n"
        f"- For THIS video, add these consistent variant traits: {traits_text}.\n"
        f"- Forbidden drift: {negatives_text}.\n"
        "- Every image prompt must keep this exact variant consistent across the entire video.\n"
    )


def _manual_planet_ref(slug: str) -> str | None:
    path = os.path.join(MANUAL_PLANET_REF_DIR, f"{slug}_grounded.png")
    return path if os.path.exists(path) else None


def _parse_jump_label_inches(jump_label: str) -> int:
    text = str(jump_label).strip().lower()
    ft_match = re.search(r"(\d+)\s*ft", text)
    in_match = re.search(r"(\d+)\s*in", text)
    feet = int(ft_match.group(1)) if ft_match else 0
    inches = int(in_match.group(1)) if in_match else 0
    if feet or inches:
        return feet * 12 + inches
    num_match = re.search(r"(\d+)", text)
    return int(num_match.group(1)) if num_match else 20


def _display_jump_label(jump_label: str) -> str:
    total_inches = _parse_jump_label_inches(jump_label)
    feet, inches = divmod(total_inches, 12)
    parts: list[str] = []
    if feet:
        parts.append(f"{feet} {'foot' if feet == 1 else 'feet'}")
    if inches:
        parts.append(f"{inches} {'inch' if inches == 1 else 'inches'}")
    return " ".join(parts) if parts else str(jump_label)


async def _add_native_scene_label_with_model(edit_client, image_path: str, planet: str, jump_label: str, fact_label: str) -> None:
    """Ask gpt-image to add the scene label naturally inside the image.

    This avoids the obviously post-edited overlay look from PIL/ffmpeg text burns.
    """
    title_text = f"{str(planet).upper()} {_display_jump_label(jump_label).upper()}"
    fact_text = str(fact_label).upper()
    prompt = (
        "Keep this image composition almost identical. Do NOT move the subject, mast, lander, horizon, or camera angle. "
        "Add a clean broadcast-style measurement card in the upper-left corner that looks like it belongs in the original shot, not pasted on afterward. "
        "The card should be a sleek dark rounded rectangle with crisp modern typography and subtle professional styling. "
        f"Exact main line text: {title_text}. "
        f"Exact smaller line text: {fact_text}. "
        "The text must be perfectly legible, correctly spelled, and integrated naturally into the image. Preserve everything else."
    )

    for attempt in range(3):
        img_file = open(image_path, "rb")
        try:
            resp = await edit_client.images.edit(
                model="gpt-image-1.5",
                image=img_file,
                prompt=prompt,
                size="1024x1536",
                quality="medium",
                input_fidelity="high",
            )
        finally:
            img_file.close()

        if resp.data and resp.data[0].b64_json:
            with open(image_path, "wb") as f:
                f.write(base64.b64decode(resp.data[0].b64_json))
            logger.info("scene label added natively by image model", image=image_path, attempt=attempt + 1)
            return
        await asyncio.sleep(1.5)

    raise RuntimeError(f"Failed to add native scene label for {planet} after retries")


async def _ensure_base_frog_reference(edit_client) -> str:
    """Create the neutral Hardcore Ranked frog base asset if it doesn't exist yet."""
    if os.path.exists(FROG_BASE_REF):
        return FROG_BASE_REF

    os.makedirs(os.path.dirname(FROG_BASE_REF), exist_ok=True)
    source_ref = FROG_LEGACY_REF if os.path.exists(FROG_LEGACY_REF) else None
    if not source_ref:
        raise RuntimeError("Missing Hardcore Ranked frog reference image")

    prompt = (
        "Create a clean neutral base-character reference on a plain white background. "
        "Keep the exact same core frog identity and proportions, but remove the astronaut helmet and any concept-specific props. "
        "The result should be a human-sized athletic green frog person with the same expressive eyes, same face, same body proportions, "
        "wearing only a simple white athletic tank top and black training shorts. "
        "Full body, centered, facing forward, no extra accessories."
    )

    source_file = open(source_ref, "rb")
    try:
        resp = await edit_client.images.edit(
            model="gpt-image-1.5",
            image=source_file,
            prompt=prompt,
            size="1024x1536",
            quality="medium",
            input_fidelity="high",
        )
    finally:
        source_file.close()

    if not (resp.data and resp.data[0].b64_json):
        raise RuntimeError("Failed to create Hardcore Ranked base frog reference")

    with open(FROG_BASE_REF, "wb") as f:
        f.write(base64.b64decode(resp.data[0].b64_json))
    logger.info("created hardcore ranked base frog reference", path=FROG_BASE_REF)
    return FROG_BASE_REF


async def _build_character_variant_ref(edit_client, base_ref_path: str, variant: dict, output_path: str, title: str) -> str:
    """Generate a concept-specific variant ref from the neutral frog base."""
    if os.path.exists(output_path):
        return output_path

    traits = "; ".join(variant.get("traits") or [])
    negatives = "; ".join(variant.get("negative_traits") or [])
    prompt = (
        f"Transform this exact Hardcore Ranked frog base character into the concept-specific variant for {title}. "
        f"{variant.get('must_keep', BASE_CHARACTER_IDENTITY)} "
        f"Add these consistent variant traits: {traits}. "
        f"Forbidden drift: {negatives}. "
        "Keep the same frog face, same eyes, same body proportions, and same full-body white-background reference image. "
        "Do not change the pose or camera. Do not add any logos, patches, words, badges, backpacks, or extra gear beyond what the prompt explicitly calls for."
    )

    base_file = open(base_ref_path, "rb")
    try:
        resp = await edit_client.images.edit(
            model="gpt-image-1.5",
            image=base_file,
            prompt=prompt,
            size="1024x1536",
            quality="medium",
            input_fidelity="high",
        )
    finally:
        base_file.close()

    if not (resp.data and resp.data[0].b64_json):
        shutil.copy2(base_ref_path, output_path)
        return output_path

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(resp.data[0].b64_json))
    logger.info("created hardcore ranked concept variant ref", path=output_path, variant=variant.get("variant_name"))
    return output_path


async def _adapt_manual_world_ref_for_variant(
    edit_client,
    source_path: str,
    variant: dict,
    output_path: str,
    planet: str,
) -> str:
    """Preserve the approved world composition while updating the frog to the active per-video variant."""
    if os.path.exists(output_path):
        return output_path

    traits = "; ".join(variant.get("traits") or [])
    negatives = "; ".join(variant.get("negative_traits") or [])
    prompt = (
        "Keep this image composition almost identical. Preserve the exact planet surface, sky, horizon, mast, lander, "
        "camera angle, crop, lighting, and grounded pre-jump stance. "
        f"Update the frog character so it matches the active Hardcore Ranked variant for {planet}. "
        f"Core identity to preserve: {variant.get('must_keep', BASE_CHARACTER_IDENTITY)} "
        f"Required variant traits: {traits}. "
        f"Forbidden drift: {negatives}. "
        "Both feet must stay planted on the ground in the same place. "
        "Keep the character clean and simple: no extra props, no logos, no printed text, no badges, and no unnecessary gadgets."
    )

    source_file = open(source_path, "rb")
    try:
        resp = await edit_client.images.edit(
            model="gpt-image-1.5",
            image=source_file,
            prompt=prompt,
            size="1024x1536",
            quality="medium",
            input_fidelity="high",
        )
    finally:
        source_file.close()

    if not (resp.data and resp.data[0].b64_json):
        shutil.copy2(source_path, output_path)
        return output_path

    with open(output_path, "wb") as f:
        f.write(base64.b64decode(resp.data[0].b64_json))
    logger.info("adapted approved world ref to active frog variant", path=output_path, planet=planet)
    return output_path


def _is_ranked_actual_planets(concept: dict, scenes_meta: list[dict]) -> bool:
    if concept.get("format_strategy") == "ranked_actual_planets" and scenes_meta:
        return True
    if not scenes_meta:
        return False
    required_keys = {"planet", "jump_label", "fact_label", "slug"}
    return all(required_keys.issubset(set(scene.keys())) for scene in scenes_meta if isinstance(scene, dict))


def _has_explicit_scene_plan(concept: dict, scenes_meta: list[dict]) -> bool:
    if concept.get("format_strategy") == "ranked_actual_planets":
        return False
    if not scenes_meta:
        return False
    return all(isinstance(scene, dict) and scene.get("image_prompt") for scene in scenes_meta)


async def build_hardcore_ranked(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Hardcore Ranked video build."""
    from packages.clients.grok import generate_image_dalle_async

    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])
    scenes_meta = concept.get("scenes") if isinstance(concept.get("scenes"), list) else []
    is_planet_jump_format = _is_ranked_actual_planets(concept, scenes_meta)
    has_explicit_scene_plan = _has_explicit_scene_plan(concept, scenes_meta)
    video_provider = str(concept.get("video_provider") or get_channel_video_provider(CHANNEL_ID)).strip().lower()
    video_model = concept.get("video_model") or get_channel_video_model(CHANNEL_ID)
    video_resolution = concept.get("video_resolution") or get_channel_video_resolution(CHANNEL_ID)

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
- Line 1 MUST state the topic as a neutral question: "How fast can you swim across a pool in every liquid?" or "How long does each material take to melt in the sun?" — this IS the title. Shorts viewers don't see video titles.
- NEVER name the test-subject character — no "frog", no "frog guy", no nickname. If a human subject is needed, refer to generic "you" / "a person" / "the test subject".
- Line 2 onwards: NUMBERED ranked list. Each line starts with the rank number. Example:
  - "Number 1: Water. Four seconds. Built for this."
  - "Number 2: Honey. Three hours. Basically a statue."
  - "Number 3: Rocket fuel. Instant explosion. Never seen again."
- ONLY 4-5 items total (lines 2-5 or 2-6). Pick the most DIFFERENT and INTERESTING ones — skip boring/similar items (saltwater is too close to water, skip it)
- CRITICAL: ONE item PER LINE. NEVER combine multiple items in one line. Each line = one surface/liquid/vehicle/planet = one scene = one image.
  BAD: "Grass gets him six feet. Dirt path, eight. Asphalt, fifteen." (3 items crammed into 1 line — impossible to visualize)
  GOOD: "Number 2: Grass. Six feet. Barely counts."
  GOOD: "Number 3: Dirt path. Eight feet. Getting somewhere."
- The SAME ACTION is performed in every scene — only the VARIABLE changes
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

    explicit_image_prompts: list[str] = []
    explicit_video_prompts: list[str] = []
    explicit_scene_prompts_for_lines: list[str] = []
    explicit_video_prompts_for_lines: list[str] = []
    if has_explicit_scene_plan:
        explicit_image_prompts = [str(scene.get("image_prompt", "")).strip() for scene in scenes_meta]
        explicit_video_prompts = [str(scene.get("video_prompt", "")).strip() for scene in scenes_meta]
        if len(explicit_image_prompts) == n_lines:
            explicit_scene_prompts_for_lines = explicit_image_prompts[:]
            explicit_video_prompts_for_lines = explicit_video_prompts[:]
        elif len(explicit_image_prompts) == max(1, n_lines - 1):
            explicit_scene_prompts_for_lines = [explicit_image_prompts[0], *explicit_image_prompts]
            explicit_video_prompts_for_lines = [explicit_video_prompts[0], *explicit_video_prompts]
        else:
            explicit_scene_prompts_for_lines = explicit_image_prompts[:n_lines]
            explicit_video_prompts_for_lines = explicit_video_prompts[:n_lines]
        while len(explicit_scene_prompts_for_lines) < n_lines and explicit_scene_prompts_for_lines:
            explicit_scene_prompts_for_lines.append(explicit_scene_prompts_for_lines[-1])
        while len(explicit_video_prompts_for_lines) < n_lines and explicit_video_prompts_for_lines:
            explicit_video_prompts_for_lines.append(explicit_video_prompts_for_lines[-1])

    # ─── STEP 2: Narration (shared) ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
    )

    from openai import AsyncOpenAI
    edit_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)

    # ─── STEP 3: Build concept-specific frog variant ───
    brief = concept.get("brief", "")
    character_variant = concept.get("character_variant") if isinstance(concept.get("character_variant"), dict) else None
    character_ref_path = ""
    if not has_explicit_scene_plan:
        if not character_variant:
            await _update_step("designing character variant")
            character_variant = _heuristic_character_variant(title, brief)
        concept["character_variant"] = character_variant
        variant_path = os.path.join(output_dir, "character_variant.json")
        with open(variant_path, "w") as vf:
            json.dump(character_variant, vf, indent=2)

        base_character_ref = await _ensure_base_frog_reference(edit_client)
        character_ref_path = await _build_character_variant_ref(
            edit_client,
            base_character_ref,
            character_variant,
            os.path.join(output_dir, "character_variant_ref.png"),
            title,
        )

    # ─── STEP 4: Image prompts (shared + channel rules) ───
    extra_rules = f"\n\nCONCEPT-SPECIFIC INSTRUCTIONS:\n{brief}" if brief else ""
    if has_explicit_scene_plan or is_planet_jump_format:
        image_prompts = []
    else:
        image_prompts = await generate_image_prompts(
            narration_lines,
            IMAGE_RULES + _variant_rules_text(character_variant) + extra_rules,
            _update_step,
        )

    manual_planet_refs: dict[str, str] = {}
    if is_planet_jump_format:
        for scene in scenes_meta:
            slug = str(scene.get("slug") or "").strip().lower()
            if slug:
                ref_path = _manual_planet_ref(slug)
                if ref_path:
                    manual_planet_refs[slug] = ref_path
        logger.info(
            "manual planet refs discovered",
            found=sorted(manual_planet_refs.keys()),
            expected=[str(scene.get("slug")) for scene in scenes_meta],
        )
    use_manual_planet_refs = is_planet_jump_format and len(manual_planet_refs) == len(scenes_meta)
    if use_manual_planet_refs:
        variant_ref_dir = os.path.join(output_dir, "variant_world_refs")
        os.makedirs(variant_ref_dir, exist_ok=True)
        adapted_refs: dict[str, str] = {}
        for scene in scenes_meta:
            slug = str(scene.get("slug") or "").strip().lower()
            source_ref = manual_planet_refs.get(slug)
            if not source_ref:
                continue
            adapted_refs[slug] = await _adapt_manual_world_ref_for_variant(
                edit_client,
                source_ref,
                character_variant,
                os.path.join(variant_ref_dir, f"{slug}_variant.png"),
                scene.get("planet", slug.title()),
            )
        if len(adapted_refs) == len(scenes_meta):
            manual_planet_refs = adapted_refs
            logger.info("using variant-adapted approved world refs", slugs=sorted(adapted_refs.keys()))

    # ─── STEP 5: Generate base scene → edit per liquid → animate ───
    if has_explicit_scene_plan:
        await _update_step("generating scene images")
        for i in range(n_lines):
            img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
            if os.path.exists(img_path):
                continue
            prompt = explicit_scene_prompts_for_lines[i]
            await generate_image_dalle_async(
                prompt=prompt,
                output_path=img_path,
                size="1024x1536",
            )
            logger.info("explicit scene image generated", scene=i, prompt=prompt[:120])
        base_scene_path = os.path.join(images_dir, "scene_00.png")
        edit_prompts = explicit_scene_prompts_for_lines
        concept_type = "EXPLICIT"
    else:
        await _update_step("generating base scene")

        # Determine concept type so we pick the right base scene + scene-change strategy
        concept_type = "MOTION" if is_planet_jump_format else None
        if not concept_type:
            from packages.clients.claude import generate as claude_gen_base
            concept_type_resp = claude_gen_base(
            prompt=f"""Classify this Hardcore Ranked concept into ONE category:

CONCEPT: {title}

CATEGORIES:
- "MOTION" — comparing terrain/condition where character physically moves (run, swim, roll, jump, race). The SETTING is the constant, the SURFACE/MEDIUM changes per scene.
- "EQUIPMENT" — comparing tools/methods (cook with X, build with Y, cut with Z). The CHARACTER ACTION stays similar, the TOOL changes per scene.
- "CONDITION" — comparing extreme environments or states (survive at X temperature, perform at Y pressure). The CHARACTER is in varying environments.
- "QUANTITY" — comparing amounts/scales (how many X can fit in Y, how much Z is too much).

Return ONLY the category name, nothing else.""",
            max_tokens=20,
            )
            concept_type = concept_type_resp.strip().upper().strip('"').split()[0] if concept_type_resp else "MOTION"
        logger.info("concept type classified", type=concept_type)

        brief = concept.get("brief", "")
        if use_manual_planet_refs:
            base_prompt = "Approved manual Earth grounded reference."
        elif is_planet_jump_format:
            first_scene = scenes_meta[0]
            variant_traits = "; ".join(character_variant.get("traits") or [])
            base_prompt = (
            "Photorealistic. SINGLE IMAGE only — NOT a comic panel, NOT a chart, NOT multiple panels. "
            "Strict side-view full-body comparison shot. The human-sized athletic green frog character stands ON THE GROUND "
            "with both feet planted flat beside a striped measurement mast and a silver research lander used for scale. "
            "The body pose is neutral and grounded, with no crouch, no leap, no floating, and no hero-angle exaggeration. "
            f"Keep these concept-specific accessories consistent: {variant_traits}. "
            f"Actual {first_scene.get('planet', 'Earth')} environment: {first_scene.get('environment', 'open rocky plain')}. "
            "The character is in a grounded pre-jump stance, ready to jump but NOT airborne. "
            "Keep the mast and lander visible in the same frame for scale. "
            "This is a static scientific measurement setup before the jump begins. NO text anywhere."
            )
        elif brief:
            _base_text = brief
            for _marker in ['For edits', 'For every edit', 'For animation', 'For each edit']:
                _base_text = _base_text.split(_marker)[0]
            _character_desc = (
            "The character is a HUMAN-SIZED athletic green frog person with glossy skin, big expressive frog eyes, upright human posture, "
            "and the same core face/body from the reference image. "
            f"Add these consistent variant traits: {'; '.join(character_variant.get('traits') or [])}."
            )
            if concept_type == "MOTION":
                _camera = "CAMERA: Behind-view, looking over the character's shoulder down the path/slope/track ahead. Like a TV camera behind a starting line."
            elif concept_type == "EQUIPMENT":
                _camera = "CAMERA: Side or three-quarter view showing the character interacting with the equipment/tool and the subject of the experiment clearly visible. The setting should match the activity (kitchen, workbench, outdoors, etc.)."
            elif concept_type == "CONDITION":
                _camera = "CAMERA: Wide or medium shot showing the character IN the extreme environment, with clear visual cues of the condition (temperature extremes, pressure, etc.)."
            else:
                _camera = "CAMERA: Wide shot showing the character and the quantity/scale being measured clearly."
            base_prompt = f"Photorealistic. SINGLE IMAGE only — NOT a comic panel layout, NOT multiple panels, NOT a grid. One continuous scene. {_camera} {_character_desc} {_base_text.strip()} NO text anywhere. ONE single frame only."
        else:
            base_prompt_resp = claude_gen_base(
            prompt=f"""Based on this concept, describe the BASE SCENE for the comparison.

CONCEPT: {title}
CONCEPT TYPE: {concept_type}

THE CHARACTER: A human-sized athletic green frog person with glossy skin, big expressive frog eyes, upright human posture, and the same core face/body from the reference image.
CONCEPT-SPECIFIC VARIANT TRAITS: {'; '.join(character_variant.get("traits") or [])}

CAMERA + SETTING based on concept type:
- MOTION (races, jumps, rolls): Camera BEHIND character, looking down a track/path/slope. Starting-line energy.
- EQUIPMENT (cooking, building, testing tools): Side or three-quarter view. Setting matches the activity (kitchen for cooking, workbench for building, lab for testing). Tools/equipment clearly visible.
- CONDITION (surviving extremes, temperatures): Character IN the environment, wide/medium shot. Environmental cues visible.
- QUANTITY (how much fits, how many): Wide shot showing scale clearly.

ACTION: The character must be MID-ACTION performing the specific activity from the title. Not standing still.

Start with "Photorealistic." End with "NO text anywhere."
Return ONLY the prompt.""",
            max_tokens=300,
            )
            base_prompt = base_prompt_resp.strip().strip('"')
        logger.info("base prompt", prompt=base_prompt[:100])

        base_scene_path = os.path.join(images_dir, "base_scene.png")
        if use_manual_planet_refs:
            earth_ref = manual_planet_refs.get("earth")
            if not earth_ref:
                raise RuntimeError("Missing approved manual Earth grounded reference for Hardcore Ranked planet format")
            shutil.copy2(earth_ref, base_scene_path)
            logger.info("using approved manual grounded Earth reference as base scene", path=earth_ref)
        elif not os.path.exists(base_scene_path):
            # Use frog reference image as input for consistent character
            if os.path.exists(character_ref_path):
                frog_file = open(character_ref_path, "rb")
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
        if use_manual_planet_refs and scenes_meta:
            first_scene = scenes_meta[0]
            await _add_native_scene_label_with_model(
            edit_client,
            scene_00,
            first_scene.get("planet", "Earth"),
            first_scene.get("jump_label", "1 ft 8 in"),
            first_scene.get("fact_label", "SPACE FACT"),
            )

        # Edit base scene for each liquid/variable — gpt-image-1.5 edit with input_fidelity=high
        await _update_step("creating scene variants")

        from packages.clients.claude import generate as claude_gen_edits

    # Build concept-aware guidance for the per-scene edits
    if not has_explicit_scene_plan and concept_type == "MOTION":
        _edit_guidance = """MOTION concept guidance:
- The character is in the SAME setting across all scenes (same road, same pool, same arena)
- The SURFACE/MEDIUM/OPPONENT is what changes per scene
- Show the character performing the action (running, swimming, jumping)
- For RACE-style comparisons: since Grok can't animate things pulling ahead, BAKE the result into the image — if the frog loses, show the opponent already far ahead with motion blur and distance. If the frog wins, show them clearly in the lead.
- If the variable is a SURFACE (grass, ice, asphalt): show the character on that specific surface with visible differences in their traction/speed"""
    elif not has_explicit_scene_plan and concept_type == "EQUIPMENT":
        _edit_guidance = """EQUIPMENT concept guidance:
- The SETTING can evolve — a solar oven belongs outdoors, a microwave in a kitchen, a magnifying glass outside on a sunny day
- Each scene should show the character actively USING the specific tool/method
- The SUBJECT of the experiment (egg, soup, whatever is being cooked/built/tested) is clearly visible
- Show the RESULT becoming visible — egg cooking, smoke rising, water boiling, etc.
- The character's expression/posture should match the effort level required (straining for a slow method, relaxed for an easy one)"""
    elif not has_explicit_scene_plan and concept_type == "CONDITION":
        _edit_guidance = """CONDITION concept guidance:
- The ENVIRONMENT is the variable — each scene should clearly show the character IN that specific extreme condition
- Visual cues of the condition: ice forming (cold), sweat pouring (hot), body deformed (pressure), etc.
- Background/setting must match the condition (frozen landscape vs molten lava)
- The character's body reaction tells the story"""
    elif not has_explicit_scene_plan:
        _edit_guidance = """QUANTITY concept guidance:
- Each scene shows a DIFFERENT amount/scale visibly
- The character should be visible for scale reference
- Make the scale comparison obvious — small pile vs massive mountain"""

    if has_explicit_scene_plan:
        edit_prompts = explicit_scene_prompts_for_lines
    elif use_manual_planet_refs:
        edit_prompts = ["No changes — grounded baseline Earth hook."]
        for scene in scenes_meta:
            edit_prompts.append(f"Use approved grounded {scene.get('planet', scene.get('slug', 'planet'))} reference.")
        while len(edit_prompts) < n_lines:
            edit_prompts.append(edit_prompts[-1])
        edit_prompts = edit_prompts[:n_lines]
    elif is_planet_jump_format:
        edit_prompts = ["No changes — grounded baseline Earth hook."]
        for scene in scenes_meta:
            edit_prompts.append(
                f"Only change the planet environment to {scene.get('environment', scene.get('planet', 'planet surface'))}. "
                "Treat the input image as a LOCKED TEMPLATE. Preserve the exact same side-view camera, crop, frog character size, body pose, foot placement, "
                "striped mast position, and silver lander position. "
                "The jumper must remain ON THE GROUND beside the mast with both boots fully touching the surface in a pre-jump stance. "
                "Do NOT show the jumper crouching deeply, airborne, floating, landing, or at the apex. "
                "This image is a static start frame before the jump only."
            )
        while len(edit_prompts) < n_lines:
            edit_prompts.append(edit_prompts[-1])
        edit_prompts = edit_prompts[:n_lines]
    else:
        edits_resp = claude_gen_edits(
            prompt=f"""For each narration line (except line 0), write a SHORT edit instruction. The base scene shows: {base_prompt[:200]}...

CONCEPT TITLE: {title}
CONCEPT TYPE: {concept_type}

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

{_edit_guidance}

KEY RULES:
- The CHARACTER must stay visually consistent across scenes — same frog face, same body proportions, same variant accessories
- For MOTION concepts: keep the same camera angle and setting, only change the surface/opponent
- For EQUIPMENT/CONDITION concepts: the BACKGROUND CAN CHANGE to match the tool/environment. Don't force the base scene's setting if it doesn't fit the variable.
- Each scene should be VISUALLY DISTINCT from the others — not all same background if the concept doesn't require it
- The ranking should ESCALATE visually: the last scene should feel more extreme/impressive than the first
- BAKE the result into the image (don't show something "about to happen" — show it happening/happened)

Return ONLY a JSON array of {n_lines} strings. Line 0 should be "No changes — use base scene as is." """,
            max_tokens=1500,
        )
        edits_match = re.search(r'\[.*\]', edits_resp, re.DOTALL)
        edit_prompts = json.loads(edits_match.group()) if edits_match else ["No changes." for _ in range(n_lines)]
        while len(edit_prompts) < n_lines:
            edit_prompts.append("No changes.")
        edit_prompts = edit_prompts[:n_lines]

    if not has_explicit_scene_plan:
        for i in range(1, n_lines):
            img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
            if os.path.exists(img_path):
                continue
            if use_manual_planet_refs:
                scene_meta = scenes_meta[i - 1] if i - 1 < len(scenes_meta) else None
                slug = str((scene_meta or {}).get("slug") or "").strip().lower()
                ref_path = manual_planet_refs.get(slug)
                if not ref_path:
                    raise RuntimeError(f"Missing approved grounded reference for scene {i} slug={slug}")
                shutil.copy2(ref_path, img_path)
                await _add_native_scene_label_with_model(
                    edit_client,
                    img_path,
                    scene_meta.get("planet", "Planet"),
                    scene_meta.get("jump_label", "1 ft 8 in"),
                    scene_meta.get("fact_label", "SPACE FACT"),
                )
                logger.info("copied approved manual grounded scene reference", scene=i, slug=slug, path=ref_path)
                continue
            review_text = ""
            for attempt in range(4):
                try:
                    base_file = open(base_scene_path, "rb")
                    if is_planet_jump_format:
                        edit_instruction = (
                            "TREAT THE INPUT IMAGE AS A LOCKED TEMPLATE. "
                            "Do not change the frog's pose, height in frame, arm position, leg position, foot placement, or facial direction. "
                            "Do not change the camera angle, crop, or framing. "
                            "Keep the striped mast and silver lander visible in the exact same relative positions and scale. "
                            f"{edit_prompts[i]} NO text anywhere."
                        )
                    else:
                        edit_instruction = (
                            f"The character must look IDENTICAL to the input image — same suit, same helmet, same body proportions, same colors. "
                            + ("Same camera angle, same setting — only change the surface/opponent/variable. Everything else stays pixel-identical. " if concept_type == "MOTION"
                               else "The character stays consistent but the BACKGROUND and SETTING can change to match the variable for this scene. ")
                            + f"Change: {edit_prompts[i]} NO text anywhere."
                        )
                    resp = await edit_client.images.edit(
                        model="gpt-image-1.5",
                        image=base_file,
                        prompt=edit_instruction,
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
                except Exception as e:
                    logger.warning("edit failed", scene=i, attempt=attempt, error=str(e)[:80])
                    try: base_file.close()
                    except: pass
                    await asyncio.sleep(3)
                    continue
                if not os.path.exists(img_path):
                    continue

                # Review: verify the edited image still matches the base scene
                try:
                    import anthropic
                    review_client = anthropic.Anthropic()
                    with open(img_path, "rb") as rf:
                        img_b64_review = base64.b64encode(rf.read()).decode()
                    with open(base_scene_path, "rb") as rf:
                        base_b64_review = base64.b64encode(rf.read()).decode()
                    if is_planet_jump_format:
                        review_prompt = (
                            "Image 1 is the locked base measurement setup. Image 2 should be the SAME setup on a different planet. "
                            "PASS only if ALL of these are true: same side-view camera, same crop, same frog character size, same body pose, both boots touching the ground, "
                            "striped mast visible, silver lander visible, and the image is clearly a pre-jump start frame. "
                            "FAIL if the frog is airborne, floating, landing, crouching deeply, framed differently, missing the mast, or missing the lander. "
                            "Answer PASS or FAIL with one short reason."
                        )
                    else:
                        review_prompt = (
                            "Image 1 is the base scene. Image 2 is an edited version. Does image 2 keep the SAME camera angle, same character position, same setting as image 1? "
                            "Only the liquid/variable should change. Answer PASS or FAIL with reason."
                        )
                    review = review_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=200,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base_b64_review}},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64_review}},
                                {"type": "text", "text": review_prompt},
                            ],
                        }],
                    )
                    review_text = review.content[0].text
                    if "FAIL" in review_text:
                        logger.warning("scene edit review FAILED", scene=i, reason=review_text[:100], attempt=attempt + 1)
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        if attempt < 3:
                            await asyncio.sleep(2)
                            continue
                    else:
                        logger.info("scene edit review passed", scene=i)
                except Exception as e:
                    logger.warning("scene edit review skipped", error=str(e)[:80])
                break
            if not os.path.exists(img_path):
                reason = review_text[:120] if review_text else "review failed"
                raise RuntimeError(f"Failed to create grounded scene {i} variant after retries: {reason}")

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
        from packages.clients.workflow_state import create_review_task, get_pending_review_task, resolve_review_task
        await _update_step("images ready for review")
        await create_review_task(
            run_id=run_id,
            kind="images",
            concept_id=concept.get("concept_id"),
            channel_id=concept.get("channel_id"),
            stage="images ready for review",
            payload={
                "expected_images": n_lines,
                "images_dir": os.path.abspath(images_dir),
                "image_names": [f"scene_{i:02d}.png" for i in range(n_lines)],
            },
        )
        if os.path.exists(_deny_file):
            os.remove(_deny_file)
        while True:
            await asyncio.sleep(3)
            if os.path.exists(_approval_file):
                logger.info("user approved images")
                os.remove(_approval_file)
                await resolve_review_task(
                    run_id=run_id,
                    kind="images",
                    status="approved",
                    resolution={"source": "file_fallback"},
                )
                break
            if os.path.exists(_deny_file):
                logger.info("user denied images — regenerating with feedback")
                os.remove(_deny_file)
                await resolve_review_task(
                    run_id=run_id,
                    kind="images",
                    status="rejected",
                    resolution={"source": "file_fallback"},
                )
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
                        elif not has_explicit_scene_plan:
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
                        else:
                            await generate_image_dalle_async(
                                prompt=f"{edit_prompts[i]} User feedback: {fb_text}.",
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
                await create_review_task(
                    run_id=run_id,
                    kind="images",
                    concept_id=concept.get("concept_id"),
                    channel_id=concept.get("channel_id"),
                    stage="images ready for review",
                    payload={
                        "expected_images": n_lines,
                        "images_dir": os.path.abspath(images_dir),
                        "image_names": [f"scene_{i:02d}.png" for i in range(n_lines)],
                    },
                )
                await _update_step("images ready for review")
                continue

            pending_task = await get_pending_review_task(run_id, "images")
            if pending_task is None:
                logger.info("image review resolved via review task")
                break

    # ─── STEP 5: Animation prompts — concept-specific movement per scene ───
    await _update_step("planning animations")
    if has_explicit_scene_plan:
        anim_prompts = explicit_video_prompts_for_lines[:]
        while len(anim_prompts) < n_lines:
            anim_prompts.append(anim_prompts[-1] if anim_prompts else "Subtle motion.")
    elif is_planet_jump_format:
        jump_inches_by_scene = [
            _parse_jump_label_inches(scene.get("jump_label", "1 ft 8 in"))
            for scene in scenes_meta
        ]
        ranked_scene_indices = sorted(
            range(len(jump_inches_by_scene)),
            key=lambda idx: jump_inches_by_scene[idx],
            reverse=True,
        )
        top_two_scene_indices = set(ranked_scene_indices[:2])
        anim_prompts = [
            "Start on the ground beside the striped mast. The frog athlete does one tiny anticipatory bend and settles back down. Keep the full body, mast, lander, and native measurement card visible. No camera movement."
        ]
        for scene_idx, scene in enumerate(scenes_meta):
            jump_label = scene.get("jump_label", "1 ft 8 in")
            jump_inches = _parse_jump_label_inches(jump_label)
            framing_note = "Keep the full body, mast, lander, and native label card visible with the usual side-view framing."
            if jump_inches <= 10:
                jump_action = "The jumper bends deeply, pushes upward with effort, barely rises a few inches beside the mast, then lands back down fast and heavy."
                framing_note = "Keep the camera locked and close so the failed jump feels heavy and cramped."
            elif jump_inches <= 24:
                jump_action = f"The jumper starts grounded, performs a normal athletic jump to about {jump_label}, then lands back in the same place."
                framing_note = "Keep the classic side-view comparison framing locked in place."
            elif jump_inches <= 72:
                jump_action = (
                    "The jumper crouches and launches obviously higher than Earth, soaring several mast-heights upward in one clean arc, "
                    "hanging long enough that the height difference is unmistakable before dropping back to the same landing spot."
                )
                framing_note = "Start wider than the Earth shot with a lot more sky, and let the camera visibly track up so the height looks dramatically bigger than Earth."
            elif jump_inches <= 240:
                jump_action = (
                    "The jumper rockets upward with absurd low gravity, climbing far beyond the mast until the mast and lander look small below, "
                    "then falls all the way back down to the same landing point."
                )
                framing_note = "Start very wide and low, then track upward aggressively so the jumper becomes tiny against the sky before following the fall back down."
            else:
                jump_action = (
                    "The jumper blasts skyward with completely impossible low-gravity power, shooting out of the original ground frame and leaving only sky for a long beat, "
                    "while the mast and lander shrink into tiny dots far below before a huge delayed fall carries the jumper back down to the same landing spot."
                )
                framing_note = "Start extremely wide with massive headroom, let the jumper leave the original ground frame entirely, and keep following upward until the jump feels wildly, hilariously taller than every previous world."
            if scene_idx in top_two_scene_indices:
                jump_action += (
                    " The airtime must feel absurdly long: the jumper becomes a tiny speck high in the sky, hangs there for a beat, "
                    "and only much later re-enters from far above."
                )
                framing_note += (
                    " Treat this as an extreme-world hero shot, not a normal comparison jump. The viewer should feel like the jumper nearly escaped the scene."
                )
            anim_prompts.append(
                f"{jump_action} Show the FULL motion cycle in one shot: start on ground, takeoff, apex, and landing. "
                f"Visually overexaggerate the height difference compared with the previous worlds so each new jump is unmistakably bigger or smaller at a glance. "
                f"Keep the {scene.get('planet', 'planet')} environment stable, with the mast and lander visible for scale. "
                f"Keep the native measurement card intact in the frame. {framing_note} No scene cuts."
            )
        while len(anim_prompts) < n_lines:
            anim_prompts.append(anim_prompts[-1])
        anim_prompts = anim_prompts[:n_lines]
    else:
        from packages.clients.claude import generate as claude_gen
        anim_resp = claude_gen(
            prompt=f"""For each narration line, write an EXTREMELY AGGRESSIVE animation prompt. Grok defaults to slow zooms — we must FORCE it to animate the specific physical action for this concept.

CONCEPT TITLE: {title}

NARRATION:
{chr(10).join(f'{i}: "{line}"' for i, line in enumerate(narration_lines))}

THE PROBLEM: Grok makes static slideshows unless the prompt is extremely specific about physical motion. EVERY word of the prompt must describe what's moving RIGHT NOW, and the motion must MATCH THE CONCEPT.

STEP 1 — IDENTIFY THE ACTION from the title/narration:
- "Race/run/sprint/jump" → running motions, leg cycles, chase
- "Cook/make/create X" → specific cooking/building motions: stirring, flipping, mixing, heating, focusing sunlight through a lens, flames flickering
- "Try to X / attempt X" → the specific attempt motion + reactions to result (success or failure)
- "Survive X / endure X" → body reactions to the condition (shivering, sweating, flailing)
- "Test/compare X" → the specific test being performed

STEP 2 — WRITE EVERY PROMPT WITH:
1. Character's specific limb/body motion matching the concept's action (e.g. for cooking: "Frog holds magnifying glass steady with both hands, tilts it to focus the sunlight beam, eggshell begins to crackle and sizzle, smoke curls up")
2. What the object/variable is DOING in reaction (the egg cooks, the hill tilts, the sprinter pulls ahead, the water freezes)
3. Environmental cues that sell the moment: steam, dust, sparks, smoke, splashes, wind, light
4. Frog's expression/reaction: concentrated focus, panic, pride, disbelief, exhaustion — match the moment
5. The frog stays ON THE EXPERIMENT — never wanders off, never does random filler motion, always engaged with the variable being tested

RULES:
- The frog is the EXPERIMENTER. Every scene shows them performing the specific action from the narration.
- Line 0 (hook): frog at the starting position, prepping the action (holding the lens, readying the pan, lining up the shot). Build anticipation.
- Lines 1+: FULL EXECUTION of the specific action. Each scene shows a different variable/attempt.
- Use specific verbs matching the concept: for racing → pumping, cycling, thundering / for cooking → stirring, flipping, searing / for freezing → shivering, trembling, cracking / for jumping → crouching, launching, landing
- NEVER: generic "moves", "does stuff", random idle animation. Always specific to the concept.
- NEVER say "camera zooms" or "camera pans" — describe character + environment motion only.
- Each prompt should be 3-4 sentences packed with motion verbs relevant to the specific concept.

Return ONLY a JSON array of {n_lines} strings.""",
            max_tokens=2500,
        )
        anim_match = re.search(r'\[.*\]', anim_resp, re.DOTALL)
        anim_prompts = json.loads(anim_match.group()) if anim_match else ["Subtle idle movement." for _ in range(n_lines)]
        while len(anim_prompts) < n_lines:
            anim_prompts.append("Subtle idle movement.")
        anim_prompts = anim_prompts[:n_lines]
    logger.info("animation prompts generated", count=len(anim_prompts))

    def _veo_duration(narr_path: str, line_index: int | None = None) -> int:
        if is_planet_jump_format and line_index is not None and line_index > 0:
            scene_idx = line_index - 1
            if scene_idx in top_two_scene_indices:
                return 8
            if 0 <= scene_idx < len(jump_inches_by_scene) and jump_inches_by_scene[scene_idx] >= 120:
                return 6
        requested = get_clip_duration(narr_path)
        if requested <= 4:
            return 4
        if requested <= 6:
            return 6
        return 8

    async def animate_scene(i, provider: str, model: str | None, resolution: str):
        clip_path = os.path.join(clips_dir, f"clip_{i:02d}.mp4")
        if os.path.exists(clip_path):
            return
        narr_path = os.path.join(narr_dir, f"line_{i:02d}.mp3")
        scene_label = "hook" if i == 0 else f"scene {i}/{n_lines - 1}"
        await _update_step(f"animating {scene_label} with {provider}")
        img_path = os.path.join(images_dir, f"scene_{i:02d}.png")
        if provider == "veo":
            from packages.clients.veo import generate_video_async as veo_generate

            primary_model = model or "veo-3.1-lite-generate-001"
            await veo_generate(
                prompt=anim_prompts[i],
                output_path=clip_path,
                model=primary_model,
                duration_seconds=_veo_duration(narr_path, i),
                aspect_ratio="9:16",
                resolution=resolution or "720p",
                image_path=img_path,
                last_frame_path=img_path if is_planet_jump_format else None,
            )
        else:
            from packages.clients.grok import generate_video_async as grok_generate

            dur = get_clip_duration(narr_path)
            with open(img_path, "rb") as f:
                img_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            await grok_generate(
                prompt=anim_prompts[i],
                output_path=clip_path,
                duration=dur,
                aspect_ratio="9:16",
                image_url=img_b64,
                timeout=600,
            )
        logger.info("scene animated", scene=i, provider=provider, model=model, resolution=resolution)

    await _update_step(f"animating scenes with {video_provider}")

    if video_provider == "veo":
        for i in range(n_lines):
            await animate_scene(i, video_provider, video_model, video_resolution)
    else:
        await run_tasks(
            [lambda i=i: animate_scene(i, video_provider, video_model, video_resolution) for i in range(n_lines)],
            parallel=True,
            max_concurrent=5,
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
