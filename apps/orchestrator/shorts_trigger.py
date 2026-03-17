"""Trigger a Shorts pipeline run. Creates a content_run and starts the Temporal workflow."""

import asyncio
import os

import structlog
from dotenv import load_dotenv
from sqlalchemy import text
from temporalio.client import Client

from apps.orchestrator.fake_data import FAKE_CHANNEL
from packages.clients.db import async_session

load_dotenv()
logger = structlog.get_logger()


async def main():
    # Ensure channel exists
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id FROM channels WHERE id = :id"),
            {"id": FAKE_CHANNEL.channel_id},
        )
        if not result.fetchone():
            import json
            await session.execute(
                text("INSERT INTO channels (id, name, niche, config) VALUES (:id, :name, :niche, :config)"),
                {
                    "id": FAKE_CHANNEL.channel_id,
                    "name": FAKE_CHANNEL.name,
                    "niche": FAKE_CHANNEL.niche,
                    "config": json.dumps(FAKE_CHANNEL.model_dump(mode="json")),
                },
            )
            await session.commit()

    # Create a content run (type = 'short')
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', 'short') RETURNING id"),
            {"cid": FAKE_CHANNEL.channel_id},
        )
        run_id = result.scalar_one()
        await session.commit()
        logger.info("shorts run created", run_id=run_id)

    # Start the Temporal workflow
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    client = await Client.connect(host, namespace=namespace)

    handle = await client.start_workflow(
        "ShortsPipeline",
        args=[run_id, FAKE_CHANNEL.channel_id],
        id=f"shorts-pipeline-run-{run_id}",
        task_queue="daily-content-pipeline",
    )

    logger.info("shorts workflow started", workflow_id=handle.id, run_id=run_id)

    # Wait for completion
    result = await handle.result()
    logger.info("shorts workflow completed", result=result)

    # Mark run as completed
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'completed', completed_at = NOW() WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    logger.info("shorts run complete", run_id=run_id)


if __name__ == "__main__":
    asyncio.run(main())
