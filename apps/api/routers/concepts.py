"""Canonical concept endpoints backed by the concepts table."""

from __future__ import annotations

import copy
import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from packages.clients.db import async_session
from packages.clients.workflow_state import ensure_concept, update_concept_status
from packages.utils.concept_formats import apply_format_strategy_defaults
from packages.utils.game_meme_identity import normalize_game_meme_concept
from packages.utils.hardcore_ranked_language import normalize_hardcore_ranked_concept, normalize_hardcore_ranked_viewer_text

router = APIRouter(prefix="/api", tags=["concepts"])


def _decode_concept(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _normalize_concept_payload(raw_concept, *, channel_id: int, title: str, form_type: str) -> dict:
    concept = _decode_concept(copy.deepcopy(raw_concept))
    if not isinstance(concept, dict):
        concept = {}
    concept = apply_format_strategy_defaults(concept, form_type=form_type)
    concept.setdefault("channel_id", channel_id)
    concept.setdefault("title", title)
    concept.setdefault("form_type", form_type)
    concept = normalize_hardcore_ranked_concept(concept, channel_id=channel_id)
    concept = normalize_game_meme_concept(concept, channel_id=channel_id)
    concept["title"] = normalize_hardcore_ranked_viewer_text(concept.get("title") or title)
    return concept


def _serialize_concept_row(row) -> dict:
    return {
        "id": row[0],
        "channel_id": row[1],
        "channel_name": row[2],
        "origin": row[3],
        "status": row[4],
        "form_type": row[5],
        "title": row[6],
        "concept": _decode_concept(row[7]),
        "notes": row[8],
        "priority": row[9],
        "latest_run_id": row[10],
        "published_run_id": row[11],
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }


@router.get("/concepts")
async def list_concepts(
    status: str | None = Query(None),
    channel_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    conditions = []
    params: dict[str, object] = {"limit": limit}
    if status and status != "all":
        conditions.append("co.status = :status")
        params["status"] = status
    if channel_id is not None:
        conditions.append("co.channel_id = :channel_id")
        params["channel_id"] = channel_id

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT co.id, co.channel_id, ch.name, co.origin, co.status, co.form_type,
                           co.title, co.concept_json, co.notes, co.priority,
                           co.latest_run_id, co.published_run_id, co.created_at, co.updated_at
                    FROM concepts co
                    JOIN channels ch ON ch.id = co.channel_id
                    {where}
                    ORDER BY co.priority ASC, co.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).fetchall()
    return [_serialize_concept_row(row) for row in rows]


@router.get("/concepts/{concept_id}")
async def get_concept(concept_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT co.id, co.channel_id, ch.name, co.origin, co.status, co.form_type,
                           co.title, co.concept_json, co.notes, co.priority,
                           co.latest_run_id, co.published_run_id, co.created_at, co.updated_at
                    FROM concepts co
                    JOIN channels ch ON ch.id = co.channel_id
                    WHERE co.id = :id
                    """
                ),
                {"id": concept_id},
            )
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Concept not found")
    return _serialize_concept_row(row)


@router.post("/concepts")
async def create_concept(payload: dict):
    channel_id = payload.get("channel_id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id required")

    concept = payload.get("concept") or payload.get("concept_json") or payload
    title = payload.get("title") or concept.get("title") or "Untitled"
    form_type = payload.get("form_type") or concept.get("form_type") or ("long" if concept.get("long_form") else "short")
    origin = payload.get("origin", "manual")
    status = payload.get("status", "draft")
    priority = int(payload.get("priority", 100))
    notes = payload.get("notes")
    queue_immediately = bool(payload.get("queue_immediately"))
    concept = _normalize_concept_payload(concept, channel_id=channel_id, title=title, form_type=form_type)

    async with async_session() as session:
        concept_id = await ensure_concept(
            channel_id=channel_id,
            title=title,
            concept_json=concept,
            origin=origin,
            status="queued" if queue_immediately else status,
            form_type=form_type,
            notes=notes,
            priority=priority,
            session=session,
        )
        bank_id = None
        if queue_immediately:
            result = await session.execute(
                text(
                    """
                    INSERT INTO content_bank (channel_id, title, concept_json, status, priority, form_type, concept_id)
                    VALUES (:channel_id, :title, :concept_json, 'queued', :priority, :form_type, :concept_id)
                    RETURNING id
                    """
                ),
                {
                    "channel_id": channel_id,
                    "title": title,
                    "concept_json": json.dumps(concept),
                    "priority": priority,
                    "form_type": form_type,
                    "concept_id": concept_id,
                },
            )
            bank_id = result.scalar_one()
            await ensure_concept(
                channel_id=channel_id,
                title=title,
                concept_json=concept,
                origin=origin,
                status="queued",
                form_type=form_type,
                priority=priority,
                concept_id=concept_id,
                content_bank_id=bank_id,
                session=session,
            )
        await session.commit()

    return {"id": concept_id, "content_bank_id": bank_id, "status": "queued" if queue_immediately else status}


@router.post("/concepts/{concept_id}/approve")
async def approve_concept(concept_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text("SELECT id, status FROM concepts WHERE id = :id"),
                {"id": concept_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Concept not found")
        await update_concept_status(concept_id, status="approved", session=session)
        await session.commit()
    return {"id": concept_id, "status": "approved"}


@router.post("/concepts/{concept_id}/reject")
async def reject_concept(concept_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text("SELECT id FROM concepts WHERE id = :id"),
                {"id": concept_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Concept not found")
        await update_concept_status(concept_id, status="rejected", session=session)
        await session.commit()
    return {"id": concept_id, "status": "rejected"}


@router.post("/concepts/{concept_id}/queue")
async def queue_concept(concept_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT channel_id, title, concept_json, form_type, priority, status
                    FROM concepts
                    WHERE id = :id
                    """
                ),
                {"id": concept_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Concept not found")

        existing_bank = (
            await session.execute(
                text(
                    """
                    SELECT id, status
                    FROM content_bank
                    WHERE concept_id = :concept_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"concept_id": concept_id},
            )
        ).fetchone()
        if existing_bank and existing_bank[1] not in {"cancelled"}:
            return {"id": concept_id, "content_bank_id": existing_bank[0], "status": existing_bank[1]}

        concept = _normalize_concept_payload(row[2], channel_id=row[0], title=row[1], form_type=row[3])
        await session.execute(
            text("UPDATE concepts SET concept_json = :concept_json, updated_at = NOW() WHERE id = :id"),
            {"id": concept_id, "concept_json": json.dumps(concept)},
        )

        result = await session.execute(
            text(
                """
                INSERT INTO content_bank (channel_id, title, concept_json, status, priority, form_type, concept_id)
                VALUES (:channel_id, :title, :concept_json, 'queued', :priority, :form_type, :concept_id)
                RETURNING id
                """
            ),
            {
                "channel_id": row[0],
                "title": row[1],
                "concept_json": json.dumps(concept),
                "priority": row[4],
                "form_type": row[3],
                "concept_id": concept_id,
            },
        )
        bank_id = result.scalar_one()
        await update_concept_status(concept_id, status="queued", session=session)
        await session.commit()
    return {"id": concept_id, "content_bank_id": bank_id, "status": "queued"}


@router.post("/concepts/{concept_id}/clone")
async def clone_concept(concept_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT channel_id, title, concept_json, origin, form_type, priority, notes
                    FROM concepts
                    WHERE id = :id
                    """
                ),
                {"id": concept_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Concept not found")

        concept = _decode_concept(row[2])
        concept = copy.deepcopy(concept)
        cloned_title = f"{row[1]} (Copy)"
        if isinstance(concept, dict):
            concept["title"] = cloned_title

        cloned_id = await ensure_concept(
            channel_id=row[0],
            title=cloned_title,
            concept_json=concept,
            origin=row[3],
            status="draft",
            form_type=row[4],
            notes=row[6],
            priority=row[5],
            session=session,
        )
        await session.commit()
    return {"id": cloned_id, "status": "draft"}
