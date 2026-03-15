"""Temporal workflow for the daily content pipeline."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from apps.orchestrator.activities import (
        build_outline,
        build_visual_plan,
        build_voice_plan,
        critique_script,
        discover_candidates,
        extract_templates,
        generate_variants,
        generate_voiceover,
        generate_thumbnail,
        mark_run_awaiting_approval,
        package_video,
        publish,
        qa_check,
        render_video,
        revise_script,
        score_breakouts,
        write_script,
    )

ACTIVITY_TIMEOUT = timedelta(seconds=300)   # Research + simple activities
VOICE_TIMEOUT = timedelta(seconds=300)     # ElevenLabs voiceover
RENDER_TIMEOUT = timedelta(seconds=600)    # FFmpeg video rendering


@workflow.defn
class DailyContentPipeline:
    def __init__(self):
        self._selected_idea_index: int | None = None

    @workflow.signal
    async def select_idea(self, index: int) -> None:
        """Signal from human to select an idea by index (1-based)."""
        self._selected_idea_index = index

    @workflow.query
    def get_status(self) -> str:
        """Query the current workflow status."""
        if self._selected_idea_index is not None:
            return f"idea_selected:{self._selected_idea_index}"
        return "awaiting_idea_selection"

    @workflow.run
    async def run(self, run_id: int, channel_id: int) -> dict:
        # 1. Discover candidates
        candidates = await workflow.execute_activity(
            discover_candidates,
            args=[run_id, channel_id],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 2. Score breakouts
        scored = await workflow.execute_activity(
            score_breakouts,
            args=[run_id, channel_id, candidates],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 3. Extract templates
        templates = await workflow.execute_activity(
            extract_templates,
            args=[run_id, channel_id, scored],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 4. Generate variants
        ideas = await workflow.execute_activity(
            generate_variants,
            args=[run_id, channel_id, templates],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 5. HUMAN GATE: Wait for idea selection
        await workflow.execute_activity(
            mark_run_awaiting_approval,
            args=[run_id, "select_best_idea"],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # Block until human sends select_idea signal
        await workflow.wait_condition(lambda: self._selected_idea_index is not None)

        # Pick the selected idea (1-based index from human)
        idx = self._selected_idea_index - 1
        if 0 <= idx < len(ideas):
            idea = ideas[idx]
        else:
            idea = ideas[0]  # Fallback to first if invalid index

        # 6. Build outline
        outline = await workflow.execute_activity(
            build_outline,
            args=[run_id, channel_id, idea],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 7. Write script
        script = await workflow.execute_activity(
            write_script,
            args=[run_id, channel_id, outline],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 8. Critique script
        critique = await workflow.execute_activity(
            critique_script,
            args=[run_id, channel_id, script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 9. Revise script
        final_script = await workflow.execute_activity(
            revise_script,
            args=[run_id, channel_id, critique],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 10. Build visual plan
        visual = await workflow.execute_activity(
            build_visual_plan,
            args=[run_id, channel_id, final_script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 11. Build voice plan
        voice = await workflow.execute_activity(
            build_voice_plan,
            args=[run_id, channel_id, final_script],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 12. Generate voiceover audio
        voiceover = await workflow.execute_activity(
            generate_voiceover,
            args=[run_id, channel_id, final_script],
            start_to_close_timeout=VOICE_TIMEOUT,
        )

        # 13. Package video metadata
        package = await workflow.execute_activity(
            package_video,
            args=[run_id, channel_id, final_script, visual, voice],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 14. Render final video (stock footage + voiceover + text overlays → MP4)
        rendered = await workflow.execute_activity(
            render_video,
            args=[run_id, channel_id, visual, voiceover, package.get("srt_content"), final_script.get("content")],
            start_to_close_timeout=RENDER_TIMEOUT,
        )

        # 15. Generate thumbnail
        thumbnail = await workflow.execute_activity(
            generate_thumbnail,
            args=[run_id, channel_id, package],
            start_to_close_timeout=ACTIVITY_TIMEOUT,
        )

        # 16. QA check (package metadata + video quality)
        qa = await workflow.execute_activity(
            qa_check,
            args=[run_id, channel_id, package, rendered],
            start_to_close_timeout=timedelta(seconds=600),  # Video analysis takes time
        )

        # 17. Publish to YouTube (or mark as ready)
        result = await workflow.execute_activity(
            publish,
            args=[run_id, channel_id, package, qa, rendered, thumbnail],
            start_to_close_timeout=timedelta(seconds=600),  # Upload can be slow
        )

        result["video_path"] = rendered.get("path")
        result["thumbnail_path"] = thumbnail.get("path")
        return result
