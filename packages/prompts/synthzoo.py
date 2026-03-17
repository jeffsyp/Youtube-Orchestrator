"""Prompts for Synth Meow — AI-generated animal Shorts via Sora 2."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated animal videos on YouTube Shorts. The channel is "Synth Meow."

THE STYLE: Photorealistic, warm, cinematic. The videos should look SO REAL that viewers pause and think "wait... is this actually real?" The animals are doing things that are slightly impossible or unlikely but filmed in a completely realistic way — real lighting, real environments, real physics (mostly).

THE VIBE: Cute, fun, funny, heartwarming. NOT extreme/chaotic. NOT "animal outrunning disaster." Think viral animal clips that make you smile and send to friends.

GOOD CONCEPTS (cute, almost-believable, makes you smile):
- A golden retriever carefully carrying a tiny kitten across a puddle
- A cat sitting at a tiny desk doing "homework" with a pencil, looking frustrated
- A raccoon opening a fridge and making itself a sandwich at 3am
- A duck leading a line of ducklings through a busy coffee shop
- A dog sneaking into a movie theater and sitting in a seat with popcorn

BAD CONCEPTS (too extreme, too chaotic, not the vibe):
- Animals outrunning lava/tornadoes/avalanches — too dramatic
- Animals in space/volcanoes/extreme environments — not cute
- Pure spectacle with no personality — boring

WHAT MAKES THESE WORK:
- The animal has PERSONALITY — curiosity, determination, mischief, pride
- The setting is EVERYDAY — homes, streets, parks, shops, schools
- The scenario is SLIGHTLY impossible but filmed like it's totally normal
- The viewer's reaction is "aww" or "lol" or "no way" — not "WHAT" """


def build_synthzoo_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_synthzoo_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating Synth Meow concept ideas."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nEach concept is a single continuous 12-second video told across Sora clips."

    user = f"""Generate {count} concepts. Each must be photorealistic, cute, and almost-believable.

EXAMPLE:
{{
  "title": "Cat Orders Coffee at a Drive-Through",
  "sora_prompts": [
    "Photorealistic close-up of an orange tabby cat sitting in the driver's seat of a parked car at a fast food drive-through window, paws on the steering wheel, looking up at the menu board with a thoughtful squinting expression, warm afternoon sunlight through the car window, shallow depth of field, filmed like a real phone video, completely realistic lighting and textures",
    "Same orange tabby cat at the same drive-through, now at the window. A human hand extends a small coffee cup. The cat reaches out one paw tentatively to take it, ears perked forward with intense concentration. Same warm afternoon light, same car interior, photorealistic, filmed like a candid moment caught on dashcam",
    "Same orange tabby cat now sitting in the driver's seat holding the tiny coffee cup between both paws, taking a sip with eyes closed in satisfaction. The car is still at the drive-through. Golden afternoon light. The cat looks deeply content. Photorealistic, warm, funny, filmed like it actually happened"
  ],
  "caption": "He orders the same thing every morning",
  "description": "This cat has a coffee addiction and I can't stop him. #cats #funny #Shorts #animals",
  "tags": ["funny cats", "animals", "cute", "coffee", "Shorts"],
  "score": 9.5
}}

RULES:
- 3 prompts per concept — setup / development / payoff
- PHOTOREALISTIC — specify "photorealistic, realistic lighting, filmed like a real video"
- Same animal description + setting + lighting in all 3 prompts for continuity
- The animal must have PERSONALITY — expressions, body language, attitude
- Everyday settings — homes, shops, parks, streets, offices, schools
- Cute and funny, NOT extreme or dramatic
- Caption should sound like a real pet owner talking about their animal
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, casual/funny",
    "sora_prompts": ["Photorealistic clip 1...", "Same setting clip 2...", "Payoff clip 3..."],
    "caption": "Casual funny caption like a pet owner would write",
    "description": "YouTube description with #cats #funny #Shorts etc",
    "tags": ["funny animals", "cute", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, photorealistic, natural lighting, "
        "shallow depth of field, filmed like a real phone/camera video, "
        "no text, no watermarks, no UI elements. "
    )

    # Continuity anchor from clip 1
    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Same animal, same setting, same lighting as: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — the animal is already doing something cute/funny. Capture it like a candid moment. No setup shots."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " Final shot — the cute/funny payoff. Same animal, same place, same light."
        else:
            style_suffix = continuity + " Middle shot — the situation develops. Same animal, same place."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
