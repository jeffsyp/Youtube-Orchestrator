"""Shared local-first workflow helpers.

These helpers add a durable run bundle, append-only run events, explicit review
tasks, and a canonical concepts table while keeping the existing content_bank /
content_runs flow working during the transition.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.clients.db import async_session


OUTPUT_ROOT = "output"


def run_output_dir(run_id: int) -> str:
    return os.path.join(OUTPUT_ROOT, f"run_{run_id}")


def manifest_path_for(run_id: int) -> str:
    return os.path.join(run_output_dir(run_id), "manifest.json")


def events_path_for(run_id: int) -> str:
    return os.path.join(run_output_dir(run_id), "events.jsonl")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2)


def _load_json(path: str, default: dict | list | None = None):
    if not os.path.exists(path):
        return {} if default is None else default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {} if default is None else default


def _write_json(path: str, payload: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(_json_dumps(payload))


def _append_jsonl(path: str, payload: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(payload, ensure_ascii=True))
        f.write("\n")


async def _load_channel_snapshot(channel_id: int) -> dict[str, Any] | None:
    async with async_session() as session:
        row = (
            await session.execute(
                text("SELECT id, name, niche, config FROM channels WHERE id = :id"),
                {"id": channel_id},
            )
        ).fetchone()
    if not row:
        return None
    config = {}
    if row[3]:
        try:
            config = json.loads(row[3]) if isinstance(row[3], str) else row[3]
        except Exception:
            config = {}
    return {
        "id": row[0],
        "name": row[1],
        "niche": row[2],
        "config": config,
    }


async def ensure_run_bundle(
    run_id: int,
    *,
    concept: dict[str, Any] | None = None,
    channel_id: int | None = None,
    pipeline_mode: str | None = None,
    trigger_type: str | None = None,
    stage: str | None = None,
    status: str | None = None,
    session: AsyncSession | None = None,
) -> dict[str, str]:
    """Ensure the run folder, concept snapshot, channel snapshot, and manifest exist."""
    output_dir = run_output_dir(run_id)
    os.makedirs(output_dir, exist_ok=True)
    manifest_file = manifest_path_for(run_id)
    concept_file = os.path.join(output_dir, "concept_snapshot.json")
    channel_file = os.path.join(output_dir, "channel_snapshot.json")

    manifest = _load_json(manifest_file, default={})
    manifest.setdefault("run_id", run_id)
    manifest.setdefault("run_dir", os.path.abspath(output_dir))
    manifest.setdefault("manifest_path", os.path.abspath(manifest_file))
    manifest.setdefault("created_at", _utc_now_iso())
    manifest["updated_at"] = _utc_now_iso()

    if pipeline_mode is not None:
        manifest["pipeline_mode"] = pipeline_mode
    if trigger_type is not None:
        manifest["trigger_type"] = trigger_type
    if stage is not None:
        manifest["stage"] = stage
    if status is not None:
        manifest["status"] = status

    if concept is not None:
        _write_json(concept_file, concept)
        manifest["concept_snapshot_path"] = os.path.abspath(concept_file)
        manifest["title"] = concept.get("title")
        channel_id = channel_id or concept.get("channel_id")

    if channel_id:
        channel_snapshot = await _load_channel_snapshot(channel_id)
        if channel_snapshot is not None:
            _write_json(channel_file, channel_snapshot)
            manifest["channel_snapshot_path"] = os.path.abspath(channel_file)
            manifest["channel_id"] = channel_id
            manifest["channel_name"] = channel_snapshot.get("name")

    _write_json(manifest_file, manifest)

    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        await session.execute(
            text(
                """
                UPDATE content_runs
                SET run_dir = :run_dir,
                    manifest_path = :manifest_path,
                    trigger_type = COALESCE(:trigger_type, trigger_type)
                WHERE id = :id
                """
            ),
            {
                "id": run_id,
                "run_dir": os.path.abspath(output_dir),
                "manifest_path": os.path.abspath(manifest_file),
                "trigger_type": trigger_type,
            },
        )
        if owned_session:
            await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)

    return {
        "run_dir": output_dir,
        "manifest_path": manifest_file,
    }


async def update_run_manifest(run_id: int, updates: dict[str, Any]):
    manifest = _load_json(manifest_path_for(run_id), default={})
    manifest.update(updates)
    manifest["updated_at"] = _utc_now_iso()
    _write_json(manifest_path_for(run_id), manifest)


async def append_run_event(
    run_id: int,
    *,
    event_type: str,
    message: str,
    stage: str | None = None,
    level: str = "info",
    data: dict[str, Any] | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    await ensure_run_bundle(run_id)
    payload = {
        "ts": _utc_now_iso(),
        "run_id": run_id,
        "level": level,
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "data": data or {},
    }

    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        await session.execute(
            text(
                """
                INSERT INTO run_events (run_id, level, event_type, stage, message, data_json)
                VALUES (:run_id, :level, :event_type, :stage, :message, :data_json)
                """
            ),
            {
                "run_id": run_id,
                "level": level,
                "event_type": event_type,
                "stage": stage,
                "message": message,
                "data_json": json.dumps(data or {}, ensure_ascii=True) if data is not None else None,
            },
        )
        if owned_session:
            await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)

    _append_jsonl(events_path_for(run_id), payload)
    await update_run_manifest(
        run_id,
        {
            "last_event": payload,
            "stage": stage,
        },
    )
    return payload


async def set_run_progress(
    run_id: int,
    *,
    step: str | None = None,
    status: str | None = None,
    message: str | None = None,
    event_type: str = "progress",
    stage: str | None = None,
    complete: bool = False,
    error: str | None = None,
    session: AsyncSession | None = None,
):
    """Update legacy content_runs fields while also writing structured events."""
    await ensure_run_bundle(run_id, stage=stage or step, status=status)
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        sets: list[str] = []
        params: dict[str, Any] = {"id": run_id}
        if step is not None:
            sets.append("current_step = :step")
            params["step"] = step
        if status is not None:
            sets.append("status = :status")
            params["status"] = status
        if error is not None:
            sets.append("error = :error")
            params["error"] = error
        if complete:
            sets.append("completed_at = NOW()")
        if sets:
            await session.execute(
                text(f"UPDATE content_runs SET {', '.join(sets)} WHERE id = :id"),
                params,
            )
            if owned_session:
                await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)

    if message or step or status or error:
        await append_run_event(
            run_id,
            event_type=event_type,
            message=message or step or status or error or "updated",
            stage=stage or step,
            level="error" if error else "info",
            data={"status": status, "step": step, "error": error},
        )
    await update_run_manifest(
        run_id,
        {
            "status": status,
            "stage": stage or step,
            "error": error,
            "completed_at": _utc_now_iso() if complete else None,
        },
    )


async def ensure_concept(
    *,
    channel_id: int,
    title: str,
    concept_json: str | dict[str, Any],
    origin: str,
    status: str,
    form_type: str = "short",
    notes: str | None = None,
    priority: int = 100,
    concept_id: int | None = None,
    draft_id: int | None = None,
    content_bank_id: int | None = None,
    run_id: int | None = None,
    session: AsyncSession | None = None,
) -> int:
    concept_payload = concept_json if isinstance(concept_json, str) else json.dumps(concept_json, ensure_ascii=True)
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None

    try:
        if concept_id is None:
            if draft_id is not None:
                row = (
                    await session.execute(
                        text("SELECT concept_id FROM concept_drafts WHERE id = :id"),
                        {"id": draft_id},
                    )
                ).fetchone()
                if row and row[0]:
                    concept_id = row[0]
            if concept_id is None and content_bank_id is not None:
                row = (
                    await session.execute(
                        text("SELECT concept_id FROM content_bank WHERE id = :id"),
                        {"id": content_bank_id},
                    )
                ).fetchone()
                if row and row[0]:
                    concept_id = row[0]

        if concept_id is None:
            result = await session.execute(
                text(
                    """
                    INSERT INTO concepts (channel_id, origin, status, form_type, title, concept_json, notes, priority, latest_run_id)
                    VALUES (:channel_id, :origin, :status, :form_type, :title, :concept_json, :notes, :priority, :latest_run_id)
                    RETURNING id
                    """
                ),
                {
                    "channel_id": channel_id,
                    "origin": origin,
                    "status": status,
                    "form_type": form_type,
                    "title": title,
                    "concept_json": concept_payload,
                    "notes": notes,
                    "priority": priority,
                    "latest_run_id": run_id,
                },
            )
            concept_id = result.scalar_one()
        else:
            await session.execute(
                text(
                    """
                    UPDATE concepts
                    SET channel_id = :channel_id,
                        origin = :origin,
                        status = :status,
                        form_type = :form_type,
                        title = :title,
                        concept_json = :concept_json,
                        notes = COALESCE(:notes, notes),
                        priority = :priority,
                        latest_run_id = COALESCE(:latest_run_id, latest_run_id),
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": concept_id,
                    "channel_id": channel_id,
                    "origin": origin,
                    "status": status,
                    "form_type": form_type,
                    "title": title,
                    "concept_json": concept_payload,
                    "notes": notes,
                    "priority": priority,
                    "latest_run_id": run_id,
                },
            )

        if draft_id is not None:
            await session.execute(
                text("UPDATE concept_drafts SET concept_id = :concept_id WHERE id = :id"),
                {"id": draft_id, "concept_id": concept_id},
            )
        if content_bank_id is not None:
            await session.execute(
                text("UPDATE content_bank SET concept_id = :concept_id WHERE id = :id"),
                {"id": content_bank_id, "concept_id": concept_id},
            )
        if run_id is not None:
            await session.execute(
                text("UPDATE content_runs SET concept_id = :concept_id WHERE id = :id"),
                {"id": run_id, "concept_id": concept_id},
            )

        if owned_session:
            await session.commit()
        return concept_id
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)


