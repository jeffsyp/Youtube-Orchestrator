"""Shared prompt builders for the two-phase concept generation.

Phase 1 (ideas): Each channel has its own ideas prompt builder.
Phase 2 (detail): This file provides a shared detail prompt builder
that works across all channels by taking the channel context as input.
"""


def build_ideas_prompt_wrapper(system_text: str, past_titles: list[str] | None = None, count: int = 5) -> tuple[str, str]:
    """Wrap a channel's system prompt into a lightweight ideas-only prompt.

    Instead of asking for full Sora prompts, just asks for concept pitches.
    """
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE CONCEPTS (already made):\n" + "\n".join(f"- {t}" for t in recent)

    user = f"""Generate {count} concept ideas. For each, provide ONLY a pitch — no Sora prompts yet.

EVERY concept must answer these 3 questions in the "brief":
1. What's the HOOK? (what grabs attention in the first 2 seconds)
2. What DEVELOPS? (how does the scene progress — something changes, builds, unfolds, or transforms)
3. What's the PAYOFF? (satisfying ending — a reveal, completion, or beautiful final moment)

Keep concepts SIMPLE and CONCRETE — describe what the viewer literally sees. Avoid abstract or overly complex scenarios that AI video can't execute convincingly.
{past_text}

Return ONLY valid JSON array, no markdown:
[
  {{
    "title": "Catchy title under 50 chars",
    "brief": "One sentence describing what happens in the video — the story arc",
    "caption": "Short caption for the video",
    "description": "YouTube description with hashtags",
    "tags": ["tag1", "tag2", "tag3", "tag4", "Shorts"],
    "score": 8.5
  }}
]

NEVER include emojis in titles, captions, or descriptions. Emojis render as empty boxes in video subtitles."""
    return system_text, user


def build_detail_prompt(concept: dict, channel_name: str, channel_niche: str,
                        feedback: str = "") -> tuple[str, str]:
    """Generate full detailed Sora prompts for a selected concept.

    This is the Phase 2 call — all creative energy focused on one concept.
    Feedback from past Gemini reviews is injected to improve quality over time.
    """
    title = concept.get("title", "")
    brief = concept.get("brief", "")
    caption = concept.get("caption", "")

    system = f"""You are a video director for "{channel_name}" — a YouTube Shorts channel focused on {channel_niche}.

You've been given a concept that was selected as the best idea. Your job is to write exactly ONE detailed Sora 2 video generation prompt — a single continuous 12-second clip.

CRITICAL: Generate exactly 1 prompt, not 2 or 3. The entire video is ONE continuous shot. No cuts, no scene changes. Everything happens in a single take.

SORA 2 CAPABILITIES:
- GOOD AT: fluid dynamics, nature, landscapes, atmospheric lighting, animals in motion, smooth transformations, architectural scenes, color
- BAD AT: precise hand/tool interactions, text rendering, exact physics (cutting, splitting), detailed facial expressions, mechanical actions

EVERY PROMPT MUST INCLUDE:
- Camera specs (lens, f-stop, angle)
- Lighting description
- Sound description (Sora generates audio)
- Specific material/texture/color details
- REPEAT the same subject description, environment, and lighting in every prompt for visual continuity

THE FORMULA THAT WORKS (learned from our best-performing video):
1. INSTANT HOOK (first 2 seconds) — something is ALREADY happening. No establishing shots.
2. DEVELOPMENT (seconds 3-15) — the scene progresses. Something changes, builds, unfolds, or transforms. The viewer stays because they want to see where it goes.
3. PAYOFF (final seconds) — satisfying conclusion. A reveal, a completion, a beautiful final moment.

The concept must be SIMPLE enough for AI to execute. "A seed sprouts and grows into a huge tree" = good. "Liquid chrome sphere absorbing dimensional color clouds" = too abstract and will look like noise.

Keep it CONCRETE and VISUAL — describe what the viewer literally SEES, not abstract concepts.

Everything in ONE continuous camera movement. No cuts.

{feedback}"""

    user = f"""Write the Sora 2 prompts for this concept:

TITLE: {title}
STORY: {brief}
CAPTION: {caption}

Generate exactly 1 detailed Sora prompt — a single continuous 12-second clip. Pack the full story into one shot.

Return ONLY valid JSON, no markdown:
{{
  "sora_prompts": [
    "One detailed 12-second continuous shot prompt with camera specs, lighting, sound, and full action arc from hook to payoff..."
  ],
  "caption": "{caption}",
  "description": "YouTube description with hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "Shorts"]
}}"""

    return system, user
