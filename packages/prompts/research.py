"""Prompts for the research phase — template extraction."""


def extract_templates_prompt(candidates_summary: str, niche: str) -> tuple[str, str]:
    """Return (system, user) prompts for extracting content templates from candidates."""
    system = (
        "You are a YouTube content strategist analyzing viral videos. "
        "Extract repeatable content patterns that explain WHY these videos went viral. "
        "Focus on structure, hook style, and narrative arc — not the specific topic."
    )
    user = f"""Analyze these viral YouTube videos in the "{niche}" niche and extract 3 content templates/patterns.

CANDIDATE VIDEOS:
{candidates_summary}

For each template, provide:
1. pattern_name: A short, memorable name (e.g., "Underdog Breakthrough", "Industry Disruption")
2. description: What makes this pattern work (1-2 sentences)
3. hook_style: How the video opens to grab attention
4. structure: The narrative sections in order (list of 4-6 steps)
5. source_video_ids: Which candidate videos use this pattern (list their video_ids)

Return EXACTLY this JSON format (no markdown, no extra text):
[
  {{
    "pattern_name": "...",
    "description": "...",
    "hook_style": "...",
    "structure": ["section1", "section2", ...],
    "source_video_ids": ["id1", "id2"]
  }},
  ...
]"""
    return system, user


def generate_ideas_prompt(
    templates_summary: str, candidates_summary: str, niche: str, tone: str
) -> tuple[str, str]:
    """Return (system, user) prompts for generating video ideas."""
    system = (
        "You are a YouTube content creator who generates viral video ideas. "
        "You combine proven content patterns with fresh angles to create compelling video concepts. "
        f"Your channel's tone is: {tone}."
    )
    user = f"""Based on these content templates and recent viral videos in the "{niche}" niche, generate 4 unique video ideas.

CONTENT TEMPLATES:
{templates_summary}

RECENT VIRAL VIDEOS:
{candidates_summary}

For each idea, provide:
1. title: A clickable YouTube title (under 60 chars)
2. hook: The opening line/hook (1-2 sentences)
3. angle: What makes this video unique (1-2 sentences)
4. target_length_seconds: Recommended video length (300-720)
5. score: Your confidence this would perform well (1.0-10.0)
6. selected: false (selection happens later)

Return EXACTLY this JSON format (no markdown, no extra text):
[
  {{
    "title": "...",
    "hook": "...",
    "angle": "...",
    "target_length_seconds": 480,
    "score": 7.5,
    "selected": false
  }},
  ...
]

Do not use emojis in titles, hooks, or any text content."""
    return system, user
