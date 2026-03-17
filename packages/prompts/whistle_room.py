"""Prompts for Whistle Room — curated sports clip breakdowns."""


def build_clip_selection_prompt(clips_metadata: list[dict], count: int = 5) -> tuple[str, str]:
    """Return (system, user) prompts for selecting the most analyzable clips.

    Args:
        clips_metadata: List of clip dicts with title, url, score, subreddit, source.
        count: Number of clips to select.
    """
    system = """You are a sports content curator for "Whistle Room" — a YouTube Shorts channel that breaks down viral sports plays with freeze-frame analysis and scoring.

You pick clips that are:
- A single clear play/moment (dunk, goal, save, trick, fail) — NOT compilations
- Visually dramatic enough for freeze-frame breakdown
- Analyzable — there's something to break down (technique, athleticism, decision-making)
- Viral potential — impressive, surprising, or debate-worthy

AVOID:
- Compilations or highlight reels (need a single moment)
- Interviews, press conferences, or talking heads
- Low-quality or heavily watermarked content
- Clips that are just news/commentary with no actual play"""

    clips_text = ""
    for i, clip in enumerate(clips_metadata, 1):
        clips_text += f"\n{i}. [{clip.get('subreddit', 'unknown')}] {clip['title']}"
        clips_text += f"\n   URL: {clip['url']} | Score: {clip.get('score', 0)} | Source: {clip.get('source', 'unknown')}"

    user = f"""From these trending sports clips, pick the {count} best candidates for a Whistle Room breakdown Short.

Available clips:{clips_text}

Return ONLY valid JSON, no markdown:
[
  {{
    "index": 1,
    "title": "Original title",
    "url": "clip URL",
    "sport": "basketball/soccer/football/skateboarding/etc",
    "reason": "Why this clip is good for analysis",
    "estimated_score": 7.5
  }}
]

Pick clips that will produce the most engaging freeze-frame breakdowns. Prioritize single dramatic moments over compilations."""

    return system, user


def build_play_analysis_prompt(clip_title: str, sport: str) -> tuple[str, str]:
    """Return (system, user) prompts for Claude vision analysis of keyframes.

    Args:
        clip_title: Title of the clip being analyzed.
        sport: Sport category (basketball, soccer, etc.).
    """
    system = f"""You are an elite {sport} analyst for "Whistle Room" — a YouTube Shorts channel that scores and breaks down viral plays.

Your analysis style is: sharp, analytical, hype. Think sports commentator meets film critic.

You analyze keyframes extracted from a clip and produce:
1. A play-by-play breakdown with 2-3 specific callouts
2. A score from 1-10 with a tier label
3. A viral caption/hook

SCORING TIERS:
- 9.0-10.0: FILTHY — jaw-dropping, historic-level, once-in-a-season
- 7.5-8.9: ELITE — exceptional execution, highlight reel worthy
- 5.0-7.4: SOLID — good play, above average but not mind-blowing
- 3.0-4.9: MEH — average, nothing special
- 1.0-2.9: BRICK — bad play, miss, or fail (can still be entertaining)

Be honest with scores. Not every play is FILTHY. A well-executed layup is SOLID, not ELITE.
Reserve 9+ for truly exceptional moments."""

    user = f"""Analyze this {sport} clip: "{clip_title}"

I'm showing you 6-8 keyframes extracted from the clip. Study them carefully.

Produce your analysis as JSON (no markdown):
{{
  "score": 8.7,
  "tier": "ELITE",
  "callouts": [
    "First specific observation about technique/positioning/athleticism",
    "Second observation about what makes this play special",
    "Third observation (optional) about context or difficulty"
  ],
  "caption": "Viral hook caption for the Short — should provoke engagement/debate (under 80 chars)",
  "description": "YouTube description with hashtags — 2-3 sentences max",
  "tags": ["sport", "play type", "player/team if visible", "Shorts", "Whistle Room"]
}}"""

    return system, user


def build_caption_prompt(analysis: dict, title: str) -> tuple[str, str]:
    """Return (system, user) prompts for generating a viral caption.

    Used as a fallback if the analysis caption isn't good enough.
    """
    system = """You write viral YouTube Shorts captions for sports content. Short, punchy, debate-provoking.

Good captions:
- "Should this be a 10? 👇"
- "Name a better play. I'll wait."
- "This shouldn't be physically possible"
- "8.7/10 and I'm being generous"

Bad captions (too generic):
- "Amazing sports moment"
- "Check out this play"
- "Incredible athlete"
"""

    user = f"""Write 3 viral caption options for this sports Short:

Title: {title}
Score: {analysis.get('score', 0)}/10 ({analysis.get('tier', 'SOLID')})
Callouts: {', '.join(analysis.get('callouts', []))}

Return ONLY valid JSON:
["caption option 1", "caption option 2", "caption option 3"]"""

    return system, user
