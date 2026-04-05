"""Content generation worker — polls content_bank and runs video pipeline."""

import asyncio
import json
import os

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

POLL_INTERVAL = 30  # seconds between polls
MAX_PARALLEL = 5  # max concurrent generations
WORKER_ID = f"worker-{os.getpid()}"

_active_tasks: set = set()  # track running generation tasks


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=5, max_overflow=3)


async def run_generation_loop():
    """Main worker loop — poll content_bank and run up to MAX_PARALLEL generations."""
    logger.info("generation worker started", worker_id=WORKER_ID, max_parallel=MAX_PARALLEL)

    while True:
        try:
            # Clean up finished tasks
            done = {t for t in _active_tasks if t.done()}
            for t in done:
                _active_tasks.discard(t)
                if t.exception():
                    logger.error("generation task error", error=str(t.exception())[:200])

            # Start new tasks if we have capacity
            slots = MAX_PARALLEL - len(_active_tasks)
            for _ in range(slots):
                item = await _claim_next_item()
                if item is None:
                    break
                task = asyncio.create_task(_generate_item(item))
                _active_tasks.add(task)

            if _active_tasks:
                logger.info("generation status", active=len(_active_tasks), slots_free=MAX_PARALLEL - len(_active_tasks))
        except Exception as e:
            logger.error("generation loop error", error=str(e)[:200])
        await asyncio.sleep(POLL_INTERVAL)


async def _claim_next_item() -> dict | None:
    """Find and claim the next queued item. Returns item dict or None."""
    engine = _get_engine()
    try:
        async with AsyncSession(engine) as s:
            # Find next queued item, respecting channel pause
            # Skip channels that already have something generating
            result = await s.execute(text("""
                SELECT cb.id, cb.channel_id, cb.title, cb.concept_json, cb.attempt_count,
                       c.name as channel_name
                FROM content_bank cb
                JOIN channels c ON c.id = cb.channel_id
                LEFT JOIN channel_schedules cs ON cs.channel_id = cb.channel_id
                WHERE cb.status = 'queued'
                AND (cs.paused IS NULL OR cs.paused = false)
                AND cb.channel_id NOT IN (
                    SELECT DISTINCT channel_id FROM content_bank WHERE status IN ('locked', 'generating')
                )
                ORDER BY cb.priority ASC, cb.created_at ASC
                LIMIT 1
            """))
            row = result.fetchone()

            if not row:
                return None

            bank_id, channel_id, title, concept_json, attempt_count, channel_name = row

            # Claim the item (optimistic lock)
            claimed = await s.execute(text("""
                UPDATE content_bank
                SET status = 'locked', locked_at = NOW()
                WHERE id = :id AND status = 'queued'
                RETURNING id
            """), {"id": bank_id})
            if not claimed.fetchone():
                return None
            await s.commit()

        logger.info("claimed content", bank_id=bank_id, channel=channel_name, title=title)
        return {
            "bank_id": bank_id, "channel_id": channel_id, "title": title,
            "concept_json": concept_json, "attempt_count": attempt_count,
            "channel_name": channel_name,
        }
    finally:
        await engine.dispose()


async def _generate_item(item: dict):
    """Generate a single content bank item end-to-end."""
    bank_id = item["bank_id"]
    channel_id = item["channel_id"]
    title = item["title"]
    attempt_count = item["attempt_count"] or 0
    concept_raw = item["concept_json"]
    if not concept_raw:
        raise ValueError(f"Missing concept JSON for content bank #{bank_id}")
    concept = json.loads(concept_raw) if isinstance(concept_raw, str) else concept_raw

    engine = _get_engine()
    try:
        # Create content_runs row
        async with AsyncSession(engine) as s:
            result = await s.execute(text("""
                INSERT INTO content_runs (channel_id, status, content_type, content_bank_id, pipeline_type, started_at)
                VALUES (:cid, 'running', 'deity', :bank_id, 'deity', NOW())
                RETURNING id
            """), {"cid": channel_id, "bank_id": bank_id})
            run_id = result.scalar_one()

            await s.execute(text("""
                UPDATE content_bank SET status = 'generating', run_id = :rid WHERE id = :id
            """), {"rid": run_id, "id": bank_id})
            await s.commit()

        # Reuse files from previous failed attempt if they exist
        prev_run_ids = []
        async with AsyncSession(engine) as s:
            r = await s.execute(text("""
                SELECT id FROM content_runs
                WHERE content_bank_id = :bid AND id != :rid AND status = 'failed'
                ORDER BY id DESC
            """), {"bid": bank_id, "rid": run_id})
            prev_run_ids = [row[0] for row in r.fetchall()]

        if prev_run_ids:
            import shutil
            new_dir = f"output/run_{run_id}"
            for prev_id in prev_run_ids:
                # Check both old and new directory naming
                prev_dir = None
                for prefix in ["run_", "deity_run_", "unified_run_"]:
                    p = f"output/{prefix}{prev_id}"
                    if os.path.isdir(p):
                        prev_dir = p
                        break
                if not prev_dir:
                    continue
                # Copy narration, images, and clips from previous run
                for subdir in ["narration", "images", "clips"]:
                    src = os.path.join(prev_dir, subdir)
                    dst = os.path.join(new_dir, subdir)
                    if os.path.isdir(src) and not os.path.isdir(dst):
                        try:
                            shutil.copytree(src, dst)
                            logger.info("reused files from previous run", prev_run=prev_id, subdir=subdir)
                        except Exception as copy_err:
                            logger.warning("failed to reuse files, will regenerate", error=str(copy_err)[:100])
                break  # only copy from the most recent previous run

        logger.info("starting generation", run_id=run_id, bank_id=bank_id, title=title)

        try:
            from apps.orchestrator.deity_pipeline import run_deity_pipeline
            # Global timeout: 60 min for shorts, 180 min for long-form
            is_long = (
                concept.get("long_form", False)
                or len(concept.get("narration", [])) >= 20
                or len(concept.get("beats", [])) >= 20
            )
            pipeline_timeout = 10800 if is_long else 3600
            await asyncio.wait_for(run_deity_pipeline(run_id, concept), timeout=pipeline_timeout)

            # Verify the video file actually exists before marking as generated
            video_path = None
            for prefix in ["run_", "deity_run_", "unified_run_"]:
                p = f"output/{prefix}{run_id}/final.mp4"
                if os.path.exists(p):
                    video_path = p
                    break
            if not video_path:
                raise RuntimeError(f"Pipeline completed but no video file found for run {run_id}")

            async with AsyncSession(engine) as s:
                await s.execute(text("""
                    UPDATE content_bank SET status = 'generated' WHERE id = :id
                """), {"id": bank_id})
                await s.commit()

            logger.info("generation complete", run_id=run_id, bank_id=bank_id, title=title)
            await _maybe_auto_upload(engine, run_id, channel_id, concept)

        except Exception as e:
            logger.error("generation failed", run_id=run_id, bank_id=bank_id, error=str(e)[:300])

            async with AsyncSession(engine) as s:
                new_attempt = attempt_count + 1
                if new_attempt < 3:
                    await s.execute(text("""
                        UPDATE content_bank
                        SET status = 'queued', locked_at = NULL, error = :err, attempt_count = :ac
                        WHERE id = :id
                    """), {"id": bank_id, "err": str(e)[:500], "ac": new_attempt})
                else:
                    await s.execute(text("""
                        UPDATE content_bank SET status = 'failed', error = :err, attempt_count = :ac
                        WHERE id = :id
                    """), {"id": bank_id, "err": str(e)[:500], "ac": new_attempt})
                await s.commit()

    finally:
        await engine.dispose()


