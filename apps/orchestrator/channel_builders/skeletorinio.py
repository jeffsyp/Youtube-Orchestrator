"""Skeletorinio channel builder — "What if you brought [item] to [era]" videos.

Concept-specific Skeletorinio variants in historical/fantasy scenarios.
Uses unified pipeline: style anchor → sub-actions → GPT images → video animation → chaining.
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
CHANNEL_ID = 18
VOICE_ID = "TxGEqnHWrfWFTfGW9XjX"  # Josh
MUSIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "music", "skeletorinio_theme.mp3")
SKELETON_REF = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "character_cache", "skeletorinio_base.png")
TAGS = ["skeletorinio", "what if", "skeletorinio", "history", "shorts", "viral", "comedy"]

BASE_CHARACTER_IDENTITY = (
    "The core Skeletorinio identity NEVER changes: same ivory plastic skeleton body, "
    "same oversized googly eyes, same grinning skull face, same overall body proportions, "
    "same human-height scale, and the same glossy toy-plastic material. "
    "Remove the old recurring accessories entirely: NO gold chain and NO sunglasses unless a concept explicitly requires them."
)

ART_STYLE = (
    "Photorealistic world with cinematic golden hour lighting. "
    "The main character is a FULL-SIZE adult human-height 3D animated Skeletorinio with an ivory plastic skeleton body "
    "with oversized googly eyes and a grinning skull face. "
    "He is the same height as the humans around him — NOT a miniature toy. "
    "He looks like a stylized glossy plastic toy character placed into a real photograph."
)

IMAGE_RULES = """RULES — FOLLOW THESE EXACTLY:
- The main character is a FULL-SIZE adult human-height 3D animated Skeletorinio with an ivory plastic skeleton body, oversized googly eyes, and a grinning skull face. He is the SAME HEIGHT as real humans — NOT a miniature toy.
- The core identity NEVER changes: same skull face, same googly eyes, same body proportions, same glossy ivory plastic skeleton material. No sunglasses and no gold chain unless the specific concept requires them.
- The skeletorinio is "YOU" — the protagonist/observer/reactor in every scene. He is the HUMAN PERSON doing the action.
- A reference image of the skeletorinio is provided — match this character exactly but at HUMAN SCALE
- For EVERY scene with the skeletorinio, start from the exact reference character and preserve the concept-specific variant consistently across every scene
- The WORLD is PHOTOREALISTIC — real-looking buildings, landscapes, people, objects. Cinematic golden hour lighting.
- The skeletorinio is the ONLY stylized-character element. Everything else looks like a photograph.
- Do NOT say "toy" or "miniature" or "figurine" — the skeletorinio is HUMAN-SIZED
- Every prompt must end with "Photorealistic world. NO text anywhere."
- Each prompt should describe ONE clear scene matching the narration line

TWO-CHARACTER CONCEPTS (demon, dragon, genie, alien, monster, ghost, god, creature):
- When the concept introduces a SECOND major entity (demon, dragon, god, etc.), that entity is a SEPARATE CHARACTER from the skeletorinio.
- The skeletorinio is "YOU" the human. The demon/dragon/god is the SPECTACLE/THREAT/COMPANION.
- In scenes where the narration mentions the second entity, that entity MUST be the VISUAL FOCUS of the scene — large, dramatic, centered.
- DESCRIBE THE SECOND ENTITY IN FULL VISUAL DETAIL — size, color, features, pose, expression. Do NOT just say "the demon" — say "a massive 10-foot horned demon with red skin, glowing yellow eyes, black leathery wings, and curved fangs, looming in the living room."
- The second entity is ALSO stylized/non-photoreal — treat it as equally cinematic as the skeletorinio (3D animated creature in a photoreal world).
- Example concept: "you summoned a demon"
  - Line mentioning the demon arrival: "The skeletorinio stands in his living room looking terrified. Behind him, a MASSIVE 10-foot horned demon with crimson skin, glowing yellow eyes, and black wings has burst through the floor, smoke curling around his hooves. The demon fills the frame."
  - Line where the demon is just "hanging around": "The skeletorinio watches TV on the couch. The massive demon sits awkwardly on the adjacent armchair, squeezing into it, holding a tiny remote in his giant claws."
