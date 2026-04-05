"""Content factory worker — runs generation and scheduling loops.

Start with: uv run python -m apps.worker.main

Auto-reloads on Python file changes (like uvicorn --reload).
"""

import asyncio
import os
import signal
import subprocess
import sys
import time

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

WATCH_DIRS = [
    "apps/worker",
    "apps/orchestrator",
    "packages/prompts",
    "packages/clients",
]
WATCH_INTERVAL = 3  # seconds


def _get_mtimes() -> dict[str, float]:
    """Get modification times of all .py files in watched directories."""
    mtimes = {}
    for d in WATCH_DIRS:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            if "__pycache__" in root:
                continue
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    try:
                        mtimes[path] = os.path.getmtime(path)
                    except OSError:
                        pass
    return mtimes


def run_with_reload():
    """Run the worker as a subprocess and restart on file changes."""
    logger.info("worker supervisor started (hot reload enabled)", dirs=WATCH_DIRS)

    while True:
        # Start worker subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "apps.worker._run"],
            cwd=os.getcwd(),
        )
        logger.info("worker process started", pid=proc.pid)

        # Watch for file changes
        mtimes = _get_mtimes()
        try:
            while proc.poll() is None:
                time.sleep(WATCH_INTERVAL)
                new_mtimes = _get_mtimes()
                changed = []
                for path, mtime in new_mtimes.items():
                    if mtimes.get(path) != mtime:
                        changed.append(path)
                for path in mtimes:
                    if path not in new_mtimes:
                        changed.append(path)

                if changed:
                    logger.info("file changes detected, reloading worker",
                                files=[os.path.basename(f) for f in changed[:5]])
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    break

                mtimes = new_mtimes
        except KeyboardInterrupt:
            logger.info("shutting down worker")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            sys.exit(0)

        if proc.returncode is not None and not changed:
            # Worker crashed without file changes
            logger.error("worker crashed", returncode=proc.returncode)
            logger.info("restarting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    run_with_reload()
