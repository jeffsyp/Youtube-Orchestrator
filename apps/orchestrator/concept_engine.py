"""Concept engine — two-phase concept generation.

Phase 1: Generate 5 lightweight idea pitches (title, caption, score, brief description)
Phase 2: Generate full detailed Sora prompts ONLY for the selected concept

This is faster and produces better results because:
- Phase 1 is fast (~15s) — just ideas, no detailed prompts
- Phase 2 focuses all creative energy on ONE concept (~30s)
- We don't waste Opus tokens generating 12+ detailed Sora prompts we'll never use
"""

import json

import structlog
from sqlalchemy import text

from packages.clients.db import async_session

logger = structlog.get_logger()


async def get_past_reviews(channel_id: int, limit: int = 10) -> list[dict]:
    """Fetch past Gemini video reviews for a channel."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT a.content FROM assets a
                    JOIN content_runs cr ON cr.id = a.run_id
                    WHERE a.channel_id = :cid AND a.asset_type = 'video_review'
                    ORDER BY a.id DESC LIMIT :lim"""),
            {"cid": channel_id, "lim": limit},
        )
        reviews = []
        for row in result.fetchall():
            try:
                review = json.loads(row[0])
                if review.get("reviewed"):
                    reviews.append(review)
            except (json.JSONDecodeError, TypeError):
                continue
        return reviews


async def get_past_titles(channel_id: int, content_type: str, limit: int = 50) -> list[str]:
    """Fetch past video titles for deduplication."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT DISTINCT s.idea_title FROM scripts s
                    JOIN content_runs cr ON cr.id = s.run_id
                    WHERE s.channel_id = :cid AND cr.content_type = :ct
                    ORDER BY s.idea_title LIMIT :lim"""),
            {"cid": channel_id, "ct": content_type, "lim": limit},
        )
        return [row[0] for row in result.fetchall()]


async def generate_idea_pitches(
    channel_id: int,
    channel_name: str,
    channel_niche: str,
    content_type: str,
    ideas_prompt_builder,
    count: int = 5,
) -> tuple[list[dict], str]:
    """Phase 1: Generate lightweight concept pitches (no Sora prompts).

    Returns:
        Tuple of (ideas list, insights string).
        Each idea has: title, caption, description, tags, score, brief.
    """
    log = logger.bind(channel=channel_name, engine="concept_engine", phase="ideas")

    past_reviews = await get_past_reviews(channel_id)
    past_titles = await get_past_titles(channel_id, content_type)

    from packages.clients.claude import generate

    if len(past_reviews) >= 2:
        log.info("using evolved idea generation", past_reviews=len(past_reviews))

        from packages.prompts.trend_research import build_trend_research_prompt
        system, user = build_trend_research_prompt(
            channel_name=channel_name,
            channel_niche=channel_niche,
            past_titles=past_titles,
            past_reviews=past_reviews,
        )

        response = generate(user, system=system, max_tokens=8192, temperature=0.9)
        text_resp = _parse_json_response(response)

        result = json.loads(text_resp)
        concepts = result.get("concepts", [])
        insights = result.get("insights", "")
        log.info("evolved ideas generated", count=len(concepts))
        return concepts, insights
    else:
        log.info("using static idea generation", past_reviews=len(past_reviews))

        system, user = ideas_prompt_builder(past_titles, count)
        response = generate(user, system=system, max_tokens=8192, temperature=0.9)
        text_resp = _parse_json_response(response)

        concepts = json.loads(text_resp)
        log.info("static ideas generated", count=len(concepts))
        return concepts, ""


async def generate_detailed_prompts(
    concept: dict,
    channel_name: str,
    channel_niche: str,
    detail_prompt_builder,
) -> dict:
    """Phase 2: Generate full Sora prompts for the selected concept.

    Takes a lightweight concept (title, caption, brief) and generates
    the detailed sora_prompts with camera specs, lighting, sounds, continuity.

    Returns:
        The concept dict enriched with sora_prompts.
    """
    log = logger.bind(channel=channel_name, engine="concept_engine", phase="detail",
                      title=concept.get("title"))

    from packages.clients.claude import generate

    system, user = detail_prompt_builder(concept, channel_name, channel_niche)
    response = generate(user, system=system, max_tokens=8192, temperature=0.7)
    text_resp = _parse_json_response(response)

    detail = json.loads(text_resp)

    # Merge detailed prompts into the concept
    concept["sora_prompts"] = detail.get("sora_prompts", [])
    concept["clip_durations"] = detail.get("clip_durations", [8] * len(concept["sora_prompts"]))
    if not concept.get("caption") and detail.get("caption"):
        concept["caption"] = detail["caption"]
    if not concept.get("description") and detail.get("description"):
        concept["description"] = detail["description"]
    if not concept.get("tags") and detail.get("tags"):
        concept["tags"] = detail["tags"]

    log.info("detailed prompts generated", clips=len(concept.get("sora_prompts", [])))
    return concept


def _parse_json_response(response: str) -> str:
    """Strip markdown code fences from a JSON response."""
    text_resp = response.strip()
    if text_resp.startswith("```"):
        lines = text_resp.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text_resp = "\n".join(lines[start:end])
    return text_resp
