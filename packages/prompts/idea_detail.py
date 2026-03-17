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
]"""
    return system_text, user


def build_detail_prompt(concept: dict, channel_name: str, channel_niche: str) -> tuple[str, str]:
    """Generate full detailed Sora prompts for a selected concept.

    This is the Phase 2 call — all creative energy focused on one concept.
    """
    title = concept.get("title", "")
    brief = concept.get("brief", "")
    caption = concept.get("caption", "")

    system = f"""You are a video director for "{channel_name}" — a YouTube Shorts channel focused on {channel_niche}.

You've been given a concept that was selected as the best idea. Your job is to write 2-3 detailed Sora 2 video generation prompts that will produce the clips for this video.

SORA 2 CAPABILITIES:
- GOOD AT: fluid dynamics, nature, landscapes, atmospheric lighting, animals in motion, smooth transformations, architectural scenes, color
- BAD AT: precise hand/tool interactions, text rendering, exact physics (cutting, splitting), detailed facial expressions, mechanical actions

EVERY PROMPT MUST INCLUDE:
- Camera specs (lens, f-stop, angle)
- Lighting description
- Sound description (Sora generates audio)
- Specific material/texture/color details
- REPEAT the same subject description, environment, and lighting in every prompt for visual continuity

STORY ARC:
- Clip 1: Hook — the viewer sees something interesting from frame 1. No establishing shots.
- Clip 2: Escalation — the situation develops, something new happens.
- Clip 3 (optional): Payoff — satisfying conclusion or twist."""

    user = f"""Write the Sora 2 prompts for this concept:

TITLE: {title}
STORY: {brief}
CAPTION: {caption}

Generate 2-3 detailed Sora prompts. Each prompt should be a complete scene description with camera, lighting, sound, and action.

Return ONLY valid JSON, no markdown:
{{
  "sora_prompts": [
    "Detailed prompt for clip 1 with camera specs, lighting, sound, action...",
    "Detailed prompt for clip 2 — same subject, same setting, escalation...",
    "Detailed prompt for clip 3 — payoff, same visual style..."
  ],
  "caption": "{caption}",
  "description": "YouTube description with hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "Shorts"]
}}"""

    return system, user
