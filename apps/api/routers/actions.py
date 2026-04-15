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


@router.post("/runs/generate")
async def execute_deity(concept: dict):
    """Execute a narrated video short."""
    from apps.orchestrator.pipeline import run_pipeline

    channel_id = concept.get("channel_id", 14)
    row = await _get_channel(channel_id)

    title = concept.get("title", "Untitled")

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', 'deity') RETURNING id"),
            {"cid": channel_id},
        )
        run_id = result.scalar_one()

        # Always create content_bank entry so it shows in Activity
        await session.execute(
            text("INSERT INTO content_bank (channel_id, title, status, run_id, concept_json) VALUES (:cid, :title, 'generating', :rid, :cj)"),
            {"cid": channel_id, "title": title, "rid": run_id, "cj": json.dumps(concept)},
        )
        await session.commit()

    import asyncio
    import threading

    def _run_bg():
        asyncio.run(run_pipeline(run_id, concept))

    threading.Thread(target=_run_bg, daemon=True).start()

    return {"run_id": run_id, "channel_name": row[1], "title": title}


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
        # Handle scheduled uploads — upload as private with publish_at
        publish_at = None
        actual_privacy = privacy
        if privacy == "scheduled":
            import random
            from datetime import datetime, timezone, timedelta
            delay = random.randint(3600, 10800)  # 1-3 hours
            publish_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
            # Round to nearest 5 minutes
            minute = (publish_time.minute // 5) * 5
            publish_time = publish_time.replace(minute=minute, second=0, microsecond=0)
            publish_at = publish_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            actual_privacy = "private"

        result = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category=category,
            privacy_status=actual_privacy,
            youtube_token_file=token_file,
            made_for_kids=made_for_kids,
            thumbnail_path=thumbnail_path,
            publish_at=publish_at,
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


@router.get("/runs/{run_id}/images")
async def get_run_images(run_id: int):
    """Get all generated images for a run — for review before animation."""
    import os, base64
    images_dir = f"output/run_{run_id}/images"
    if not os.path.isdir(images_dir):
        raise HTTPException(status_code=404, detail="No images directory found")
    
    images = []
    seen_hashes = set()
    for f in sorted(os.listdir(images_dir)):
        if not f.endswith('.png'):
            continue
        if '_lastframe' in f or '_feedback' in f:
            continue
        if not (f.startswith('sub_') or f.startswith('scene_') or f == 'style_anchor.png' or f == 'base_scene.png'):
            continue
        path = os.path.join(images_dir, f)
        with open(path, "rb") as img:
            raw = img.read()
        # Skip exact duplicates
        h = hash(raw)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        b64 = base64.b64encode(raw).decode()

        # Try to get narration/prompt context for this image
        narration_text = ""
        try:
            # Load word timestamps to get narration lines
            ts_path = f"output/run_{run_id}/word_timestamps.json"
            plan_path = f"output/run_{run_id}/images/plan.json"
            if os.path.exists(ts_path):
                import json as _json
                with open(ts_path) as tf:
                    words = _json.load(tf)
                # Group words by line
                lines = {}
                for w in words:
                    line_idx = w.get("line", 0)
                    lines.setdefault(line_idx, []).append(w["word"])
                narr_lines = {k: " ".join(v) for k, v in sorted(lines.items())}

                # Map image to narration line — use plan.json if available
                plan_path = os.path.join(images_dir, "plan.json")
                plan = None
                if os.path.exists(plan_path):
                    try:
                        with open(plan_path) as pf:
                            plan = _json.load(pf)
                    except:
                        pass

                if f.startswith("sub_"):
                    idx = int(f.replace("sub_", "").replace(".png", ""))
                    if plan and idx < len(plan):
                        line_idx = plan[idx].get("line", 0)
                        narration_text = narr_lines.get(line_idx, "")
                    else:
                        total_subs = len([x for x in os.listdir(images_dir) if x.startswith("sub_") and x.endswith(".png") and "_lastframe" not in x])
                        if total_subs > 0 and narr_lines:
                            line_idx = min(idx * len(narr_lines) // max(total_subs, 1), len(narr_lines) - 1)
                            narration_text = narr_lines.get(line_idx, "")
                elif f.startswith("scene_"):
                    idx = int(f.replace("scene_", "").replace(".png", ""))
                    narration_text = narr_lines.get(idx, "")
                elif f == "base_scene.png":
                    narration_text = narr_lines.get(0, "(base scene)")
                elif f == "style_anchor.png":
                    narration_text = "(style reference)"
        except Exception:
            pass

        images.append({
            "name": f,
            "path": path,
            "b64": b64,
            "approved": None,
            "narration": narration_text,
        })
    
    # Try to get expected count from the sub-action plan
    expected = len(images)
    plan_path = os.path.join(images_dir, "plan.json")
    if not os.path.exists(plan_path):
        # Check if shared pipeline saved the plan
        for f in os.listdir(images_dir):
            if f.startswith("sub_") and f.endswith(".png") and "_lastframe" not in f and "_feedback" not in f:
                pass  # count is already in images

    # Get expected from the run's current step if it has "X/Y" format
    try:
        from sqlalchemy import text
        from packages.clients.db import async_session
        async with async_session() as session:
            result = await session.execute(
                text("SELECT current_step FROM content_runs WHERE id = :id"),
                {"id": run_id},
            )
            row = result.fetchone()
            if row and row[0]:
                step = row[0]
                # Parse "scene 3/14" format
                import re as _re
                m = _re.search(r'(\d+)/(\d+)', step)
                if m:
                    expected = int(m.group(2))
    except Exception:
        pass

    # Count how many new-scene images are expected (exclude lastframes)
    all_sub_pngs = [f for f in os.listdir(images_dir) if f.startswith("sub_") and f.endswith(".png") and "_lastframe" not in f and "_feedback" not in f]

    return {"run_id": run_id, "images": images, "total": len(images), "expected": max(expected, len(all_sub_pngs))}


@router.post("/runs/{run_id}/images/approve")
async def approve_run_images(run_id: int, approved: list[str] = None, denied: list[dict] = None):
    """Approve or deny specific images. 
    
    approved: list of image filenames to approve
    denied: list of {"name": "filename", "feedback": "what to fix"} objects
    
    If all images are approved (none denied), sets run status to continue.
    If any denied, regenerates them with feedback and returns for re-review.
    """
    import os
    from sqlalchemy import text
    from packages.clients.db import async_session
    
    images_dir = f"output/run_{run_id}/images"
    
    # Handle denials — regenerate with feedback
    regenerated = []
    if denied:
        from packages.clients.grok import generate_image_dalle
        for item in denied:
            name = item.get("name", "")
            feedback = item.get("feedback", "")
            path = os.path.join(images_dir, name)
            if os.path.exists(path):
                os.remove(path)
                # Regenerate with feedback as additional prompt guidance
                # For now, store the feedback — the pipeline will use it on retry
                feedback_path = os.path.join(images_dir, name.replace('.png', '_feedback.txt'))
                with open(feedback_path, 'w') as f:
                    f.write(feedback)
                regenerated.append({"name": name, "feedback": feedback})
    
    if regenerated:
        # Signal pipeline to regenerate via file
        deny_file = f"output/run_{run_id}/.images_denied"
        with open(deny_file, 'w') as f:
            f.write("denied")
        return {"run_id": run_id, "status": "regenerating", "regenerated": regenerated}

    # All approved — signal pipeline via file
    approval_file = f"output/run_{run_id}/.images_approved"
    with open(approval_file, 'w') as f:
        f.write("approved")

    return {"run_id": run_id, "status": "approved", "message": "All images approved — continuing to animation"}


@router.post("/runs/{run_id}/images/approve-all")
async def approve_all_images(run_id: int):
    """Approve all images and continue pipeline."""
    approval_file = f"output/run_{run_id}/.images_approved"
    import os
    os.makedirs(f"output/run_{run_id}", exist_ok=True)
    with open(approval_file, 'w') as f:
        f.write("approved")
    return {"run_id": run_id, "status": "approved"}


@router.get("/runs/{run_id}/script")
async def get_run_script(run_id: int):
    """Get the narration script for a run."""
    import os, json
    ts_path = f"output/run_{run_id}/word_timestamps.json"
    narr_dir = f"output/run_{run_id}/narration"
    
    # Try word_timestamps first
    if os.path.exists(ts_path):
        with open(ts_path) as f:
            words = json.load(f)
        lines = {}
        for w in words:
            lines.setdefault(w.get("line", 0), []).append(w["word"])
        narration = [" ".join(v) for k, v in sorted(lines.items())]
        return {"run_id": run_id, "narration": narration, "status": "generated"}
    
    # Try concept_json from content_bank
    from sqlalchemy import text
    from packages.clients.db import async_session
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cb.concept_json FROM content_runs cr 
                    JOIN content_bank cb ON cb.id = cr.content_bank_id 
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()
    
    if row and row[0]:
        concept = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        narration = concept.get("narration", [])
        if narration:
            return {"run_id": run_id, "narration": narration, "status": "from_concept"}
    
    return {"run_id": run_id, "narration": [], "status": "not_found"}


@router.post("/runs/{run_id}/script/approve")
async def approve_run_script(run_id: int):
    """Approve the script — continue to image generation."""
    from sqlalchemy import text
    from packages.clients.db import async_session
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET current_step = 'script approved' WHERE id = :id"),
            {"id": run_id},
        )
        await session.commit()
    return {"run_id": run_id, "status": "approved"}


@router.post("/runs/{run_id}/script/edit")
async def edit_run_script(run_id: int, narration: list[str] = None):
    """Replace the narration lines and re-approve."""
    import os, json
    from sqlalchemy import text
    from packages.clients.db import async_session
    
    if not narration:
        return {"error": "No narration provided"}
    
    # Update the concept_json in content_bank
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT cb.id, cb.concept_json FROM content_runs cr 
                    JOIN content_bank cb ON cb.id = cr.content_bank_id 
                    WHERE cr.id = :id"""),
            {"id": run_id},
        )
        row = result.fetchone()
        if row:
            concept = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            concept["narration"] = narration
            await session.execute(
                text("UPDATE content_bank SET concept_json = :cj WHERE id = :id"),
                {"id": row[0], "cj": json.dumps(concept)},
            )
            await session.commit()
    
    # Clear old narration files so they regenerate
    narr_dir = f"output/run_{run_id}/narration"
    if os.path.isdir(narr_dir):
        for f in os.listdir(narr_dir):
            os.remove(os.path.join(narr_dir, f))
    
    # Also clear word_timestamps
    ts_path = f"output/run_{run_id}/word_timestamps.json"
    if os.path.exists(ts_path):
        os.remove(ts_path)
    
    return {"run_id": run_id, "status": "script updated", "lines": len(narration)}
