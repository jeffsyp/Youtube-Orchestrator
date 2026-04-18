"""Cleanup old run artifacts to save disk space.

Keeps final.mp4 for recently uploaded videos (configurable retention).
Deletes everything else — narration, images, clips, segments.
"""

import asyncio
import os
import shutil
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

CLEANUP_INTERVAL = 3600 * 6  # run every 6 hours
KEEP_FINAL_DAYS = 7  # keep run directory for 7 days after upload
DELETE_ARTIFACTS_DAYS = 1  # delete narration/images/clips after 1 day for uploaded videos

import json as _json
import re as _re

def _safe_filename(s):
    s = _re.sub(r'[^\w\s-]', '', s).strip()
    return _re.sub(r'[\s]+', ' ', s)[:80]


async def _copy_to_channel_folder(session, run_id):
    """Copy final.mp4 to output/videos/{channel}/{title}.mp4"""
    r = await session.execute(text("""
        SELECT c.name, a.content FROM content_runs cr
        JOIN channels c ON c.id = cr.channel_id
        LEFT JOIN assets a ON a.run_id = cr.id AND a.asset_type = 'publish_metadata'
        WHERE cr.id = :rid
    """), {"rid": run_id})
    row = r.fetchone()
    if not row:
        return
    channel_name, meta_json = row
    title = "Untitled"
    if meta_json:
        meta = _json.loads(meta_json) if isinstance(meta_json, str) else meta_json
        title = meta.get("title", "Untitled")

    for prefix in ["run_", "unified_run_", "deity_run_"]:
        src = f"output/{prefix}{run_id}/final.mp4"
        if os.path.exists(src):
            dest_dir = os.path.join("output", "videos", _safe_filename(channel_name))
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, f"{_safe_filename(title)}.mp4")
            if not os.path.exists(dest):
                import shutil
                shutil.copy2(src, dest)
                logger.info("copied to channel folder", dest=dest)
            break


async def _has_channel_copy(session, run_id) -> bool:
    """Check if the video has been copied to the channel folder."""
    r = await session.execute(text("""
        SELECT c.name, a.content FROM content_runs cr
        JOIN channels c ON c.id = cr.channel_id
        LEFT JOIN assets a ON a.run_id = cr.id AND a.asset_type = 'publish_metadata'
        WHERE cr.id = :rid
    """), {"rid": run_id})
    row = r.fetchone()
    if not row:
        return False
    channel_name, meta_json = row
    title = "Untitled"
    if meta_json:
        meta = _json.loads(meta_json) if isinstance(meta_json, str) else meta_json
        title = meta.get("title", "Untitled")
    dest = os.path.join("output", "videos", _safe_filename(channel_name), f"{_safe_filename(title)}.mp4")
    return os.path.isfile(dest)


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=1, max_overflow=0)


