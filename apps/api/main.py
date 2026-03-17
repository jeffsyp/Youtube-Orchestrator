"""FastAPI backend for the YouTube Orchestrator dashboard.

Run with:
    uvicorn apps.api.main:app --port 8000
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from apps.api.routers import actions, channels, metrics, runs, status, videos

app = FastAPI(
    title="YouTube Orchestrator API",
    version="0.1.0",
    description="Dashboard API for YouTube content pipeline management",
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
)

# Include routers
app.include_router(status.router)
app.include_router(channels.router)
app.include_router(runs.router)
app.include_router(videos.router)
app.include_router(actions.router)
app.include_router(metrics.router)

# Mount output/ directory for static file serving (images, etc.)
output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "output")
output_dir = os.path.abspath(output_dir)
if os.path.isdir(output_dir):
    app.mount("/output", StaticFiles(directory=output_dir), name="output")


@app.get("/api/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}
