"""Temporal workflow for the Fundational pipeline.

Pipeline: concepts → select → generate clips → prescreen → retry failed →
render → QA → video review → publish (gated on review score >= 6)
"""

from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.fundational_activities import (
        generate_fundational_clips,
        pick_fundational_concepts,
        prescreen_fundational_clips,
        publish_fundational_short,
        render_fundational_short,
        review_fundational_video,
        fundational_qa_check,
        store_fundational_concept,
    )
    from apps.orchestrator.shared_activities import generate_concept_detail, retry_failed_clips
    from apps.orchestrator.activities import mark_run_awaiting_approval

ACTIVITY_TIMEOUT = timedelta(seconds=300)
SORA_TIMEOUT = timedelta(seconds=1800)
RENDER_TIMEOUT = timedelta(seconds=600)
REVIEW_TIMEOUT = timedelta(seconds=180)
MIN_PUBLISH_SCORE = 8.5


@workflow.defn
class FundationalPipeline:
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
        concepts = await workflow.execute_activity(
            pick_fundational_concepts, args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        if auto_pick:
            concept = concepts[0]
            self._selected_concept_index = 1
        else:
            await workflow.execute_activity(
                mark_run_awaiting_approval, args=[run_id, "select_fundational_concept"],
                start_to_close_timeout=ACTIVITY_TIMEOUT)
            await workflow.wait_condition(lambda: self._selected_concept_index is not None)
            idx = self._selected_concept_index - 1
            concept = concepts[idx] if 0 <= idx < len(concepts) else concepts[0]

        await workflow.execute_activity(
            store_fundational_concept, args=[run_id, channel_id, concept],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        # Generate detailed Sora prompts for selected concept
        concept = await workflow.execute_activity(
            generate_concept_detail,
            args=[run_id, channel_id, concept, "Fundational", "AI step-by-step building and construction"],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        clips = await workflow.execute_activity(
            generate_fundational_clips, args=[run_id, channel_id, concept],
            start_to_close_timeout=SORA_TIMEOUT)

        prescreen = await workflow.execute_activity(
            prescreen_fundational_clips, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=REVIEW_TIMEOUT)

        clips = await workflow.execute_activity(
            retry_failed_clips,
            args=[run_id, channel_id, clips, prescreen, concept,
                  "packages.prompts.fundational", 12],
            start_to_close_timeout=SORA_TIMEOUT)

        rendered = await workflow.execute_activity(
            render_fundational_short, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=RENDER_TIMEOUT)

        qa = await workflow.execute_activity(
            fundational_qa_check, args=[run_id, channel_id, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        review = await workflow.execute_activity(
            review_fundational_video, args=[run_id, channel_id, rendered, concept],
            start_to_close_timeout=REVIEW_TIMEOUT)

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
            publish_fundational_short, args=[run_id, channel_id, concept, qa, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        result["video_path"] = rendered.get("path")
        result["topic"] = concept.get("title", "")
        result["review"] = review
        return result
