"""Prompts for Synth Meow — AI-generated animal Shorts via Sora 2."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated animal videos on YouTube Shorts. The channel is "Synth Meow."

VISUAL STYLE: Watercolor animation — soft painted textures, gentle brush strokes, like a children's book illustration come to life. Warm pastel colors, dreamy painted backgrounds.

Every Sora prompt MUST include: "watercolor animation style, soft painted textures, gentle brush strokes, children's book illustration come to life, warm pastel colors, dreamy painted backgrounds"

THE FORMULA — CAUSE AND EFFECT:
Every video follows one rule: an animal does something innocent → it causes an unexpected funny chain reaction. Something HAPPENS, then something RESULTS. The humor comes from the gap between the tiny action and the big consequence.

GOOD CONCEPTS (innocent action → unexpected chain reaction):
- A cat knocks a cup off a table → it triggers a Rube Goldberg chain reaction across the kitchen
- A dog pulls a loose thread on a sweater → everything in the room starts unraveling
- A hamster starts running on its wheel → the wheel powers up the entire house
- A bird lands on a branch → the branch bends and catapults another animal into the sky
- A cat sneezes → the force blows papers everywhere causing total office chaos

BAD CONCEPTS — AUTOMATIC SCORE BELOW 5:
- An animal just walking around or exploring — nothing HAPPENS
- An animal observing nature or looking at things — passive, no chain reaction
- An animal being passively cute with no consequence — cute but boring
- Pure spectacle with no trigger moment — no cause, no effect
- "A River of [animals] floods a [place]" — nature documentary, not a story
- "POV you are a [animal]" — no story, just a camera angle gimmick
- "[Animal] emerges from [place]" — just an animal appearing, nothing happens
- "Bioluminescent [anything]" — pretty but zero story
- ANY concept where the main appeal is "beautiful nature scene with an animal in it"
- ANY concept that could be described as "animal does [normal animal thing] in [pretty setting]"
- ANY concept without a clear BEGINNING → MIDDLE → END story arc

THE LITMUS TEST — every concept must pass ALL of these:
1. Does an animal DO something that causes an unexpected chain reaction? If no → REJECT
2. Is there a clear story with setup → escalation → punchline? If no → REJECT
3. Would someone LAUGH or say "oh no what happened"? If no → REJECT
4. Is the animal a CHARACTER with personality, not just a prop? If no → REJECT

WHAT MAKES THESE WORK:
- There is a clear TRIGGER moment (the cause) and a surprising RESULT (the effect)
- The animal is innocently unaware of the chaos they caused — this IS the comedy
- The chain reaction ESCALATES — each step gets bigger/funnier/worse
- The watercolor style makes the chaos feel whimsical, not destructive
- The animal has PERSONALITY — curious, mischievous, oblivious, smug
- There is a PUNCHLINE — the last clip delivers a comedic payoff

NEVER include emojis in titles, captions, or descriptions."""


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

    user = f"""Generate {count} concepts. Each must use watercolor animation style with cause-and-effect chain reactions.

EXAMPLE:
{{
  "title": "Cat Knocks Over the First Domino",
  "sora_prompts": [
    "Watercolor animation style, soft painted textures, gentle brush strokes, children's book illustration come to life, warm pastel colors, dreamy painted backgrounds. A fluffy orange tabby cat sitting on a watercolor-painted kitchen counter, one paw reaching toward a small cup near the edge, the cat looks curious and innocent, warm pastel lighting, soft brush stroke textures on every surface",
    "Same watercolor kitchen, same orange tabby cat watching with wide eyes as the cup falls and hits a stack of painted plates, which slide into a row of bottles, which knock over a broom, which bumps a shelf — a chain reaction spreading across the kitchen in soft watercolor motion, warm pastel colors, gentle brush strokes, the cat's expression shifts to surprise",
    "Same watercolor kitchen, same orange tabby cat now sitting calmly amid total whimsical chaos — flour clouds painted in soft white, pots and pans scattered like a children's book illustration, the cat licks its paw contentedly as if nothing happened, warm pastel tones, dreamy painted background, gentle brush stroke textures"
  ],
  "caption": "He has no idea what he started",
  "description": "One little tap and the whole kitchen went down. #cats #funny #Shorts #animals",
  "tags": ["funny cats", "animals", "cute", "chain reaction", "Shorts"],
  "score": 9.5
}}

RULES:
- 3 prompts per concept — trigger moment / chain reaction / aftermath
- WATERCOLOR STYLE — every prompt must include "watercolor animation style, soft painted textures, gentle brush strokes, children's book illustration come to life, warm pastel colors, dreamy painted backgrounds"
- Same animal description + setting + lighting in all 3 prompts for continuity
- Must have CAUSE AND EFFECT — animal does something small, big chain reaction follows
- The animal should be innocently unaware of the chaos
- Everyday settings — homes, shops, parks, streets, offices, schools
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
        "Vertical 9:16 aspect ratio, watercolor animation style, soft painted textures, "
        "gentle brush strokes, children's book illustration come to life, warm pastel colors, "
        "dreamy painted backgrounds, no text, no watermarks, no UI elements. "
    )

    # Continuity anchor from clip 1
    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Same animal, same setting, same lighting as: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            style_suffix = " Opening shot — the animal does something small and innocent that triggers everything. Show the cause moment."
        elif clip_index == total_clips - 1:
            style_suffix = continuity + " Final shot — the chain reaction is complete. The animal sits calmly amid the whimsical chaos, unaware. Same watercolor style."
        else:
            style_suffix = continuity + " Middle shot — the chain reaction escalates. Each thing causes the next. Same animal, same watercolor world."
    else:
        style_suffix = ""

    return style_prefix + raw_prompt + style_suffix
