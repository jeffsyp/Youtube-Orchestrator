"""Pipeline action endpoints — execute concepts, publish, reject, delete."""

import json
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import (
    ExecuteConceptRequest,
    ExecuteConceptResponse,
)

router = APIRouter(prefix="/api", tags=["actions"])


# Temporal no longer used — direct pipeline runs as background task


async def _get_channel(channel_id: int) -> tuple:
    """Fetch channel row or raise 404."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, name, niche, config FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return row


@router.post("/runs/execute", response_model=ExecuteConceptResponse)
async def execute_concept(req: ExecuteConceptRequest, background_tasks: BackgroundTasks):
    """Execute a fully-formed concept through the direct pipeline."""
    from apps.orchestrator.direct_pipeline import run_pipeline

    row = await _get_channel(req.channel_id)

    # Build concept dict from request
    concept = {
        "title": req.title,
        "channel_id": req.channel_id,
        "visual_style": req.visual_style,
        "clips": [clip.model_dump() for clip in req.clips],
        "caption": req.caption,
        "tags": req.tags,
        "voice_id": req.voice_id,
        "sora_volume": req.sora_volume,
        "narration_volume": req.narration_volume,
        "privacy": req.privacy,
        "video_engine": req.video_engine,
        "skip_subtitles": req.skip_subtitles,
        "frame_chain": req.frame_chain,
        "reference_image": req.reference_image,
    }

    # Create the run row
    async with async_session() as session:
        result = await session.execute(
            text(
                "INSERT INTO content_runs (channel_id, status, content_type) "
                "VALUES (:cid, 'running', 'unified') RETURNING id"
            ),
            {"cid": req.channel_id},
        )
        run_id = result.scalar_one()

        metadata = json.dumps({
            "title": req.title,
            "description": req.caption,
            "tags": req.tags,
            "category": "Entertainment",
        })
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": req.channel_id, "type": "publish_metadata", "content": metadata},
        )
        await session.commit()

    # Run pipeline directly as background task — no Temporal, no worker
    background_tasks.add_task(_run_pipeline_bg, run_id, concept)

    return ExecuteConceptResponse(
        run_id=run_id,
        workflow_id=f"direct-run-{run_id}",
        channel_name=row[1],
    )


def _run_pipeline_bg(run_id: int, concept: dict):
    """Run pipeline in background thread."""
    import asyncio
    from apps.orchestrator.direct_pipeline import run_pipeline
    asyncio.run(run_pipeline(run_id, concept))


@router.post("/runs/deity")
async def execute_deity(concept: dict):
    """Execute a narrated video short."""
    from apps.orchestrator.deity_pipeline import run_deity_pipeline

    channel_id = concept.get("channel_id", 14)
    row = await _get_channel(channel_id)

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', 'deity') RETURNING id"),
            {"cid": channel_id},
        )
        run_id = result.scalar_one()
        await session.commit()

    import asyncio
    import threading

    def _run_bg():
        asyncio.run(run_deity_pipeline(run_id, concept))

    threading.Thread(target=_run_bg, daemon=True).start()

    return {"run_id": run_id, "channel_name": row[1], "title": concept.get("title", "Untitled")}


@router.post("/runs/{run_id}/publish")
async def publish_run(run_id: int, privacy: str = "private"):
    """Publish a pending_review run (initial upload) or change privacy on an already-uploaded run."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.status, c.config, cr.channel_id,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'youtube_upload' ORDER BY id DESC LIMIT 1) as upload_info,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_info,
                    (SELECT content FROM assets WHERE run_id = cr.id AND (asset_type LIKE 'rendered%%') ORDER BY id DESC LIMIT 1) as rendered_info,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1) as publish_metadata,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_info
                    FROM content_runs cr
                    JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_status = row[0]
    config = json.loads(row[1]) if row[1] else {}
    channel_id = row[2]
    token_file = config.get("youtube_token_file")

    # Derive token file from channel name if not explicitly configured
    if not token_file:
        async with async_session() as session:
            ch_result = await session.execute(
                text("SELECT name FROM channels WHERE id = :id"), {"id": channel_id}
            )
            ch_name = ch_result.scalar()
        if ch_name:
            token_name = ch_name.lower().replace(" ", "").replace("'", "").replace("\u2019", "")
            token_file = f"youtube_token_{token_name}.json"
        else:
            token_file = "youtube_token.json"

    # --- Case 1: Already uploaded — change privacy ---
    upload_info_raw = row[3] or row[4]
    if upload_info_raw and run_status != "pending_review":
        try:
            upload_info = json.loads(upload_info_raw)
            video_id = upload_info.get("video_id")
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid upload data")

        if not video_id:
            raise HTTPException(status_code=400, detail="No video_id in upload data")

        from apps.publishing_service.uploader import _get_youtube_client

        try:
            youtube = _get_youtube_client(youtube_token_file=token_file)
            youtube.videos().update(
                part="status",
                body={"id": video_id, "status": {"privacyStatus": privacy}},
            ).execute()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"YouTube API error: {str(e)}")

        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'published' WHERE id = :id"),
                {"id": run_id},
            )
            await session.commit()

        return {"run_id": run_id, "video_id": video_id, "status": privacy}

    # --- Case 2: pending_review — initial upload ---
    if run_status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run status is '{run_status}', expected 'pending_review' for initial upload",
        )

    # Get rendered video path
    rendered_raw = row[5]
    if not rendered_raw:
        raise HTTPException(status_code=400, detail="No rendered video found for this run")

    try:
        rendered_info = json.loads(rendered_raw)
        video_path = rendered_info.get("path")
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid rendered video data")

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=400, detail=f"Rendered video file not found: {video_path}")

    # Get publish metadata
    metadata_raw = row[6]
    if metadata_raw:
        try:
            metadata = json.loads(metadata_raw)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    else:
        metadata = {}

    title = metadata.get("title", "Untitled")
    description = metadata.get("description", "")
    tags = metadata.get("tags", [])
    category = metadata.get("category", "Entertainment")

    # Get thumbnail path
    thumbnail_path = metadata.get("thumbnail_path")
    if not thumbnail_path and row[7]:
        try:
            thumb_info = json.loads(row[7])
            thumbnail_path = thumb_info.get("path") if isinstance(thumb_info, dict) else None
        except (json.JSONDecodeError, TypeError):
            thumbnail_path = None

    made_for_kids = False

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    if not is_upload_configured(youtube_token_file=token_file):
        raise HTTPException(
            status_code=400,
            detail=f"YouTube OAuth2 not configured for token file: {token_file}",
        )

    try:
        result = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category=category,
            privacy_status=privacy,
            youtube_token_file=token_file,
            made_for_kids=made_for_kids,
            thumbnail_path=thumbnail_path,
        )
    except Exception as e:
        error_msg = str(e)
        if "uploadLimitExceeded" in error_msg:
            raise HTTPException(status_code=429, detail="YouTube daily upload limit exceeded. Try again tomorrow.")
        raise HTTPException(status_code=500, detail=f"Upload failed: {error_msg}")

    if result.get("published"):
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'published' WHERE id = :id"),
                {"id": run_id},
            )
            # Store publish result for URL tracking
            await session.execute(
                text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                       VALUES (:run_id, :channel_id, :type, :content)"""),
                {
                    "run_id": run_id, "channel_id": channel_id,
                    "type": "publish_result",
                    "content": json.dumps(result),
                },
            )
            await session.commit()

    return {"run_id": run_id, **result}


@router.post("/runs/{run_id}/reject")
async def reject_run(run_id: int):
    """Reject a pending_review run — delete output files and mark as rejected."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cr.status, cr.channel_id,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type LIKE 'rendered%%' ORDER BY id DESC LIMIT 1) as rendered_info
                    FROM content_runs cr WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Derive output directory from rendered video path
    video_path = None
    if row[2]:
        try:
            rendered_info = json.loads(row[2])
            video_path = rendered_info.get("path")
        except (json.JSONDecodeError, TypeError):
            pass

    if video_path:
        import shutil
        output_dir = os.path.dirname(video_path)
        if output_dir and os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'rejected' WHERE id = :id"),
            {"id": run_id},
        )
        # Also update content_bank status
        await session.execute(
            text("UPDATE content_bank SET status = 'rejected' WHERE run_id = :id"),
            {"id": run_id},
        )
        await session.commit()

    return {"run_id": run_id, "status": "rejected"}


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: int):
    """Cancel a running or pending_review run and reset its content bank item."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT status, content_bank_id FROM content_runs WHERE id = :id"),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'failed', current_step = 'cancelled', error = 'cancelled by user' WHERE id = :id"),
            {"id": run_id},
        )
        if row[1]:  # content_bank_id
            await session.execute(
                text("UPDATE content_bank SET status = 'skipped', attempt_count = 99 WHERE id = :id"),
                {"id": row[1]},
            )
        await session.commit()

    return {"run_id": run_id, "status": "cancelled"}


@router.post("/runs/{run_id}/delete-video")
async def delete_video(run_id: int):
    """Delete a video from YouTube."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT c.config,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'youtube_upload' ORDER BY id DESC LIMIT 1) as upload_info
                    FROM content_runs cr
                    JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if not row[1]:
        raise HTTPException(status_code=400, detail="No YouTube upload found for this run")

    try:
        upload_info = json.loads(row[1])
        video_id = upload_info.get("video_id")
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid upload data")

    if not video_id:
        raise HTTPException(status_code=400, detail="No video_id in upload data")

    config = json.loads(row[0]) if row[0] else {}
    token_file = config.get("youtube_token_file", "youtube_token.json")

    from apps.publishing_service.uploader import _get_youtube_client

    try:
        youtube = _get_youtube_client(youtube_token_file=token_file)
        youtube.videos().delete(id=video_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube API error: {str(e)}")

    return {"run_id": run_id, "video_id": video_id, "deleted": True}
