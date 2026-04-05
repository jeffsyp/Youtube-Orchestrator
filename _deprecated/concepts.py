"""Concept review queue endpoints — list pending concepts, approve, reject."""

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from temporalio.client import Client

from packages.clients.db import async_session

router = APIRouter(prefix="/api", tags=["concepts"])


async def _get_temporal_client() -> Client:
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(host, namespace=namespace)


# Same mapping as actions.py
PIPELINE_MAP = {
    "synthzoo": "synthzoo",
    "satisdefying": "satisdefying",
    "lad_stories": "lad_stories",
    "fundational": "fundational",
    "whistle_room": "whistle_room",
    "yeah_thats_clean": "yeah_thats_clean",
    "shorts": "short",
    "short": "short",
}


@router.get("/concepts/pending")
async def list_pending_concepts():
    """List all runs awaiting concept approval, with their pending concepts."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type,
                    cr.started_at, cr.current_step,
                    (SELECT content FROM assets
                     WHERE run_id = cr.id AND asset_type = 'pending_concepts'
                     ORDER BY id DESC LIMIT 1) as concepts_json
                    FROM content_runs cr
                    JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.status = 'awaiting_approval'
                      AND cr.current_step = 'concept_review'
                    ORDER BY cr.id DESC""")
        )
        rows = result.fetchall()

    runs = []
    for row in rows:
        concepts = []
        if row[6]:
            try:
                raw = json.loads(row[6])
                # Normalize field names across pipelines
                for c in raw:
                    if "topic" in c and "title" not in c:
                        c["title"] = c["topic"]
                    if "hook_angle" in c and "caption" not in c:
                        c["caption"] = c["hook_angle"]
                    if "brief" in c and "caption" not in c:
                        c["caption"] = c["brief"]
                concepts = raw
            except (json.JSONDecodeError, TypeError):
                pass

        runs.append({
            "run_id": row[0],
            "channel_id": row[1],
            "channel_name": row[2],
            "content_type": row[3],
            "started_at": row[4].isoformat() if row[4] else None,
            "current_step": row[5],
            "concepts": concepts,
        })

    return runs


@router.get("/runs/{run_id}/concepts")
async def get_run_concepts(run_id: int):
    """Get pending concepts for a specific run."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.status, cr.current_step,
                    (SELECT content FROM assets
                     WHERE run_id = cr.id AND asset_type = 'pending_concepts'
                     ORDER BY id DESC LIMIT 1) as concepts_json
                    FROM content_runs cr WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    concepts = []
    if row[2]:
        try:
            concepts = json.loads(row[2])
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "run_id": run_id,
        "status": row[0],
        "current_step": row[1],
        "concepts": concepts,
    }


@router.post("/runs/{run_id}/concepts/{index}/approve")
async def approve_concept(run_id: int, index: int):
    """Approve a concept — sends select_concept signal to the Temporal workflow."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.status, cr.current_step, cr.content_type
                    FROM content_runs cr WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if row[0] != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run status is '{row[0]}', expected 'awaiting_approval'",
        )

    content_type = row[2]
    # Determine the workflow ID pattern based on content_type
    pipeline_type = content_type
    # Map content_type back to pipeline key if needed
    if content_type == "short":
        pipeline_type = "shorts"
    workflow_id = f"{pipeline_type}-pipeline-run-{run_id}"

    # Send the select_concept signal (1-based index)
    client = await _get_temporal_client()
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("select_concept", index)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to signal workflow {workflow_id}: {str(e)}",
        )

    # Update run status back to running
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'running', current_step = 'concept_approved' WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    return {"run_id": run_id, "approved_index": index, "status": "running"}


