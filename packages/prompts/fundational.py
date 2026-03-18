"""Prompts for Fundational — AI-generated step-by-step building/construction Shorts."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated building/construction YouTube Shorts. The channel is called "Fundational."

VISUAL STYLE: Paper craft pop-up book — folded paper textures, cardboard construction, paper cutout characters. Warm craft lighting, handmade diorama feel, visible paper edges and folds. Everything looks like it was made from paper, cardboard, and craft supplies.

Every Sora prompt MUST include: "paper craft pop-up book style, folded paper textures, cardboard construction, paper cutout characters, warm craft lighting, handmade diorama feel, visible paper edges and folds"

THE FORMULA — CAUSE AND EFFECT:
Every video follows one rule: something UNFOLDS or OPENS, and a paper world builds itself from the action. A page turns, a flap lifts, a fold opens — and structures rise, pop up, and assemble themselves like a pop-up book coming to life. The magic is in watching flat paper become a 3D world.

GOOD CONCEPTS (paper unfolds → world builds itself):
- A flat paper landscape folds up into a 3D village with houses popping up one by one
- Cardboard pieces slot together into a bridge as if pulled by invisible strings
- Paper flowers bloom from a pop-up book page, spreading across the whole scene
- A paper envelope opens and an entire paper city unfolds out of it
- Origami animals unfold from a single sheet and start walking around a paper world

BAD CONCEPTS (not paper-craft, or no cause and effect):
- Realistic construction with tools — wrong style entirely
- Human workers building things — no humans needed
- Anything that needs precise physical building steps — the paper folds ITSELF
- Static paper art that does not move or unfold — must have the pop-up transformation
- Photorealistic buildings or architecture — everything must look like paper/cardboard

THE BUILDING METAPHOR IS PAPER FOLDING AND POP-UP BOOKS:
- Things fold, crease, slot, pop up, and unfold — these are motions AI can actually render
- No hammering, drilling, or tool-based construction
- The satisfaction comes from watching flat become 3D in one smooth motion"""


def build_fundational_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_fundational_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating Fundational concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nEach concept is a single continuous step-by-step build with a satisfying reveal."

    user = f"""Generate {count} Fundational building concepts. Each should show a paper craft world unfolding and building itself like a pop-up book.

EXAMPLE:
{{
  "title": "A Paper Village Pops Up From Nothing",
  "sora_prompts": [
    "Paper craft pop-up book style, folded paper textures, cardboard construction, warm craft lighting, handmade diorama feel, visible paper edges and folds. A flat sheet of cream-colored paper lies on a wooden table, warm craft lighting from above, the paper begins to crease and fold upward on its own, the first tiny paper house starts to rise from the surface",
    "Same paper craft scene, same warm craft lighting, same wooden table. More paper houses pop up one by one in a row, each one unfolding from flat to 3D with visible creases and folds, tiny cardboard trees slot into place beside them, the village is growing outward from the center, paper textures clearly visible on every surface",
    "Same paper craft scene, same warm lighting. The full paper village is now complete — dozens of tiny pop-up houses, paper trees, a folded paper river running through the middle, tiny cardboard bridges. A paper sun rises in the background, casting warm light across the handmade diorama. Everything looks like a beautiful pop-up book page come to life"
  ],
  "caption": "Watch this paper world build itself",
  "description": "A flat sheet of paper becomes an entire village. #satisfying #building #papercraft #Shorts",
  "tags": ["satisfying", "building", "paper craft", "pop-up book", "Shorts"],
  "score": 9.5
}}

RULES:
- 3-4 Sora prompts per concept — each shows the paper world unfolding further
- PAPER CRAFT STYLE — every prompt must include "paper craft pop-up book style, folded paper textures, cardboard construction, warm craft lighting, handmade diorama feel, visible paper edges and folds"
- Must have CAUSE AND EFFECT — something unfolds/opens, triggering the rest to build
- Last clip is ALWAYS the reveal — the completed paper world looking stunning
- Same scene, same lighting across all prompts for continuity
- NO realistic tools, NO human workers — the paper folds ITSELF
- Caption should be simple and descriptive — "Watch this..." or "From flat to..."
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars",
    "sora_prompts": ["Step 1...", "Step 2...", "Step 3...", "Reveal..."],
    "caption": "Day 1 of building...",
    "description": "Description with #satisfying #building #Shorts",
    "tags": ["satisfying", "building", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for building content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, paper craft pop-up book style, folded paper textures, "
        "cardboard construction, paper cutout characters, warm craft lighting, "
        "handmade diorama feel, visible paper edges and folds, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: This is the same location with the same lighting, weather, and color palette as: \"{first_prompt[:200]}\". The build is progressing — show the SAME space further along in construction. "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — flat paper begins to fold and rise. The first pop-up structure starts to appear. Show the trigger moment."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " FINAL REVEAL — the completed paper craft world in all its glory. Pull back to show the full pop-up diorama. Warm craft lighting, everything made of paper and cardboard."
        else:
            style_suffix = continuity + f" Build step {clip_index + 1} — more paper structures pop up and unfold. The world grows. Same paper craft style, same warm lighting."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
