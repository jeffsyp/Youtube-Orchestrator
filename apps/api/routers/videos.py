"""Video and thumbnail serving endpoints with Range header support."""

import json
import os
import stat

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import text

from packages.clients.db import async_session

router = APIRouter(prefix="/api", tags=["videos"])


async def _get_asset_path(run_id: int, asset_type: str) -> str:
    """Look up an asset path from the DB and verify the file exists."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT content FROM assets WHERE run_id = :id AND asset_type = :atype ORDER BY id DESC LIMIT 1"),
            {"id": run_id, "atype": asset_type},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"No {asset_type} asset for run {run_id}")

    try:
        info = json.loads(row[0])
        path = info.get("path") if isinstance(info, dict) else row[0]
    except (json.JSONDecodeError, TypeError):
        path = row[0]

    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    return path


@router.get("/videos/{run_id}/stream")
async def stream_video(run_id: int, request: Request):
    """Serve the rendered MP4 with HTTP Range support for seeking."""
    path = await _get_asset_path(run_id, "rendered_video")
    file_size = os.path.getsize(path)

    range_header = request.headers.get("range")
    if range_header:
        # Parse Range: bytes=start-end
        range_spec = range_header.strip().replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(content_length)

        return Response(
            content=data,
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": "video/mp4",
            },
        )

    return FileResponse(
        path,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@router.get("/videos/{run_id}/thumbnail")
async def get_thumbnail(run_id: int):
    """Serve the thumbnail PNG for a run."""
    # Try the thumbnail asset first
    try:
        path = await _get_asset_path(run_id, "thumbnail")
        return FileResponse(path, media_type="image/png")
    except HTTPException:
        pass

    # Fall back to conventional path
    fallback = f"output/run_{run_id}/thumbnail.png"
    if os.path.isfile(fallback):
        return FileResponse(fallback, media_type="image/png")

    raise HTTPException(status_code=404, detail=f"No thumbnail for run {run_id}")
