"""Internal worker entry point — spawned by main.py's reload supervisor."""

import asyncio
import json
import os
import time
import structlog
from dotenv import load_dotenv

load_dotenv(override=True)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger()

HEARTBEAT_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "output", "worker_heartbeat.json")


def _start_heartbeat_thread():
    """Start a heartbeat writer in a separate thread — keeps ticking even if the event loop blocks."""
    import threading

    os.makedirs(os.path.dirname(HEARTBEAT_FILE), exist_ok=True)
    start_time = time.time()

    def _writer():
        while True:
            try:
                data = {
                    "pid": os.getpid(),
                    "started_at": start_time,
                    "last_heartbeat": time.time(),
                    "uptime_seconds": int(time.time() - start_time),
                    "status": "running",
                }
                with open(HEARTBEAT_FILE, "w") as f:
                    json.dump(data, f)
            except Exception:
                pass
            time.sleep(10)

    t = threading.Thread(target=_writer, daemon=True)
    t.start()
    return t


async def run():
    from apps.worker.runner import run_generation_loop
    from apps.worker.scheduler import run_scheduler_loop
    from apps.worker.monitor import run_monitor_loop
    from apps.worker.cleanup import run_cleanup_loop
    from apps.worker.concept_generator import run_concept_replenish_loop

    logger.info("worker started (generation + scheduler + monitor + cleanup + concepts)")

    # Heartbeat runs in a separate thread so it keeps ticking even if event loop blocks
    _start_heartbeat_thread()

    # Thread pool for concept generation (sync Claude calls) and other helpers
    # Needs enough slots so concept gen doesn't starve subprocess management
    import concurrent.futures
    loop = asyncio.get_event_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=32))

    await asyncio.gather(
        run_generation_loop(),
        run_scheduler_loop(),
        run_monitor_loop(),
        run_cleanup_loop(),
        run_concept_replenish_loop(),
    )


LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "..", "output", "worker.lock")


def _acquire_lock():
    """Kill any existing worker and acquire the lock."""
    os.makedirs(os.path.dirname(LOCKFILE), exist_ok=True)
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE) as f:
                old_pid = int(f.read().strip())
            # Check if old process is still running
            os.kill(old_pid, 0)
            # It's alive — kill it
            logger.warning("killing stale worker", pid=old_pid)
            import signal
            os.kill(old_pid, signal.SIGKILL)
            time.sleep(1)
        except (ProcessLookupError, ValueError, PermissionError):
            pass  # Old process already dead
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))
    import atexit
    atexit.register(lambda: os.remove(LOCKFILE) if os.path.exists(LOCKFILE) else None)


if __name__ == "__main__":
    _acquire_lock()
    asyncio.run(run())
