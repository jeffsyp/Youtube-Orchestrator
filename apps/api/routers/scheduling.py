"""Scheduling endpoints — manage per-channel generation schedules."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session

router = APIRouter(prefix="/api", tags=["scheduling"])


@router.get("/schedules")
async def list_schedules():
    """List all channel schedules with queue stats."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT cs.channel_id, c.name, cs.videos_per_day, cs.time_windows,
                   cs.auto_upload, cs.upload_privacy, cs.paused, cs.timezone,
                   cs.voice_id, cs.updated_at,
                   (SELECT COUNT(*) FROM content_bank cb WHERE cb.channel_id = cs.channel_id AND cb.status = 'queued') as queue_depth,
                   (SELECT COUNT(*) FROM content_runs cr WHERE cr.channel_id = cs.channel_id AND cr.status IN ('pending_review', 'published') AND cr.started_at >= CURRENT_DATE) as today_count
            FROM channel_schedules cs
            JOIN channels c ON c.id = cs.channel_id
            ORDER BY c.name
        """))
        rows = result.fetchall()

    return [
        {
            "channel_id": r[0], "channel_name": r[1], "videos_per_day": r[2],
            "time_windows": json.loads(r[3]) if r[3] else [], "auto_upload": r[4],
            "upload_privacy": r[5], "paused": r[6], "timezone": r[7],
            "voice_id": r[8], "updated_at": r[9].isoformat() if r[9] else None,
            "queue_depth": r[10], "today_count": r[11],
        }
        for r in rows
    ]


@router.get("/schedules/{channel_id}")
async def get_schedule(channel_id: int):
    """Get schedule for a specific channel."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT cs.*, c.name,
                   (SELECT COUNT(*) FROM content_bank cb WHERE cb.channel_id = :cid AND cb.status = 'queued') as queue_depth,
                   (SELECT COUNT(*) FROM content_bank cb WHERE cb.channel_id = :cid AND cb.status IN ('generated', 'uploaded') AND cb.created_at >= CURRENT_DATE) as today_count
            FROM channel_schedules cs
            JOIN channels c ON c.id = cs.channel_id
            WHERE cs.channel_id = :cid
        """), {"cid": channel_id})
        row = result.fetchone()

    if not row:
        # Create default schedule
        async with async_session() as session:
            await session.execute(
                text("INSERT INTO channel_schedules (channel_id) VALUES (:cid) ON CONFLICT (channel_id) DO NOTHING"),
                {"cid": channel_id},
            )
            await session.commit()
        return {"channel_id": channel_id, "videos_per_day": 2, "paused": True, "queue_depth": 0, "today_count": 0}

    return {
        "channel_id": row[1], "channel_name": row[11],
        "videos_per_day": row[2], "time_windows": json.loads(row[3]) if row[3] else [],
        "auto_upload": row[4], "upload_privacy": row[5],
        "paused": row[6], "timezone": row[7], "voice_id": row[8],
        "queue_depth": row[12], "today_count": row[13],
    }


@router.put("/schedules/{channel_id}")
async def update_schedule(channel_id: int, config: dict):
    """Update schedule config for a channel. Creates if not exists."""
    time_windows = config.get("time_windows")
    if time_windows and isinstance(time_windows, list):
        time_windows = json.dumps(time_windows)

    async with async_session() as session:
        # Upsert
        await session.execute(text("""
            INSERT INTO channel_schedules (channel_id, videos_per_day, time_windows, auto_upload,
                upload_privacy, paused, timezone, voice_id, updated_at)
            VALUES (:cid, :vpd, :tw, :au, :up, :paused, :tz, :vid, NOW())
            ON CONFLICT (channel_id) DO UPDATE SET
                videos_per_day = COALESCE(:vpd, channel_schedules.videos_per_day),
                time_windows = COALESCE(:tw, channel_schedules.time_windows),
                auto_upload = COALESCE(:au, channel_schedules.auto_upload),
                upload_privacy = COALESCE(:up, channel_schedules.upload_privacy),
                paused = COALESCE(:paused, channel_schedules.paused),
                timezone = COALESCE(:tz, channel_schedules.timezone),
                voice_id = COALESCE(:vid, channel_schedules.voice_id),
                updated_at = NOW()
        """), {
            "cid": channel_id,
            "vpd": config.get("videos_per_day"),
            "tw": time_windows,
            "au": config.get("auto_upload"),
            "up": config.get("upload_privacy"),
            "paused": config.get("paused"),
            "tz": config.get("timezone"),
            "vid": config.get("voice_id"),
        })
        await session.commit()

    return {"channel_id": channel_id, "updated": True}


@router.post("/schedules/{channel_id}/pause")
async def pause_channel(channel_id: int):
    """Pause generation for a channel."""
    async with async_session() as session:
        await session.execute(
            text("UPDATE channel_schedules SET paused = true, updated_at = NOW() WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        await session.commit()
    return {"channel_id": channel_id, "paused": True}


@router.post("/schedules/{channel_id}/resume")
async def resume_channel(channel_id: int):
    """Resume generation for a channel."""
    async with async_session() as session:
        await session.execute(
            text("UPDATE channel_schedules SET paused = false, updated_at = NOW() WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        await session.commit()
    return {"channel_id": channel_id, "paused": False}
