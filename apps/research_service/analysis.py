"""Research analysis — extract templates and generate ideas using Claude."""

import json

import structlog

from packages.clients.claude import generate, generate_cheap
from packages.prompts.research import extract_templates_prompt, generate_ideas_prompt
from packages.schemas.research import CandidateVideo, TemplatePattern
from packages.schemas.writing import IdeaVariant

logger = structlog.get_logger()


def _parse_json_list(text: str) -> list:
    """Extract a JSON array from a response that might have markdown fencing."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])
    return json.loads(text)


def _candidates_summary(candidates: list[CandidateVideo]) -> str:
    """Format candidates for inclusion in a prompt."""
    lines = []
    for c in candidates:
        lines.append(
            f"- [{c.video_id}] \"{c.title}\" by {c.channel_name} "
            f"({c.views:,} views, {c.channel_subscribers:,} subs, "
            f"score={c.breakout_score}, tags={c.tags[:5]})"
        )
    return "\n".join(lines)


def extract_templates(
    candidates: list[CandidateVideo], niche: str
) -> list[TemplatePattern]:
    """Use Claude to extract content patterns from top-performing videos."""
    log = logger.bind(service="research", action="extract_templates")
    log.info("extracting templates", candidate_count=len(candidates))

    summary = _candidates_summary(candidates)
    system, user = extract_templates_prompt(summary, niche)
    response = generate(user, system=system, max_tokens=2048, temperature=0.5)
    data = _parse_json_list(response)

    templates = [TemplatePattern(**t) for t in data]
    log.info("templates extracted", count=len(templates))
    return templates


def generate_ideas(
    templates: list[TemplatePattern],
    candidates: list[CandidateVideo],
    niche: str,
    tone: str,
    past_titles: list[str] | None = None,
) -> list[IdeaVariant]:
    """Use Claude to generate video ideas based on templates and candidates.

    Args:
        past_titles: List of previously generated idea titles to avoid repeating.
    """
    log = logger.bind(service="research", action="generate_ideas")
    log.info("generating ideas", past_to_avoid=len(past_titles) if past_titles else 0)

    templates_summary = "\n".join(
        f"- {t.pattern_name}: {t.description} (hook: {t.hook_style})"
        for t in templates
    )
    candidates_summary = _candidates_summary(candidates[:10])  # Top 10 only

    system, user = generate_ideas_prompt(templates_summary, candidates_summary, niche, tone)

    # Add dedup instructions if we have past ideas
    if past_titles:
        avoid_list = "\n".join(f"- {t}" for t in past_titles[:30])
        user += f"\n\nIMPORTANT: Do NOT generate ideas similar to these past ideas (already produced):\n{avoid_list}"

    response = generate(user, system=system, max_tokens=2048, temperature=0.8)
    data = _parse_json_list(response)

    ideas = [IdeaVariant(**d) for d in data]
    # Sort by score descending, but do NOT auto-select — human picks
    ideas.sort(key=lambda i: i.score, reverse=True)

    log.info("ideas generated", count=len(ideas), top_title=ideas[0].title if ideas else "")
    return ideas