- NEVER swap the second entity for a random human bystander. If the script says "demon," draw a demon.

HOOK / LINE 0 — PAYOFF VISUAL:
- The hook frame must depict the CONCEPT in motion — not a setup scene, not a random establishing shot.
- For "summoned a demon": show the skeletorinio in his living room with the massive demon already there (the "can't send back" situation already happening).
- For "brought a jetpack to Rome": show the skeletorinio flying over the Colosseum in a jetpack.
- NEVER let the hook be a random unrelated scene (e.g. cupcake shop, coffee house) — it must illustrate the video's actual premise.

POWER / DOMAIN CONCEPTS:
- If the premise gives the skeletorinio a mythic job, divine title, or control over a domain (lightning, storms, sea, sun, fire, time, weather, etc.), the visuals must show that power visibly affecting the world.
- Do NOT reduce these concepts to meetings, paperwork, or reaction poses. Bureaucracy can support the joke, but the dominant image must still be the power misfiring, being used badly, or changing the environment.
- When narration mentions approvals for storms, tides, sunlight, weather, or other divine systems, depict the actual sky, sea, light, clouds, waves, or environment reacting on screen.
- For Zeus / storm-king concepts specifically, show lightning, storm bands, broken weather patterns, sunlight patches, or sky control in at least half the scenes. Do not let the whole video become "people handing him scrolls."
- For accidental god-power concepts, the fun should come from visible POWER PROGRESSION: a small accidental glitch first, then a controlled trick, then a useful/funny public use, then a huge world-scale flex. Do not spend multiple scenes on throne-room complaints.
"""

SCRIPT_PROMPT = """Write a narration script for a Skeletorinio YouTube video.

CONCEPT: {title}
BRIEF: {brief}

THE FORMAT:
- Line 1 is the HOOK — it MUST state the concept directly so a viewer with ZERO title context knows what the video is about. Shorts viewers don't see the title.
  - THE HOOK SHOULD BASICALLY MIRROR THE TITLE AS A "What if..." QUESTION.
  - TITLE: "WHAT IF YOU ACCIDENTALLY SUMMONED A DEMON YOU COULDN'T SEND BACK" → HOOK: "What if you accidentally summoned a demon you couldn't send back?"
  - TITLE: "WHAT IF YOU ACCIDENTALLY BECAME THE CHOSEN ONE" → HOOK: "What if you accidentally pulled a sword from a stone?" (close paraphrase — the sword-from-stone IS the becoming-chosen-one moment)
  - TITLE: "WHAT IF YOU BROUGHT A JETPACK TO ANCIENT ROME" → HOOK: "What if you brought a jetpack to Ancient Rome?"
