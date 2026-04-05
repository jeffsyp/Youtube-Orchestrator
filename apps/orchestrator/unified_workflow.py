"""Unified pipeline workflow — single Temporal workflow for all channels."""

import json
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.unified_activities import (
        generate_narrations,
        generate_sora_clips,
        mix_clip_audio,
        normalize_and_concat,
        generate_karaoke_subtitles,
        unified_qa_check,
        gemini_review,
        gemini_production_qa,
        auto_fix_subtitles,
        unified_mark_pending_review,
    )


@workflow.defn(name="UnifiedPipeline")
class UnifiedPipeline:
    """Single workflow that handles all channel pipelines.

    Concept is fully formed before workflow starts — no signals, no gates.
    Human interaction happens before (concept in chat) and after (review in chat).
    """

    @workflow.run
    async def run(self, run_id: int, concept: dict) -> dict:
        # 1. Generate narrations (ElevenLabs TTS)
        narration_result = await workflow.execute_activity(
            generate_narrations,
            args=[run_id, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 2. Generate Sora clips (with frame chaining)
        clips_result = await workflow.execute_activity(
            generate_sora_clips,
            args=[run_id, concept, narration_result],
            start_to_close_timeout=timedelta(seconds=3600),
        )

        # 3. Mix clip audio (Sora + narration)
        mixed_result = await workflow.execute_activity(
            mix_clip_audio,
            args=[run_id, clips_result, narration_result, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 4. Normalize and concatenate
        concat_result = await workflow.execute_activity(
            normalize_and_concat,
            args=[run_id, mixed_result, narration_result],
            start_to_close_timeout=timedelta(seconds=1800),
        )

        # 5. Generate karaoke subtitles and burn in
        rendered = await workflow.execute_activity(
            generate_karaoke_subtitles,
            args=[run_id, concat_result, narration_result, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 6. QA check
        qa = await workflow.execute_activity(
            unified_qa_check,
            args=[run_id, rendered],
            start_to_close_timeout=timedelta(seconds=120),
        )

        # 7. Gemini review
        review = await workflow.execute_activity(
            gemini_review,
            args=[run_id, rendered, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 8. Production QA (Gemini watches like an editor)
        production_qa = await workflow.execute_activity(
            gemini_production_qa,
            args=[run_id, rendered, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 9. Auto-fix subtitle issues if QA flagged them
        final_rendered = await workflow.execute_activity(
            auto_fix_subtitles,
            args=[run_id, rendered, production_qa, concat_result, narration_result, concept],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 10. Mark pending review
        await workflow.execute_activity(
            unified_mark_pending_review,
            args=[run_id, concept],
            start_to_close_timeout=timedelta(seconds=60),
        )

        return {
            "status": "pending_review",
            "video_path": final_rendered.get("video_path"),
            "review": review,
            "production_qa": production_qa,
            "qa": qa,
            "topic": concept.get("title", ""),
            "auto_fixed": final_rendered.get("auto_fixed", False),
        }