@router.post("/runs/{run_id}/concepts/reject-all")
async def reject_all_concepts(run_id: int):
    """Reject all concepts — sends reject_all_concepts signal to the Temporal workflow."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.status, cr.current_step, cr.content_type
                    FROM content_runs cr WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if row[0] != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run status is '{row[0]}', expected 'awaiting_approval'",
        )

    content_type = row[2]
    pipeline_type = content_type
    if content_type == "short":
        pipeline_type = "shorts"
    workflow_id = f"{pipeline_type}-pipeline-run-{run_id}"

    # Send the reject signal
    client = await _get_temporal_client()
    try:
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("reject_all_concepts")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to signal workflow {workflow_id}: {str(e)}",
        )

    # Update run status to rejected
    async with async_session() as session:
        result2 = await session.execute(
            text("SELECT channel_id FROM content_runs WHERE id = :id"),
            {"id": run_id},
        )
        channel_id = result2.scalar()
        await session.execute(
            text("UPDATE content_runs SET status = 'rejected', current_step = 'concepts_rejected' WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    # Auto-restart pipeline with fresh concepts
    new_run = None
    if channel_id:
        try:
            from apps.api.routers.actions import _start_pipeline
            new_run = await _start_pipeline(channel_id, auto_pick=True, privacy="private")
        except Exception:
            pass  # Non-critical — reject still succeeds even if restart fails

    resp = {"run_id": run_id, "status": "rejected"}
    if new_run:
        resp["new_run_id"] = new_run.run_id
        resp["message"] = "Rejected. New concepts generating..."
    return resp


# --- Concept Feedback ---

class ConceptFeedbackBody(BaseModel):
    feedback: str


@router.get("/channels/{channel_id}/concept-feedback")
async def get_concept_feedback(channel_id: int):
    """Return all stored concept feedback for a channel."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT id, content FROM assets
                    WHERE channel_id = :cid AND asset_type = 'concept_feedback'
                    ORDER BY id ASC"""),
            {"cid": channel_id},
        )
        rows = result.fetchall()

    items = []
    for row in rows:
        try:
            data = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            data = {"feedback": row[1]}
        items.append({"id": row[0], **data})

    return items


@router.post("/channels/{channel_id}/concept-feedback")
async def add_concept_feedback(channel_id: int, body: ConceptFeedbackBody):
    """Store new concept feedback for a channel."""
    if not body.feedback.strip():
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")

    content = json.dumps({
        "feedback": body.feedback.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with async_session() as session:
        # run_id has a FK constraint — use the earliest run for this channel as a dummy ref
        ref_run = await session.execute(
            text("SELECT MIN(id) FROM content_runs WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        run_id = ref_run.scalar() or 1
        result = await session.execute(
            text("""INSERT INTO assets (channel_id, run_id, asset_type, content)
                    VALUES (:cid, :rid, 'concept_feedback', :content)
                    RETURNING id"""),
            {"cid": channel_id, "rid": run_id, "content": content},
        )
        new_id = result.scalar()
        await session.commit()

    return {"id": new_id, "status": "saved"}


@router.delete("/channels/{channel_id}/concept-feedback/{feedback_id}")
async def delete_concept_feedback(channel_id: int, feedback_id: int):
    """Delete a specific concept feedback entry."""
    async with async_session() as session:
        result = await session.execute(
            text("""DELETE FROM assets
                    WHERE id = :fid AND channel_id = :cid AND asset_type = 'concept_feedback'"""),
            {"fid": feedback_id, "cid": channel_id},
        )
        await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return {"status": "deleted"}


# --- Video Feedback ---

class VideoFeedbackBody(BaseModel):
    feedback: str


@router.get("/channels/{channel_id}/video-feedback")
async def get_video_feedback(channel_id: int):
    """Return all stored video feedback for a channel."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT id, content FROM assets
                    WHERE channel_id = :cid AND asset_type = 'video_feedback'
                    ORDER BY id ASC"""),
            {"cid": channel_id},
        )
        rows = result.fetchall()

    items = []
    for row in rows:
        try:
            data = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            data = {"feedback": row[1]}
        items.append({"id": row[0], **data})

    return items


@router.post("/channels/{channel_id}/video-feedback")
async def add_video_feedback(channel_id: int, body: VideoFeedbackBody):
    """Store new video feedback for a channel."""
    if not body.feedback.strip():
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")

    content = json.dumps({
        "feedback": body.feedback.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with async_session() as session:
        # run_id has a FK constraint — use the earliest run for this channel as a dummy ref
        ref_run = await session.execute(
            text("SELECT MIN(id) FROM content_runs WHERE channel_id = :cid"),
            {"cid": channel_id},
        )
        run_id = ref_run.scalar() or 1
        result = await session.execute(
            text("""INSERT INTO assets (channel_id, run_id, asset_type, content)
                    VALUES (:cid, :rid, 'video_feedback', :content)
                    RETURNING id"""),
            {"cid": channel_id, "rid": run_id, "content": content},
        )
        new_id = result.scalar()
        await session.commit()

    return {"id": new_id, "status": "saved"}


@router.delete("/channels/{channel_id}/video-feedback/{feedback_id}")
async def delete_video_feedback(channel_id: int, feedback_id: int):
    """Delete a specific video feedback entry."""
    async with async_session() as session:
        result = await session.execute(
            text("""DELETE FROM assets
                    WHERE id = :fid AND channel_id = :cid AND asset_type = 'video_feedback'"""),
            {"fid": feedback_id, "cid": channel_id},
        )
        await session.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return {"status": "deleted"}
