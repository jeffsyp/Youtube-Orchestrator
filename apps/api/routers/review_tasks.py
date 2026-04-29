"""Explicit review task inbox for local-first operator flows."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from packages.clients.db import async_session
from packages.clients.workflow_state import resolve_review_task

router = APIRouter(prefix="/api", tags=["review-tasks"])


def _decode(raw):
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


@router.get("/review-tasks")
async def list_review_tasks(
    status: str = Query("pending"),
    kind: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    conditions = ["rt.status = :status"]
    params: dict[str, object] = {"status": status, "limit": limit}
    if kind:
        conditions.append("rt.kind = :kind")
        params["kind"] = kind

    where = " AND ".join(conditions)
    async with async_session() as session:
        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT rt.id, rt.run_id, rt.concept_id, rt.channel_id, rt.kind, rt.status,
                           rt.payload_json, rt.resolution_json, rt.created_at, rt.resolved_at,
                           cr.current_step, cr.status, ch.name,
                           COALESCE(co.title, cb.title)
                    FROM review_tasks rt
                    LEFT JOIN content_runs cr ON cr.id = rt.run_id
                    LEFT JOIN channels ch ON ch.id = rt.channel_id
                    LEFT JOIN concepts co ON co.id = rt.concept_id
                    LEFT JOIN content_bank cb ON cb.run_id = rt.run_id
                    WHERE {where}
                    ORDER BY rt.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).fetchall()

    tasks = []
    for row in rows:
        payload = _decode(row[6])
        tasks.append(
            {
                "id": row[0],
                "run_id": row[1],
                "concept_id": row[2],
                "channel_id": row[3],
                "kind": row[4],
                "status": row[5],
                "payload": payload,
                "resolution": _decode(row[7]),
                "created_at": row[8].isoformat() if row[8] else None,
                "resolved_at": row[9].isoformat() if row[9] else None,
                "current_step": row[10],
                "run_status": row[11],
                "channel_name": row[12],
                "title": row[13],
            }
        )
    return tasks


@router.get("/review-tasks/{task_id}")
async def get_review_task(task_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, run_id, concept_id, channel_id, kind, status,
                           payload_json, resolution_json, created_at, resolved_at
                    FROM review_tasks
                    WHERE id = :id
                    """
                ),
                {"id": task_id},
            )
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review task not found")
    return {
        "id": row[0],
        "run_id": row[1],
        "concept_id": row[2],
        "channel_id": row[3],
        "kind": row[4],
        "status": row[5],
        "payload": _decode(row[6]),
        "resolution": _decode(row[7]),
        "created_at": row[8].isoformat() if row[8] else None,
        "resolved_at": row[9].isoformat() if row[9] else None,
    }


@router.post("/review-tasks/{task_id}/approve")
async def approve_review_task(task_id: int):
    async with async_session() as session:
        row = (
            await session.execute(
                text("SELECT id, run_id, kind FROM review_tasks WHERE id = :id"),
                {"id": task_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Review task not found")

    await resolve_review_task(run_id=row[1], kind=row[2], status="approved", resolution={"approved_all": True})
    if row[2] == "images":
        approval_file = f"output/run_{row[1]}/.images_approved"
        os.makedirs(os.path.dirname(approval_file), exist_ok=True)
        with open(approval_file, "w") as f:
            f.write("approved")
    return {"id": task_id, "status": "approved"}


@router.post("/review-tasks/{task_id}/reject")
async def reject_review_task(task_id: int, payload: dict | None = None):
    payload = payload or {}
    async with async_session() as session:
        row = (
            await session.execute(
                text("SELECT id, run_id, kind FROM review_tasks WHERE id = :id"),
                {"id": task_id},
            )
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Review task not found")

    await resolve_review_task(run_id=row[1], kind=row[2], status="rejected", resolution=payload)
    if row[2] == "images":
        deny_file = f"output/run_{row[1]}/.images_denied"
        os.makedirs(os.path.dirname(deny_file), exist_ok=True)
        with open(deny_file, "w") as f:
            f.write("denied")
    return {"id": task_id, "status": "rejected"}