async def _maybe_auto_upload(engine, run_id: int, channel_id: int, concept: dict):
    """Upload video if channel has auto_upload enabled."""
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT auto_upload, upload_privacy FROM channel_schedules
            WHERE channel_id = :cid
        """), {"cid": channel_id})
        row = result.fetchone()

    if not row or not row[0]:  # no schedule or auto_upload=false
        return

    privacy = row[1] or "private"

    # Find the rendered video path
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT content FROM assets
            WHERE run_id = :rid AND asset_type = 'rendered_unified_short'
            LIMIT 1
        """), {"rid": run_id})
        asset_row = result.fetchone()

    if not asset_row:
        logger.warning("no rendered video found for auto-upload", run_id=run_id)
        return

    asset = json.loads(asset_row[0]) if isinstance(asset_row[0], str) else asset_row[0]
    video_path = asset.get("path")
    if not video_path or not os.path.exists(video_path):
        logger.warning("video file not found", run_id=run_id, path=video_path)
        return

    # Find channel name for token file
    async with AsyncSession(engine) as s:
        result = await s.execute(text("SELECT name FROM channels WHERE id = :id"), {"id": channel_id})
        channel_name = result.scalar()

    # Derive token file name
    token_name = channel_name.lower().replace(" ", "").replace("'", "").replace("'", "")
    token_file = f"youtube_token_{token_name}.json"

    if not os.path.exists(token_file):
        logger.warning("token file not found, skipping auto-upload", token_file=token_file)
        return

    # Get publish metadata
    title = concept.get("title", "Untitled")
    description = concept.get("caption", "")
    tags = concept.get("tags", [])

    try:
        from apps.publishing_service.uploader import upload_video
        import random
        from datetime import datetime, timezone, timedelta

        # Schedule to go public 1-3 hours from now, rounded to :X0 or :X5
        public_delay = random.randint(3600, 10800)
        publish_time = datetime.now(timezone.utc) + timedelta(seconds=public_delay)
        # Round minutes to nearest 5
        minute = publish_time.minute
        rounded_minute = (minute // 5) * 5
        publish_time = publish_time.replace(minute=rounded_minute, second=0, microsecond=0)
        publish_at_iso = publish_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        import asyncio as _aio
        loop = _aio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category="Entertainment",
            privacy_status="private",
            youtube_token_file=token_file,
            made_for_kids=False,
            publish_at=publish_at_iso,
        ))

        if result.get("published"):
            async with AsyncSession(engine) as s:
                await s.execute(text("""
                    UPDATE content_bank SET status = 'uploaded' WHERE run_id = :rid
                """), {"rid": run_id})
                await s.execute(text("""
                    INSERT INTO assets (run_id, channel_id, asset_type, content)
                    VALUES (:rid, :cid, 'publish_result', :content)
                """), {
                    "rid": run_id, "cid": channel_id,
                    "content": json.dumps({**result, "publish_at": publish_at_iso}),
                })
                await s.commit()

            logger.info("auto-uploaded, YouTube will publish at",
                        run_id=run_id, url=result.get("url"),
                        publish_at=publish_at_iso)
        else:
            logger.warning("auto-upload failed", run_id=run_id, result=result)

    except Exception as e:
        logger.error("auto-upload error", run_id=run_id, error=str(e)[:200])
