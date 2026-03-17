"""Temporal worker entrypoint. Registers workflow and activities."""

import asyncio
import os

import structlog
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

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
from apps.orchestrator.lad_stories_activities import (
    generate_lad_stories_clips,
    lad_stories_qa_check,
    pick_lad_stories_concepts,
    prescreen_lad_stories_clips,
    publish_lad_stories_short,
    render_lad_stories_short,
    review_lad_stories_video,
    store_lad_stories_concept,
)
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
from apps.orchestrator.satisdefying_activities import (
    generate_satisdefying_clips,
    pick_satisdefying_concepts,
    prescreen_satisdefying_clips,
    publish_satisdefying_short,
    render_satisdefying_short,
    review_satisdefying_video,
    satisdefying_qa_check,
    store_satisdefying_concept,
)
from apps.orchestrator.whistle_room_activities import (
    analyze_whistle_room_play,
    download_whistle_room_clip,
    find_whistle_room_clips,
    publish_whistle_room_short,
    render_whistle_room_short,
    whistle_room_qa_check,
)
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
from apps.orchestrator.workflows import DailyContentPipeline
from apps.orchestrator.shorts_workflows import ShortsPipeline
from apps.orchestrator.synthzoo_workflows import SynthZooPipeline
from apps.orchestrator.lad_stories_workflows import LadStoriesPipeline
from apps.orchestrator.fundational_workflows import FundationalPipeline
from apps.orchestrator.satisdefying_workflows import SatisdefyingPipeline
from apps.orchestrator.whistle_room_workflows import WhistleRoomPipeline
from apps.orchestrator.yeah_thats_clean_workflows import YeahThatsCleanPipeline

load_dotenv()
logger = structlog.get_logger()

TASK_QUEUE = "daily-content-pipeline"


async def main():
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

    logger.info("connecting to temporal", host=host, namespace=namespace)
    client = await Client.connect(host, namespace=namespace)

    import concurrent.futures
    activity_executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        max_concurrent_activities=20,
        max_concurrent_workflow_tasks=10,
        activity_executor=activity_executor,
        workflows=[DailyContentPipeline, ShortsPipeline, SynthZooPipeline, SatisdefyingPipeline, FundationalPipeline, LadStoriesPipeline, WhistleRoomPipeline, YeahThatsCleanPipeline],
        activities=[
            # Long-form activities
            discover_candidates,
            score_breakouts,
            extract_templates,
            generate_variants,
            mark_run_awaiting_approval,
            build_outline,
            write_script,
            critique_script,
            revise_script,
            build_visual_plan,
            build_voice_plan,
            generate_voiceover,
            package_video,
            render_video,
            generate_thumbnail,
            qa_check,
            publish,
            # Shorts activities
            pick_shorts_topics,
            write_shorts_script,
            build_shorts_visual_plan,
            generate_shorts_srt,
            generate_shorts_voiceover,
            render_short,
            shorts_qa_check,
            review_shorts_video,
            publish_short,
            # Synth Zoo activities
            pick_synthzoo_concepts,
            store_synthzoo_concept,
            generate_synthzoo_clips,
            prescreen_synthzoo_clips,
            render_synthzoo_short,
            synthzoo_qa_check,
            review_synthzoo_video,
            publish_synthzoo_short,
            # Shared activities
            generate_concept_detail,
            retry_failed_clips,
            # Lad Stories activities
            pick_lad_stories_concepts,
            store_lad_stories_concept,
            generate_lad_stories_clips,
            prescreen_lad_stories_clips,
            render_lad_stories_short,
            lad_stories_qa_check,
            review_lad_stories_video,
            publish_lad_stories_short,
            # Fundational activities
            pick_fundational_concepts,
            store_fundational_concept,
            generate_fundational_clips,
            prescreen_fundational_clips,
            render_fundational_short,
            fundational_qa_check,
            review_fundational_video,
            publish_fundational_short,
            # Satisdefying activities
            pick_satisdefying_concepts,
            store_satisdefying_concept,
            generate_satisdefying_clips,
            prescreen_satisdefying_clips,
            render_satisdefying_short,
            satisdefying_qa_check,
            review_satisdefying_video,
            publish_satisdefying_short,
            # Whistle Room activities
            find_whistle_room_clips,
            download_whistle_room_clip,
            analyze_whistle_room_play,
            render_whistle_room_short,
            whistle_room_qa_check,
            publish_whistle_room_short,
            # Yeah Thats Clean activities
            pick_yeah_thats_clean_concepts,
            store_yeah_thats_clean_concept,
            generate_yeah_thats_clean_clips,
            prescreen_yeah_thats_clean_clips,
            render_yeah_thats_clean_short,
            yeah_thats_clean_qa_check,
            review_yeah_thats_clean_video,
            publish_yeah_thats_clean_short,
        ],
    )

    logger.info("worker started", task_queue=TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