- BAD HOOK (skips the concept): TITLE is "SUMMONED A DEMON" but line 1 says "What if you read one line from an old book out loud?" — a viewer has no idea what this is about, no context for the demon that appears in line 2
- The hook must LABEL the concept — use the specific noun from the title (demon, sword, jetpack, dragon, time portal, genie, etc.) in line 1, not a vague setup
- If the title says "ACCIDENTALLY X" — the hook must include "accidentally" and name what X is
- The story is about the SITUATION — the skeletorinio is the person doing it. The situation is the star.
- If the concept gives you a mythic job, divine title, or control over a domain (Zeus, Poseidon, sun god, storms, tides, weather, fire, time, etc.), at least 3 post-hook lines must show you visibly USING or MISUSING that exact power in the world.
- Bureaucracy can appear, but it cannot dominate those concepts. One complaint/help-desk line is enough. The rest should show the sky, sea, light, weather, or world physically reacting to your bad decisions.
- Bad Zeus version: gods hand you scrolls for three lines in a row.
- Good Zeus version: you grab the lightning, the sky obeys, storms hit the wrong places, tides move wrong, sunlight patches keep shifting, THEN Olympus opens a ridiculous help desk.
- GREAT accidental-Zeus version: the powers visibly LEVEL UP over time. Start with little shocks on touch, then command lightning, then use it for something funny/useful in public, then ride clouds/control weather, then end on a giant god-of-lightning flex with a concrete story consequence.
- For accidental god-power concepts, at least one line must show SMALL accidental power, one line must show USEFUL or EMBARRASSING everyday use, and one line must show huge WORLD-SCALE control.
- CHOOSE THE RIGHT STRUCTURE for the concept:
  A) DAY-BY-DAY ESCALATION — use when the concept spans time (arriving somewhere new, starting a job, entering a new world):
     - Lines include "Day 1:", "Day 2:", "Week 2:", "Month 3:" as part of the narration
     - Time jumps ACCELERATE — Day 1, Day 2, Day 3, then suddenly "Week 2" or "Year 5" to show things spiraling
     - Each time jump shows a BIGGER consequence
     - GOOD fit: "What if you brought a lighter to the Ice Age" → Day 1: discovery, Day 3: worshipped, Month 2: civilization built
     - GOOD fit: "What if you accidentally became the chosen one" → Day 1: sword pull, Week 2: crowned king, Month 3: abolished feudalism
  B) REAL-TIME ESCALATION — use when the concept is a single moment that spirals (one interaction, one event, one attempt):
     - No day markers, just rapid beat-by-beat escalation within one scene/event
     - GOOD fit: "What if Poseidon became a plumber" → shows up, touches pipe, bathroom floods, building floods, city floods
     - GOOD fit: "What if you tried to return something on Black Friday" → walk in, line is insane, chaos erupts
  Pick whichever structure fits the concept naturally. Day-by-day is the default for concepts that span time. Real-time is for single-moment chaos.
- The ending must GO ABSOLUTELY INSANE:
  - NOT "people get mad" or "the authorities arrive" — that's boring
  - YES: you become president, you buy an island, you accidentally start a religion, you get launched into space, you break reality, the simulation crashes, the gods revolt
  - The ending should make viewers replay the video. Realistic endings are BORING — go full absurd comedy.
- THE PENULTIMATE LINE (second to last) MUST BE A MAXIMUM ESCALATION — the biggest, most absurd, world-scale consequence. The ending line then resolves that peak.
  - Good peak examples: "Year 1: Prophecies about you are carved into mountains.", "Year 3: It has a seat at Thanksgiving, a LinkedIn profile, and joint custody of the dog."
  - Bad peak examples: "You get a crown", "You get it a chair" (too small — nothing lands after)
  - The peak should feel OVERWHELMING so the final line has something to land against.

