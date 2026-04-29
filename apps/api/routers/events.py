"""Structured run-event APIs and a lightweight SSE stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from packages.clients.db import async_session

router = APIRouter(prefix="/api", tags=["events"])


def _decode(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


async def _fetch_events(after_id: int = 0, run_id: int | None = None, limit: int = 200):
    params: dict[str, object] = {"after_id": after_id, "limit": limit}
    where = ["re.id > :after_id"]
    if run_id is not None:
        where.append("re.run_id = :run_id")
        params["run_id"] = run_id

    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT re.id, re.run_id, re.ts, re.level, re.event_type, re.stage, re.message, re.data_json
                    FROM run_events re
                    WHERE {' AND '.join(where)}
                    ORDER BY re.id ASC
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).fetchall()
    return [
        {
            "id": row[0],
            "run_id": row[1],
            "ts": row[2].isoformat() if row[2] else None,
            "level": row[3],
            "event_type": row[4],
            "stage": row[5],
            "message": row[6],
            "data": _decode(row[7]),
        }
        for row in rows
    ]


@router.get("/runs/{run_id}/events")
async def list_run_events(run_id: int, after_id: int = Query(0), limit: int = Query(200, ge=1, le=1000)):
    return await _fetch_events(after_id=after_id, run_id=run_id, limit=limit)


@router.get("/events/stream")
async def stream_events(request: Request, run_id: int | None = Query(None), after_id: int = Query(0)):
    async def event_source():
        last_id = after_id
        while True:
            if await request.is_disconnected():
                break
            events = await _fetch_events(after_id=last_id, run_id=run_id, limit=200)
            if events:
                for event in events:
                    last_id = max(last_id, event["id"])
                    yield f"id: {event['id']}\n"
                    yield f"data: {json.dumps(event, ensure_ascii=True)}\n\n"
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
