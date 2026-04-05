"""Internal worker entry point — spawned by main.py's reload supervisor."""

import asyncio
import structlog
from dotenv import load_dotenv

load_dotenv()
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger()


async def run():
    from apps.worker.runner import run_generation_loop
    from apps.worker.scheduler import run_scheduler_loop
    from apps.worker.monitor import run_monitor_loop
    from apps.worker.cleanup import run_cleanup_loop
    from apps.worker.concept_generator import run_concept_replenish_loop

    logger.info("worker started (generation + scheduler + monitor + cleanup + concepts)")

    await asyncio.gather(
        run_generation_loop(),
        run_scheduler_loop(),
        run_monitor_loop(),
        run_cleanup_loop(),
        run_concept_replenish_loop(),
    )


if __name__ == "__main__":
    asyncio.run(run())
