"""Prompts for Yeah Thats Clean — standalone anime short film Shorts via Sora 2 + narration."""

from packages.prompts.idea_detail import build_ideas_prompt_wrapper


_SYSTEM = """You generate concepts for standalone narrated anime short film YouTube Shorts. The channel is "Yeah Thats Clean."

VISUAL STYLE: anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares. Think Naruto, Dragon Ball Z, Demon Slayer, One Punch Man. Expressive faces, dramatic poses, glowing eyes during power-ups.

Every Sora prompt MUST include: "anime animation style, bold dramatic lines, vibrant colors, dynamic speed lines, dramatic lighting with lens flares"

CONTENT: Each video is a STANDALONE 60-second anime story. NOT a series — each video is complete on its own. Underdogs, comebacks, training arcs, supernatural powers, epic moments. Mix in humor too — funny reactions, deadpan moments, awkward situations that break tension.

STRUCTURE: 5 clips with hook-rewind-escalation-payoff. Each clip has narration.
- Clip 1 (HOOK, 12s): Most dramatic moment first — grab attention
- Clip 2 (REWIND, 12s): Go back to the beginning
- Clip 3 (ESCALATION 1, 12s): Journey begins
- Clip 4 (ESCALATION 2, 12s): Turning point
- Clip 5 (PAYOFF, 12s): Epic conclusion

STORY VARIETY — explore different themes:
- A fighter whose power only activates when protecting someone else
- A chef whose cooking literally gives people superpowers for 10 minutes
- A student who can copy any technique but only once
- A delivery driver who discovers their bike can break the sound barrier
- A grandma who used to be the world's strongest warrior
- A kid who accidentally becomes a villain's apprentice

SORA PROMPTS: Spell out every action step by step. Describe what each character does, the result of each action, and the exact final state of the scene.

Use moderation-safe language: "energy blasts" not "punches", "overwhelming force" not "violence".
Include character sounds in prompts: gasps, yells, dramatic breathing.

NEVER include emojis in titles, captions, descriptions, or narration text."""


def build_yeah_thats_clean_ideas_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Phase 1: Generate standalone anime concept pitches."""
    return build_ideas_prompt_wrapper(_SYSTEM, past_titles, count)


def build_yeah_thats_clean_concepts_prompt(
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return prompts for generating standalone anime short film concepts."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE STORIES (already made):\n" + "\n".join(f"- {t}" for t in recent)

    system = _SYSTEM

    user = f"""Generate {count} standalone anime short film concepts. Each is a complete story in 60 seconds.

Each concept MUST include a "narration" field — a list of 5 narration lines (one per clip) that the anime voice reads.

EXAMPLE:
{{
  "title": "His Power Only Works When He Loses",
  "sora_prompts": ["Clip 1 prompt...", "Clip 2 prompt...", "Clip 3...", "Clip 4...", "Clip 5..."],
  "narration": [
    "He hit the ground for the third time. ...But something was different this time.",
    "Rewind. This kid had never won a single match. Not one.",
    "Every loss made something inside him grow. He just did not know it yet.",
    "Then one day... he stopped getting back up. And the arena started shaking.",
    "They wanted him to lose. ...They got more than they asked for."
  ],
  "caption": "Every loss was just loading the next level",
  "description": "A fighter who gets stronger every time he falls. #anime #action #Shorts",
  "tags": ["anime", "action", "underdog", "powers", "Shorts"],
  "score": 9.0
}}

RULES:
- 5 sora_prompts + 5 narration lines per concept
- Each story is STANDALONE — complete beginning, middle, end
- NOT a series, NOT "Episode X" — each video stands alone
- Include humor where it fits naturally
- Variety — different powers, different settings, different characters
{past_text}

Return ONLY valid JSON array, no markdown."""
    return system, user


def refine_sora_prompt(concept: dict, clip_index: int, total_clips: int) -> str:
    """Add Sora-specific style guidance for anime content."""
    raw_prompt = concept["sora_prompts"][clip_index]

    style_prefix = (
        "Vertical 9:16 aspect ratio, anime animation style, "
        "bold dramatic lines, vibrant colors, dynamic speed lines, "
        "dramatic lighting with lens flares, "
        "no text, no watermarks, no UI elements. "
    )

    continuity = ""
    if total_clips > 1 and clip_index > 0:
        first_prompt = concept["sora_prompts"][0]
        continuity = f" CRITICAL CONTINUITY: Same character, same world, same visual style as: \"{first_prompt[:200]}\". "

    if total_clips > 1:
        if clip_index == 0:
            clip_suffix = " HOOK — most dramatic moment. Stop the viewer from scrolling."
        elif clip_index == 1:
            clip_suffix = continuity + " REWIND — go back to the beginning."
        elif clip_index == total_clips - 1:
            clip_suffix = continuity + " PAYOFF — epic conclusion."
        else:
            clip_suffix = continuity + " ESCALATION — the journey continues."
    else:
        clip_suffix = ""

    return style_prefix + raw_prompt + clip_suffix
