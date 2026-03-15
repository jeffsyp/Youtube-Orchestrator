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
from apps.orchestrator.workflows import DailyContentPipeline

load_dotenv()
logger = structlog.get_logger()

TASK_QUEUE = "daily-content-pipeline"


async def main():
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")

    logger.info("connecting to temporal", host=host, namespace=namespace)
    client = await Client.connect(host, namespace=namespace)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[DailyContentPipeline],
        activities=[
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
        ],
    )

    logger.info("worker started", task_queue=TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
