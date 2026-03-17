"""Clip retry logic — regenerates Sora clips that fail Gemini prescreening.

Used by all channel workflows to implement the prescreen → retry loop.
If a clip fails, the Sora prompt is adjusted with Gemini's feedback and regenerated.
Max 1 retry per clip to avoid infinite loops.
"""

import json
import os

import structlog

logger = structlog.get_logger()


def build_retry_prompt(original_prompt: str, gemini_feedback: dict) -> str:
    """Adjust a Sora prompt based on Gemini's feedback about what went wrong.

    Args:
        original_prompt: The original Sora prompt that produced a bad clip.
        gemini_feedback: The Gemini prescreen review dict.

    Returns:
        Adjusted prompt with corrections.
    """
    issues = gemini_feedback.get("issues", [])
    description = gemini_feedback.get("description", "")

    if not issues and not description:
        # No useful feedback — just re-roll with same prompt
        return original_prompt

    feedback_text = ""
    if issues:
        feedback_text = "PREVIOUS ATTEMPT ISSUES: " + "; ".join(issues) + ". "
    if description:
        feedback_text += f"PREVIOUS ATTEMPT SHOWED: {description}. "

    feedback_text += "FIX these issues in this generation. "

    return feedback_text + original_prompt


async def regenerate_failed_clips(
    clips: list[str],
    prescreen_results: list[dict],
    concept: dict,
    refine_fn,
    generate_fn,
    output_dir: str,
    sora_duration: int = 8,
    sora_size: str = "720x1280",
) -> list[str]:
    """Regenerate clips that failed prescreening.

    Args:
        clips: Original clip paths.
        prescreen_results: Gemini prescreen results for each clip.
        concept: The concept dict with sora_prompts.
        refine_fn: Channel-specific prompt refinement function.
        generate_fn: Sora generate_video function.
        output_dir: Directory for regenerated clips.
        sora_duration: Clip duration.
        sora_size: Clip resolution.

    Returns:
        Updated clip paths (failed clips replaced with regenerated ones).
    """
    log = logger.bind(service="clip_retry")
    updated_clips = list(clips)
    sora_prompts = concept.get("sora_prompts", [])

    for review in prescreen_results:
        clip_idx = review.get("clip", -1)
        if clip_idx < 0 or clip_idx >= len(clips):
            continue

        if review.get("passed", True):
            continue

        # This clip failed — regenerate it
        log.info("regenerating failed clip", clip=clip_idx,
                 issues=review.get("issues", []),
                 match_score=review.get("match_score"),
                 quality_score=review.get("quality_score"))

        # Build adjusted prompt
        original_prompt = refine_fn(concept, clip_idx, len(sora_prompts))
        adjusted_prompt = build_retry_prompt(original_prompt, review)

        # Generate new clip
        retry_path = os.path.join(output_dir, f"clip_{clip_idx:02d}_retry.mp4")
        try:
            result = generate_fn(
                prompt=adjusted_prompt,
                output_path=retry_path,
                duration=sora_duration,
                size=sora_size,
                timeout=1200,
            )
            updated_clips[clip_idx] = result["path"]
            log.info("clip regenerated", clip=clip_idx, path=result["path"])
        except Exception as e:
            log.warning("clip regeneration failed, keeping original", clip=clip_idx, error=str(e))

    return updated_clips