async def update_concept_status(
    concept_id: int,
    *,
    status: str,
    latest_run_id: int | None = None,
    published_run_id: int | None = None,
    session: AsyncSession | None = None,
):
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        await session.execute(
            text(
                """
                UPDATE concepts
                SET status = :status,
                    latest_run_id = COALESCE(:latest_run_id, latest_run_id),
                    published_run_id = COALESCE(:published_run_id, published_run_id),
                    updated_at = NOW()
                WHERE id = :id
                """
            ),
            {
                "id": concept_id,
                "status": status,
                "latest_run_id": latest_run_id,
                "published_run_id": published_run_id,
            },
        )
        if owned_session:
            await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)


async def get_latest_rendered_asset(run_id: int, session: AsyncSession | None = None) -> tuple[str, dict[str, Any]] | None:
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        row = (
            await session.execute(
                text(
                    """
                    SELECT asset_type, content
                    FROM assets
                    WHERE run_id = :rid
                      AND (asset_type = 'rendered_video' OR asset_type LIKE 'rendered%')
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"rid": run_id},
            )
        ).fetchone()
        if not row:
            return None
        content = row[1]
        payload = content if isinstance(content, dict) else json.loads(content)
        return row[0], payload
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)


async def create_review_task(
    *,
    run_id: int,
    kind: str,
    payload: dict[str, Any] | None = None,
    concept_id: int | None = None,
    channel_id: int | None = None,
    stage: str | None = None,
    session: AsyncSession | None = None,
) -> int:
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        existing = (
            await session.execute(
                text(
                    """
                    SELECT id
                    FROM review_tasks
                    WHERE run_id = :run_id AND kind = :kind AND status = 'pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "kind": kind},
            )
        ).fetchone()
        if existing:
            await session.execute(
                text(
                    """
                    UPDATE review_tasks
                    SET payload_json = :payload_json
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing[0],
                    "payload_json": json.dumps(payload or {}, ensure_ascii=True),
                },
            )
            task_id = existing[0]
        else:
            result = await session.execute(
                text(
                    """
                    INSERT INTO review_tasks (run_id, concept_id, channel_id, kind, status, payload_json)
                    VALUES (:run_id, :concept_id, :channel_id, :kind, 'pending', :payload_json)
                    RETURNING id
                    """
                ),
                {
                    "run_id": run_id,
                    "concept_id": concept_id,
                    "channel_id": channel_id,
                    "kind": kind,
                    "payload_json": json.dumps(payload or {}, ensure_ascii=True),
                },
            )
            task_id = result.scalar_one()

        await session.execute(
            text("UPDATE content_runs SET status = 'blocked', current_step = :step WHERE id = :id"),
            {"id": run_id, "step": stage or f"{kind} review pending"},
        )
        if concept_id is not None:
            await update_concept_status(concept_id, status="blocked", latest_run_id=run_id, session=session)
        if owned_session:
            await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)

    await append_run_event(
        run_id,
        event_type="review_requested",
        message=f"{kind} review requested",
        stage=stage or kind,
        data={"task_id": task_id, "kind": kind},
    )
    return task_id


async def resolve_review_task(
    *,
    run_id: int,
    kind: str,
    status: str,
    resolution: dict[str, Any] | None = None,
    session: AsyncSession | None = None,
) -> int | None:
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    task_id = None
    concept_id = None
    try:
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, concept_id
                    FROM review_tasks
                    WHERE run_id = :run_id AND kind = :kind AND status = 'pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "kind": kind},
            )
        ).fetchone()
        if not row:
            return None
        task_id = row[0]
        concept_id = row[1]
        await session.execute(
            text(
                """
                UPDATE review_tasks
                SET status = :status,
                    resolution_json = :resolution_json,
                    resolved_at = NOW()
                WHERE id = :id
                """
            ),
            {
                "id": task_id,
                "status": status,
                "resolution_json": json.dumps(resolution or {}, ensure_ascii=True),
            },
        )
        if status == "approved":
            await session.execute(
                text("UPDATE content_runs SET status = 'running' WHERE id = :id AND status = 'blocked'"),
                {"id": run_id},
            )
            if concept_id is not None:
                await update_concept_status(concept_id, status="running", latest_run_id=run_id, session=session)
        if owned_session:
            await session.commit()
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)

    await append_run_event(
        run_id,
        event_type="review_resolved",
        message=f"{kind} review {status}",
        stage=kind,
        data={"task_id": task_id, "resolution": resolution or {}},
    )
    return task_id


async def get_pending_review_task(run_id: int, kind: str, session: AsyncSession | None = None) -> dict[str, Any] | None:
    owned_session = session is None
    if owned_session:
        session_cm = async_session()
        session = await session_cm.__aenter__()
    else:
        session_cm = None
    try:
        row = (
            await session.execute(
                text(
                    """
                    SELECT id, run_id, concept_id, channel_id, kind, payload_json, created_at
                    FROM review_tasks
                    WHERE run_id = :run_id AND kind = :kind AND status = 'pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"run_id": run_id, "kind": kind},
            )
        ).fetchone()
        if not row:
            return None
        payload = {}
        if row[5]:
            try:
                payload = json.loads(row[5]) if isinstance(row[5], str) else row[5]
            except Exception:
                payload = {}
        return {
            "id": row[0],
            "run_id": row[1],
            "concept_id": row[2],
            "channel_id": row[3],
            "kind": row[4],
            "payload": payload,
            "created_at": row[6].isoformat() if row[6] else None,
        }
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)
