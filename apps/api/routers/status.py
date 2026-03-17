"""Dashboard / status endpoint — mirrors the CLI `status` command."""

import json
import os

from fastapi import APIRouter
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import (
    ChannelResponse,
    ChannelStats,
    DashboardResponse,
    RunSummary,
    SystemCheck,
)

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=DashboardResponse)
async def get_status():
    """Dashboard overview: running pipelines, recent runs, channel stats, system health."""
    async with async_session() as session:
        # Running pipelines
        running = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int as elapsed_seconds
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.status = 'running' ORDER BY cr.id""")
        )
        running_rows = running.fetchall()

        # Recent completed/published/failed (last 20)
        recent = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'rendered_video' ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.status IN ('completed', 'published', 'failed')
                    ORDER BY cr.id DESC LIMIT 20""")
        )
        recent_rows = recent.fetchall()

        # Channel stats
        stats = await session.execute(
            text("""SELECT c.id, c.name, c.niche, c.config,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'completed') as completed,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                    COUNT(cr.id) as total
                    FROM channels c
                    LEFT JOIN content_runs cr ON cr.channel_id = c.id
                    GROUP BY c.id, c.name, c.niche, c.config ORDER BY c.id""")
        )
        stats_rows = stats.fetchall()

    # Build running pipelines
    running_pipelines = []
    for row in running_rows:
        running_pipelines.append(
            RunSummary(
                id=row[0],
                channel_id=row[1],
                channel_name=row[2],
                content_type=row[3],
                status=row[4],
                current_step=row[5],
                started_at=row[6],
                completed_at=row[7],
                error=row[8],
                elapsed_seconds=row[9],
            )
        )

    # Build recent runs
    recent_runs = []
    for row in recent_rows:
        review_score = None
        review_rec = None
        video_path = None
        thumbnail_path = None
        youtube_url = None
        youtube_privacy = None

        if row[9]:
            try:
                review = json.loads(row[9])
                if review.get("reviewed"):
                    review_score = review.get("overall_score")
                    review_rec = review.get("publish_recommendation")
            except (json.JSONDecodeError, TypeError):
                pass

        if row[10]:
            try:
                video_info = json.loads(row[10])
                video_path = video_info.get("path")
            except (json.JSONDecodeError, TypeError):
                pass

        if row[11]:
            try:
                thumb_info = json.loads(row[11])
                thumbnail_path = thumb_info.get("path") if isinstance(thumb_info, dict) else thumb_info
            except (json.JSONDecodeError, TypeError):
                thumbnail_path = row[11] if isinstance(row[11], str) and row[11].endswith(".png") else None

        if row[12]:
            try:
                publish_info = json.loads(row[12])
                youtube_url = publish_info.get("url")
                youtube_privacy = publish_info.get("privacy")
            except (json.JSONDecodeError, TypeError):
                pass

        recent_runs.append(
            RunSummary(
                id=row[0],
                channel_id=row[1],
                channel_name=row[2],
                content_type=row[3],
                status=row[4],
                current_step=row[5],
                started_at=row[6],
                completed_at=row[7],
                error=row[8],
                review_score=review_score,
                review_recommendation=review_rec,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                youtube_url=youtube_url,
                youtube_privacy=youtube_privacy,
            )
        )

    # Build channel stats
    channel_stats = []
    for row in stats_rows:
        config = json.loads(row[3]) if row[3] else {}
        channel_stats.append(
            ChannelResponse(
                id=row[0],
                name=row[1],
                niche=row[2],
                pipeline=config.get("pipeline", "shorts"),
                description=config.get("description"),
                stats=ChannelStats(
                    published=row[4],
                    completed=row[5],
                    failed=row[6],
                    total=row[7],
                ),
            )
        )

    # System checks
    system_checks = [
        SystemCheck(name="Claude (Opus)", active=bool(os.getenv("ANTHROPIC_API_KEY"))),
        SystemCheck(name="Sora 2 Pro", active=bool(os.getenv("OPENAI_API_KEY"))),
        SystemCheck(name="Gemini 3 Pro", active=bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))),
        SystemCheck(name="ElevenLabs", active=bool(os.getenv("ELEVENLABS_API_KEY"))),
        SystemCheck(name="YouTube OAuth", active=os.path.exists("youtube_token.json")),
    ]

    return DashboardResponse(
        running_pipelines=running_pipelines,
        recent_runs=recent_runs,
        channel_stats=channel_stats,
        system_checks=system_checks,
    )
