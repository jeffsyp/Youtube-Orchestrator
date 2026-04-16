"""Run listing and detail endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import (
    AssetDetail,
    RunDetail,
    RunSummary,
)
from apps.api.routers.status import _is_stalled

router = APIRouter(prefix="/api", tags=["runs"])


def _parse_review(review_json: str | None) -> tuple[float | None, str | None]:
    """Extract score and recommendation from review JSON."""
    if not review_json:
        return None, None
    try:
        review = json.loads(review_json)
        if review.get("reviewed"):
            return review.get("overall_score"), review.get("publish_recommendation")
    except (json.JSONDecodeError, TypeError):
        pass
    return None, None


def _parse_path(asset_json: str | None, key: str = "path") -> str | None:
    """Extract a path from an asset's JSON content."""
    if not asset_json:
        return None
    try:
        info = json.loads(asset_json)
        return info.get(key) if isinstance(info, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_title(metadata_json: str | None) -> str | None:
    """Extract title from publish_metadata asset."""
    if not metadata_json:
        return None
    try:
        info = json.loads(metadata_json)
        return info.get("title") if isinstance(info, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    channel_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List runs with optional filters."""
    conditions = []
    params: dict = {"limit": limit}

    if channel_id is not None:
        conditions.append("cr.channel_id = :channel_id")
        params["channel_id"] = channel_id
    if status is not None:
        conditions.append("cr.status = :status")
        params["status"] = status

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with async_session() as session:
        result = await session.execute(
            text(f"""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review,
                    (SELECT content FROM assets WHERE run_id = cr.id AND (asset_type = 'rendered_video' OR asset_type LIKE 'rendered_%') ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    CASE WHEN cr.status = 'running'
                         THEN EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int
                         ELSE NULL END as elapsed_seconds,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1) as metadata_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'production_qa' ORDER BY id DESC LIMIT 1) as prod_qa_asset,
                    cr.log_entries
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    {where}
                    ORDER BY cr.id DESC LIMIT :limit"""),
            params,
        )
        rows = result.fetchall()

    runs = []
    for row in rows:
        review_score, review_rec = _parse_review(row[9])
        video_path = _parse_path(row[10])
        thumbnail_path = _parse_path(row[11])
        youtube_url = _parse_path(row[13], key="url")
        youtube_privacy = _parse_path(row[13], key="privacy")
        title = _parse_title(row[14])
        prod_qa_verdict = _parse_path(row[15], key="verdict")

        # Extract last change from log entries — prefer [MANUAL] entries, fallback to last line
        last_change = None
        log_text = row[16] or ""
        if log_text:
            lines = [l.strip() for l in log_text.strip().split("\n") if l.strip()]
            manual_lines = [l for l in lines if "[MANUAL]" in l]
            if manual_lines:
                last_change = manual_lines[-1]
            elif lines:
                last_change = lines[-1]

        runs.append(
            RunSummary(
                id=row[0],
                channel_id=row[1],
                channel_name=row[2],
                content_type=row[3],
                status=row[4],
                current_step=row[5],
                started_at=row[6],
                completed_at=row[7],
                error=row[8],
                title=title,
                review_score=review_score,
                review_recommendation=review_rec,
                production_qa_verdict=prod_qa_verdict,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                elapsed_seconds=row[12],
                stalled=_is_stalled(row[4], row[5], row[12]),
                youtube_url=youtube_url,
                youtube_privacy=youtube_privacy,
                last_change=last_change,
            )
        )
    return runs


@router.delete("/runs/cleanup")
async def cleanup_old_runs(
    keep: int = Query(5, ge=1, le=50, description="Number of recent runs per status to keep"),
):
    """Delete old failed/rejected runs, keeping only the most recent `keep` per status."""
    async with async_session() as session:
        result = await session.execute(
            text("""DELETE FROM content_runs
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id, ROW_NUMBER() OVER (PARTITION BY status ORDER BY id DESC) as rn
                            FROM content_runs
                            WHERE status IN ('failed', 'rejected')
                        ) ranked
                        WHERE rn > :keep
                    )
                    RETURNING id"""),
            {"keep": keep},
        )
        deleted_ids = [row[0] for row in result.fetchall()]
        await session.commit()

    return {"deleted_count": len(deleted_ids), "deleted_run_ids": deleted_ids}


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: int):
    """Get full detail for a single run."""
    async with async_session() as session:
        # Main run
        result = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review,
                    (SELECT content FROM assets WHERE run_id = cr.id AND (asset_type = 'rendered_video' OR asset_type LIKE 'rendered_%') ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    CASE WHEN cr.status = 'running'
                         THEN EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int
                         ELSE NULL END as elapsed_seconds,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1) as metadata_asset
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Assets
        assets_result = await session.execute(
            text("SELECT id, asset_type, content FROM assets WHERE run_id = :id ORDER BY id"),
            {"id": run_id},
        )
        assets_rows = assets_result.fetchall()

    review_score, review_rec = _parse_review(row[9])
    video_path = _parse_path(row[10])
    thumbnail_path = _parse_path(row[11])
    youtube_url = _parse_path(row[13], key="url")
    youtube_privacy = _parse_path(row[13], key="privacy")
    title = _parse_title(row[14])

    assets = [
        AssetDetail(id=r[0], asset_type=r[1], content=r[2])
        for r in assets_rows
    ]

    return RunDetail(
        id=row[0],
        channel_id=row[1],
        channel_name=row[2],
        content_type=row[3],
        status=row[4],
        current_step=row[5],
        started_at=row[6],
        completed_at=row[7],
        error=row[8],
        title=title,
        review_score=review_score,
        review_recommendation=review_rec,
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        elapsed_seconds=row[12],
        stalled=_is_stalled(row[4], row[5], row[12]),
        youtube_url=youtube_url,
        youtube_privacy=youtube_privacy,
        assets=assets,
    )


@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: int):
    """Get log entries for a run."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT log_entries, current_step, status FROM content_runs WHERE id = :id"),
            {"id": run_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")

        logs = row[0] or ""
        return {
            "run_id": run_id,
            "current_step": row[1],
            "status": row[2],
            "logs": logs.split("\n") if logs and logs != "[]" else [],
        }
