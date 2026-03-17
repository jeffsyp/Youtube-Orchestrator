"""Pipeline action endpoints — create runs, publish, delete."""

import json
import os

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from temporalio.client import Client

from packages.clients.db import async_session
from apps.api.schemas import (
    BatchRunRequest,
    BatchRunResponse,
    CreateRunRequest,
    CreateRunResponse,
)

router = APIRouter(prefix="/api", tags=["actions"])

# Same mapping as admin/cli.py make_short
PIPELINE_MAP = {
    "synthzoo": ("SynthZooPipeline", "synthzoo"),
    "satisdefying": ("SatisdefyingPipeline", "satisdefying"),
    "lad_stories": ("LadStoriesPipeline", "lad_stories"),
    "fundational": ("FundationalPipeline", "fundational"),
    "whistle_room": ("WhistleRoomPipeline", "whistle_room"),
    "yeah_thats_clean": ("YeahThatsCleanPipeline", "yeah_thats_clean"),
    "shorts": ("ShortsPipeline", "short"),
}


async def _get_temporal_client() -> Client:
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(host, namespace=namespace)


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


async def _start_pipeline(
    channel_id: int, auto_pick: bool, privacy: str
) -> CreateRunResponse:
    """Create a content_run, start the Temporal workflow, return immediately."""
    row = await _get_channel(channel_id)
    config = json.loads(row[3]) if row[3] else {}
    pipeline_type = config.get("pipeline", "shorts")

    if pipeline_type not in PIPELINE_MAP:
        raise HTTPException(
            status_code=400, detail=f"Unknown pipeline type: {pipeline_type}"
        )

    workflow_name, content_type = PIPELINE_MAP[pipeline_type]

    # Create the run row
    async with async_session() as session:
        result = await session.execute(
            text(
                "INSERT INTO content_runs (channel_id, status, content_type) "
                "VALUES (:cid, 'running', :ct) RETURNING id"
            ),
            {"cid": channel_id, "ct": content_type},
        )
        run_id = result.scalar_one()
        await session.commit()

    # Start workflow (non-blocking)
    client = await _get_temporal_client()
    workflow_id = f"{pipeline_type}-pipeline-run-{run_id}"
    await client.start_workflow(
        workflow_name,
        args=[run_id, channel_id, auto_pick, privacy],
        id=workflow_id,
        task_queue="daily-content-pipeline",
    )

    return CreateRunResponse(
        run_id=run_id,
        workflow_id=workflow_id,
        channel_name=row[1],
        pipeline=pipeline_type,
    )


@router.post("/runs/create", response_model=CreateRunResponse)
async def create_run(req: CreateRunRequest):
    """Start a single pipeline run. Returns immediately with the run_id."""
    return await _start_pipeline(req.channel_id, req.auto_pick, req.privacy)


@router.post("/runs/batch", response_model=BatchRunResponse)
async def batch_create_runs(req: BatchRunRequest):
    """Start pipelines for multiple channels. All auto-pick, returns immediately."""
    response = BatchRunResponse()
    for cid in req.channel_ids:
        try:
            run = await _start_pipeline(cid, auto_pick=True, privacy=req.privacy)
            response.runs.append(run)
        except HTTPException as e:
            response.errors.append(f"Channel {cid}: {e.detail}")
        except Exception as e:
            response.errors.append(f"Channel {cid}: {str(e)}")
    return response


@router.post("/runs/{run_id}/publish")
async def publish_run(run_id: int):
    """Change a video's YouTube privacy status to public."""
    async with async_session() as session:
        # Get channel config for token file
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
        youtube.videos().update(
            part="status",
            body={"id": video_id, "status": {"privacyStatus": "public"}},
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube API error: {str(e)}")

    # Update run status
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'published' WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()

    return {"run_id": run_id, "video_id": video_id, "status": "public"}


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
