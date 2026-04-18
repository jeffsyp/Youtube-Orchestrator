"""Content bank endpoints — manage the concept queue per channel."""

import json

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session
from packages.clients.workflow_state import ensure_concept, update_concept_status
from packages.utils.concept_formats import apply_format_strategy_defaults

router = APIRouter(prefix="/api", tags=["content-bank"])


def _normalize_concept_payload(raw_concept, *, channel_id: int, title: str, form_type: str) -> str:
    concept = raw_concept
    if isinstance(concept, str):
        try:
            concept = json.loads(concept)
        except Exception:
            concept = {}
    elif not isinstance(concept, dict):
        concept = {}

    concept = apply_format_strategy_defaults(dict(concept), form_type=form_type)
    concept.setdefault("channel_id", channel_id)
    concept.setdefault("title", title)
    concept.setdefault("form_type", form_type)
    return json.dumps(concept)


async def _delete_run_dependencies(session, run_id: int):
    """Delete or null all records that still reference a run before deleting it."""
    await session.execute(
        text("""
            UPDATE concepts
            SET latest_run_id = NULL
            WHERE latest_run_id = :rid
        """),
        {"rid": run_id},
    )
    await session.execute(
        text("""
            UPDATE concepts
            SET published_run_id = NULL
            WHERE published_run_id = :rid
        """),
        {"rid": run_id},
    )
    await session.execute(
        text("DELETE FROM review_tasks WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.execute(
        text("DELETE FROM run_events WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.execute(
        text("DELETE FROM scheduled_uploads WHERE run_id = :rid"),
        {"rid": run_id},
    )
    for table_name in ["source_candidates", "templates", "ideas", "scripts", "packages", "assets"]:
        await session.execute(
            text(f"DELETE FROM {table_name} WHERE run_id = :rid"),
            {"rid": run_id},
        )


@router.get("/content-bank")
async def list_content_bank(channel_id: int | None = None, status: str = "queued", limit: int = 50):
    """List content bank items, optionally filtered by channel and status."""
    async with async_session() as session:
        query = """
            SELECT cb.id, cb.channel_id, c.name as channel_name, cb.title,
                   cb.status, cb.priority, cb.created_at, cb.run_id,
                   cb.error, cb.attempt_count, cb.concept_id
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            WHERE 1=1
        """
        params = {}
        if channel_id:
            query += " AND cb.channel_id = :cid"
            params["cid"] = channel_id
        if status != "all":
            query += " AND cb.status = :status"
            params["status"] = status
        query += " ORDER BY cb.priority ASC, cb.created_at ASC LIMIT :limit"
        params["limit"] = limit

        result = await session.execute(text(query), params)
        rows = result.fetchall()

    return [
        {
            "id": r[0], "channel_id": r[1], "channel_name": r[2], "title": r[3],
            "status": r[4], "priority": r[5], "created_at": r[6].isoformat() if r[6] else None,
            "run_id": r[7], "error": r[8], "attempt_count": r[9], "concept_id": r[10],
        }
        for r in rows
    ]


@router.post("/content-bank/{item_id}/cancel")
async def cancel_content_bank_item(item_id: int):
    """Cancel a queued, locked, or generating content bank item."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, status, run_id, concept_id FROM content_bank WHERE id = :id"),
            {"id": item_id},
        )
        item = result.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        status = item[1]
        run_id = item[2]
        concept_id = item[3]

        if status in ("uploaded", "generated"):
            raise HTTPException(status_code=400, detail=f"Cannot cancel item with status '{status}'")

        # Cancel the content bank item
        await session.execute(
            text("UPDATE content_bank SET status = 'cancelled', locked_at = NULL WHERE id = :id"),
            {"id": item_id},
        )

        # If there's a running content_run, fail it too
        if run_id:
            await session.execute(
                text("UPDATE content_runs SET status = 'failed', error = 'cancelled by user' WHERE id = :id AND status = 'running'"),
                {"id": run_id},
            )
        if concept_id:
            await update_concept_status(concept_id, status="archived", session=session)

        await session.commit()

    return {"id": item_id, "status": "cancelled"}


@router.post("/content-bank/{item_id}/clear")
async def clear_content_bank_item(item_id: int):
    """Remove a content bank item and its related files."""
    import os
    import shutil

    async with async_session() as session:
        result = await session.execute(
            text("SELECT cb.id, cb.status, cb.run_id, cb.concept_id FROM content_bank cb WHERE cb.id = :id"),
            {"id": item_id},
        )
        item = result.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        status = item[1]
        run_id = item[2]
        concept_id = item[3]

        if status in ("generating", "locked"):
            raise HTTPException(status_code=400, detail=f"Cannot clear actively generating item. Cancel it first.")

        # Delete related output files if there's a run
        if run_id:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", f"run_{run_id}")
            if os.path.isdir(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)

            # Clear run reference first, then delete content_bank, then runs/assets
            await session.execute(
                text("UPDATE content_bank SET run_id = NULL WHERE id = :id"),
                {"id": item_id},
            )
            await _delete_run_dependencies(session, run_id)

        # Clear concept_drafts reference
        await session.execute(
            text("UPDATE concept_drafts SET content_bank_id = NULL WHERE content_bank_id = :id"),
            {"id": item_id},
        )

        # Delete the content_bank item
        await session.execute(
            text("DELETE FROM content_bank WHERE id = :id"),
            {"id": item_id},
        )
        if concept_id:
            await update_concept_status(concept_id, status="archived", session=session)

        # Now safe to delete the content_run
        if run_id:
            await session.execute(
                text("DELETE FROM content_runs WHERE id = :rid"),
                {"rid": run_id},
            )

        await session.commit()

    return {"id": item_id, "status": "cleared", "files_deleted": bool(run_id)}


@router.post("/content-bank/clear-all")
async def clear_all_activity():
    """Clear all non-generating activity — for starting fresh."""
    import os
    import shutil

    async with async_session() as session:
        # Get all clearable items — skip only those whose run is actually still running
        result = await session.execute(
            text("""SELECT cb.id, cb.run_id, cb.concept_id FROM content_bank cb
                    LEFT JOIN content_runs cr ON cr.id = cb.run_id
                    WHERE cb.status != 'queued'
                    AND (cr.id IS NULL OR cr.status NOT IN ('running', 'generating'))""")
        )
        items = result.fetchall()

        cleared = 0
        for item_id, run_id, concept_id in items:
            if run_id:
                output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", f"run_{run_id}")
                if os.path.isdir(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)
                await session.execute(
                    text("UPDATE content_bank SET run_id = NULL WHERE id = :id"),
                    {"id": item_id},
                )
                await _delete_run_dependencies(session, run_id)

            await session.execute(
                text("UPDATE concept_drafts SET content_bank_id = NULL WHERE content_bank_id = :id"),
                {"id": item_id},
            )
            await session.execute(
                text("DELETE FROM content_bank WHERE id = :id"),
                {"id": item_id},
            )
            if concept_id:
                await update_concept_status(concept_id, status="archived", session=session)

            if run_id:
                await session.execute(
                    text("DELETE FROM content_runs WHERE id = :rid"),
                    {"rid": run_id},
                )
            cleared += 1

        # Also clean up orphaned content_runs with no content_bank entry
        orphans = await session.execute(
            text("""SELECT id FROM content_runs
                    WHERE status NOT IN ('running', 'generating')
                    AND id NOT IN (SELECT run_id FROM content_bank WHERE run_id IS NOT NULL)""")
        )
        orphan_ids = [r[0] for r in orphans.fetchall()]
        for rid in orphan_ids:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", f"run_{rid}")
            if os.path.isdir(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            await _delete_run_dependencies(session, rid)
            await session.execute(text("DELETE FROM content_runs WHERE id = :rid"), {"rid": rid})
            cleared += 1

        await session.commit()

    return {"cleared": cleared}


@router.post("/content-bank/{item_id}/retry")
async def retry_content_bank_item(item_id: int):
    """Re-queue a failed content bank item for retry."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, status, concept_id FROM content_bank WHERE id = :id"),
            {"id": item_id},
        )
        item = result.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if item[1] not in ("failed", "rejected"):
            raise HTTPException(status_code=400, detail=f"Cannot retry item with status '{item[1]}'")

        await session.execute(
            text("UPDATE content_bank SET status = 'queued', locked_at = NULL, error = NULL, run_id = NULL WHERE id = :id"),
            {"id": item_id},
        )
        if item[2]:
            await update_concept_status(item[2], status="queued", session=session)
        await session.commit()

    return {"id": item_id, "status": "queued"}


