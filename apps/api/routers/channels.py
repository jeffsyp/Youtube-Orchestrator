"""Channel endpoints."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import ChannelResponse, ChannelStats

router = APIRouter(prefix="/api", tags=["channels"])


@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels():
    """List all channels with their run stats."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT c.id, c.name, c.niche, c.config,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'completed') as completed,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                    COUNT(cr.id) as total
                    FROM channels c
                    LEFT JOIN content_runs cr ON cr.channel_id = c.id
                    GROUP BY c.id, c.name, c.niche, c.config ORDER BY c.id""")
        )
        rows = result.fetchall()

    channels = []
    for row in rows:
        config = json.loads(row[3]) if row[3] else {}
        channels.append(
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
    return channels


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int):
    """Get a single channel with stats."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT c.id, c.name, c.niche, c.config,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'completed') as completed,
                    COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                    COUNT(cr.id) as total
                    FROM channels c
                    LEFT JOIN content_runs cr ON cr.channel_id = c.id
                    WHERE c.id = :id
                    GROUP BY c.id, c.name, c.niche, c.config"""),
            {"id": channel_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    config = json.loads(row[3]) if row[3] else {}
    return ChannelResponse(
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
