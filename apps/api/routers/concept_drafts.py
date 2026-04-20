"""API routes for concept drafts — auto-generated concepts for review."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session
from packages.clients.workflow_state import ensure_concept, update_concept_status
from packages.utils.game_meme_identity import normalize_game_meme_concept
from packages.utils.hardcore_ranked_language import normalize_hardcore_ranked_concept, normalize_hardcore_ranked_viewer_text

router = APIRouter(prefix="/api", tags=["concept-drafts"])


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
    """Count pending drafts per active channel + videos posted in last 24h."""
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

        # Get videos completed in last 24h per channel + form type
        recent = await s.execute(text("""
            SELECT cr.channel_id,
                   CASE WHEN cb.form_type = 'long' THEN 'long' ELSE 'short' END as form,
                   COUNT(*) as cnt
            FROM content_runs cr
            JOIN content_bank cb ON cb.run_id = cr.id
            WHERE cr.status IN ('pending_review', 'published', 'uploaded')
              AND cr.started_at > NOW() - INTERVAL '24 hours'
            GROUP BY cr.channel_id, form
        """))
        recent_rows = recent.fetchall()

    recent_map = {}
    for r in recent_rows:
        cid = r[0]
        if cid not in recent_map:
            recent_map[cid] = {"short": 0, "long": 0}
        recent_map[cid][r[1]] = r[2]

    return [
        {"channel_id": r[0], "channel_name": r[1],
         "pending_count": r[2], "total_approved": r[3], "total_rejected": r[4],
         "posted_24h_short": recent_map.get(r[0], {}).get("short", 0),
         "posted_24h_long": recent_map.get(r[0], {}).get("long", 0)}
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
    try:
        concept = json.loads(concept_json) if isinstance(concept_json, str) else (concept_json or {})
    except Exception:
        concept = {}
    concept = normalize_hardcore_ranked_concept(concept, channel_id=channel_id)
    concept = normalize_game_meme_concept(concept, channel_id=channel_id)
    title = normalize_hardcore_ranked_viewer_text(concept.get("title") or title)
    concept_json = json.dumps(concept)

    async with async_session() as s:
        concept_id = await ensure_concept(
            channel_id=channel_id,
            title=title,
            concept_json=concept_json,
            origin="auto",
            status="queued",
            form_type=form_type,
            draft_id=draft_id,
            session=s,
        )
        # Insert into content_bank
        cb = await s.execute(text("""
            INSERT INTO content_bank (channel_id, title, concept_json, status, priority, form_type, concept_id)
            VALUES (:cid, :title, :cjson, 'queued', 50, :ft, :concept_id)
            RETURNING id
        """), {"cid": channel_id, "title": title, "cjson": concept_json, "ft": form_type, "concept_id": concept_id})
        cb_id = cb.scalar()

        # Update draft status
        await s.execute(text("""
            UPDATE concept_drafts
            SET status = 'approved', resolved_at = :now, content_bank_id = :cbid
            WHERE id = :id
        """), {"id": draft_id, "now": datetime.now(timezone.utc), "cbid": cb_id})
        await s.execute(
            text("UPDATE concepts SET updated_at = NOW() WHERE id = :id"),
            {"id": concept_id},
        )
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
        concept_id = (
            await s.execute(text("SELECT concept_id FROM concept_drafts WHERE id = :id"), {"id": draft_id})
        ).scalar_one_or_none()
        await s.execute(text("""
            UPDATE concept_drafts
            SET status = 'rejected', resolved_at = :now, rejection_reason = :reason
            WHERE id = :id
        """), {"id": draft_id, "now": datetime.now(timezone.utc), "reason": reason or None})
        if concept_id:
            await update_concept_status(concept_id, status="rejected", session=s)
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
