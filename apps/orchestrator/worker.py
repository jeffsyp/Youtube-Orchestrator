"""Temporal worker entrypoint. Registers workflow and activities."""

import asyncio
import os
import signal

import structlog
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from apps.orchestrator.unified_activities import (
    generate_narrations,
    generate_sora_clips,
    mix_clip_audio,
    normalize_and_concat,
    generate_karaoke_subtitles,
    unified_qa_check,
    gemini_review,
    gemini_production_qa,
    auto_fix_subtitles,
    unified_mark_pending_review,
)
from apps.orchestrator.unified_workflow import UnifiedPipeline

load_dotenv()
logger = structlog.get_logger()

TASK_QUEUE = "daily-content-pipeline"
PID_FILE = "/tmp/youtube_worker.pid"


def _ensure_single_worker() -> None:
    """Ensure only one worker process runs at a time using a PID file.

    If a previous worker is still alive, kill it before proceeding.
    """
    my_pid = os.getpid()

    # Check if a previous worker is still running
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            if old_pid != my_pid:
                # Check if the old process is still alive
                os.kill(old_pid, 0)  # Signal 0 = check existence, don't kill
                logger.warning("killing previous worker", old_pid=old_pid)
                os.kill(old_pid, signal.SIGTERM)
                # Give it a moment to shut down
                import time
                time.sleep(2)
                # Force kill if still alive
                try:
                    os.kill(old_pid, 0)
                    logger.warning("force killing previous worker", old_pid=old_pid)
                    os.kill(old_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass  # Already dead
        except (ValueError, ProcessLookupError):
            pass  # PID file invalid or process already dead
        except PermissionError:
            logger.warning("cannot kill previous worker — permission denied", old_pid=old_pid)

    # Write our PID
    with open(PID_FILE, "w") as f:
        f.write(str(my_pid))
    logger.info("pid file written", pid=my_pid, path=PID_FILE)


def _cleanup_pid_file() -> None:
    """Remove PID file on shutdown."""
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                stored_pid = int(f.read().strip())
            if stored_pid == os.getpid():
                os.remove(PID_FILE)
    except (ValueError, OSError):
        pass


async def main():
    _ensure_single_worker()

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
        max_cached_workflows=0,
        build_id="unified-v1",
        use_worker_versioning=False,
        no_remote_activities=False,
        activity_executor=activity_executor,
        workflows=[UnifiedPipeline],
        activities=[
            generate_narrations,
            generate_sora_clips,
            mix_clip_audio,
            normalize_and_concat,
            generate_karaoke_subtitles,
            unified_qa_check,
            gemini_review,
            gemini_production_qa,
            auto_fix_subtitles,
            unified_mark_pending_review,
        ],
    )

    logger.info("worker started", task_queue=TASK_QUEUE)
    try:
        await worker.run()
    finally:
        _cleanup_pid_file()


if __name__ == "__main__":
    asyncio.run(main())
