"""Prompts for generating timed text overlay cues from a script."""


def generate_overlay_cues_prompt(script_content: str, duration_seconds: float) -> tuple[str, str]:
    """Return (system, user) prompts for generating text overlay cues."""
    duration_min = round(duration_seconds / 60, 1)
    words = len(script_content.split())
    wpm = 150

    system = (
        "You are a professional YouTube video editor who adds text overlays. "
        "You know exactly when to show key phrases on screen to reinforce what the narrator is saying. "
        "You are tasteful — you don't spam text. You only show text when it adds real value: "
        "section titles, key numbers, important names, or dramatic reveals."
    )

    user = f"""Analyze this script for a {duration_min}-minute video and generate text overlay cues.

SCRIPT:
{script_content}

VIDEO DURATION: {duration_seconds:.0f} seconds ({duration_min} minutes)
NARRATION SPEED: ~{wpm} words per minute

For each text overlay, provide:
1. start_seconds: When the text appears (calculate from word position at {wpm} wpm)
2. duration: How long it stays on screen (2-4 seconds)
3. text: The text to show (keep SHORT — max 6 words, ideally 2-4)
4. style: One of these types:
   - "section_title" — for numbered items or section headers (large, centered, bold)
   - "key_fact" — for important numbers, stats, names (medium, lower third)
   - "emphasis" — for dramatic single words or short phrases (large, centered, brief)

RULES:
- Generate 10-20 overlays for a {duration_min}-minute video (roughly 1-2 per minute)
- Section titles for numbered items (e.g., "#1 Directed Energy Weapons")
- Key facts for specific numbers, costs, dates, names
- Emphasis for dramatic moments ("This changes everything")
- Space them at least 15 seconds apart — never overlap
- Calculate start_seconds based on word position in the script at {wpm} wpm
- DO NOT show text for every sentence — only the most impactful moments

Return ONLY valid JSON array, no markdown:
[
  {{"start_seconds": 5, "duration": 3, "text": "#1 Directed Energy", "style": "section_title"}},
  {{"start_seconds": 45, "duration": 3, "text": "$3.2 Billion Budget", "style": "key_fact"}}
]

Do not use emojis in any text overlay content."""

    return system, user
