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

# Steps that involve Sora clip generation — these are expected to be slow
_SORA_STEPS = frozenset({
    "generate_clips", "generate_sora_clips",
    "retry_failed_clips",
})

# Stall thresholds in seconds
_SORA_STALL_SECONDS = 20 * 60   # 20 minutes for Sora steps
_DEFAULT_STALL_SECONDS = 30 * 60  # 30 minutes for everything else


def _is_stalled(status: str, current_step: str | None, elapsed_seconds: int | None) -> bool:
    """Return True if a running pipeline looks stalled."""
    if status != "running" or elapsed_seconds is None:
        return False
    threshold = _SORA_STALL_SECONDS if current_step in _SORA_STEPS else _DEFAULT_STALL_SECONDS
    return elapsed_seconds > threshold


router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=DashboardResponse)
async def get_status():
    """Dashboard overview: running pipelines, recent runs, channel stats, system health."""
    async with async_session() as session:
        # Running pipelines
        running = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int as elapsed_seconds,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1) as metadata_asset
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.status = 'running' ORDER BY cr.id""")
        )
        running_rows = running.fetchall()

        # Recent runs — last 48 hours only
        recent = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name as channel_name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review,
                    (SELECT content FROM assets WHERE run_id = cr.id AND (asset_type = 'rendered_video' OR asset_type LIKE 'rendered_%') ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1) as metadata_asset
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.started_at > NOW() - INTERVAL '48 hours'
                    AND cr.status IN ('completed', 'published', 'failed', 'pending_review', 'rejected')
                    ORDER BY cr.id DESC
                    LIMIT 50""")
        )
        recent_rows = recent.fetchall()

        # Channel stats — last 48 hours only
        stats = await session.execute(
            text("""SELECT c.id, c.name, c.niche, c.config,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'pending_review') as pending_review,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                    COUNT(cr.id) as total
                    FROM channels c
                    LEFT JOIN content_runs cr ON cr.channel_id = c.id AND cr.started_at > NOW() - INTERVAL '48 hours'
                    GROUP BY c.id, c.name, c.niche, c.config ORDER BY c.id""")
        )
        stats_rows = stats.fetchall()

    # Build running pipelines
    running_pipelines = []
    for row in running_rows:
        title = None
        if row[10]:
            try:
                metadata = json.loads(row[10])
                title = metadata.get("title") if isinstance(metadata, dict) else None
            except (json.JSONDecodeError, TypeError):
                pass

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
                title=title,
                elapsed_seconds=row[9],
                stalled=_is_stalled(row[4], row[5], row[9]),
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
        title = None

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

        if row[13]:
            try:
                metadata = json.loads(row[13])
                title = metadata.get("title") if isinstance(metadata, dict) else None
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
                title=title,
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
                    published=row[5],
                    completed=row[4],  # pending_review as "ready"
                    failed=row[6],
                    total=row[7],
                ),
            )
        )

    # Today's stats (UTC day)
    async with async_session() as session:
        today = await session.execute(
            text("""SELECT
                COUNT(*) FILTER (WHERE cr.status = 'published') as published,
                COUNT(*) FILTER (WHERE cr.status = 'pending_review') as ready,
                COUNT(*) FILTER (WHERE cr.status = 'running') as generating,
                COUNT(*) FILTER (WHERE cr.status = 'failed') as failed,
                COUNT(*) as total,
                COUNT(DISTINCT cr.channel_id) as channels_active
                FROM content_runs cr
                WHERE cr.started_at >= CURRENT_DATE
            """)
        )
        today_row = today.fetchone()

        today_by_channel = await session.execute(
            text("""SELECT c.name, c.id,
                COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                COUNT(cr.id) FILTER (WHERE cr.status = 'pending_review') as ready,
                COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                COUNT(cr.id) as total
                FROM channels c
                JOIN channel_schedules cs ON cs.channel_id = c.id AND cs.paused = false
                LEFT JOIN content_runs cr ON cr.channel_id = c.id AND cr.started_at >= CURRENT_DATE
                GROUP BY c.name, c.id
                ORDER BY COUNT(cr.id) DESC, c.name
            """)
        )
        today_channels = today_by_channel.fetchall()

        today_uploads = await session.execute(
            text("""SELECT c.name, a.content
                FROM assets a
                JOIN content_runs cr ON cr.id = a.run_id
                JOIN channels c ON c.id = cr.channel_id
                WHERE a.asset_type = 'publish_result'
                AND a.id IN (SELECT id FROM assets WHERE created_at >= CURRENT_DATE OR id > (SELECT COALESCE(MAX(id) - 200, 0) FROM assets))
                AND cr.started_at >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY a.id DESC
                LIMIT 30
            """)
        )
        today_upload_rows = today_uploads.fetchall()

    today_stats = {
        "published": today_row[0] or 0,
        "ready": today_row[1] or 0,
        "generating": today_row[2] or 0,
        "failed": today_row[3] or 0,
        "total": today_row[4] or 0,
        "channels_active": today_row[5] or 0,
        "by_channel": [
            {"name": r[0], "id": r[1], "published": r[2], "ready": r[3], "failed": r[4], "total": r[5]}
            for r in today_channels
        ],
        "uploads": [
            {"channel": r[0], **(json.loads(r[1]) if r[1] else {})}
            for r in today_upload_rows
        ],
    }

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
        today_stats=today_stats,
    )


@router.get("/api-usage")
async def get_api_usage():
    """Get API usage stats from the usage tracker file."""
    import json
    usage_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "api_usage.json")
    if os.path.exists(usage_file):
        with open(usage_file) as f:
            return json.load(f)
    return {"session_totals": {}, "per_run": {}, "updated": None}
