"""Temporal workflow for the Gamatatsuken pipeline.

Pipeline: concepts -> select -> generate clips -> prescreen ->
render (with narration) -> QA -> video review -> pending_review
"""

from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.gamatatsuken_activities import (
        generate_gamatatsuken_clips,
        pick_gamatatsuken_concepts,
        prescreen_gamatatsuken_clips,
        publish_gamatatsuken_short,
        render_gamatatsuken_short,
        review_gamatatsuken_video,
        gamatatsuken_qa_check,
        store_gamatatsuken_concept,
    )
    from apps.orchestrator.shared_activities import generate_concept_detail, retry_failed_clips
    from apps.orchestrator.activities import mark_run_awaiting_approval, mark_run_pending_review, store_pending_concepts

ACTIVITY_TIMEOUT = timedelta(seconds=900)
SORA_TIMEOUT = timedelta(seconds=3600)
RENDER_TIMEOUT = timedelta(seconds=1800)
REVIEW_TIMEOUT = timedelta(seconds=600)


@workflow.defn
class GamatatsukenPipeline:
    def __init__(self):
        self._selected_concept_index: int | None = None
        self._rejected: bool = False

    @workflow.signal
    async def select_concept(self, index: int) -> None:
        self._selected_concept_index = index

    @workflow.signal
    async def reject_all_concepts(self) -> None:
        self._rejected = True

    @workflow.query
    def get_status(self) -> str:
        if self._rejected:
            return "concepts_rejected"
        if self._selected_concept_index is not None:
            return f"concept_selected:{self._selected_concept_index}"
        return "awaiting_concept_selection"

    @workflow.run
    async def run(self, run_id: int, channel_id: int, auto_pick: bool = False,
                  privacy: str = "private") -> dict:
        concepts = await workflow.execute_activity(
            pick_gamatatsuken_concepts, args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        if auto_pick:
            concept = concepts[0]
            self._selected_concept_index = 1
        else:
            await workflow.execute_activity(
                store_pending_concepts, args=[run_id, channel_id, concepts],
                start_to_close_timeout=ACTIVITY_TIMEOUT)
            await workflow.execute_activity(
                mark_run_awaiting_approval, args=[run_id, "concept_review"],
                start_to_close_timeout=ACTIVITY_TIMEOUT)
            await workflow.wait_condition(
                lambda: self._selected_concept_index is not None or self._rejected)
            if self._rejected:
                return {"status": "rejected", "reason": "All concepts rejected by user"}
            idx = self._selected_concept_index - 1
            concept = concepts[idx] if 0 <= idx < len(concepts) else concepts[0]

        await workflow.execute_activity(
            store_gamatatsuken_concept, args=[run_id, channel_id, concept],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        # Generate detailed Sora prompts for selected concept
        concept = await workflow.execute_activity(
            generate_concept_detail,
            args=[run_id, channel_id, concept, "Gamatatsuken", "Narrated anime short films"],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        clips = await workflow.execute_activity(
            generate_gamatatsuken_clips, args=[run_id, channel_id, concept],
            start_to_close_timeout=SORA_TIMEOUT)

        prescreen = await workflow.execute_activity(
            prescreen_gamatatsuken_clips, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=REVIEW_TIMEOUT)

        clips = await workflow.execute_activity(
            retry_failed_clips,
            args=[run_id, channel_id, clips, prescreen, concept,
                  "packages.prompts.gamatatsuken"],
            start_to_close_timeout=SORA_TIMEOUT)

        rendered = await workflow.execute_activity(
            render_gamatatsuken_short, args=[run_id, channel_id, clips, concept],
            start_to_close_timeout=RENDER_TIMEOUT)

        qa = await workflow.execute_activity(
            gamatatsuken_qa_check, args=[run_id, channel_id, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        review = await workflow.execute_activity(
            review_gamatatsuken_video, args=[run_id, channel_id, rendered, concept],
            start_to_close_timeout=REVIEW_TIMEOUT)

        review_score = review.get("overall_score", 10) if review.get("reviewed") else 10

        # Mark as pending human review instead of auto-publishing
        description = concept.get("description", "")
        if "#Shorts" not in description:
            description += "\n\n#Shorts"
        publish_metadata = {
            "title": concept.get("title", ""),
            "description": description,
            "tags": concept.get("tags", []),
            "category": "Entertainment",
        }
        await workflow.execute_activity(
            mark_run_pending_review, args=[run_id, publish_metadata],
            start_to_close_timeout=ACTIVITY_TIMEOUT)

        return {
            "status": "pending_review",
            "video_path": rendered.get("path"),
            "topic": concept.get("title", ""),
            "review": review,
            "review_score": review_score,
            "qa": qa,
        }
