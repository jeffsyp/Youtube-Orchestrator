"""Scheduler — decides when to generate and upload videos per channel."""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

SCHEDULE_INTERVAL = 300  # check every 5 minutes


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=2, max_overflow=1)


async def run_scheduler_loop():
    """Main scheduler loop — trigger generations and process uploads."""
    logger.info("scheduler started")

    while True:
        try:
            await _check_channels()
            await _process_scheduled_uploads()
        except Exception as e:
            logger.error("scheduler loop error", error=str(e)[:200])
        await asyncio.sleep(SCHEDULE_INTERVAL)


async def _check_channels():
    """For each non-paused channel, decide if we should queue a generation."""
    engine = _get_engine()
    try:
        async with AsyncSession(engine) as s:
            # Get all channel schedules
            result = await s.execute(text("""
                SELECT cs.channel_id, cs.videos_per_day, cs.time_windows, cs.paused, cs.timezone,
                       c.name as channel_name
                FROM channel_schedules cs
                JOIN channels c ON c.id = cs.channel_id
                WHERE cs.paused = false
            """))
            schedules = result.fetchall()

        for row in schedules:
            channel_id, videos_per_day, time_windows_json, paused, timezone, channel_name = row
            try:
                await _check_channel(engine, channel_id, channel_name, videos_per_day, time_windows_json, timezone)
            except Exception as e:
                logger.error("channel check error", channel=channel_name, error=str(e)[:200])

    finally:
        await engine.dispose()


async def _check_channel(engine, channel_id: int, channel_name: str,
                          videos_per_day: int, time_windows_json: str, timezone: str):
    """Check if a channel needs a new video generated."""
    import pytz

    tz = pytz.timezone(timezone)
    now = datetime.now(tz)

    # Parse time windows
    try:
        windows = json.loads(time_windows_json)
    except (json.JSONDecodeError, TypeError):
        windows = [{"start": "09:00", "end": "21:00"}]

    # Check if we're in a time window
    in_window = False
    for window in windows:
        start_h, start_m = map(int, window["start"].split(":"))
        end_h, end_m = map(int, window["end"].split(":"))
        start_time = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end_time = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        if start_time <= now <= end_time:
            in_window = True
            break

    if not in_window:
        return

    async with AsyncSession(engine) as s:
        # Count videos generated today for this channel
        result = await s.execute(text("""
            SELECT COUNT(*) FROM content_bank
            WHERE channel_id = :cid
            AND status IN ('generating', 'generated', 'uploaded')
            AND created_at >= CURRENT_DATE
        """), {"cid": channel_id})
        today_count = result.scalar()

        if today_count >= videos_per_day:
            return  # already hit daily limit

        # Check if there's already something queued with high priority (already triggered)
        result = await s.execute(text("""
            SELECT COUNT(*) FROM content_bank
            WHERE channel_id = :cid AND status IN ('queued', 'locked', 'generating') AND priority <= 10
        """), {"cid": channel_id})
        already_triggered = result.scalar()

        if already_triggered > 0:
            return  # already have something in progress or about to start

        # Check if there are queued items available
        result = await s.execute(text("""
            SELECT id, title FROM content_bank
            WHERE channel_id = :cid AND status = 'queued'
            ORDER BY priority ASC, created_at ASC
            LIMIT 1
        """), {"cid": channel_id})
        next_item = result.fetchone()

        if not next_item:
            return  # queue is empty

        # Trigger it by setting priority to 0
        await s.execute(text("""
            UPDATE content_bank SET priority = 0 WHERE id = :id
        """), {"id": next_item[0]})
        await s.commit()

        logger.info("scheduler triggered generation",
                    channel=channel_name, bank_id=next_item[0], title=next_item[1],
                    today_count=today_count, target=videos_per_day)


async def _process_scheduled_uploads():
    """Process pending scheduled uploads (upload or make public)."""
    engine = _get_engine()
    try:
        async with AsyncSession(engine) as s:
            result = await s.execute(text("""
                SELECT su.id, su.run_id, su.channel_id, su.action, su.youtube_video_id,
                       c.name as channel_name
                FROM scheduled_uploads su
                JOIN channels c ON c.id = su.channel_id
                WHERE su.status = 'pending' AND su.scheduled_at <= NOW()
                ORDER BY su.scheduled_at ASC
                LIMIT 5
            """))
            pending = result.fetchall()

        for row in pending:
            su_id, run_id, channel_id, action, youtube_video_id, channel_name = row
            try:
                if action == "make_public" and youtube_video_id:
                    await _make_video_public(engine, su_id, youtube_video_id, channel_name)
                elif action == "upload":
                    await _upload_video(engine, su_id, run_id, channel_id, channel_name)
            except Exception as e:
                logger.error("scheduled upload error", su_id=su_id, error=str(e)[:200])
                async with AsyncSession(engine) as s:
                    await s.execute(text("""
                        UPDATE scheduled_uploads SET status = 'failed', error = :err WHERE id = :id
                    """), {"id": su_id, "err": str(e)[:500]})
                    await s.commit()

    finally:
        await engine.dispose()


async def _make_video_public(engine, su_id: int, video_id: str, channel_name: str):
    """Switch a YouTube video from private/unlisted to public."""
    token_name = channel_name.lower().replace(" ", "").replace("'", "").replace("'", "")
    token_file = f"youtube_token_{token_name}.json"

    if not os.path.exists(token_file):
        raise FileNotFoundError(f"Token file not found: {token_file}")

    from apps.publishing_service.uploader import update_video_privacy
    update_video_privacy(video_id, "public", token_file)

    async with AsyncSession(engine) as s:
        await s.execute(text("""
            UPDATE scheduled_uploads SET status = 'completed', completed_at = NOW() WHERE id = :id
        """), {"id": su_id})
        await s.commit()

    logger.info("video made public", video_id=video_id, channel=channel_name)


async def _upload_video(engine, su_id: int, run_id: int, channel_id: int, channel_name: str):
    """Upload a video that was scheduled for later upload."""
    # This delegates to the same auto-upload logic in runner.py
    from apps.worker.runner import _maybe_auto_upload

    async with AsyncSession(engine) as s:
        # Get concept from content_bank or assets
        result = await s.execute(text("""
            SELECT content FROM assets WHERE run_id = :rid AND asset_type = 'publish_metadata' LIMIT 1
        """), {"rid": run_id})
        row = result.fetchone()
        concept = json.loads(row[0]) if row else {}

    await _maybe_auto_upload(engine, run_id, channel_id, concept)

    async with AsyncSession(engine) as s:
        await s.execute(text("""
            UPDATE scheduled_uploads SET status = 'completed', completed_at = NOW() WHERE id = :id
        """), {"id": su_id})
        await s.commit()
