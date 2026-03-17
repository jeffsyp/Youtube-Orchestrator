"""Prompts for YouTube Shorts — script generation, visual planning, packaging."""


# Proven hook patterns baked into the system prompt
HOOK_LIBRARY = """
HOOK PATTERNS (pick one and adapt to your topic — vary across Shorts):

STAT SHOCK: "97% of people get this wrong..." / "This costs $X billion a year..."
BOLD CLAIM: "Everything you know about X is wrong." / "X is secretly destroying Y."
QUESTION BAIT: "Why does nobody talk about this?" / "What if I told you..."
PATTERN BREAK: "Stop scrolling. This changes everything about X."
CHALLENGE: "I bet you can't name 3..." / "Most people fail this..."
MICRO-STORY: "Last week, a developer discovered something that..."
CONTRARIAN: "Everyone says X. They're wrong. Here's why."
COUNTDOWN: "Three things about X that will blow your mind. Number one..."
"""

# Short formats that scale well
SHORTS_FORMATS = """
FORMATS (pick the best fit for the topic):

THREE_TIPS: "3 Things You Didn't Know About X" — micro-listicle, one tip per 15-20s segment
WRONG_WAY: "You're Doing X Wrong" — call out a common mistake, show the fix
WAIT_WHAT: Start normal, drop a mind-blowing reveal midway — pattern break
DID_YOU_KNOW: Rapid-fire facts building to a surprising conclusion
BEFORE_AFTER: Compare old way vs new way, weak vs strong, etc.
RANKING: "Top 3 X Nobody Talks About" — countdown format with ranked items
"""


def write_shorts_script_prompt(
    topic: str,
    niche: str,
    tone: str,
    past_titles: list[str] | None = None,
) -> tuple[str, str]:
    """Return (system, user) prompts for writing a YouTube Short script."""
    past_text = ""
    if past_titles:
        recent = past_titles[-20:]
        past_text = f"\nAVOID THESE TITLES (already used):\n" + "\n".join(f"- {t}" for t in recent)

    system = f"""You are a YouTube Shorts scriptwriter who specializes in high-retention, viral short-form content.
You write scripts designed for 30-60 second vertical videos. Every word earns its place.
Your tone is: {tone}.

You write for VOICE PERFORMANCE — this will be read by an AI voice.
- Short punchy sentences for impact. Like this.
- Ellipses for dramatic pauses...
- Dashes — for quick pivots
- Questions to create vocal uptick?
- Vary sentence length constantly

{HOOK_LIBRARY}
{SHORTS_FORMATS}

CRITICAL RULES:
- The first sentence IS the hook. It must stop the scroll in under 2 seconds.
- Never waste a single second. No "hey guys", no "welcome back", no throat-clearing.
- Every 10-15 seconds needs a micro-payoff — a surprising fact, a twist, or new info that resets attention.
- The ending should feel like it connects back to the beginning (loop-friendly).
- Mark scene breaks with [CUT] — aim for a cut every 5-8 seconds of narration.
- NEVER use episode numbers, series names, or recurring format branding.
- Channel name is "Signal Intel" — never reference it in the script.
"""

    user = f"""Write a YouTube Shorts script about this topic:

TOPIC: {topic}
NICHE: {niche}

TARGET: 120-170 words (30-55 seconds when spoken — MUST stay under 58 seconds to qualify as a YouTube Short)
{past_text}

Return ONLY valid JSON, no markdown:
{{
  "title": "Catchy title under 60 chars (no episode numbers, no series names)",
  "format": "three_tips|wrong_way|wait_what|did_you_know|before_after|ranking",
  "hook": {{
    "text": "The exact first sentence that stops the scroll",
    "style": "stat_shock|bold_claim|question_bait|pattern_break|challenge|contrarian|countdown"
  }},
  "script": "Full narration text with [CUT] markers between segments. No stage directions.",
  "loop_ending": "Final sentence that connects back to the hook",
  "description": "YouTube description with #Shorts and 3-5 hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}"""
    return system, user


