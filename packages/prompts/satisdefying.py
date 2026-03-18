"""Prompts for Satisdefying — AI-generated ASMR/satisfying Shorts via Sora 2."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated oddly satisfying YouTube Shorts. The channel is "Satisdefying."

VISUAL STYLE: Glossy 3D render — smooth reflective surfaces, perfect geometric shapes, satisfying motion graphics. Vibrant saturated colors, studio lighting on dark background. Everything looks like a high-end product render or motion design piece.

Every Sora prompt MUST include: "glossy 3D render style, smooth reflective surfaces, perfect geometric shapes, satisfying motion graphics, vibrant saturated colors, studio lighting on dark background"

THE FORMULA — CAUSE AND EFFECT:
Every video follows one rule: ONE action triggers a cascade of perfect satisfying movements. Something starts, and then everything else follows in a chain of flawless motion. The satisfaction comes from watching one trigger set off a perfect sequence.

GOOD CONCEPTS (one action → cascade of perfect movements):
- A ball rolls and triggers a perfect domino cascade of glossy spheres
- Paint pours from above and fills a geometric pattern perfectly, section by section
- One touch melts a glossy object that reforms into something new and perfect
- A single marble drops and triggers a chain of perfectly synchronized movements
- A cube splits and each piece slides into a new formation with satisfying clicks

BAD CONCEPTS (no cause and effect):
- Abstract swirling colors with no structure — no trigger, no chain reaction
- Multiple unrelated scenes cut together — breaks the continuous feeling
- Nothing actually transforming — static beauty is not satisfying
- Random particles or noise without a clear sequence

KEY PRINCIPLE: ONE continuous satisfying transformation in ONE shot. Simple, clean, mesmerizing. The viewer watches one trigger moment cascade into perfection.

CRITICAL — CLIP COUNT:
- Prefer 1-2 clips, NOT 3. A single 8-second satisfying moment is better than 3 disjointed scenes.
- If using 2 clips: they must show the SAME object/scene from the SAME angle — just a continuation, not a scene change.
- NEVER jump to a completely different view or object between clips.
- One perfect satisfying loop > three mediocre disconnected scenes."""


def build_satisdefying_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_satisdefying_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating satisfying video concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nEach concept is a 2-3 clip satisfying visual experience."

    user = f"""Generate {count} satisfying concepts. Focus on ONE trigger action that causes a perfect cascade of movements — glossy 3D render style.

EXAMPLE:
{{
  "title": "One Ball Starts a Perfect Chain",
  "sora_prompts": [
    "Glossy 3D render style, smooth reflective surfaces, perfect geometric shapes, vibrant saturated colors, studio lighting on dark background. A single glossy red sphere sits at the top of a curved track, studio lighting catches its perfect reflective surface, dark background, the ball begins to roll slowly, satisfying smooth motion",
    "Same glossy 3D scene, same dark background and studio lighting. The red sphere reaches the bottom and strikes a row of perfectly aligned glossy spheres in graduated colors, each one clicking into motion one after another in a perfect cascade, the chain reaction spreads outward in a mesmerizing wave of color and synchronized movement, smooth reflective surfaces catching light"
  ],
  "caption": "One tap and everything falls into place",
  "description": "When one ball starts the perfect chain reaction. #oddlysatisfying #Shorts #satisfying",
  "tags": ["oddly satisfying", "chain reaction", "satisfying", "Shorts"],
  "score": 9.5
}}

RULES:
- 1-2 prompts per concept — ONE continuous satisfying transformation, not 3 disjointed scenes
- GLOSSY 3D STYLE — every prompt must include "glossy 3D render style, smooth reflective surfaces, perfect geometric shapes, vibrant saturated colors, studio lighting on dark background"
- Must have CAUSE AND EFFECT — one action triggers a cascade of perfect movements
- Same scene, same lighting, same camera across all prompts for continuity
- Simple, clean, mesmerizing — the viewer is hypnotized by the perfect chain of motion
- Vary the concepts: domino cascades, paint fills, object transformations, synchronized movements
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, descriptive",
    "sora_prompts": ["Clip 1...", "Clip 2..."],
    "caption": "Short sensory caption",
    "description": "YouTube description with #oddlysatisfying #asmr #Shorts",
    "tags": ["oddly satisfying", "ASMR", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for satisfying content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, glossy 3D render style, smooth reflective surfaces, "
        "perfect geometric shapes, satisfying motion graphics, vibrant saturated colors, "
        "studio lighting on dark background, no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Match the exact same material, lighting, camera angle, and color palette as this scene: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — immediately show the satisfying action in progress. The flow/pour/transformation must be visible from frame 1. No setup, no establishing shots."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " Final shot — the most satisfying moment. The payoff. Same material, lighting, and camera as the opening."
        else:
            style_suffix = continuity + " Middle shot — the transformation continues. Maintain identical lighting and camera setup."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
