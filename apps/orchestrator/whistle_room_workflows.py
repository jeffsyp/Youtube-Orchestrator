"""Temporal workflow for the Whistle Room pipeline.

7-step workflow — real clips with transformative editorial commentary:
1. Find viral clips → 2. [Human gate or auto-pick] → 3. Download clip →
4. Analyze play (Claude vision) → 5. Render → 6. QA → 7. Publish

Supports auto mode: pass auto_pick=True to skip the human gate
and automatically select the highest-scored clip.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.whistle_room_activities import (
        analyze_whistle_room_play,
        download_whistle_room_clip,
        find_whistle_room_clips,
        publish_whistle_room_short,
        render_whistle_room_short,
        whistle_room_qa_check,
    )
    from apps.orchestrator.activities import mark_run_awaiting_approval

ACTIVITY_TIMEOUT = timedelta(seconds=300)
DOWNLOAD_TIMEOUT = timedelta(seconds=600)
RENDER_TIMEOUT = timedelta(seconds=600)


@workflow.defn
class WhistleRoomPipeline:
    def __init__(self):
        self._selected_clip_index: int | None = None

    @workflow.signal
    async def select_clip(self, index: int) -> None:
        """Signal from human to select a clip by index (1-based)."""
        self._selected_clip_index = index

    @workflow.query
    def get_status(self) -> str:
        if self._selected_clip_index is not None:
            return f"clip_selected:{self._selected_clip_index}"
        return "awaiting_clip_selection"

    @workflow.run
    async def run(self, run_id: int, channel_id: int, auto_pick: bool = False,
                  privacy: str = "private") -> dict:
        # 1. Find viral clips
        clips = await workflow.execute_activity(
            find_whistle_room_clips,
            args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 2. Clip selection — auto or human gate
        if auto_pick:
            clip = clips[0]
            self._selected_clip_index = 1
        else:
            await workflow.execute_activity(
                mark_run_awaiting_approval,
                args=[run_id, "select_whistle_room_clip"],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
            )
            await workflow.wait_condition(lambda: self._selected_clip_index is not None)

            idx = self._selected_clip_index - 1
            clip = clips[idx] if 0 <= idx < len(clips) else clips[0]

        # 3. Download clip
        clip_info = await workflow.execute_activity(
            download_whistle_room_clip,
            args=[run_id, channel_id, clip],
            start_to_close_timeout=DOWNLOAD_TIMEOUT,
        )

        # Attach metadata for analysis
        clip_meta = {
            "title": clip.get("title", ""),
            "sport": clip.get("sport", "general"),
            "duration": clip_info.get("duration", 0),
            "source_url": clip_info.get("source_url", ""),
        }

        # 4. Analyze play (Claude vision on keyframes)
        analysis = await workflow.execute_activity(
            analyze_whistle_room_play,
            args=[run_id, channel_id, clip_info["path"], clip_meta],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 5. Render
        rendered = await workflow.execute_activity(
            render_whistle_room_short,
            args=[run_id, channel_id, clip_info["path"], analysis],
            start_to_close_timeout=RENDER_TIMEOUT,
        )

        # 6. QA
        qa = await workflow.execute_activity(
            whistle_room_qa_check,
            args=[run_id, channel_id, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 7. Publish
        if privacy != "private":
            analysis["_privacy_override"] = privacy
        result = await workflow.execute_activity(
            publish_whistle_room_short,
            args=[run_id, channel_id, analysis, qa, rendered],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        result["video_path"] = rendered.get("path")
        result["topic"] = clip.get("title", "")
        result["score"] = analysis.get("score")
        result["tier"] = analysis.get("tier")
        return result