async def _check_duplicate(session, channel_id: int, title: str) -> dict | None:
    """Check if a similar topic already exists for this channel."""
    # Check content_bank (all statuses)
    result = await session.execute(
        text("""SELECT id, title, status FROM content_bank
                WHERE channel_id = :cid AND LOWER(title) = LOWER(:title)"""),
        {"cid": channel_id, "title": title},
    )
    exact = result.fetchone()
    if exact:
        return {"duplicate": True, "match": "exact", "existing_id": exact[0], "existing_title": exact[1], "status": exact[2]}

    # Fuzzy check — look for similar titles (shared significant words)
    # Extract words > 3 chars from the new title
    words = [w.lower() for w in title.split() if len(w) > 3 and w.upper() not in ("THE", "AND", "FOR", "WITH", "FROM", "THAT", "HAVE", "THIS", "WHAT", "WHEN", "YOUR")]
    if words:
        # Check if any existing title contains 2+ of the same significant words
        result = await session.execute(
            text("SELECT id, title, status FROM content_bank WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        for row in result.fetchall():
            existing_words = [w.lower() for w in row[1].split() if len(w) > 3]
            overlap = set(words) & set(existing_words)
            if len(overlap) >= 3:
                return {"duplicate": True, "match": "similar", "overlap": list(overlap), "existing_id": row[0], "existing_title": row[1], "status": row[2]}

    # Also check content_runs publish_metadata for already-published videos
    result = await session.execute(
        text("""SELECT a.run_id, a.content FROM assets a
                JOIN content_runs cr ON cr.id = a.run_id
                WHERE cr.channel_id = :cid AND a.asset_type = 'publish_metadata'"""),
        {"cid": channel_id},
    )
    for row in result.fetchall():
        try:
            meta = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            existing_title = meta.get("title", "")
            if existing_title.lower() == title.lower():
                return {"duplicate": True, "match": "published", "run_id": row[0], "existing_title": existing_title}
            existing_words = [w.lower() for w in existing_title.split() if len(w) > 3]
            overlap = set(words) & set(existing_words)
            if len(overlap) >= 2:
                return {"duplicate": True, "match": "similar_published", "overlap": list(overlap), "run_id": row[0], "existing_title": existing_title}
        except (json.JSONDecodeError, TypeError):
            pass

    return None


@router.post("/content-bank")
async def add_to_content_bank(item: dict):
    """Add a single concept to the content bank."""
    channel_id = item.get("channel_id")
    title = item.get("title", "Untitled")
    concept_json = item.get("concept_json") or item.get("concept")
    priority = item.get("priority", 100)
    skip_duplicate_check = item.get("skip_duplicate_check", False)
    form_type = item.get("form_type", "short")

    if not channel_id or not concept_json:
        raise HTTPException(status_code=400, detail="channel_id and concept_json required")

    concept_json = _normalize_concept_payload(
        concept_json,
        channel_id=channel_id,
        title=title,
        form_type=form_type,
    )

    async with async_session() as session:
        if not skip_duplicate_check:
            dup = await _check_duplicate(session, channel_id, title)
            if dup:
                return {"id": None, "status": "duplicate", "title": title, "duplicate_info": dup}

        concept_id = await ensure_concept(
            channel_id=channel_id,
            title=title,
            concept_json=concept_json,
            origin="manual",
            status="queued",
            form_type=form_type,
            priority=priority,
            session=session,
        )
        result = await session.execute(
            text("""INSERT INTO content_bank (channel_id, title, concept_json, priority, concept_id)
                    VALUES (:cid, :title, :concept, :priority, :concept_id) RETURNING id"""),
            {"cid": channel_id, "title": title, "concept": concept_json, "priority": priority, "concept_id": concept_id},
        )
        bank_id = result.scalar_one()
        await ensure_concept(
            channel_id=channel_id,
            title=title,
            concept_json=concept_json,
            origin="manual",
            status="queued",
            form_type=form_type,
            priority=priority,
            concept_id=concept_id,
            content_bank_id=bank_id,
            session=session,
        )
        await session.commit()

    return {"id": bank_id, "concept_id": concept_id, "status": "queued", "title": title}


@router.post("/content-bank/bulk")
async def bulk_add_to_content_bank(payload: dict):
    """Add multiple concepts to the content bank.

    Body: {"channel_id": 14, "concepts": [{"title": "...", "concept_json": {...}}, ...]}
    """
    channel_id = payload.get("channel_id")
    concepts = payload.get("concepts", [])

    if not channel_id or not concepts:
        raise HTTPException(status_code=400, detail="channel_id and concepts required")

    ids = []
    async with async_session() as session:
        skipped = []
        for i, c in enumerate(concepts):
            title = c.get("title", f"Concept {i+1}")
            concept_json = c.get("concept_json") or c.get("concept")
            priority = c.get("priority", 100)
            form_type = c.get("form_type", "short")
            concept_json = _normalize_concept_payload(
                concept_json,
                channel_id=channel_id,
                title=title,
                form_type=form_type,
            )

            dup = await _check_duplicate(session, channel_id, title)
            if dup:
                skipped.append({"title": title, "reason": dup})
                continue

            concept_id = await ensure_concept(
                channel_id=channel_id,
                title=title,
                concept_json=concept_json,
                origin="manual",
                status="queued",
                form_type=form_type,
                priority=priority,
                session=session,
            )
            result = await session.execute(
                text("""INSERT INTO content_bank (channel_id, title, concept_json, priority, concept_id)
                        VALUES (:cid, :title, :concept, :priority, :concept_id) RETURNING id"""),
                {"cid": channel_id, "title": title, "concept": concept_json, "priority": priority, "concept_id": concept_id},
            )
            bank_id = result.scalar_one()
            await ensure_concept(
                channel_id=channel_id,
                title=title,
                concept_json=concept_json,
                origin="manual",
                status="queued",
                form_type=form_type,
                priority=priority,
                concept_id=concept_id,
                content_bank_id=bank_id,
                session=session,
            )
            ids.append(bank_id)
        await session.commit()

    return {"added": len(ids), "ids": ids, "skipped": skipped}


@router.patch("/content-bank/{item_id}")
async def update_content_bank_item(item_id: int, update: dict):
    """Update priority or status of a content bank item."""
    sets = []
    params = {"id": item_id}

    if "priority" in update:
        sets.append("priority = :priority")
        params["priority"] = update["priority"]
    if "status" in update:
        sets.append("status = :status")
        params["status"] = update["status"]

    if not sets:
        raise HTTPException(status_code=400, detail="Nothing to update")

    async with async_session() as session:
        if "status" in update:
            concept_id = (
                await session.execute(text("SELECT concept_id FROM content_bank WHERE id = :id"), {"id": item_id})
            ).scalar_one_or_none()
            if concept_id:
                await update_concept_status(concept_id, status=update["status"], session=session)
        await session.execute(
            text(f"UPDATE content_bank SET {', '.join(sets)} WHERE id = :id"), params
        )
        await session.commit()

    return {"id": item_id, "updated": True}


@router.delete("/content-bank/{item_id}")
async def delete_content_bank_item(item_id: int):
    """Remove an item from the content bank."""
    async with async_session() as session:
        concept_id = (
            await session.execute(text("SELECT concept_id FROM content_bank WHERE id = :id"), {"id": item_id})
        ).scalar_one_or_none()
        await session.execute(text("DELETE FROM content_bank WHERE id = :id"), {"id": item_id})
        if concept_id:
            await update_concept_status(concept_id, status="archived", session=session)
        await session.commit()
    return {"id": item_id, "deleted": True}


@router.post("/content-bank/{item_id}/generate-now")
async def generate_now(item_id: int):
    """Force immediate generation by setting priority to 0."""
    async with async_session() as session:
        concept_id = (
            await session.execute(text("SELECT concept_id FROM content_bank WHERE id = :id"), {"id": item_id})
        ).scalar_one_or_none()
        await session.execute(
            text("UPDATE content_bank SET priority = 0, status = 'queued', locked_at = NULL WHERE id = :id"),
            {"id": item_id},
        )
        if concept_id:
            await update_concept_status(concept_id, status="queued", session=session)
        await session.commit()
    return {"id": item_id, "priority": 0, "message": "Queued for immediate generation"}


@router.get("/content-bank/youtube-links")
async def get_youtube_links(channel_id: int | None = None):
    """Get YouTube video URLs for uploaded content, optionally filtered by channel."""
    async with async_session() as session:
        query = """
            SELECT cr.id, cr.channel_id, c.name, a_meta.content as metadata, a_pub.content as publish
            FROM content_runs cr
            JOIN channels c ON c.id = cr.channel_id
            JOIN assets a_pub ON a_pub.run_id = cr.id AND a_pub.asset_type = 'publish_result'
            LEFT JOIN assets a_meta ON a_meta.run_id = cr.id AND a_meta.asset_type = 'publish_metadata'
            WHERE 1=1
        """
        params = {}
        if channel_id:
            query += " AND cr.channel_id = :cid"
            params["cid"] = channel_id
        query += " ORDER BY cr.id DESC"

        result = await session.execute(text(query), params)
        rows = result.fetchall()

    import json
    links = []
    for row in rows:
        pub = json.loads(row[4]) if isinstance(row[4], str) else row[4]
        meta = json.loads(row[3]) if row[3] and isinstance(row[3], str) else (row[3] or {})
        links.append({
            "run_id": row[0],
            "channel_id": row[1],
            "channel_name": row[2],
            "title": meta.get("title", "Untitled"),
            "url": pub.get("url"),
            "video_id": pub.get("video_id"),
            "publish_at": pub.get("publish_at"),
        })
    return links


@router.get("/activity")
async def get_activity(limit: int = 50):
    """Activity feed — recent content across all channels with status, type, and YouTube links."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT cb.id, cb.channel_id, c.name as channel_name, cb.title,
                   CASE
                       WHEN cr.status = 'failed' THEN 'failed'
                       WHEN cr.status = 'rejected' THEN 'rejected'
                       WHEN cr.status = 'pending_review' THEN 'generated'
                       ELSE cb.status
                   END as status,
                   cb.created_at, cb.run_id, cb.attempt_count,
                   cr.current_step, cr.started_at, cr.completed_at,
                   (SELECT content FROM assets WHERE run_id = cb.run_id AND asset_type = 'publish_result' LIMIT 1) as pub_result,
                   CASE WHEN cj.beats_count >= 20 THEN 'long' ELSE 'short' END as form_type
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            LEFT JOIN content_runs cr ON cr.id = cb.run_id
            LEFT JOIN LATERAL (
                SELECT jsonb_array_length(cb.concept_json::jsonb -> 'beats') as beats_count
            ) cj ON true
            WHERE cb.created_at > NOW() - INTERVAL '48 hours'
            ORDER BY cb.id DESC
            LIMIT :limit
        """), {"limit": limit})
        rows = result.fetchall()

    import json as _json
    items = []
    for r in rows:
        pub = None
        if r[11]:
            try:
                pub = _json.loads(r[11]) if isinstance(r[11], str) else r[11]
            except: pass

        items.append({
            "id": r[0],
            "channel_id": r[1],
            "channel_name": r[2],
            "title": r[3],
            "status": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "run_id": r[6],
            "attempts": r[7],
            "current_step": r[8],
            "started_at": r[9].isoformat() if r[9] else None,
            "completed_at": r[10].isoformat() if r[10] else None,
            "youtube_url": pub.get("url") if pub else None,
            "youtube_publish_at": pub.get("publish_at") if pub else None,
            "form_type": r[12] or "short",
        })
    return items
