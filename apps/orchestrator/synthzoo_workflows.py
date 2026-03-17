"""Temporal workflow for the Synth Zoo pipeline.

Pipeline: concepts → select → generate clips → prescreen → retry failed →
render → QA → video review → publish (gated on review score >= 6)
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.synthzoo_activities import (
        generate_synthzoo_clips,
        pick_synthzoo_concepts,
        prescreen_synthzoo_clips,
        publish_synthzoo_short,
        render_synthzoo_short,
        review_synthzoo_video,
        store_synthzoo_concept,
        synthzoo_qa_check,
    )
    from apps.orchestrator.shared_activities import generate_concept_detail, retry_failed_clips
    from apps.orchestrator.activities import mark_run_awaiting_approval

ACTIVITY_TIMEOUT = timedelta(seconds=900)
SORA_TIMEOUT = timedelta(seconds=3600)
RENDER_TIMEOUT = timedelta(seconds=1800)
REVIEW_TIMEOUT = timedelta(seconds=600)
MIN_PUBLISH_SCORE = 7.0


@workflow.defn
class SynthZooPipeline:
    def __init__(self):
        self._selected_concept_index: int | None = None

    @workflow.signal
    async def select_concept(self, index: int) -> None:
        self._selected_concept_index = index

    @workflow.query
    def get_status(self) -> str:
        if self._selected_concept_index is not None:
            return f"concept_selected:{self._selected_concept_index}"
        return "awaiting_concept_selection"

    @workflow.run
    async def run(self, run_id: int, channel_id: int, auto_pick: bool = False,
                  privacy: str = "private") -> dict:
        # 1. Pick concepts
        concepts = await workflow.execute_activity(
            pick_synthzoo_concepts,
            args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 2. Concept selection
        if auto_pick:
            concept = concepts[0]
            self._selected_concept_index = 1
        else:
            await workflow.execute_activity(
                mark_run_awaiting_approval,
                args=[run_id, "select_synthzoo_concept"],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
            )
            await workflow.wait_condition(lambda: self._selected_concept_index is not None)
            idx = self._selected_concept_index - 1
            concept = concepts[idx] if 0 <= idx < len(concepts) else concepts[0]

        await workflow.execute_activity(
            store_synthzoo_concept,
            args=[run_id, channel_id, concept],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # Generate detailed Sora prompts for selected concept
        concept = await workflow.execute_activity(
            generate_concept_detail,
            args=[run_id, channel_id, concept, "Synth Meow", "AI-generated animal videos"],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 3. Generate Sora clips
        clips = await workflow.execute_activity(
            generate_synthzoo_clips,
            args=[run_id, channel_id, concept],
            start_to_close_timeout=SORA_TIMEOUT,
        )

        # 4. Prescreen clips (Gemini watches each one)
        prescreen = await workflow.execute_activity(
            prescreen_synthzoo_clips,
            args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=REVIEW_TIMEOUT,
        )

        # 5. Retry failed clips (regenerate with Gemini feedback)
        clips = await workflow.execute_activity(
            retry_failed_clips,
            args=[run_id, channel_id, clips, prescreen, concept,
                  "packages.prompts.synthzoo"],
            start_to_close_timeout=SORA_TIMEOUT,
        )

        # 6. Render
        rendered = await workflow.execute_activity(
            render_synthzoo_short,
            args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=RENDER_TIMEOUT,
        )

        # 7. QA
        qa = await workflow.execute_activity(
            synthzoo_qa_check,
            args=[run_id, channel_id, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 8. Video review (Gemini watches final video)
        review = await workflow.execute_activity(
            review_synthzoo_video,
            args=[run_id, channel_id, rendered, concept],
            start_to_close_timeout=REVIEW_TIMEOUT,
        )

        # 9. Publish — gated on review score
        # Only gate on score if review actually succeeded — don't block on review errors
        review_score = review.get("overall_score", 10) if review.get("reviewed") else 10
        if review_score < MIN_PUBLISH_SCORE:
            return {
                "published": False,
                "reason": f"Review score {review_score} below minimum {MIN_PUBLISH_SCORE}",
                "video_path": rendered.get("path"),
                "topic": concept.get("title", ""),
                "review": review,
            }

        if privacy != "private":
            concept["_privacy_override"] = privacy
        result = await workflow.execute_activity(
            publish_synthzoo_short,
            args=[run_id, channel_id, concept, qa, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        result["video_path"] = rendered.get("path")
        result["topic"] = concept.get("title", "")
        result["review"] = review
        return result
