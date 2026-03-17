"""Prompts for Lad Stories — claymation-style character adventures via Sora 2.

Uses a consistent character bible + style lock for visual consistency across all videos.
No dialogue — stories told through animation, sound effects, and physical comedy.
"""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper

# Character bible — injected into every single Sora prompt
CHARACTER_BIBLE = (
    "A small round clay character called Lad, about 6 inches tall, "
    "with a dusty terracotta-orange body, stubby arms and legs, "
    "big round white eyes with small black dot pupils, no visible mouth, "
    "wearing a tiny dark green backpack. "
    "Lad is expressive through body language — tilting, bouncing, arm gestures."
)

# Style bible — injected into every prompt for visual consistency
STYLE_BIBLE = (
    "Claymation stop-motion style, visible hand-crafted textures, "
    "fingerprint marks in clay, miniature handmade set/diorama, "
    "slightly jerky frame-by-frame stop-motion movement, "
    "warm soft diffused lighting like a stop-motion studio, "
    "color palette: dusty terracotta, sage green, warm cream, muted coral, soft sky blue. "
    "Everything looks tactile and handmade. Charming and whimsical."
)

# System prompt shared between ideas and full concepts
_SYSTEM = f"""You generate short claymation adventure stories for a YouTube Shorts channel called "Lad Stories."

THE CHARACTER:
{CHARACTER_BIBLE}

THE STYLE:
{STYLE_BIBLE}

STORY RULES:
- NO dialogue — stories are told entirely through animation, body language, and sound effects
- Each story is a 3-clip mini adventure with a clear setup → complication → punchline/payoff
- Lad can be in ANY setting: forests, space, underwater, cities, mountains, kitchens, deserts
- Other clay characters can appear (animals, creatures, objects) — all in the same claymation style
- Stories should be FUNNY, CHARMING, or SURPRISING — physical comedy works great
- The humor comes from Lad's reactions and the absurdity of the situation
- Think Shaun the Sheep, Wallace & Gromit, or Pingu vibes — no words needed

STORY TYPES TO MIX:
- ADVENTURE: Lad explores a new place and discovers something unexpected
- COMEDY: Lad tries to do something simple and it goes hilariously wrong
- DISCOVERY: Lad finds a mysterious object/creature and interacts with it
- CHALLENGE: Lad faces an obstacle and finds a creative solution
- FRIENDSHIP: Lad meets a new clay creature and they have an interaction

EVERY PROMPT MUST INCLUDE the character bible and style bible to maintain consistency."""


def build_lad_stories_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_lad_stories_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating Lad Stories concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE STORIES (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM

    user = f"""Generate {count} Lad Stories concepts. Each is a 3-clip claymation adventure.

CRITICAL: Every Sora prompt MUST start with the exact same character + style description to maintain consistency:
"{CHARACTER_BIBLE} {STYLE_BIBLE}"

Then add the specific scene action after that style block.

EXAMPLE:
{{
  "title": "Lad Finds a Magic Mushroom",
  "sora_prompts": [
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Lad is walking through a tiny clay forest diorama with handmade felt trees and paper leaves. He spots a glowing mushroom on the ground and tilts his head curiously, leaning toward it. The mushroom pulses with a soft warm light. Camera at eye level, gentle stop-motion animation.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay forest diorama. Lad pokes the glowing mushroom with one stubby arm. The mushroom suddenly grows to three times Lad's size, launching him backwards. He tumbles across the mossy ground, arms flailing. The giant mushroom wobbles and glows brighter. Comical bouncy sound effects.",
    "{CHARACTER_BIBLE} {STYLE_BIBLE} Same clay forest. Lad cautiously peeks out from behind a tiny felt bush at the giant glowing mushroom. He slowly approaches and climbs on top of it. The mushroom lifts off the ground like a hot air balloon, carrying Lad upward through the paper leaf canopy into a starry clay sky. Lad looks down in wonder, arms raised in excitement. Whimsical magical sounds."
  ],
  "caption": "He should NOT have poked it",
  "description": "Lad finds a mushroom in the forest and immediately regrets touching it. #claymation #animation #funny #Shorts",
  "tags": ["claymation", "stop motion", "funny animation", "clay character", "Shorts"],
  "score": 9.3
}}

RULES:
- 3 prompts per story — setup / complication / payoff
- EVERY prompt starts with the full character + style bible (copy-paste it exactly)
- Settings should be miniature clay dioramas — everything looks handmade
- No human dialogue — express everything through Lad's body language
- Funny, charming, surprising — not dark or scary
- Vary the settings and story types
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars",
    "sora_prompts": ["Full bible + scene 1...", "Full bible + scene 2...", "Full bible + scene 3..."],
    "caption": "Short funny caption",
    "description": "Description with #claymation #animation #Shorts",
    "tags": ["claymation", "stop motion", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]"""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific guidance. The character + style bible should already be in the prompt."""
    raw_prompt = concept["sora_prompts"][clip_index]

    # Ensure the style bible is present (in case the LLM skipped it)
    if "claymation" not in raw_prompt.lower():
        raw_prompt = f"{CHARACTER_BIBLE} {STYLE_BIBLE} {raw_prompt}"

    style_prefix = (
        "Vertical 9:16 aspect ratio, no text, no watermarks, no UI elements. "
        "Generate charming stop-motion sound effects — bouncy, squelchy, whimsical foley sounds. "
    )

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — Lad is already in the scene doing something. No title cards, no empty establishing shots."
        elif clip_index == total_clips - 1:
            style_suffix = " Final shot — the funny payoff or surprising conclusion. Same diorama set and lighting."
        else:
            style_suffix = " Middle shot — the complication. Something unexpected happens. Same set, same lighting, same Lad."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
