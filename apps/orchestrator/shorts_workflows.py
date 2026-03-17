"""Temporal workflow for the YouTube Shorts pipeline (Signal Intel).

Pipeline: topics → select → write script → visual plan → voiceover → SRT →
render → QA → video review (Gemini) → publish (gated on review score >= 6)
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.shorts_activities import (
        build_shorts_visual_plan,
        generate_shorts_srt,
        generate_shorts_voiceover,
        pick_shorts_topics,
        publish_short,
        render_short,
        review_shorts_video,
        shorts_qa_check,
        write_shorts_script,
    )
    from apps.orchestrator.activities import mark_run_awaiting_approval

ACTIVITY_TIMEOUT = timedelta(seconds=900)
RENDER_TIMEOUT = timedelta(seconds=3600)
REVIEW_TIMEOUT = timedelta(seconds=600)
MIN_PUBLISH_SCORE = 8.5


@workflow.defn
class ShortsPipeline:
    def __init__(self):
        self._selected_topic_index: int | None = None

    @workflow.signal
    async def select_topic(self, index: int) -> None:
        self._selected_topic_index = index

    @workflow.query
    def get_status(self) -> str:
        if self._selected_topic_index is not None:
            return f"topic_selected:{self._selected_topic_index}"
        return "awaiting_topic_selection"

    @workflow.run
    async def run(self, run_id: int, channel_id: int, auto_pick: bool = False,
                  privacy: str = "private") -> dict:
        # 1. Pick topics
        topics = await workflow.execute_activity(
            pick_shorts_topics,
            args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 2. Topic selection
        if auto_pick:
            topic = topics[0]
            self._selected_topic_index = 1
        else:
            await workflow.execute_activity(
                mark_run_awaiting_approval,
                args=[run_id, "select_shorts_topic"],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
            )
            await workflow.wait_condition(lambda: self._selected_topic_index is not None)
            idx = self._selected_topic_index - 1
            topic = topics[idx] if 0 <= idx < len(topics) else topics[0]

        # 3. Write script
        script = await workflow.execute_activity(
            write_shorts_script,
            args=[run_id, channel_id, topic],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 4. Visual plan
        scenes = await workflow.execute_activity(
            build_shorts_visual_plan,
            args=[run_id, channel_id, script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 5. Voiceover
        voiceover = await workflow.execute_activity(
            generate_shorts_voiceover,
            args=[run_id, channel_id, script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 6. Generate SRT
        srt_content = await workflow.execute_activity(
            generate_shorts_srt,
            args=[run_id, script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 7. Render (SRT saved to disk inside the render activity)
        narration = script.get("script", "").replace("[CUT]", " ").strip()
        rendered = await workflow.execute_activity(
            render_short,
            args=[run_id, channel_id, scenes, voiceover, srt_content, narration],
            start_to_close_timeout=RENDER_TIMEOUT,
        )

        # 8. QA
        qa = await workflow.execute_activity(
            shorts_qa_check,
            args=[run_id, channel_id, rendered],
            start_to_close_timeout=timedelta(seconds=600),
        )

        # 9. Video review (Gemini)
        review = await workflow.execute_activity(
            review_shorts_video,
            args=[run_id, channel_id, rendered, script],
            start_to_close_timeout=REVIEW_TIMEOUT,
        )

        # 10. Publish — gated on review score
        review_score = review.get("overall_score", 0) if review.get("reviewed") else 10
        if review_score < MIN_PUBLISH_SCORE:
            return {
                "published": False,
                "reason": f"Review score {review_score} below minimum {MIN_PUBLISH_SCORE}",
                "video_path": rendered.get("path"),
                "topic": topic.get("topic", ""),
                "review": review,
            }

        if privacy != "private":
            script["_privacy_override"] = privacy
        result = await workflow.execute_activity(
            publish_short,
            args=[run_id, channel_id, script, qa, rendered],
            start_to_close_timeout=timedelta(seconds=600),
        )

        result["video_path"] = rendered.get("path")
        result["topic"] = topic.get("topic", "")
        result["review"] = review
        return result
