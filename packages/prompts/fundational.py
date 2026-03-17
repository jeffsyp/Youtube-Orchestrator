"""Prompts for Fundational — AI-generated step-by-step building/construction Shorts."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated building/construction YouTube Shorts. The channel is called "Fundational."

THE VIBE:
- Satisfying step-by-step building processes — the joy of watching something come together
- Slightly surreal/cartoony aesthetic — vibrant colors, impossibly clean work, dream-like quality
- The viewer should wonder "wait... is this real?" — uncanny valley between real and AI
- Entertainment and visual satisfaction, NOT informational/tutorial content
- Workers/hands may appear but the focus is on the PROCESS and the RESULT

WHAT TO BUILD:
- Backyard projects: rivers, ponds, waterfalls, treehouses, underground rooms, swimming pools
- Miniature worlds: tiny villages, model landscapes, fairy gardens, dioramas
- Impossible architecture: glass treehouses, upside-down rooms, floating platforms
- Nature manipulation: redirecting streams, building living walls, moss gardens
- Whimsical structures: hobbit holes, secret passages, bridges to nowhere
- Satisfying landscaping: perfect lawns, zen gardens, terracing hillsides

STYLE GUIDELINES:
- Bright, saturated colors — almost like a Wes Anderson film or a video game
- Clean, smooth motions — no jerky camera work
- Each step should feel satisfying on its own (digging, pouring, shaping, placing)
- Time-lapse/sped-up feeling — things come together efficiently
- Wide establishing shots mixed with close-up detail shots
- The finished result should be a "wow" reveal

AI VIDEO MODEL STRENGTHS (design around these):
- Great at: landscapes, water, nature, architectural scenes, lighting/atmosphere
- Great at: smooth transformations, before/after, environmental changes
- OK at: hands/tools from a distance (don't need close-ups of fingers)
- Avoid: precise tool close-ups, detailed hand manipulation, text/measurements"""


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

    system = _SYSTEM + "\n\nEach concept is a 3-4 clip step-by-step build with a satisfying reveal."

    user = f"""Generate {count} Fundational building concepts. Each should be a 3-4 clip step-by-step build with a satisfying reveal.

EXAMPLE:
{{
  "title": "Building a River Through the Backyard",
  "sora_prompts": [
    "Wide shot of a lush green backyard on a bright sunny day, a person in work clothes digging a long winding trench through the grass with a shovel, fresh dark earth piled neatly along the sides, the trench curves naturally through the yard, slightly dreamlike saturated colors, warm golden hour light, cinematic wide angle, the work looks impossibly clean and satisfying",
    "Same bright sunny backyard, the winding trench now lined with smooth river stones and slate, a worker carefully placing the last stones along the edge, the channel curves beautifully through the vivid green grass, small plants placed along the banks, warm golden light, wide angle showing the full winding path, satisfying and methodical, slightly surreal color saturation",
    "Same backyard in golden hour light, crystal clear water now flowing through the completed stone-lined river channel, the water catches sunlight with sparkling reflections, small water plants and moss along the edges, tiny fish visible in the clear water, the grass perfectly green on both sides, camera slowly pulling back to reveal the full winding river through the dream-like backyard, ambient water flowing sounds",
    "Aerial drone shot looking straight down at the completed backyard river winding through the impossibly perfect green lawn, the water sparkling in golden sunset light, small bridges crossing at two points, flower beds along the banks, the whole scene looks like a miniature model or a painting come to life, warm saturated colors, satisfying final reveal"
  ],
  "caption": "Day 1 of building a river in my backyard",
  "description": "Built a flowing river through the backyard from scratch. Every step was satisfying. #satisfying #building #backyard #diy #Shorts",
  "tags": ["satisfying", "building", "backyard river", "construction", "DIY", "Shorts"],
  "score": 9.5
}}

RULES:
- 3-4 Sora prompts per concept — each is a BUILD STEP leading to the final reveal
- Last clip is ALWAYS the reveal — the finished project looking incredible
- Same location, same lighting, same color palette across all prompts for continuity
- Bright, saturated, slightly dreamlike colors — NOT gritty/realistic construction
- Workers can appear but keep them at medium/wide distance (no hand close-ups)
- Each step should feel satisfying on its own — neat digging, clean placement, smooth pouring
- Caption should use "Day 1 of..." or "Building a..." format — makes it feel like a series
- Projects should be impressive but not absurd — the viewer should half-believe it's real
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
]"""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for building content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, photorealistic with slightly dreamlike saturated colors, "
        "cinematic lighting, smooth camera movement, "
        "no text, no watermarks, no UI elements. "
        "Generate ambient construction/nature sounds synchronized with the action. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: This is the same location with the same lighting, weather, and color palette as: \"{first_prompt[:200]}\". The build is progressing — show the SAME space further along in construction. "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — show the build already in progress. The first satisfying action should be visible immediately. No standing around, no before-shot of empty space."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " FINAL REVEAL — the completed project looking absolutely stunning. Pull back to show the full result. This should be the 'wow' moment. Golden hour lighting, everything perfect."
        else:
            style_suffix = continuity + f" Build step {clip_index + 1} — show the next satisfying phase of construction. Things are coming together. Same location progressing."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
