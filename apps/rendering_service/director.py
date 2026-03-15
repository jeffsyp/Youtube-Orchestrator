"""Director Agent — creates a unified visual plan from a script.

Instead of separate shot plans, footage queries, and overlay cues,
the director reads the entire script and produces one cohesive plan
that specifies exactly what to show at each moment:

- Stock footage clips with specific search queries
- Stat cards (big numbers/text on dark background)
- Section title cards
- Text overlays on footage

Each scene has a type, duration, and all the info needed to render it.
"""

import json

import structlog

from packages.clients.claude import generate

logger = structlog.get_logger()


def create_visual_plan(script_content: str, duration_seconds: float, title: str) -> list[dict]:
    """Have Claude act as a video director and create a complete scene-by-scene plan.

    Returns a list of scene dicts, each with:
    - type: "footage", "stat_card", or "title_card"
    - duration: seconds this scene should last
    - For footage: search_query (Pexels search terms)
    - For stat_card: stat_text (the big number), subtitle (context)
    - For title_card: title_text (section heading)
    - text_overlay: optional text to show over footage (or null)
    """
    log = logger.bind(service="director")
    log.info("creating visual plan", title=title, duration=round(duration_seconds))

    wpm = 150
    words = len(script_content.split())
    num_scenes = int(duration_seconds / 5) + 2  # ~5 seconds per scene

    system = (
        "You are a professional YouTube video director. You read narration scripts and create "
        "visual plans that make the content compelling. You think about PACING — fast cuts during "
        "energy moments, longer holds during emotional points. You think about VARIETY — mixing "
        "stock footage with stat cards and title cards so the viewer never gets bored. You think "
        "about RELEVANCE — every visual reinforces what the narrator is saying at that exact moment."
    )

    user = f"""Read this script and create a scene-by-scene visual plan for a {duration_seconds/60:.0f}-minute video.

TITLE: {title}
NARRATION SPEED: {wpm} wpm
TOTAL SCENES NEEDED: ~{num_scenes}

SCRIPT:
{script_content}

SCENE TYPES YOU CAN USE:

1. "footage" — Stock video clip from Pexels
   - search_query: 2-4 word CONCRETE search (e.g., "person typing laptop", "city traffic night")
   - duration: 4-8 seconds
   - text_overlay: optional short text shown on the clip (or null)
   - IMPORTANT: queries must be REAL FILMABLE scenes, not abstract concepts
   - Speed up any b-roll that might be slow-mo by describing ACTIVE scenes

2. "stat_card" — Full-screen stat/number on dark background
   - stat_text: The big number or stat (e.g., "56%", "$3.2B", "10x")
   - subtitle: One line of context (e.g., "of Americans use AI monthly")
   - duration: 3-4 seconds
   - Use these for impactful numbers, percentages, dollar amounts
   - These break up footage and make key stats memorable

3. "title_card" — Section heading on dark background
   - title_text: Section title (e.g., "The Paradox", "Why People Don't Trust It")
   - duration: 2-3 seconds
   - Use at major topic transitions (like chapter markers)

DIRECTING RULES:
- Start with a footage scene (NOT a title card — hook the viewer immediately)
- Use stat_cards when a key number is mentioned — make it visual
- Use title_cards at major section transitions (4-6 per video)
- Never put two stat_cards or title_cards back to back — always have footage between them
- Vary footage duration: 4s for fast energy, 6-8s for emotional/reflective moments
- Search queries should describe ACTIVE scenes with MOVEMENT (people doing things, not static objects)
- Add text_overlay on footage only for key terms or names (not stats — use stat_cards for those)
- Total duration of all scenes should equal ~{int(duration_seconds)} seconds

Return ONLY a JSON array, no markdown:
[
  {{"type": "footage", "duration": 5, "search_query": "person scrolling phone quickly", "text_overlay": null}},
  {{"type": "title_card", "duration": 3, "title_text": "The Numbers"}},
  {{"type": "stat_card", "duration": 4, "stat_text": "56%", "subtitle": "use AI every month"}},
  {{"type": "footage", "duration": 6, "search_query": "office workers busy typing", "text_overlay": "Reluctant Adoption"}}
]"""

    response = generate(user, system=system, max_tokens=8192, temperature=0.5)

    # Parse JSON
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        scenes = json.loads(text)
    except json.JSONDecodeError:
        fixed = text.rstrip()
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        scenes = json.loads(fixed)

    # Validate
    valid = []
    for scene in scenes:
        if "type" not in scene:
            continue
        scene["duration"] = max(2, min(10, float(scene.get("duration", 5))))
        if scene["type"] == "footage" and "search_query" not in scene:
            continue
        if scene["type"] == "stat_card" and "stat_text" not in scene:
            continue
        if scene["type"] == "title_card" and "title_text" not in scene:
            continue
        valid.append(scene)

    # Count types
    footage = sum(1 for s in valid if s["type"] == "footage")
    stats = sum(1 for s in valid if s["type"] == "stat_card")
    titles = sum(1 for s in valid if s["type"] == "title_card")
    total_dur = sum(s["duration"] for s in valid)

    log.info("visual plan created",
             scenes=len(valid), footage=footage, stat_cards=stats,
             title_cards=titles, total_duration=round(total_dur))

    return valid
