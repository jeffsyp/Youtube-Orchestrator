"""Prompts for Yeah Thats Clean — AI-generated satisfying cleaning Shorts via Sora 2."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated satisfying cleaning YouTube Shorts. The channel is "Yeah Thats Clean."

VISUAL STYLE: Bright cel animation — bold outlines, flat vibrant colors, anime-inspired clean aesthetic. Smooth color transitions, crisp clean lines, studio animation quality. Everything looks like a high-quality animated show with bold graphic style.

Every Sora prompt MUST include: "bright cel animation style, bold outlines, flat vibrant colors, anime-inspired clean aesthetic, smooth color transitions, crisp clean lines, studio animation quality"

THE FORMULA — CAUSE AND EFFECT:
Every video follows one rule: ONE cleaning action triggers a magical transformation that sweeps across the entire scene. A single touch, swipe, or wave causes grime to shatter, dissolve, or flee — and color floods in to replace it. The cleaning is not realistic scrubbing. It is MAGICAL and ANIMATED.

GOOD CONCEPTS (one magic action → transformation sweeps across scene):
- A magic wave sweeps across a dirty surface leaving it sparkling with vibrant color
- Color floods into a grey/brown scene making everything bright and vibrant in a cascade
- Grime cracks and falls away like a shell, revealing gleaming color underneath
- A single raindrop hits a dusty surface and a ripple of clean spreads outward
- One touch sends a pulse of light that dissolves all the dirt in its path

BAD CONCEPTS (no magic, or no cause and effect):
- Realistic scrubbing or wiping motions — too mundane, not animated
- Human hands holding sponges or tools — no hands needed
- Pressure washers or cleaning machines — too realistic
- Anything needing real physics — the cleaning is magical, not mechanical
- Dirt just fading away with no trigger moment — needs a clear cause

KEY PRINCIPLE: The cleaning is MAGICAL and ANIMATED — one sweep, one wave, one transformation. A single moment triggers the entire clean. No realistic tools, no human hands, no physics-based scrubbing.

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""


def build_yeah_thats_clean_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts)."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_yeah_thats_clean_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating satisfying cleaning concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nEach concept is a 2-3 clip dirty-to-clean transformation."

    user = f"""Generate {count} satisfying cleaning concepts. Focus on MAGICAL ANIMATED transformations — one action triggers a wave of clean sweeping across the scene. Bright cel animation style.

EXAMPLE:
{{
  "title": "One Touch Cleans the Whole Room",
  "sora_prompts": [
    "Bright cel animation style, bold outlines, flat vibrant colors, anime-inspired clean aesthetic, crisp clean lines, studio animation quality. A dusty grey-brown animated room with bold outlines, everything covered in a layer of dull grime, cobwebs in corners, faded colors on every surface, a single glowing fingertip reaches toward the nearest wall",
    "Same animated room, same bold outline style. The moment the fingertip touches the wall, a brilliant wave of color explodes outward like a ripple in water, sweeping across every surface — the grime shatters and falls away like glass, vibrant blues, greens, and yellows flood in behind the wave, the room transforms from dull to gleaming in one continuous magical sweep",
    "Same animated room, now completely transformed. Every surface gleams with flat vibrant colors and crisp clean lines, the room is spotless and radiant, bold outlines on every object, the colors are impossibly vivid and satisfying, studio animation quality, a few sparkles fade in the air where the last grime dissolved"
  ],
  "caption": "One touch and it all just melts away",
  "description": "The most satisfying clean you will ever see. #satisfying #cleaning #Shorts #oddlysatisfying",
  "tags": ["satisfying", "cleaning", "oddly satisfying", "animation", "Shorts"],
  "score": 9.5
}}

RULES:
- 2-3 prompts per concept — clip 1: grimy reveal, clip 2: magical cleaning wave, clip 3: sparkling result
- CEL ANIMATION STYLE — every prompt must include "bright cel animation style, bold outlines, flat vibrant colors, anime-inspired clean aesthetic, crisp clean lines, studio animation quality"
- Must have CAUSE AND EFFECT — one magic trigger causes the entire clean
- NO realistic tools, NO human hands, NO pressure washers — the cleaning is MAGICAL
- The contrast between dirty (grey/brown/dull) and clean (vibrant/bright/colorful) must be extreme
- Same scene, same style across all prompts for continuity
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, descriptive",
    "sora_prompts": ["Clip 1 dirty reveal...", "Clip 2 cleaning action...", "Clip 3 clean reveal..."],
    "caption": "Short punchy caption",
    "description": "YouTube description with #satisfying #cleaning #Shorts",
    "tags": ["satisfying", "cleaning", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for cleaning content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, bright cel animation style, bold outlines, "
        "flat vibrant colors, anime-inspired clean aesthetic, smooth color transitions, "
        "crisp clean lines, studio animation quality, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Match the exact same location, surface material, lighting, camera angle, and color palette as this scene: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — show the grimy, dull, colorless scene immediately. Bold outlines, everything faded and dirty. The viewer must see how bad it is from frame 1."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " Final shot — everything is now sparkling clean with vibrant cel animation colors. Bold outlines, flat bright colors, the transformation is complete and stunning."
        else:
            style_suffix = continuity + " Middle shot — the magical cleaning wave sweeps across the scene. Color floods in, grime shatters away. One continuous animated transformation."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
