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
    num_scenes = int(duration_seconds / 20) + 5  # ~20 seconds per scene, fewer longer clips

    system = (
        "You are a professional YouTube video director. You create CALM, DELIBERATE visual plans. "
        "You know that good faceless videos let clips BREATHE — holding on a single shot for 20-40 seconds "
        "while the narrator talks, not cutting every 5 seconds like a slideshow. "
        "You use stat cards and title cards as punctuation — not filler. "
        "You think about what the viewer is FEELING, not just what they're seeing."
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
   - duration: 15-40 seconds (LET IT BREATHE — this is not a slideshow)
   - text_overlay: optional short text shown briefly on the clip (or null)
   - IMPORTANT: queries must be REAL FILMABLE scenes with natural movement
   - Think: what would a documentary show during this narration?

2. "stat_card" — Full-screen stat/number on dark background
   - stat_text: The big number or stat (e.g., "56%", "$3.2B", "10x")
   - subtitle: One line of context (e.g., "of Americans use AI monthly")
   - duration: 3-4 seconds
   - Use SPARINGLY — only for the 3-5 most impactful numbers in the entire video

3. "title_card" — Section heading on dark background
   - title_text: Section title (e.g., "The Paradox", "Why People Don't Trust It")
   - duration: 2-3 seconds
   - Use only at major topic transitions (3-5 per video max)

CRITICAL DIRECTING RULES:
- FEWER SCENES IS BETTER. Aim for {num_scenes}-{num_scenes + 5} total scenes, not 50+
- Footage clips should be 15-40 seconds each. Let them hold while the narrator talks.
- Only 3-5 stat cards in the ENTIRE video — the most impactful numbers only
- Only 3-5 title cards — at major section breaks
- Search queries should find PEOPLE DOING THINGS (not static objects or landscapes)
- Total duration of all scenes must equal ~{int(duration_seconds)} seconds
- 70-80% of the video should be footage scenes

Return ONLY a JSON array, no markdown:
[
  {{"type": "footage", "duration": 25, "search_query": "person scrolling phone cafe", "text_overlay": null}},
  {{"type": "stat_card", "duration": 4, "stat_text": "56%", "subtitle": "use AI every month"}},
  {{"type": "footage", "duration": 30, "search_query": "office workers at desks typing", "text_overlay": "Reluctant Adoption"}},
  {{"type": "title_card", "duration": 3, "title_text": "The Numbers"}}
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
        if scene["type"] == "footage":
            scene["duration"] = max(8, min(45, float(scene.get("duration", 20))))
        elif scene["type"] == "stat_card":
            scene["duration"] = max(3, min(5, float(scene.get("duration", 4))))
        elif scene["type"] == "title_card":
            scene["duration"] = max(2, min(4, float(scene.get("duration", 3))))
        else:
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