- THE LAST LINE — write a REAL STORY ENDING that resolves the arc into a new stable state. The viewer should feel "the story is complete" — not "there's more to figure out."

  GOOD REAL-STORY ENDINGS (the situation RESOLVES, a new normal sticks):
  - Chosen One: "Year 50: You died of old age. The kingdom named a star after you. The sword quietly returned to its stone." (lifetime arc closes, cycle resets)
  - Demon: "Year 10: You and the demon run a bakery together now. He does the dishes. You split the rent." (the terror became a roommate — new equilibrium)
  - Jetpack in Rome: "Year 3: Rome colonized the Moon. History books say you did it on purpose. You did not." (world permanently changed)
  - Genie lamp: "Year 5: The genie opened a law firm. You're his first client. Business is thriving." (both parties found their place)

  BAD ENDINGS:
  - Cliffhangers: "You still don't know what the sword does." (leaves mystery unresolved — feels incomplete)
  - Shrugs without resolution: "It has attended every family dinner." (doesn't show where the story ENDS)
  - Reveals that open more questions: "The sword finally speaks. It says your name." (another mystery, not a resolution)
  - Power-status claims: "You are a god now." (too abstract, no concrete endpoint)

  Structure: TIME JUMP (Year 5, Year 10, Year 50, "decades later") + NEW NORMAL (what life looks like now) + a CONCRETE DETAIL that shows the absurdity has become routine. This is the Pixar-short ending pattern — tension resolves into a new stable equilibrium, not a reveal.

- The LAST LINE must be memorable — the line people quote when sharing the video. Weak endings are BAD.
- Second person narration ("You walk in...", "You show...", "You realize...")
- 6-8 narration lines total, ~20-30 seconds. SHORTER IS BETTER — every line must earn its place
- Each line = one scene = one image
- Each line UNDER 15 words
- Punchy, fast-paced, funny
- Do NOT mention skeletorinio, bones, or the character's appearance — just tell the story

REFERENCE EXAMPLE (the Chosen One — this was a hit, study its shape):
Title: WHAT IF YOU ACCIDENTALLY BECAME THE CHOSEN ONE
Narration:
  0: What if you accidentally pulled a sword from a stone?
  1: Day 1: You were just curious. The sword slides out with a hum.
  2: Day 2: A dragon lands in front of you and bows. You did not ask for this.
  3: Day 3: Wizards appear from thin air. They are all weeping.
  4: Week 1: You are crowned king of a realm you cannot pronounce.
  5: Month 2: The dragon is your ride now. You sleep in a floating castle.
  6: Year 1: Prophecies about you are carved into mountains.
  7: You still don't know what the sword does.

Why this worked:
- Universal mythology (Excalibur) — zero-context entry
- "You" is a REACTOR — things happen TO you (dragon bows, wizards weep, prophecies carve themselves)
- Time jumps ACCELERATE: Day 1, Day 2, Day 3, Week 1, Month 2, Year 1
- CONCRETE visuals only (sword, dragon, crown, castle, mountains) — never abstract
- Anticlimactic punchline: "You still don't know what the sword does" — leaves mystery
- 8 lines, each under 15 words

Aim for this shape. Match it in structure and energy.

Return ONLY a JSON object:
{{"narration": ["line 1", "line 2", ...], "title": "SHORT PUNCHY TITLE"}}"""


def _heuristic_character_variant(title: str, brief: str, era: str) -> dict:
    text = f"{title} {brief} {era}".lower()
    traits: list[str] = []
    variant_name = "default"

    if any(term in text for term in ["zeus", "olympus", "lightning", "thunder"]):
        variant_name = "storm king"
        traits = [
            "storm-white curly hair crackling with faint blue lightning",
            "a laurel crown with subtle lightning motifs",
            "white-and-gold Greek god drapery and divine shoulder armor",
        ]
    elif any(term in text for term in ["poseidon", "ocean", "sea", "trident"]):
        variant_name = "sea king"
        traits = [
            "sea-blue crest-like hair swept backward",
            "coral-and-bronze sea god accessories",
            "wet oceanic drapery with shell details",
        ]
    elif any(term in text for term in ["hades", "underworld", "dead", "afterlife"]):
        variant_name = "underworld ruler"
        traits = [
            "dark smoke-like crown or shadow halo",
            "black-and-deep-purple underworld robes",
            "subtle ember glow in the eye sockets",
        ]
    elif any(term in text for term in ["rome", "roman", "caesar", "colosseum"]):
        variant_name = "roman troublemaker"
        traits = [
            "messy short curls under a Roman-style laurel wreath",
            "worn Roman tunic layered over the skeleton body",
            "leather sandals and simple bronze accents",
        ]
    elif any(term in text for term in ["jetpack", "space", "rocket", "moon", "mars"]):
        variant_name = "sci-fi rider"
        traits = [
            "windswept white crest-hair or helmet fins",
            "sleek sci-fi harness and propulsion rig",
            "bright metallic accent panels over the skeleton body",
        ]
    else:
        traits = [
            "concept-appropriate hair or crown only if the setting calls for it",
            "era-appropriate outfit pieces fitted over the same skeleton body",
            "no modern jewelry or recurring gag accessories by default",
        ]

    return {
        "variant_name": variant_name,
        "must_keep": BASE_CHARACTER_IDENTITY,
        "traits": traits,
        "negative_traits": [
            "no gold chain",
            "no sunglasses",
            "no human skin replacing the skeleton face",
            "no random redesign of the head or body proportions",
        ],
    }


def _build_character_variant(title: str, brief: str, era: str) -> dict:
    variant = _heuristic_character_variant(title, brief, era)
    try:
        from packages.clients.claude import generate as claude_generate

        resp = claude_generate(
            prompt=f"""Design a concept-specific Skeletorinio variant for this one video.

VIDEO TITLE: {title}
BRIEF: {brief}
ERA: {era or "not specified"}

BASE CHARACTER RULES:
- {BASE_CHARACTER_IDENTITY}
- The variant should adapt with accessories, hair, crowns, clothing layers, or divine markings ONLY
- Never redesign the core face/head/body
- Never use the old recurring accessories: no gold chain, no sunglasses
- Keep it visually simple enough to stay consistent across 5-7 scenes

Return ONLY JSON:
{{
  "variant_name": "short label",
  "must_keep": "one sentence about the unchanged core identity",
  "traits": ["2-4 short visual traits"],
  "negative_traits": ["2-4 forbidden traits"]
}}""",
            max_tokens=300,
        )
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if parsed.get("traits"):
                parsed.setdefault("must_keep", BASE_CHARACTER_IDENTITY)
                parsed.setdefault("negative_traits", variant["negative_traits"])
                return parsed
    except Exception as e:
        logger.warning("character variant generation fallback", error=str(e)[:120])
    return variant


def _variant_rules_text(character_variant: dict) -> str:
    traits = character_variant.get("traits") or []
    negatives = character_variant.get("negative_traits") or []
    traits_text = "; ".join(traits) if traits else "no extra accessories"
    negatives_text = "; ".join(negatives) if negatives else "no off-model redesigns"
    return (
        "\n\nCONCEPT-SPECIFIC SKELETORINIO VARIANT:\n"
        f"- {character_variant.get('must_keep', BASE_CHARACTER_IDENTITY)}\n"
        f"- For THIS video, add these consistent variant traits: {traits_text}.\n"
        f"- Forbidden drift: {negatives_text}.\n"
        "- Every image_prompt must keep this exact variant consistent across the entire video.\n"
    )


def _is_domain_power_concept(title: str, brief: str) -> bool:
    text = f"{title} {brief}".lower()
    keywords = [
        "zeus", "poseidon", "apollo", "artemis", "hades",
        "lightning", "thunder", "storm", "weather", "tide", "tides",
        "sun", "sunlight", "moon", "ocean", "sea", "fire", "time",
        "god", "goddess", "olympus",
    ]
    return any(word in text for word in keywords)


def _count_domain_effect_lines(narration_lines: list[str]) -> int:
    effect_words = [
        "lightning", "storm", "storms", "weather", "sky", "cloud", "clouds",
        "rain", "sun", "sunlight", "tide", "tides", "ocean", "sea",
        "wave", "waves", "wind", "winds", "fire", "moon", "thunder",
        "shock", "shocks", "bolt", "bolts", "cook", "cooks", "cooking",
        "cloudride", "ride", "rides", "split", "splits",
    ]
    count = 0
    for line in narration_lines[1:]:
        text = line.lower()
        if any(word in text for word in effect_words):
            count += 1
    return count


def _is_power_progression_concept(title: str, brief: str) -> bool:
    text = f"{title} {brief}".lower()
    return _is_domain_power_concept(title, brief) and any(
        phrase in text
        for phrase in [
            "accidentally became",
            "became the new",
            "new zeus",
            "new poseidon",
            "new apollo",
            "new hades",
            "new god",
        ]
    )


def _needs_power_progression_rewrite(title: str, brief: str, narration_lines: list[str]) -> bool:
    if not narration_lines or not _is_power_progression_concept(title, brief):
        return False

    admin_words = [
        "help desk", "complaint", "complaints", "approve", "approval",
        "reporting", "meeting", "scroll", "throne", "paperwork",
    ]
    milestone_markers = ("day ", "week ", "month ", "year ")
    progression_words = [
        "shock", "lightning", "bolt", "cook", "cloud", "ride",
        "storm", "weather", "split", "sky", "rain", "sun",
    ]

    progress_lines = 0
    admin_lines = 0
    for line in narration_lines[1:]:
        lower = line.lower()
        if any(lower.startswith(marker) for marker in milestone_markers):
            progress_lines += 1
        if any(word in lower for word in admin_words):
            admin_lines += 1

    return progress_lines < 4 or _count_domain_effect_lines(narration_lines) < 4 or admin_lines > 1 or not any(
        word in " ".join(narration_lines[1:]).lower() for word in progression_words
    )


def _fallback_power_rewrite(title: str, narration_lines: list[str]) -> list[str]:
    hook = narration_lines[0] if narration_lines else f"What if {title.lower()}?"
    if "zeus" in title.lower():
        return [
            hook,
            "Day 1: Tiny shocks jump out whenever you touch metal.",
            "Week 1: You call lightning on command and sear every dinner perfectly.",
            "Month 2: You ride a cloud, then ruin three weddings with perfect weather.",
            "Year 1: Farmers beg for rain while sailors beg you to stop the storms.",
            "Year 2: One finger splits the sky open, and Olympus already calls you Zeus.",
        ]
    return [
        hook,
        "Day 1: You grab one loose lightning bolt and the sky obeys.",
        "Day 2: One bad shrug puts thunderstorms over beaches and sunshine over the sea.",
        "Week 1: Poseidon is furious because you keep pulling the tides backward.",
        "Month 1: Farmers cheer, sailors panic, and every cloud follows your finger.",
        "Olympus opens a weather help desk, and somehow you still run it.",
    ]


def _maybe_strengthen_power_narration(title: str, brief: str, narration_lines: list[str]) -> list[str]:
    if not narration_lines or not _is_domain_power_concept(title, brief):
        return narration_lines

    min_effect_lines = min(3, max(1, len(narration_lines) - 1))
    if _count_domain_effect_lines(narration_lines) >= min_effect_lines and not _needs_power_progression_rewrite(title, brief, narration_lines):
        return narration_lines

    try:
        from packages.clients.claude import generate as claude_generate

        resp = claude_generate(
            prompt=f"""Rewrite this Skeletorinio narration so the spectacle comes from visibly USING or MISUSING the domain power, not just meetings or complaints.

TITLE: {title}
BRIEF: {brief}
CURRENT NARRATION:
{json.dumps(narration_lines, ensure_ascii=False)}

RULES:
- Keep the same core premise and comedic tone.
- Keep 6-8 lines total.
- Every line under 15 words.
- Keep the hook as a clear "What if..." line naming the concept.
- At least 3 post-hook lines must show visible environment effects from the power/domain.
- Bureaucracy/help-desk/complaint beats can appear at most once.
- For Zeus/weather concepts, physically show lightning, storms, tides, sunlight, clouds, or sky behavior.
- If this is an accidental new-god concept, make it feel like POWER PROGRESSION over time:
  1. small accidental glitch,
  2. controlled trick,
  3. useful or embarrassing public use,
  4. huge world-scale mastery/payoff.
- For Zeus specifically, prefer shocks-on-touch, called lightning, cloud-riding, cooking/helping people, weather chaos, and a final god-of-lightning flex over throne-room admin.

Return ONLY JSON:
{{"narration": ["line 1", "line 2", "..."]}}""",
            max_tokens=400,
        )
        match = re.search(r"\{.*\}", resp, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            candidate = parsed.get("narration") or []
            if candidate and _count_domain_effect_lines(candidate) >= min_effect_lines:
                logger.info("strengthened power narration", title=title, before=narration_lines, after=candidate)
                return candidate
    except Exception as e:
        logger.warning("power narration rewrite fallback", title=title, error=str(e)[:120])

    fallback = _fallback_power_rewrite(title, narration_lines)
    logger.info("using fallback power narration", title=title, fallback=fallback)
    return fallback


async def build_skeletorinio(run_id: int, concept: dict, output_dir: str, _update_step, db_url: str):
    """Full Skeletorinio video build using unified pipeline."""
    title = concept.get("title", "Untitled")
    narration_lines = concept.get("narration", [])
    brief = concept.get("brief", title)
    era = concept.get("era", "")

    narr_dir = os.path.join(output_dir, "narration")
    segments_dir = os.path.join(output_dir, "segments")
    for d in [narr_dir, segments_dir]:
        os.makedirs(d, exist_ok=True)

    # ─── STEP 1: Write script if not provided ───
    if not narration_lines:
        await _update_step("writing script")
        from packages.clients.claude import generate as claude_generate
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

    narration_lines = _maybe_strengthen_power_narration(title, brief, narration_lines)
    concept["narration"] = narration_lines

    n_lines = len(narration_lines)

    # ─── STEP 2: Narration ───
    await _update_step("generating narration")
    await generate_narration_with_timestamps(
        narration_lines, narr_dir, output_dir, VOICE_ID, _update_step,
    )

    # ─── STEP 3: Build concept-specific character variant + style anchor ───
    from openai import AsyncOpenAI
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    anchor_path = os.path.join(images_dir, "style_anchor.png")
    character_variant = concept.get("character_variant") if isinstance(concept.get("character_variant"), dict) else None
    if not character_variant:
        await _update_step("designing character variant")
        character_variant = _build_character_variant(title, brief, era)
    concept["character_variant"] = character_variant
    variant_path = os.path.join(output_dir, "character_variant.json")
    with open(variant_path, "w") as vf:
        json.dump(character_variant, vf, indent=2)

    if not os.path.exists(anchor_path) and os.path.exists(SKELETON_REF):
        # Generate a concept-specific Skeletorinio variant IN the first scene — this becomes the style anchor
        # so all subsequent scenes share the same era, lighting, character scale, and accessory profile.
        _oai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
        era_part = f"STRICT ERA: {era}. All humans in period-accurate clothing. NO modern clothing, NO modern objects. " if era else "Historical time period — NOT modern day. "
        variant_traits = "; ".join(character_variant.get("traits") or [])
        variant_negatives = "; ".join(character_variant.get("negative_traits") or [])
        _ref = open(SKELETON_REF, "rb")
        try:
            _resp = await _oai.images.edit(
                model="gpt-image-1.5",
                image=_ref,
                prompt=(
                    f"{era_part}Transform this exact base Skeletorinio reference into the concept-specific variant for this video: {title}. "
                    f"{character_variant.get('must_keep', BASE_CHARACTER_IDENTITY)} "
                    f"Add these consistent variant traits: {variant_traits}. "
                    f"Forbidden drift: {variant_negatives}. "
                    f"Place the resulting variant into the scene for this video: {brief[:200]}. "
                    f"{narration_lines[0] if narration_lines else ''}. "
                    "The character is FULL ADULT HUMAN HEIGHT — same size as real people around him. "
                    "Photorealistic world with cinematic golden hour lighting. NO text anywhere."
                ),
                size="1024x1536",
                quality="medium",
                input_fidelity="high",
            )
            _ref.close()
            if _resp.data and _resp.data[0].b64_json:
                import base64 as _b64
                with open(anchor_path, "wb") as _f:
                    _f.write(_b64.b64decode(_resp.data[0].b64_json))
                logger.info("style anchor generated from skeletorinio ref in scene")
        except Exception as _e:
            try: _ref.close()
            except: pass
            import shutil
            shutil.copy2(SKELETON_REF, anchor_path)
            logger.warning("style anchor fallback to bare skeletorinio ref", error=str(_e)[:80])

    # ─── STEP 4: Unified pipeline — uses style anchor (skeleton IN scene) for all edits ───
    image_rules = IMAGE_RULES + _variant_rules_text(character_variant)
    clips_dir, clip_paths, n_clips, line_clip_map = await generate_and_animate_scenes(
        narration_lines, concept, image_rules, ART_STYLE, output_dir, _update_step, run_id=run_id, character_ref_path=anchor_path,
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
    logger.info("skeletorinio complete", run_id=run_id, title=title, duration=f"{total_dur:.0f}s")
