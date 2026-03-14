"""Prompts for the writing phase — outline, script, critique, revision."""


def build_outline_prompt(idea: dict, niche: str) -> tuple[str, str]:
    """Return (system, user) prompts for building a video outline."""
    system = (
        "You are a YouTube scriptwriter who creates detailed video outlines. "
        "Your outlines are structured for maximum retention — strong hook, clear narrative, satisfying conclusion."
    )
    user = f"""Create a detailed outline for this YouTube video in the "{niche}" niche.

VIDEO IDEA:
- Title: {idea['title']}
- Hook: {idea['hook']}
- Angle: {idea['angle']}
- Target length: {idea['target_length_seconds']} seconds

Provide:
1. idea_title: The video title
2. sections: A list of 5-8 sections (each is a brief description of what that section covers)
3. estimated_duration_seconds: Target duration
4. key_points: 3-5 key takeaways the viewer should leave with

Return EXACTLY this JSON format (no markdown, no extra text):
{{
  "idea_title": "...",
  "sections": ["Hook: ...", "Section 2: ...", ...],
  "estimated_duration_seconds": {idea['target_length_seconds']},
  "key_points": ["point1", "point2", ...]
}}"""
    return system, user


def write_script_prompt(outline: dict, niche: str, tone: str) -> tuple[str, str]:
    """Return (system, user) prompts for writing a full script."""
    sections_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(outline["sections"]))
    key_points_text = "\n".join(f"  - {p}" for p in outline["key_points"])

    system = (
        f"You are a top YouTube scriptwriter. Your tone is: {tone}. "
        "You write scripts that feel natural when read aloud — conversational, punchy, no filler. "
        "Every sentence earns its place. You never use cliches or generic transitions."
    )
    user = f"""Write a complete YouTube video script based on this outline.

TITLE: {outline['idea_title']}
NICHE: {niche}
TARGET DURATION: {outline['estimated_duration_seconds']} seconds (~{outline['estimated_duration_seconds'] * 150 // 60} words at 150 wpm)

OUTLINE:
{sections_text}

KEY POINTS TO COVER:
{key_points_text}

REQUIREMENTS:
- Write the FULL script, word for word as it would be narrated
- Start with a strong hook in the first 5 seconds
- Include a clear call-to-action near the end
- Use short paragraphs (1-3 sentences each)
- Aim for ~{outline['estimated_duration_seconds'] * 150 // 60} words
- Do NOT include stage directions, visual cues, or [brackets]

Return ONLY the script text, no JSON wrapping."""
    return system, user


def critique_script_prompt(script_content: str, idea_title: str) -> tuple[str, str]:
    """Return (system, user) prompts for critiquing a script."""
    system = (
        "You are a ruthless but constructive YouTube script editor. "
        "You identify weak points that would cause viewers to click away. "
        "You are specific, actionable, and honest."
    )
    user = f"""Critique this YouTube script. Be specific about what works and what doesn't.

TITLE: {idea_title}

SCRIPT:
{script_content}

Provide your critique in this format:

STRENGTHS:
- (list 2-3 things that work well)

WEAKNESSES:
- (list 3-5 specific issues with line references or quotes)

RETENTION RISKS:
- (list moments where viewers might click away and why)

WORD COUNT ASSESSMENT:
- Current word count and whether it matches the target duration

PRIORITY FIXES:
- (numbered list of the top 3 changes that would most improve this script)

Return ONLY the critique text, no JSON wrapping."""
    return system, user


def revise_script_prompt(
    script_content: str, critique: str, idea_title: str, tone: str
) -> tuple[str, str]:
    """Return (system, user) prompts for revising a script based on critique."""
    system = (
        f"You are a top YouTube scriptwriter. Your tone is: {tone}. "
        "You are revising a script based on editorial feedback. "
        "Address every critique point while maintaining the script's voice and flow."
    )
    user = f"""Revise this YouTube script based on the critique below. Address every weakness and priority fix.

TITLE: {idea_title}

ORIGINAL SCRIPT:
{script_content}

CRITIQUE:
{critique}

REQUIREMENTS:
- Fix every issue raised in the critique
- Maintain the original tone and voice
- Keep or improve the hook
- Ensure the script flows naturally when read aloud
- Do NOT include stage directions, visual cues, or [brackets]

Return ONLY the revised script text, no JSON wrapping or commentary."""
    return system, user
