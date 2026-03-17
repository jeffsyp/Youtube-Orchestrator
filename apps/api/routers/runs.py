"""Run listing and detail endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import (
    AssetDetail,
    IdeaDetail,
    PackageDetail,
    RunDetail,
    RunSummary,
    ScriptDetail,
)

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
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'rendered_video' ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    CASE WHEN cr.status = 'running'
                         THEN EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int
                         ELSE NULL END as elapsed_seconds,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset
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
                review_score=review_score,
                review_recommendation=review_rec,
                video_path=video_path,
                thumbnail_path=thumbnail_path,
                elapsed_seconds=row[12],
                youtube_url=youtube_url,
                youtube_privacy=youtube_privacy,
            )
        )
    return runs


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: int):
    """Get full detail for a single run, including ideas, scripts, assets, and packages."""
    async with async_session() as session:
        # Main run
        result = await session.execute(
            text("""SELECT cr.id, cr.channel_id, c.name, cr.content_type, cr.status, cr.current_step,
                    cr.started_at, cr.completed_at, cr.error,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'rendered_video' ORDER BY id DESC LIMIT 1) as video_asset,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'thumbnail' ORDER BY id DESC LIMIT 1) as thumb_asset,
                    CASE WHEN cr.status = 'running'
                         THEN EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int
                         ELSE NULL END as elapsed_seconds,
                    (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'publish_result' ORDER BY id DESC LIMIT 1) as publish_asset
                    FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Ideas
        ideas_result = await session.execute(
            text("SELECT id, title, hook, angle, score, selected FROM ideas WHERE run_id = :id ORDER BY score DESC"),
            {"id": run_id},
        )
        ideas_rows = ideas_result.fetchall()

        # Scripts
        scripts_result = await session.execute(
            text("SELECT id, stage, idea_title, word_count, content, critique_notes FROM scripts WHERE run_id = :id ORDER BY id"),
            {"id": run_id},
        )
        scripts_rows = scripts_result.fetchall()

        # Assets
        assets_result = await session.execute(
            text("SELECT id, asset_type, content FROM assets WHERE run_id = :id ORDER BY id"),
            {"id": run_id},
        )
        assets_rows = assets_result.fetchall()

        # Packages
        packages_result = await session.execute(
            text("SELECT id, title, description, tags, category, status FROM packages WHERE run_id = :id ORDER BY id"),
            {"id": run_id},
        )
        packages_rows = packages_result.fetchall()

    review_score, review_rec = _parse_review(row[9])
    video_path = _parse_path(row[10])
    thumbnail_path = _parse_path(row[11])
    youtube_url = _parse_path(row[13], key="url")
    youtube_privacy = _parse_path(row[13], key="privacy")

    ideas = [
        IdeaDetail(id=r[0], title=r[1], hook=r[2], angle=r[3], score=r[4], selected=r[5])
        for r in ideas_rows
    ]

    scripts = [
        ScriptDetail(id=r[0], stage=r[1], idea_title=r[2], word_count=r[3], content=r[4], critique_notes=r[5])
        for r in scripts_rows
    ]

    assets = [
        AssetDetail(id=r[0], asset_type=r[1], content=r[2])
        for r in assets_rows
    ]

    packages = []
    for r in packages_rows:
        try:
            tags = json.loads(r[3]) if r[3] else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        packages.append(
            PackageDetail(id=r[0], title=r[1], description=r[2], tags=tags, category=r[4], status=r[5])
        )

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
        review_score=review_score,
        review_recommendation=review_rec,
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        elapsed_seconds=row[12],
        youtube_url=youtube_url,
        youtube_privacy=youtube_privacy,
        ideas=ideas,
        scripts=scripts,
        assets=assets,
        packages=packages,
    )
