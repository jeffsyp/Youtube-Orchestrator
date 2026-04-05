"""API routes for concept drafts — auto-generated concepts for review."""

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

router = APIRouter(prefix="/api", tags=["concept-drafts"])

db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
if "asyncpg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")


def async_session():
    engine = create_async_engine(db_url, pool_size=2, max_overflow=1)
    return AsyncSession(engine)


@router.get("/concept-drafts")
async def list_concept_drafts(status: str = "pending", channel_id: int | None = None, form_type: str = "short"):
    """List concept drafts, optionally filtered by channel and form type."""
    async with async_session() as s:
        params = {"status": status, "form_type": form_type}
        where = "cd.status = :status AND cd.form_type = :form_type"
        if channel_id:
            where += " AND cd.channel_id = :cid"
            params["cid"] = channel_id

        result = await s.execute(text(f"""
            SELECT cd.id, cd.channel_id, c.name as channel_name,
                   cd.title, cd.brief, cd.score, cd.status,
                   cd.concept_json, cd.created_at, cd.form_type
            FROM concept_drafts cd
            JOIN channels c ON c.id = cd.channel_id
            WHERE {where}
            ORDER BY cd.channel_id, cd.id DESC
        """), params)
        rows = result.fetchall()

    drafts = []
    for r in rows:
        try:
            concept = json.loads(r[7])
        except (json.JSONDecodeError, TypeError):
            concept = {}
        drafts.append({
            "id": r[0],
            "channel_id": r[1],
            "channel_name": r[2],
            "title": r[3],
            "brief": r[4],
            "score": r[5],
            "status": r[6],
            "concept": concept,
            "created_at": r[8].isoformat() if r[8] else None,
            "form_type": r[9] if len(r) > 9 else "short",
        })

    return drafts


@router.get("/concept-drafts/summary")
async def concept_drafts_summary():
    """Count pending drafts per active channel."""
    async with async_session() as s:
        result = await s.execute(text("""
            SELECT c.id, c.name,
                   COALESCE(SUM(CASE WHEN cd.status = 'pending' THEN 1 ELSE 0 END), 0) as pending,
                   COALESCE(SUM(CASE WHEN cd.status = 'approved' THEN 1 ELSE 0 END), 0) as approved,
                   COALESCE(SUM(CASE WHEN cd.status = 'rejected' THEN 1 ELSE 0 END), 0) as rejected
            FROM channels c
            JOIN channel_schedules cs ON cs.channel_id = c.id AND cs.paused = false
            LEFT JOIN concept_drafts cd ON cd.channel_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.name
        """))
        rows = result.fetchall()

    return [
        {"channel_id": r[0], "channel_name": r[1],
         "pending_count": r[2], "total_approved": r[3], "total_rejected": r[4]}
        for r in rows
    ]


@router.post("/concept-drafts/{draft_id}/approve")
async def approve_draft(draft_id: int, bg: BackgroundTasks):
    """Approve a draft — moves it to content_bank as queued."""
    async with async_session() as s:
        result = await s.execute(text(
            "SELECT channel_id, title, concept_json, status, form_type FROM concept_drafts WHERE id = :id"
        ), {"id": draft_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(404, "Draft not found")
    if row[3] != "pending":
        raise HTTPException(400, f"Draft is {row[3]}, not pending")

    channel_id, title, concept_json, form_type = row[0], row[1], row[2], row[4] or "short"

    async with async_session() as s:
        # Insert into content_bank
        cb = await s.execute(text("""
            INSERT INTO content_bank (channel_id, title, concept_json, status, priority, form_type)
            VALUES (:cid, :title, :cjson, 'queued', 50, :ft)
            RETURNING id
        """), {"cid": channel_id, "title": title, "cjson": concept_json, "ft": form_type})
        cb_id = cb.scalar()

        # Update draft status
        await s.execute(text("""
            UPDATE concept_drafts
            SET status = 'approved', resolved_at = :now, content_bank_id = :cbid
            WHERE id = :id
        """), {"id": draft_id, "now": datetime.now(timezone.utc), "cbid": cb_id})
        await s.commit()

    # Trigger replenishment in background
    bg.add_task(_replenish_channel, channel_id)

    return {"draft_id": draft_id, "content_bank_id": cb_id, "status": "approved"}


@router.post("/concept-drafts/{draft_id}/reject")
async def reject_draft(draft_id: int, bg: BackgroundTasks, reason: str = ""):
    """Reject a draft — marks it and triggers replacement."""
    async with async_session() as s:
        result = await s.execute(text(
            "SELECT channel_id, status FROM concept_drafts WHERE id = :id"
        ), {"id": draft_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(404, "Draft not found")
    if row[1] != "pending":
        raise HTTPException(400, f"Draft is {row[1]}, not pending")

    channel_id = row[0]

    async with async_session() as s:
        await s.execute(text("""
            UPDATE concept_drafts
            SET status = 'rejected', resolved_at = :now, rejection_reason = :reason
            WHERE id = :id
        """), {"id": draft_id, "now": datetime.now(timezone.utc), "reason": reason or None})
        await s.commit()

    # Trigger replenishment in background
    bg.add_task(_replenish_channel, channel_id)

    return {"draft_id": draft_id, "status": "rejected"}


@router.post("/concept-drafts/generate")
async def trigger_generation(channel_id: int, count: int = 5, form_type: str = "short"):
    """Manually trigger concept generation for a channel."""
    from apps.worker.concept_generator import generate_drafts_for_channel
    ids = await generate_drafts_for_channel(channel_id, count, form_type=form_type)
    return {"channel_id": channel_id, "generated": len(ids), "ids": ids, "form_type": form_type}


async def _replenish_channel(channel_id: int):
    """Background task: mark channel for replenishment. The worker loop handles actual generation."""
    # Don't generate here — it blocks the API event loop with synchronous Claude calls.
    # The worker's concept_replenish_loop will pick up the deficit within 2 minutes.
    import structlog
    structlog.get_logger().info("replenish scheduled (worker will handle)", channel_id=channel_id)
