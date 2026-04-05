"""Prompts for Fundational — AI-generated fairy tales and legends brought to life."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


# System prompt shared between ideas and full concepts
_SYSTEM = """You generate concepts for AI-generated fairy tale and legend YouTube Shorts. The channel is called "Fundational" — as in foundational stories that shaped who we are.

VISUAL STYLE: Dreamlike cinematic — slightly surreal lighting, warm golden tones, shallow depth of field, atmospheric fog and particles in the air. Photorealistic but with a magical quality. Think Terrence Malick meets fairy tale illustrations come to life.

Every Sora prompt MUST include: "dreamlike cinematic style, slightly surreal lighting, warm golden tones, shallow depth of field, atmospheric fog and particles in the air, photorealistic but with a magical quality"

WHAT THE VIDEOS ARE:
5-clip narrated stories (60 seconds total) that tell fairy tales, myths, and legends AS IF THEY REALLY HAPPENED. Each video follows a character through a journey — growing up, overcoming something, discovering something impossible. The visuals are dreamlike and cinematic. A narrator tells the story over the clips.

THE FORMAT:
- HOOK (12s): Start with the most dramatic moment. The viewer sees the climax first.
- REWIND (12s): "Rewind..." Go back to the beginning. How did this start?
- ESCALATION 1 (12s): The journey progresses. Stakes rise.
- ESCALATION 2 (12s): The most challenging moment. Will they make it?
- PAYOFF (12s): The emotional conclusion. Triumph, transformation, or bittersweet truth.

GOOD CONCEPTS (fairy tales / myths / legends as if real):
EPIC STORIES:
- A boy raised by wolves who becomes faster than them (ALREADY MADE — don't repeat)
- A fisherman who caught a star and had to return it to the sky
- A girl who planted one seed that grew into an entire kingdom overnight

LIGHTHEARTED / WHIMSICAL STORIES (make MORE of these):
- A fairy who keeps losing her magic wand and causes chaos looking for it
- A wizard apprentice who accidentally turns everything into frogs
- A tiny dragon who is terrified of fire and sneezes bubbles instead
- A girl who befriends the moon and visits it every night in her dreams
- A talking cat who secretly runs an entire village
- A cloud who wants to be a mountain
- A boy who finds a door in a tree that leads to a world made of candy

MIX OF TONES: Some stories should make you laugh, some should give you wonder, some should be emotional. Not every story needs to be dark or heavy. Studio Ghibli vibes — playful, magical, warm.

BAD CONCEPTS:
- Building or construction of any kind — NOT a building channel
- Too dark or heavy without any lightness
- Generic nature scenes without a character
- Boring, predictable stories with no twist or fun

EVERY STORY NEEDS:
1. A PROTAGONIST — one character we follow
2. SOMETHING MAGICAL — a power, a creature, an impossible event
3. A FEELING — wonder, laughter, warmth, surprise
4. MYTHICAL QUALITY — it should feel like a story passed down through generations
5. A KILLER HOOK — the first clip must make viewers say "WHAT? I need to see how this happened"

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
    """Return (system, user) prompts for generating Fundational fairy tale concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE STORIES (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM + "\n\nEach concept is a 5-clip narrated fairy tale with hook-rewind-escalation-payoff structure."

    user = f"""Generate {count} fairy tale / legend concepts. Each follows a character through a mythical journey.

EXAMPLE:
{{
  "title": "The Girl Who Grew a Kingdom",
  "sora_prompts": [
    "Dreamlike cinematic style, warm golden tones, atmospheric fog. A vast kingdom stretches across rolling hills — towers, bridges, gardens, all grown from living plants and vines. At the center stands a young woman with flowers woven through her hair, looking out over her creation from a balcony of living wood. Wind blows petals through the air. She smiles.",
    "Same dreamlike style. Rewind. A small girl about five years old kneels in dry cracked earth. She is alone in a barren field. She pushes a tiny seed into the soil with one finger. She cups her hands over the spot and closes her eyes. A single green sprout pushes through the dirt between her fingers.",
    "Same dreamlike style. The girl is now about twelve. The sprout has become a massive tree. She sits in its branches reading. Below the tree, grass and flowers have spread in all directions. Small vine structures are growing on their own — arches, walls, pathways. The girl watches them grow with wonder on her face.",
    "Same dreamlike style. The girl is now about eighteen. The vines and plants have formed buildings, bridges, towers. People have come from distant lands — they walk through the living corridors in amazement. The young woman walks among them, touching walls and making new rooms grow with a wave of her hand.",
    "Same dreamlike style. The woman stands on a balcony of living wood overlooking the vast plant kingdom. Thousands of people live in the vine city below. She reaches down and plants another seed in a pot on the balcony railing. A tiny sprout appears. She smiles. It never ends."
  ],
  "caption": "She planted one seed. It never stopped growing.",
  "description": "A girl plants a seed in barren earth. Twenty years later, it is a kingdom. #fairytale #story #legend #Shorts",
  "tags": ["fairy tale", "legend", "story", "magical", "kingdom", "Shorts"],
  "score": 9.5
}}

RULES:
- 5 Sora prompts per concept — hook, rewind, escalation 1, escalation 2, payoff
- DREAMLIKE STYLE — every prompt must include the visual style description
- Must follow ONE CHARACTER through time (aging, growing, changing)
- Must feel like a MYTH or LEGEND — not a modern story
- Each clip should describe the EXACT scene in detail — setting, character appearance, actions, emotions
- The hook must be the most dramatic moment shown FIRST
- Caption should be short and mythical
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Under 50 chars, mythical",
    "sora_prompts": ["Hook...", "Rewind...", "Escalation 1...", "Escalation 2...", "Payoff..."],
    "caption": "Short mythical caption",
    "description": "Description with #fairytale #legend #story #Shorts",
    "tags": ["fairy tale", "legend", "story", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for fairy tale content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, dreamlike cinematic style, "
        "slightly surreal lighting, warm golden tones, shallow depth of field, "
        "atmospheric fog and particles in the air, photorealistic but magical, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Same character, same world, same visual style as: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            clip_suffix = " HOOK — the most dramatic, visually stunning moment. This must stop the viewer from scrolling."
        elif clip_index == 1:
            clip_suffix = continuity + " REWIND — go back to the beginning. Show the humble origin."
        elif clip_index == total_clips - 1:
            clip_suffix = continuity + " PAYOFF — the emotional conclusion. Show the transformation complete."
        else:
            clip_suffix = continuity + f" ESCALATION — the journey continues. Show growth and change."
    else:
        clip_suffix = ""

    return style_prefix + raw_prompt + clip_suffix
