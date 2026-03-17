"""Shorts script generation — one-shot scripts with strong hooks."""

import json

import structlog

from packages.clients.claude import generate, generate_cheap

logger = structlog.get_logger()


def _parse_json(text: str) -> dict | list:
    """Extract JSON from a response that might have markdown fencing."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = text.rstrip()
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        return json.loads(fixed)


def pick_shorts_topics(
    niche: str,
    tone: str,
    past_titles: list[str] | None = None,
    count: int = 5,
) -> list[dict]:
    """Generate topic ideas for Shorts using Claude."""
    log = logger.bind(service="shorts_writer", action="pick_topics")
    log.info("generating shorts topics", niche=niche, count=count)

    from packages.prompts.shorts import build_shorts_topics_prompt
    system, user = build_shorts_topics_prompt(niche, tone, past_titles, count)
    response = generate(user, system=system, model="claude-sonnet-4-6", max_tokens=2048)
    topics = _parse_json(response)

    log.info("topics generated", count=len(topics))
    return topics


def write_shorts_script(
    topic: str,
    niche: str,
    tone: str,
    past_titles: list[str] | None = None,
) -> dict:
    """Generate a complete Shorts script in one pass.

    Returns a dict with: title, format, hook, script, loop_ending, description, tags.
    """
    log = logger.bind(service="shorts_writer", action="write_script")
    log.info("writing shorts script", topic=topic)

    from packages.prompts.shorts import write_shorts_script_prompt
    system, user = write_shorts_script_prompt(topic, niche, tone, past_titles)
    response = generate(user, system=system, max_tokens=2048, temperature=0.7)
    script_data = _parse_json(response)

    # Validate required fields
    required = ["title", "script", "hook"]
    for field in required:
        if field not in script_data:
            raise ValueError(f"Script missing required field: {field}")

    # Calculate word count from the script text (strip [CUT] markers)
    clean_script = script_data["script"].replace("[CUT]", "")
    script_data["word_count"] = len(clean_script.split())

    log.info("shorts script written",
             title=script_data["title"],
             word_count=script_data["word_count"],
             format=script_data.get("format"))
    return script_data
