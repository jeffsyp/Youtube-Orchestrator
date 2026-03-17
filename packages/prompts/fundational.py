"""Prompts for Fundational — AI-generated step-by-step building/construction Shorts."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated building/construction YouTube Shorts. The channel is called "Fundational."

VISUAL STYLE: Stylized 3D animation — like a high-end animated movie or a beautiful video game. NOT photorealistic. Think vibrant colors, smooth clean geometry, slightly exaggerated proportions, magical/whimsical atmosphere. The building process looks like magic — things assemble themselves, materials flow into place, structures grow from the ground.

Every Sora prompt MUST include: "stylized 3D animation style, vibrant saturated colors, smooth clean geometry, magical whimsical atmosphere, Pixar-quality lighting, not photorealistic"

THE VIBE:
- Things BUILD THEMSELVES — no human hands needed. Materials flow, stack, assemble magically
- Time-lapse feeling — a structure grows from nothing to complete in one continuous shot
- Nature and architecture merging — treehouses that grow from trees, bridges that form from stone
- Miniature world aesthetic — everything looks like a beautiful diorama or model
- The satisfaction is watching something appear from nothing in a smooth magical transformation

WHAT TO BUILD:
- Miniature worlds: tiny villages, fairy gardens, magical dioramas coming to life
- Nature builds: treehouses growing from trees, bridges forming from vines, caves crystallizing
- Magical construction: castles assembling from floating blocks, towers spiraling upward
- Water features: waterfalls carving themselves, rivers flowing into existence, ponds filling
- Garden magic: flowers blooming into patterns, moss spreading into designs, paths forming

AVOID:
- Realistic human workers or hands
- Real construction tools or machinery
- Photorealistic buildings or architecture
- Anything that requires precise physical construction steps"""


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

    user = f"""Generate {count} Fundational building concepts. Each should be a single continuous step-by-step build with a satisfying reveal.

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
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
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
