"""YouTube metrics endpoints — disabled to conserve API quota.

Metrics can be checked directly on YouTube Studio.
"""

import json

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import ChannelMetrics, VideoMetrics

router = APIRouter(prefix="/api", tags=["metrics"])
logger = structlog.get_logger()


def _get_publish_info(publish_json: str | None) -> dict | None:
    """Parse publish_result asset JSON."""
    if not publish_json:
        return None
    try:
        info = json.loads(publish_json)
        if isinstance(info, dict) and info.get("video_id"):
            return info
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _get_channel_youtube_token(config_json: str | None) -> str | None:
    """Extract youtube_token_file from channel config."""
    if not config_json:
        return None
    try:
        config = json.loads(config_json)
        return config.get("youtube_token_file")
    except (json.JSONDecodeError, TypeError):
        return None


def _fetch_video_stats(video_id: str, youtube_token_file: str | None = None) -> dict:
    """Disabled — check YouTube Studio directly. Returns empty to conserve API quota."""
    return {}


@router.get("/metrics/{run_id}", response_model=VideoMetrics)
async def get_run_metrics(run_id: int):
    """Fetch real-time YouTube metrics for a published video."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT
                    a.content as publish_result,
                    c.config as channel_config
                    FROM assets a
                    JOIN content_runs cr ON cr.id = a.run_id
                    JOIN channels c ON c.id = cr.channel_id
                    WHERE a.run_id = :run_id AND a.asset_type = 'publish_result'
                    ORDER BY a.id DESC LIMIT 1"""),
            {"run_id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No publish result found for run {run_id}")

    publish_info = _get_publish_info(row[0])
    if not publish_info or not publish_info.get("video_id"):
        raise HTTPException(status_code=404, detail=f"No YouTube video ID found for run {run_id}")

    video_id = publish_info["video_id"]
    youtube_token_file = _get_channel_youtube_token(row[1])

    stats = _fetch_video_stats(video_id, youtube_token_file)

    return VideoMetrics(
        run_id=run_id,
        video_id=video_id,
        title=stats.get("title"),
        views=stats.get("views", 0),
        likes=stats.get("likes", 0),
        comments=stats.get("comments", 0),
        youtube_url=publish_info.get("url"),
        privacy=stats.get("privacy") or publish_info.get("privacy"),
        published_at=stats.get("published_at"),
    )


@router.get("/metrics/channel/{channel_id}", response_model=ChannelMetrics)
async def get_channel_metrics(channel_id: int):
    """Aggregate YouTube metrics for all published videos on a channel."""
    async with async_session() as session:
        # Get channel info
        ch_result = await session.execute(
            text("SELECT id, name, config FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        ch_row = ch_result.fetchone()
        if not ch_row:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

        channel_name = ch_row[1]
        youtube_token_file = _get_channel_youtube_token(ch_row[2])

        # Get all publish results for this channel
        pub_result = await session.execute(
            text("""SELECT a.run_id, a.content
                    FROM assets a
                    JOIN content_runs cr ON cr.id = a.run_id
                    WHERE cr.channel_id = :channel_id
                    AND a.asset_type = 'publish_result'
                    ORDER BY a.id DESC"""),
            {"channel_id": channel_id},
        )
        pub_rows = pub_result.fetchall()

    total_views = 0
    total_likes = 0
    total_comments = 0
    video_count = 0

    for pub_row in pub_rows:
        publish_info = _get_publish_info(pub_row[1])
        if not publish_info or not publish_info.get("video_id"):
            continue

        stats = _fetch_video_stats(publish_info["video_id"], youtube_token_file)
        if stats:
            total_views += stats.get("views", 0)
            total_likes += stats.get("likes", 0)
            total_comments += stats.get("comments", 0)
            video_count += 1

    avg_views = total_views / video_count if video_count > 0 else 0

    return ChannelMetrics(
        channel_id=channel_id,
        channel_name=channel_name,
        total_views=total_views,
        total_likes=total_likes,
        total_comments=total_comments,
        video_count=video_count,
        avg_views_per_video=round(avg_views, 1),
    )
