"""Temporal workflow for the Yeah Thats Clean pipeline.

Pipeline: concepts -> select -> generate clips -> prescreen -> retry failed ->
render -> QA -> video review -> publish (gated on review score >= 6)
"""

from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.yeah_thats_clean_activities import (
        generate_yeah_thats_clean_clips,
        pick_yeah_thats_clean_concepts,
        prescreen_yeah_thats_clean_clips,
        publish_yeah_thats_clean_short,
        render_yeah_thats_clean_short,
        review_yeah_thats_clean_video,
        yeah_thats_clean_qa_check,
        store_yeah_thats_clean_concept,
    )
    from apps.orchestrator.shared_activities import generate_concept_detail, retry_failed_clips
    from apps.orchestrator.activities import mark_run_awaiting_approval

ACTIVITY_TIMEOUT = timedelta(seconds=900)
SORA_TIMEOUT = timedelta(seconds=3600)
RENDER_TIMEOUT = timedelta(seconds=1800)
REVIEW_TIMEOUT = timedelta(seconds=600)
MIN_PUBLISH_SCORE = 7.0


@workflow.defn
class YeahThatsCleanPipeline:
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
            pick_yeah_thats_clean_concepts, args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        if auto_pick:
            concept = concepts[0]
            self._selected_concept_index = 1
        else:
            await workflow.execute_activity(
                mark_run_awaiting_approval, args=[run_id, "select_yeah_thats_clean_concept"],
                start_to_close_timeout=ACTIVITY_TIMEOUT)
            await workflow.wait_condition(lambda: self._selected_concept_index is not None)
            idx = self._selected_concept_index - 1
            concept = concepts[idx] if 0 <= idx < len(concepts) else concepts[0]

        await workflow.execute_activity(
            store_yeah_thats_clean_concept, args=[run_id, channel_id, concept],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        # Generate detailed Sora prompts for selected concept
        concept = await workflow.execute_activity(
            generate_concept_detail,
            args=[run_id, channel_id, concept, "Yeah Thats Clean", "AI-generated satisfying cleaning videos"],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        clips = await workflow.execute_activity(
            generate_yeah_thats_clean_clips, args=[run_id, channel_id, concept],
            start_to_close_timeout=SORA_TIMEOUT)

        prescreen = await workflow.execute_activity(
            prescreen_yeah_thats_clean_clips, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=REVIEW_TIMEOUT)

        clips = await workflow.execute_activity(
            retry_failed_clips,
            args=[run_id, channel_id, clips, prescreen, concept,
                  "packages.prompts.yeah_thats_clean"],
            start_to_close_timeout=SORA_TIMEOUT)

        rendered = await workflow.execute_activity(
            render_yeah_thats_clean_short, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=RENDER_TIMEOUT)

        qa = await workflow.execute_activity(
            yeah_thats_clean_qa_check, args=[run_id, channel_id, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        review = await workflow.execute_activity(
            review_yeah_thats_clean_video, args=[run_id, channel_id, rendered, concept],
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
            publish_yeah_thats_clean_short, args=[run_id, channel_id, concept, qa, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        result["video_path"] = rendered.get("path")
        result["topic"] = concept.get("title", "")
        result["review"] = review
        return result
