"""Shared activities used across multiple channel pipelines."""

import json
import os

import structlog
from sqlalchemy import text
from temporalio import activity

from packages.clients.db import async_session

logger = structlog.get_logger()

USE_SORA = bool(os.getenv("OPENAI_API_KEY"))
USE_GEMINI = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


async def _execute(query: str, params: dict) -> None:
    async with async_session() as session:
        await session.execute(text(query), params)
        await session.commit()


@activity.defn
async def generate_concept_detail(
    run_id: int, channel_id: int, concept: dict,
    channel_name: str, channel_niche: str,
) -> dict:
    """Phase 2: Generate full Sora prompts for the selected concept.

    Takes a lightweight concept pitch and generates detailed sora_prompts.
    """
    log = logger.bind(activity="generate_concept_detail", run_id=run_id, title=concept.get("title"))

    async def _update_step():
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET current_step = 'generate_detail' WHERE id = :run_id"),
                {"run_id": run_id},
            )
            await session.commit()

    await _update_step()

    from apps.orchestrator.concept_engine import generate_detailed_prompts
    from packages.prompts.idea_detail import build_detail_prompt

    result = await generate_detailed_prompts(
        concept=concept,
        channel_name=channel_name,
        channel_niche=channel_niche,
        detail_prompt_builder=build_detail_prompt,
    )

    log.info("concept detail generated", clips=len(result.get("sora_prompts", [])))
    return result


@activity.defn
async def retry_failed_clips(
    run_id: int, channel_id: int, clips: list[str],
    prescreen_results: list[dict], concept: dict,
    prompt_module: str, sora_duration: int = 8, sora_size: str = "720x1280",
) -> list[str]:
    """Regenerate clips that failed Gemini prescreening.

    Args:
        run_id: Current run ID.
        channel_id: Channel ID.
        clips: Original clip paths.
        prescreen_results: Gemini prescreen results.
        concept: Concept dict with sora_prompts.
        prompt_module: Dotted module path for the channel's refine_sora_prompt function.
        sora_duration: Sora clip duration.
        sora_size: Sora resolution.

    Returns:
        Updated clip paths with failed clips replaced.
    """
    log = logger.bind(activity="retry_failed_clips", run_id=run_id)

    # Check if any clips failed
    failed = [r for r in prescreen_results if not r.get("passed", True)]
    if not failed:
        log.info("all clips passed prescreen, no retries needed")
        return clips

    if not USE_SORA:
        log.info("sora not configured, skipping retry")
        return clips

    import importlib
    mod = importlib.import_module(prompt_module)
    refine_fn = mod.refine_sora_prompt

    from packages.clients.sora import generate_video
    from apps.orchestrator.clip_retry import build_retry_prompt

    sora_prompts = concept.get("sora_prompts", [])
    updated_clips = list(clips)
    output_dir = os.path.dirname(clips[0]) if clips else f"output/run_{run_id}/clips"

    for review in failed:
        clip_idx = review.get("clip", -1)
        if clip_idx < 0 or clip_idx >= len(clips):
            continue

        log.info("regenerating failed clip", clip=clip_idx,
                 match_score=review.get("match_score"),
                 quality_score=review.get("quality_score"),
                 issues=review.get("issues", []))

        original_prompt = refine_fn(concept, clip_idx, len(sora_prompts))
        adjusted_prompt = build_retry_prompt(original_prompt, review)

        retry_path = os.path.join(output_dir, f"clip_{clip_idx:02d}_retry.mp4")
        try:
            result = generate_video(
                prompt=adjusted_prompt,
                output_path=retry_path,
                duration=sora_duration,
                size=sora_size,
                timeout=1200,
            )
            updated_clips[clip_idx] = result["path"]
            log.info("clip regenerated successfully", clip=clip_idx)
        except Exception as e:
            log.warning("clip regeneration failed, keeping original", clip=clip_idx, error=str(e))

    # Store retry info
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "clip_retry",
            "content": json.dumps({"retried": len(failed), "clips": updated_clips}),
        },
    )

    return updated_clips