async def run_cleanup_loop():
    """Periodic cleanup of old artifacts."""
    logger.info("cleanup worker started", interval_hours=CLEANUP_INTERVAL // 3600)
    # Wait a bit before first cleanup so other workers start first
    await asyncio.sleep(60)
    while True:
        try:
            await _cleanup_cycle()
        except Exception as e:
            logger.error("cleanup error", error=str(e)[:200])
        await asyncio.sleep(CLEANUP_INTERVAL)


async def _cleanup_cycle():
    """One cleanup cycle."""
    engine = _get_engine()
    freed = 0
    try:
        async with AsyncSession(engine) as s:
            now = datetime.now(timezone.utc)

            # 0. Copy ALL completed videos to channel folders first
            result = await s.execute(text("""
                SELECT cr.id FROM content_runs cr
                WHERE cr.status IN ('pending_review', 'published')
            """))
            for (run_id,) in result.fetchall():
                await _copy_to_channel_folder(s, run_id)

            # 1. For uploaded videos older than 1 day — delete artifacts but keep final.mp4
            cutoff_artifacts = now - timedelta(days=DELETE_ARTIFACTS_DAYS)
            result = await s.execute(text("""
                SELECT cr.id FROM content_runs cr
                JOIN content_bank cb ON cb.run_id = cr.id
                WHERE cb.status = 'uploaded'
                AND cr.completed_at < :cutoff
                AND cr.completed_at IS NOT NULL
            """), {"cutoff": cutoff_artifacts})

            for (run_id,) in result.fetchall():
                for prefix in ["run_", "unified_run_", "deity_run_"]:
                    run_dir = f"output/{prefix}{run_id}"
                    if not os.path.isdir(run_dir):
                        continue
                    # Delete sub-directories (narration, images, clips, segments, normalized)
                    for subdir in ["narration", "images", "clips", "segments", "normalized", "mixed"]:
                        sub_path = os.path.join(run_dir, subdir)
                        if os.path.isdir(sub_path):
                            size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(sub_path) for f in fns)
                            shutil.rmtree(sub_path)
                            freed += size
                    # Delete intermediate files (raw_concat, subs.ass, concat_list, etc)
                    for fname in os.listdir(run_dir):
                        fpath = os.path.join(run_dir, fname)
                        if os.path.isfile(fpath) and fname != "final.mp4":
                            freed += os.path.getsize(fpath)
                            os.remove(fpath)

            # 2. For uploaded videos older than 7 days — delete run dir only if channel folder copy exists
            cutoff_final = now - timedelta(days=KEEP_FINAL_DAYS)
            result = await s.execute(text("""
                SELECT cr.id FROM content_runs cr
                JOIN content_bank cb ON cb.run_id = cr.id
                WHERE cb.status = 'uploaded'
                AND cr.completed_at < :cutoff
                AND cr.completed_at IS NOT NULL
            """), {"cutoff": cutoff_final})

            for (run_id,) in result.fetchall():
                # Verify channel folder copy exists before deleting
                await _copy_to_channel_folder(s, run_id)
                has_channel_copy = await _has_channel_copy(s, run_id)
                if not has_channel_copy:
                    logger.warning("skipping run dir deletion — no channel folder copy", run_id=run_id)
                    continue
                for prefix in ["run_", "unified_run_", "deity_run_"]:
                    run_dir = f"output/{prefix}{run_id}"
                    if os.path.isdir(run_dir):
                        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(run_dir) for f in fns)
                        shutil.rmtree(run_dir)
                        freed += size

            # 3. Delete failed run directories older than 1 day
            result = await s.execute(text("""
                SELECT id FROM content_runs
                WHERE status = 'failed'
                AND started_at < :cutoff
            """), {"cutoff": cutoff_artifacts})

            for (run_id,) in result.fetchall():
                for prefix in ["run_", "unified_run_", "deity_run_"]:
                    run_dir = f"output/{prefix}{run_id}"
                    if os.path.isdir(run_dir):
                        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(run_dir) for f in fns)
                        shutil.rmtree(run_dir)
                        freed += size

            # 4. Delete old unified_run directories that have no content_runs entry
            for dirname in os.listdir("output"):
                if not dirname.startswith(("run_", "unified_run_", "deity_run_")):
                    continue
                try:
                    run_id = int(dirname.split("_")[-1])
                except ValueError:
                    continue
                r = await s.execute(text("SELECT id FROM content_runs WHERE id = :id"), {"id": run_id})
                if not r.fetchone():
                    run_dir = os.path.join("output", dirname)
                    if os.path.isdir(run_dir):
                        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(run_dir) for f in fns)
                        shutil.rmtree(run_dir)
                        freed += size

        if freed > 0:
            logger.info("cleanup complete", freed_mb=round(freed / 1024 / 1024, 1))
        else:
            logger.info("cleanup complete — nothing to clean")

    finally:
        await engine.dispose()


async def run_now():
    """Run cleanup once immediately."""
    await _cleanup_cycle()


if __name__ == "__main__":
    asyncio.run(run_now())
