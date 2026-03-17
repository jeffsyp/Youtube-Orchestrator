"""Feedback loop — stores Gemini suggestions and injects them into future Sora prompts.

After each video review, Gemini's suggestions are stored in the DB as "feedback" assets.
When generating new Sora prompts, the most recent feedback is pulled and injected into
the prompt refinement step, so the pipeline learns and improves over time.

This creates a closed loop:
  generate → review → extract feedback → inject into next generation → generate better
"""

import json

import structlog
from sqlalchemy import text

from packages.clients.db import async_session

logger = structlog.get_logger()


async def store_feedback(channel_id: int, review: dict) -> None:
    """Extract actionable feedback from a Gemini review and store it.

    Pulls out the suggestions, top_issue, and score patterns
    into a structured feedback record.
    """
    if not review.get("reviewed"):
        return

    feedback = {
        "overall_score": review.get("overall_score", 0),
        "top_issue": review.get("top_issue", ""),
        "summary": review.get("summary", ""),
    }

    # Collect all suggestion fields
    suggestions = []
    for key in ["suggestions", "prompt_suggestions", "continuity_suggestions",
                "concept_suggestions", "rendering_suggestions", "general_suggestions"]:
        if key in review and isinstance(review[key], list):
            suggestions.extend(review[key])
    feedback["suggestions"] = suggestions

    # Extract individual scores for pattern tracking
    score_keys = [k for k in review.keys() if k.endswith("_score") and k != "overall_score"]
    feedback["dimension_scores"] = {k: review[k] for k in score_keys if isinstance(review.get(k), (int, float))}

    # Find the latest run_id for this channel to attach feedback to
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id FROM content_runs WHERE channel_id = :cid ORDER BY id DESC LIMIT 1"),
            {"cid": channel_id},
        )
        row = result.fetchone()
        feedback_run_id = row[0] if row else 1

        await session.execute(
            text("""INSERT INTO assets (channel_id, run_id, asset_type, content)
                    VALUES (:cid, :rid, :type, :content)"""),
            {
                "cid": channel_id,
                "rid": feedback_run_id,
                "type": "pipeline_feedback",
                "content": json.dumps(feedback),
            },
        )
        await session.commit()

    logger.info("feedback stored", channel_id=channel_id,
                score=feedback["overall_score"],
                suggestions=len(suggestions))


async def get_accumulated_feedback(channel_id: int, limit: int = 10) -> str:
    """Get accumulated feedback for a channel, formatted for injection into Sora prompts.

    Returns a string of actionable rules derived from past reviews.
    """
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT content FROM assets
                    WHERE channel_id = :cid AND asset_type = 'pipeline_feedback'
                    ORDER BY id DESC LIMIT :lim"""),
            {"cid": channel_id, "lim": limit},
        )
        rows = result.fetchall()

    if not rows:
        return ""

    # Parse all feedback records
    feedbacks = []
    for row in rows:
        try:
            feedbacks.append(json.loads(row[0]))
        except (json.JSONDecodeError, TypeError):
            continue

    if not feedbacks:
        return ""

    # Find recurring issues (mentioned in 2+ reviews)
    issue_counts = {}
    all_suggestions = []
    low_dimensions = {}

    for fb in feedbacks:
        # Track top issues
        issue = fb.get("top_issue", "")
        if issue:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        # Collect all suggestions
        all_suggestions.extend(fb.get("suggestions", []))

        # Track consistently low-scoring dimensions
        for dim, score in fb.get("dimension_scores", {}).items():
            if score < 7:
                low_dimensions[dim] = low_dimensions.get(dim, 0) + 1

    # Build feedback string
    lines = ["LEARNED RULES FROM PAST REVIEWS (follow these strictly):"]

    # Recurring issues become hard rules
    recurring = [issue for issue, count in issue_counts.items() if count >= 2]
    if recurring:
        lines.append("\nRECURRING ISSUES TO FIX:")
        for issue in recurring[:3]:
            lines.append(f"- {issue}")

    # Consistently low dimensions
    weak_dims = [dim for dim, count in low_dimensions.items() if count >= 2]
    if weak_dims:
        lines.append("\nWEAK AREAS TO IMPROVE:")
        for dim in weak_dims[:3]:
            clean_name = dim.replace("_score", "").replace("_", " ").title()
            lines.append(f"- {clean_name} consistently scores low — prioritize this")

    # Top suggestions (deduplicated, most recent first)
    seen = set()
    unique_suggestions = []
    for s in all_suggestions:
        key = s[:50].lower()
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)
    if unique_suggestions:
        lines.append("\nSPECIFIC IMPROVEMENTS TO APPLY:")
        for s in unique_suggestions[:5]:
            lines.append(f"- {s}")

    if len(lines) <= 1:
        return ""

    return "\n".join(lines)
