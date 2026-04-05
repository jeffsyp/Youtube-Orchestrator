"""Force a specific concept through the Satisdefying pipeline.

Bypasses concept generation and injects a pre-defined concept,
then runs the full pipeline (detail → clips → prescreen → render → QA → review).

Usage:
    uv run python scripts/force_satisdefying.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import structlog
from sqlalchemy import text
from packages.clients.db import async_session

logger = structlog.get_logger()

CHANNEL_ID = 4  # Satisdefying

FORCED_CONCEPT = {
    "title": "Hydraulic Press vs Diamond",
    "caption": "It tried to resist... it couldn't",
    "description": "Hydraulic press slowly crushes a flawless diamond — watch it resist, crack, and shatter spectacularly #oddlysatisfying #asmr #hydraulicpress #Shorts",
    "tags": ["oddly satisfying", "ASMR", "hydraulic press", "diamond", "crushing", "satisfying", "Shorts"],
    "score": 10.0,
    "brief": (
        "A glossy 3D render of a massive chrome hydraulic press descending onto a flawless "
        "brilliant-cut diamond sitting on a polished black platform. The diamond resists at first — "
        "the press strains, the platform flexes — then hairline cracks appear across the diamond's "
        "facets, spreading like lightning. Finally the diamond shatters spectacularly into hundreds "
        "of glittering fragments that scatter across the platform in slow motion. "
        "The whole scene is lit with dramatic studio lighting, reflections everywhere."
    ),
}


async def main():
    log = logger.bind(script="force_satisdefying")

    # 1. Create content_run
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', 'satisdefying') RETURNING id"),
            {"cid": CHANNEL_ID},
        )
        run_id = result.scalar_one()
        await session.commit()

    log.info("created run", run_id=run_id)

    try:
        await _run_pipeline(run_id, log)
    except Exception as e:
        log.error("pipeline failed", run_id=run_id, error=str(e))
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]},
            )
            await session.commit()
        raise


async def _run_pipeline(run_id, log):
    # 2. Store concept in ideas table (for tracking)
    async with async_session() as session:
        await session.execute(
            text("""INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
                    VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, true)"""),
            {
                "run_id": run_id, "channel_id": CHANNEL_ID,
                "title": FORCED_CONCEPT["title"],
                "hook": FORCED_CONCEPT["caption"],
                "angle": "satisdefying", "length": 25,
                "score": FORCED_CONCEPT["score"],
            },
        )
        await session.commit()

    # 3. Store concept as script record
    from apps.orchestrator.satisdefying_activities import (
        store_satisdefying_concept,
        generate_satisdefying_clips,
        prescreen_satisdefying_clips,
        render_satisdefying_short,
        satisdefying_qa_check,
        review_satisdefying_video,
    )
    from apps.orchestrator.shared_activities import generate_concept_detail, retry_failed_clips
    from apps.orchestrator.activities import mark_run_pending_review

    # Store concept
    log.info("storing concept", title=FORCED_CONCEPT["title"])
    await store_satisdefying_concept(run_id, CHANNEL_ID, FORCED_CONCEPT)

    # 4. Generate detailed Sora prompts via Claude
    log.info("generating detailed sora prompts via Claude")
    concept = await generate_concept_detail(
        run_id, CHANNEL_ID, FORCED_CONCEPT,
        "Satisdefying", "AI-generated ASMR satisfying videos",
    )
    log.info("detail generated", clips=len(concept.get("sora_prompts", [])),
             prompts=[p[:80] for p in concept.get("sora_prompts", [])])

    # 5. Generate Sora clips
    log.info("generating sora clips")
    clips = await generate_satisdefying_clips(run_id, CHANNEL_ID, concept)
    log.info("clips generated", count=len(clips))

    # 6. Prescreen clips with Gemini
    log.info("prescreening clips")
    prescreen = await prescreen_satisdefying_clips(run_id, CHANNEL_ID, clips, concept)
    log.info("prescreen done", results=prescreen)

    # 7. Retry failed clips (currently a no-op but keep for pipeline parity)
    clips = await retry_failed_clips(
        run_id, CHANNEL_ID, clips, prescreen, concept,
        "packages.prompts.satisdefying",
    )

    # 8. Render
    log.info("rendering short")
    rendered = await render_satisdefying_short(run_id, CHANNEL_ID, clips, concept)
    log.info("rendered", path=rendered.get("path"))

    # 9. QA check
    log.info("running QA")
    qa = await satisdefying_qa_check(run_id, CHANNEL_ID, rendered)
    log.info("QA result", passed=qa.get("passed"), issues=qa.get("issues"))

    # 10. Video review via Gemini
    log.info("reviewing video")
    review = await review_satisdefying_video(run_id, CHANNEL_ID, rendered, concept)
    log.info("review done", score=review.get("overall_score"),
             recommendation=review.get("publish_recommendation"))

    # 11. Mark as pending review (NO upload)
    description = concept.get("description", "")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"
    publish_metadata = {
        "title": concept.get("title", ""),
        "description": description,
        "tags": concept.get("tags", []),
        "category": "Entertainment",
    }
    await mark_run_pending_review(run_id, publish_metadata)

    # Update run status
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'pending_review', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    log.info("DONE",
             run_id=run_id,
             video=rendered.get("path"),
             qa_passed=qa.get("passed"),
             review_score=review.get("overall_score"),
             recommendation=review.get("publish_recommendation"))

    print(f"\n{'='*60}")
    print(f"  Satisdefying Forced Concept Complete")
    print(f"{'='*60}")
    print(f"  Run ID:    {run_id}")
    print(f"  Concept:   {FORCED_CONCEPT['title']}")
    print(f"  Video:     {rendered.get('path')}")
    print(f"  QA:        {'PASSED' if qa.get('passed') else 'FAILED'}")
    print(f"  Review:    {review.get('overall_score', 'N/A')}/10")
    print(f"  Status:    pending_review (NOT uploaded)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
