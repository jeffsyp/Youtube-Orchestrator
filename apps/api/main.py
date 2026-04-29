"""FastAPI backend for the YouTube Orchestrator dashboard.

Run with:
    uvicorn apps.api.main:app --port 8000
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from apps.api.routers import actions, channels, concept_drafts, concepts, content_bank, events, metrics, review_tasks, runs, scheduling, status, videos

logger = logging.getLogger("orchestrator.remediation")

app = FastAPI(
    title="YouTube Orchestrator API",
    version="2.0.0",
    description="Unified pipeline dashboard API",
)

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

# Include routers
app.include_router(status.router)
app.include_router(channels.router)
app.include_router(runs.router)
app.include_router(videos.router)
app.include_router(actions.router)
app.include_router(concepts.router)
app.include_router(concept_drafts.router)
app.include_router(content_bank.router)
app.include_router(review_tasks.router)
app.include_router(events.router)
app.include_router(scheduling.router)
app.include_router(metrics.router)

# Mount output/ directory for static file serving (images, etc.)
output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
output_dir = os.path.abspath(output_dir)
if os.path.isdir(output_dir):
    app.mount("/output", StaticFiles(directory=output_dir), name="output")


# ---------------------------------------------------------------------------
# Background auto-remediation task
# ---------------------------------------------------------------------------

async def _remediate_stalled_runs():
    """Periodically find and fix stuck pipeline runs."""
    from packages.clients.db import async_session
    from sqlalchemy import text

    while True:
        await asyncio.sleep(60)
        try:
            # --- Case 1: Sticky queue (step=NULL, >3 min) ---
            async with async_session() as session:
                result = await session.execute(
                    text(
                        "SELECT id, channel_id, content_type "
                        "FROM content_runs "
                        "WHERE status = 'running' "
                        "  AND current_step IS NULL "
                        "  AND started_at < NOW() - INTERVAL '3 minutes'"
                    )
                )
                stuck_null = result.fetchall()

            for row in stuck_null:
                run_id, channel_id, content_type = row[0], row[1], row[2]
                workflow_id = f"unified-pipeline-run-{run_id}"

                # Terminate the stuck workflow
                try:
                    client = await actions._get_temporal_client()
                    handle = client.get_workflow_handle(workflow_id)
                    await handle.terminate(reason="Auto-remediated: sticky queue")
                except Exception as e:
                    logger.warning("Could not terminate workflow %s: %s", workflow_id, e)

                # Mark as failed
                async with async_session() as session:
                    await session.execute(
                        text(
                            "UPDATE content_runs "
                            "SET status = 'failed', error = :err "
                            "WHERE id = :id"
                        ),
                        {"id": run_id, "err": "Auto-remediated: sticky queue"},
                    )
                    await session.commit()

                logger.info(
                    "Remediated sticky-queue run %d (channel=%d, workflow=%s)",
                    run_id, channel_id, workflow_id,
                )

            # Cases 2 & 3 (dead worker / Sora timeout) REMOVED
            # Direct pipeline handles its own timeouts and errors

        except Exception:
            logger.exception("Error in auto-remediation loop")


@app.on_event("startup")
async def start_remediation_task():
    asyncio.create_task(_remediate_stalled_runs())


@app.get("/api/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}


@app.get("/api/worker/status")
async def worker_status():
    """Check worker status via heartbeat file."""
    import json as _json
    import time as _time

    heartbeat_path = os.path.join(os.path.dirname(__file__), "..", "..", "output", "worker_heartbeat.json")
    if not os.path.exists(heartbeat_path):
        return {"status": "stopped", "pid": None, "started_at": None, "uptime_seconds": 0, "last_heartbeat": None}

    try:
        with open(heartbeat_path) as f:
            data = _json.load(f)

        last_beat = data.get("last_heartbeat", 0)
        stale = (_time.time() - last_beat) > 30  # no heartbeat in 30s = dead

        if stale:
            return {"status": "stopped", "pid": data.get("pid"), "started_at": data.get("started_at"), "uptime_seconds": 0, "last_heartbeat": last_beat}

        return {
            "status": "running",
            "pid": data.get("pid"),
            "started_at": data.get("started_at"),
            "uptime_seconds": data.get("uptime_seconds", 0),
            "last_heartbeat": last_beat,
        }
    except Exception:
        return {"status": "unknown", "pid": None, "started_at": None, "uptime_seconds": 0, "last_heartbeat": None}


@app.post("/api/worker/start")
async def worker_start():
    """Start the worker process."""
    import subprocess, sys

    # Check if already running
    try:
        import json as _json
        import time as _time
        heartbeat_path = os.path.join(os.path.dirname(__file__), "..", "..", "output", "worker_heartbeat.json")
        if os.path.exists(heartbeat_path):
            with open(heartbeat_path) as f:
                data = _json.load(f)
            if (_time.time() - data.get("last_heartbeat", 0)) < 30:
                return {"status": "already_running", "pid": data.get("pid")}
    except Exception:
        pass

    proc = subprocess.Popen(
        [sys.executable, "-m", "apps.worker.main"],
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"status": "started", "pid": proc.pid}


@app.post("/api/worker/stop")
async def worker_stop():
    """Stop the worker process."""
    import signal as _signal

    heartbeat_path = os.path.join(os.path.dirname(__file__), "..", "..", "output", "worker_heartbeat.json")
    if not os.path.exists(heartbeat_path):
        return {"status": "not_running"}

    try:
        import json as _json
        with open(heartbeat_path) as f:
            data = _json.load(f)
        pid = data.get("pid")
        if pid:
            # Kill the worker subprocess and its parent (supervisor)
            import psutil
            try:
                proc = psutil.Process(pid)
                parent = proc.parent()
                proc.kill()
                if parent and parent.name().startswith("python"):
                    parent.kill()
            except psutil.NoSuchProcess:
                pass
            # Clear heartbeat
            os.remove(heartbeat_path)
            return {"status": "stopped", "pid": pid}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200]}

    return {"status": "not_running"}
