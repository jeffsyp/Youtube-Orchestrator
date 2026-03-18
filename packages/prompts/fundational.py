"""Prompts for Fundational — AI-generated step-by-step building/construction Shorts."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated satisfying building/construction YouTube Shorts. The channel is called "Fundational."

VISUAL STYLE: Colorful isometric cartoon — like a mobile game or animated infographic. Bright flat colors, clean geometric blocks, isometric camera angle looking down at the build. Think Minecraft meets Monument Valley meets LEGO instruction animations.

Every Sora prompt MUST include: "colorful isometric cartoon style, bright flat colors, clean geometric blocks, isometric camera angle, animated construction, game-like aesthetic, smooth block-by-block assembly"

WHAT THE VIDEOS SHOW:
Cartoon buildings/structures assembling themselves PIECE BY PIECE in a satisfying way. Blocks slide into place, walls stack up, roofs click on top. Like watching a LEGO set build itself in fast-forward. Each piece appears and slots perfectly into position.

THE SATISFACTION IS IN THE ASSEMBLY:
- Blocks/bricks stacking one by one, each clicking into place
- Walls rising layer by layer with satisfying precision
- A roof piece floating down and landing perfectly on top
- Windows and doors popping into their slots
- The camera slowly reveals more of the structure as it builds

GOOD CONCEPTS (piece-by-piece cartoon assembly):
- A tiny cartoon house builds itself brick by brick, roof clicks on at the end
- An isometric castle assembles from floating blocks that slide into place
- A cartoon bridge extends across a gap, each segment locking in with a click
- A treehouse grows around a tree as planks and platforms slot together
- A whole cartoon city block assembles from the ground up, building by building

BAD CONCEPTS:
- Nature growing (vines, trees, flowers) — that's nature, not building
- Abstract transformations with no visible pieces — must see individual parts assembling
- Realistic construction — must be cartoon/game style
- Anything without visible block-by-block assembly — the satisfaction IS the pieces fitting together

NEVER include emojis in titles, captions, or descriptions."""


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
        "Vertical 9:16 aspect ratio, colorful isometric cartoon style, bright flat colors, "
        "clean geometric blocks, isometric camera angle, animated construction, "
        "game-like aesthetic, smooth block-by-block assembly, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: This is the same location with the same lighting, weather, and color palette as: \"{first_prompt[:200]}\". The build is progressing — show the SAME space further along in construction. "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — first blocks/pieces start appearing and slotting into place. The build begins immediately."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " FINAL REVEAL — the completed cartoon structure in all its glory. Pull back to show the full build. Last piece clicks into place."
        else:
            style_suffix = continuity + f" Build step {clip_index + 1} — more blocks and pieces slide into place. The structure grows piece by piece. Same isometric angle, same colors."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
