"""Prompts for Yeah Thats Clean — AI-generated satisfying cleaning Shorts via Sora 2."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated satisfying cleaning YouTube Shorts.

The channel is "Yeah Thats Clean" — every video shows something FILTHY getting transformed to FLAWLESS.

VISUAL STYLE: Stylized, colorful, slightly cartoon-like — NOT photorealistic. Think Pixar/animated movie quality with vibrant saturated colors, clean geometric shapes, and smooth surfaces. The world looks polished and exaggerated, like a high-end 3D animation or a video game cutscene. This style makes the cleaning transformations look more dramatic and satisfying because the contrast between dirty and clean is amplified.

Every Sora prompt MUST include: "stylized 3D animation style, vibrant saturated colors, smooth clean surfaces, slightly cartoon-like, Pixar-quality lighting, not photorealistic"

CONCEPTS THAT WORK:
- Magical cleaning transformations — dirt/grime melts away in a wave of color
- Satisfying liquid/foam dynamics — foam cascading down and revealing clean surface
- Before/after time-lapse — object goes from grimy to gleaming in one smooth motion
- Color reveal — dull faded surface transforms to vibrant bright colors
- Nature cleaning — rain washing away dust, water restoring color to faded things

AVOID:
- Realistic human hands or tools (cartoon style means no detailed hands needed)
- Precise scrubbing motions
- Interior household scenes with many small objects
- Anything that needs exact physics

The satisfaction comes from the DRAMATIC color transformation — dirty/dull to bright/clean in one smooth motion."""


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

    user = f"""Generate {count} satisfying cleaning concepts. Focus on DRAMATIC dirty-to-clean transformations using water, chemicals, foam, and restoration — NOT hand scrubbing or tool manipulation.

EXAMPLE:
{{
  "title": "Pressure Washing a Black Driveway",
  "sora_prompts": [
    "Aerial establishing shot of a concrete driveway completely blackened with years of grime, moss, and oil stains, the surface barely recognizable as concrete, overcast daylight providing even flat lighting, wide angle 24mm lens, the driveway looks abandoned and neglected, ambient outdoor sounds with distant birds",
    "Medium shot of a high-pressure washer stream hitting the black driveway surface, the water jet carving a perfect clean stripe through the grime revealing bright white concrete underneath, water spraying outward carrying black debris, the contrast between clean and dirty is extreme, same overcast daylight, 35mm lens at f/4, satisfying whooshing water pressure sounds with splashing",
    "Wide overhead drone shot showing the driveway now three-quarters cleaned, the dramatic split between pristine white concrete and remaining black grime creating a geometric pattern, water still flowing across the surface catching light, same overcast daylight, 24mm lens, ambient water drainage sounds with a sense of completion"
  ],
  "caption": "Years of grime, gone in minutes",
  "description": "This driveway hadn't been cleaned in YEARS. Watch the transformation. #satisfying #cleaning #pressurewashing #Shorts #oddlysatisfying",
  "tags": ["satisfying", "cleaning", "pressure washing", "oddly satisfying", "Shorts"],
  "score": 9.5
}}

RULES:
- 2-3 prompts per concept — clip 1: dirty reveal, clip 2: cleaning action, clip 3: clean reveal
- Every prompt must include camera specs (lens mm, f-stop), lighting description, and sound description
- Repeat the same location, lighting, and camera style across all prompts for continuity
- The DIRTIER the starting state, the more satisfying the transformation
- Satisfaction comes from WATCHING the transformation happen, not from precise tool work
- Vary the concepts: driveways, walls, pools, cars, fences, roofs, metal, stone, brick, tile
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
        "Vertical 9:16 aspect ratio, photorealistic, cinematic photography, "
        "high dynamic range, no text, no watermarks, no UI elements. "
        "Generate rich, detailed audio synchronized with the visual action — "
        "water splashing, fizzing, scrubbing, dripping, pressure hissing. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Match the exact same location, surface material, lighting, camera angle, and color palette as this scene: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — show the FILTHY surface immediately. The viewer must see how dirty it is from frame 1. No setup, no establishing shots — jump straight to the grime."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " Final shot — the BIG REVEAL. Show the surface now completely clean and pristine. Same location, same lighting — the transformation is unmistakable."
        else:
            style_suffix = continuity + " Middle shot — the cleaning action in progress. Water, foam, or chemicals actively removing grime. The transformation is happening before our eyes."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