def build_shorts_visual_plan_prompt(script: str, title: str) -> tuple[str, str]:
    """Return (system, user) prompts for creating a Shorts visual plan."""
    system = """You are a YouTube Shorts video director. You create FAST-CUT visual plans for vertical (9:16) videos.
Shorts demand rapid visual changes — a new shot every 2-4 seconds to maintain retention.
You think in vertical format: close-ups work better than wide shots. Faces, hands, screens, details.
"""

    user = f"""Create a visual plan for this YouTube Short (vertical 9:16, 30-58 seconds).

TITLE: {title}

SCRIPT (with [CUT] markers):
{script}

IMPORTANT: Every scene has stock footage playing. Text scenes overlay text ON TOP of footage — there are NEVER static slides or text-on-black-background. The viewer should always see motion.

SCENE TYPES (all require search_query for stock footage):

1. "footage" — Stock video with 1-3 keyword(s) overlaid in the center
   - search_query: 2-4 word CONCRETE search (close-ups, hands, screens, faces)
   - keyword: 1-3 words from the narration that the viewer should read (the most important/interesting word or phrase being said during this scene)
   - duration: 2-4 seconds

2. "text_punch" — Bold emphasized text overlaid on stock footage (for stats, punchlines, key claims)
   - search_query: 2-4 word search for visually relevant background footage
   - text: Key phrase or stat (3-8 words max)
   - duration: 2-3 seconds

3. "hook_card" — Attention-grabbing text overlaid on dramatic footage
   - search_query: 2-4 word search for dramatic/cinematic background footage
   - text: The hook that stops the scroll
   - duration: 2-3 seconds

RULES:
- 10-18 scenes total
- Each scene 2-4 seconds MAX
- Alternate between footage and text_punch for rhythm
- Start with a hook_card
- EVERY scene must have a search_query — footage always plays
- Search queries should be CONCRETE and visual (not abstract concepts)
- Total duration MUST be 30-58 seconds (hard limit for YouTube Shorts)
- ~60% footage, ~30% text_punch, ~10% hook_card

Return ONLY a JSON array, no markdown:
[
  {{"type": "hook_card", "duration": 2, "text": "Stop scrolling.", "search_query": "dramatic eye close up"}},
  {{"type": "footage", "duration": 3, "search_query": "person typing phone close up", "keyword": "secretly draining"}},
  {{"type": "text_punch", "duration": 2, "text": "97% get this wrong", "search_query": "confused person thinking"}},
  {{"type": "footage", "duration": 3, "search_query": "phone battery low", "keyword": "40% faster"}}
]"""
    return system, user


def build_shorts_topics_prompt(
    niche: str,
    tone: str,
    past_titles: list[str] | None = None,
    count: int = 5,
) -> tuple[str, str]:
    """Return (system, user) prompts for generating Short topic ideas."""
    past_text = ""
    if past_titles:
        recent = past_titles[-30:]
        past_text = f"\nAVOID THESE TOPICS (already covered):\n" + "\n".join(f"- {t}" for t in recent)

    system = f"""You are a YouTube Shorts strategist for a tech channel. You identify topics that will stop the scroll.
You know that the best Shorts topics are: surprising, contrarian, or immediately useful.
The channel tone is: {tone}.
NEVER suggest episode-style content, series names, or recurring formats.
Every Short must stand alone with its own unique hook."""

    user = f"""Suggest {count} YouTube Shorts topics for the "{niche}" niche.

Each topic should be:
- Specific enough to cover in 30-60 seconds
- Have a clear hook angle (surprising stat, common mistake, hidden feature, etc.)
- Be standalone — no episode numbers or series
{past_text}

Return ONLY valid JSON, no markdown:
[
  {{
    "topic": "Brief topic description",
    "hook_angle": "Why this stops the scroll",
    "format": "three_tips|wrong_way|wait_what|did_you_know|before_after|ranking",
    "score": 8.5
  }}
]"""
    return system, user
