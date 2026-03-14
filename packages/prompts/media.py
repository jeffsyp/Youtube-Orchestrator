"""Prompts for the media phase — visual plan, voice plan, packaging."""


def build_visual_plan_prompt(script_content: str, idea_title: str) -> tuple[str, str]:
    """Return (system, user) prompts for creating a visual/shot plan."""
    system = (
        "You are a YouTube video director who creates shot lists and visual plans. "
        "You think in terms of what keeps viewers watching — dynamic visuals, clear information display, and pacing."
    )
    user = f"""Create a visual plan (shot list) for this YouTube video. These will be used to search for STOCK FOOTAGE on Pexels, so descriptions must be concrete, filmable scenes — not abstract concepts.

TITLE: {idea_title}

SCRIPT (first 500 words):
{' '.join(script_content.split()[:500])}

RULES:
- 10-15 shots for fast-paced editing
- Each shot 3-4 seconds (duration_seconds: 3 or 4)
- Descriptions must be SEARCHABLE stock footage terms (e.g., "close up of circuit board", "person typing on laptop", "server room with blinking lights")
- Do NOT describe abstract concepts, animations, or graphics — only real filmable scenes
- text_overlay should be null (we handle text separately)

Return ONLY valid JSON, no markdown:
{{
  "shots": [
    {{"scene_number": 1, "description": "person using smartphone in dark room", "duration_seconds": 3, "visual_style": "b-roll", "text_overlay": null}}
  ],
  "total_duration_seconds": 45,
  "style_notes": "brief style note"
}}"""
    return system, user


def build_voice_plan_prompt(script_content: str, idea_title: str, tone: str) -> tuple[str, str]:
    """Return (system, user) prompts for creating a voice/narration plan."""
    system = (
        "You are a voice director for YouTube videos. "
        "You guide narrators on pacing, emphasis, and delivery to maximize viewer engagement."
    )
    user = f"""Create a voice/narration plan for this YouTube video.

TITLE: {idea_title}
TONE: {tone}

SCRIPT (first 300 words):
{' '.join(script_content.split()[:300])}

Provide:
1. narration_style: Overall delivery style (1 sentence)
2. pacing: How pacing should shift throughout the video (1-2 sentences)
3. tone: Emotional tone guidance (1 sentence)
4. emphasis_points: List of 4-6 key delivery moments (keep each under 20 words)
5. script_with_directions: Just write "See script" (do NOT repeat the full script)

Return ONLY valid JSON, no markdown:
{{
  "narration_style": "...",
  "pacing": "...",
  "tone": "...",
  "emphasis_points": ["...", "..."],
  "script_with_directions": "See script"
}}"""
    return system, user


def build_package_prompt(
    idea_title: str, script_content: str, niche: str
) -> tuple[str, str]:
    """Return (system, user) prompts for creating the final video package metadata."""
    system = (
        "You are a YouTube SEO and packaging expert. "
        "You write titles, descriptions, and tags that maximize click-through rate while being honest."
    )
    user = f"""Create the YouTube upload package for this video.

TITLE: {idea_title}
NICHE: {niche}

SCRIPT (first 300 words):
{' '.join(script_content.split()[:300])}

Provide:
1. title: Optimized YouTube title (under 60 chars, clickable but not clickbait)
2. description: YouTube description (150-300 words, include key points, timestamps placeholder, and relevant hashtags)
3. tags: List of 8-12 relevant YouTube tags
4. category: YouTube category (e.g., "Science & Technology", "Education")
5. thumbnail_text: Short text for thumbnail (2-4 words, high contrast)

Return EXACTLY this JSON format (no markdown, no extra text):
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2", ...],
  "category": "...",
  "thumbnail_text": "..."
}}"""
    return system, user
