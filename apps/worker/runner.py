"""Content generation worker — polls content_bank and runs video pipeline."""

import asyncio
import json
import os
import sys

import structlog
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from packages.clients.db import get_engine
from packages.clients.workflow_state import (
    append_run_event,
    ensure_concept,
    ensure_run_bundle,
    get_latest_rendered_asset,
    update_concept_status,
    update_run_manifest,
)
from packages.prompts.concept_drafts import KIDS_CHANNELS

load_dotenv(override=True)
logger = structlog.get_logger()

POLL_INTERVAL = 10  # seconds between polls (faster claim cycle)
MAX_PARALLEL = 2  # max concurrent videos — reduced from 10 to prevent OOM (exit 137)
WORKER_ID = f"worker-{os.getpid()}"

_active_tasks: set = set()  # track running generation tasks
_active_bank_ids: set[int] = set()  # prevent this process from double-claiming one bank item

ACTIVE_RUN_STATUSES = ("running", "blocked", "pending_review")
CHANNEL_BUSY_RUN_STATUSES = ("running", "blocked")


def _get_engine():
    return get_engine()


async def run_generation_loop():
    """Main worker loop — poll content_bank and run up to MAX_PARALLEL generations."""
    logger.info("generation worker started", worker_id=WORKER_ID, max_parallel=MAX_PARALLEL)

    while True:
        try:
            # Clean up finished tasks
            done = {t for t in _active_tasks if t.done()}
            for t in done:
                _active_tasks.discard(t)
                bank_id = getattr(t, "_bank_id", None)
                if bank_id is not None:
                    _active_bank_ids.discard(bank_id)
                if t.exception():
                    logger.error("generation task error", error=str(t.exception())[:200])

            # Start new tasks if we have capacity
            slots = MAX_PARALLEL - len(_active_tasks)
            for _ in range(slots):
                item = await _claim_next_item(exclude_bank_ids=_active_bank_ids)
                if item is None:
                    break
                task = asyncio.create_task(_generate_item(item))
                task._bank_id = item["bank_id"]
                _active_tasks.add(task)
                _active_bank_ids.add(item["bank_id"])

            if _active_tasks:
                logger.info("generation status", active=len(_active_tasks), slots_free=MAX_PARALLEL - len(_active_tasks))
        except Exception as e:
            logger.error("generation loop error", error=str(e)[:200])
        await asyncio.sleep(POLL_INTERVAL)


async def _claim_next_item(exclude_bank_ids: set[int] | None = None) -> dict | None:
    """Find and claim the next queued item. Returns item dict or None."""
    engine = _get_engine()
    async with AsyncSession(engine) as s:
        exclude_clause = ""
        if exclude_bank_ids:
            exclude_ids = ", ".join(str(int(bank_id)) for bank_id in sorted(exclude_bank_ids))
            exclude_clause = f"AND cb.id NOT IN ({exclude_ids})"

        # Find next queued item, respecting channel pause.
        # Skip channels that already have something generating.
        # Also skip bank items that already have a live run even if some other path
        # incorrectly flipped the content_bank row back to queued.
        # FOR UPDATE SKIP LOCKED on cb prevents two concurrent claimers from
        # both selecting the same row before either commits the status change.
        result = await s.execute(text("""
            SELECT cb.id, cb.channel_id, cb.title, cb.concept_json, cb.attempt_count,
                   c.name as channel_name, cb.concept_id, cb.form_type
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            LEFT JOIN channel_schedules cs ON cs.channel_id = cb.channel_id
            WHERE cb.status = 'queued'
            AND (cs.paused IS NULL OR cs.paused = false)
            AND NOT EXISTS (
                SELECT 1
                FROM content_runs cr_active
                WHERE cr_active.content_bank_id = cb.id
                  AND cr_active.status IN ('running', 'blocked', 'pending_review')
            )
            AND cb.channel_id NOT IN (
                SELECT DISTINCT channel_id FROM content_bank WHERE status IN ('locked', 'generating')
                UNION
                SELECT DISTINCT channel_id FROM content_runs WHERE status IN ('running', 'blocked')
            )
            """ + exclude_clause + """
            ORDER BY cb.priority ASC, cb.created_at ASC
            LIMIT 1
            FOR UPDATE OF cb SKIP LOCKED
        """))
        row = result.fetchone()

        if not row:
            return None

        bank_id, channel_id, title, concept_json, attempt_count, channel_name, concept_id, form_type = row

        # Claim the item (optimistic lock — second layer of protection).
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
        "channel_name": channel_name, "concept_id": concept_id, "form_type": form_type or "short",
    }


async def _generate_item(item: dict):
    """Generate a single content bank item end-to-end."""
    bank_id = item["bank_id"]
    channel_id = item["channel_id"]
    title = item["title"]
    attempt_count = item["attempt_count"] or 0
    concept_id = item.get("concept_id")
    form_type = item.get("form_type") or "short"
    concept_raw = item["concept_json"]
    if not concept_raw:
        raise ValueError(f"Missing concept JSON for content bank #{bank_id}")
    concept = json.loads(concept_raw) if isinstance(concept_raw, str) else concept_raw
    if concept_id and isinstance(concept, dict):
        concept.setdefault("concept_id", concept_id)

    engine = _get_engine()

    # Create content_runs row
    async with AsyncSession(engine) as s:
        bank_row = (
            await s.execute(
                text(
                    """
                    SELECT status, run_id
                    FROM content_bank
                    WHERE id = :id
                    FOR UPDATE
                    """
                ),
                {"id": bank_id},
            )
        ).fetchone()
        if not bank_row:
            raise ValueError(f"Missing content_bank row #{bank_id}")

        active_row = (
            await s.execute(
                text(
                    """
                    SELECT id, status
                    FROM content_runs
                    WHERE content_bank_id = :bid
                      AND status IN ('running', 'blocked', 'pending_review')
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"bid": bank_id},
            )
        ).fetchone()
        if active_row:
            active_run_id, active_status = active_row
            await s.execute(
                text(
                    """
                    UPDATE content_bank
                    SET status = CASE
                            WHEN :active_status IN ('running', 'blocked') THEN 'generating'
                            ELSE status
                        END,
                        run_id = :rid
                    WHERE id = :id
                    """
                ),
                {"id": bank_id, "rid": active_run_id, "active_status": active_status},
            )
            await s.commit()
            logger.warning(
                "duplicate claim suppressed before run creation",
                bank_id=bank_id,
                existing_run_id=active_run_id,
                existing_status=active_status,
                bank_status=bank_row[0],
            )
            return

        if bank_row[0] != "locked":
            await s.commit()
            logger.warning(
                "skipping generation start because bank is no longer locked",
                bank_id=bank_id,
                bank_status=bank_row[0],
                bank_run_id=bank_row[1],
            )
            return

        if not concept_id:
            concept_id = await ensure_concept(
                channel_id=channel_id,
                title=title,
                concept_json=concept,
                origin="manual",
                status="running",
                form_type=form_type,
                content_bank_id=bank_id,
                session=s,
            )
        try:
            result = await s.execute(text("""
                INSERT INTO content_runs (channel_id, status, content_type, content_bank_id, concept_id, pipeline_type, trigger_type, started_at)
                VALUES (:cid, 'running', :content_type, :bank_id, :concept_id, 'deity', 'scheduler', NOW())
                RETURNING id
            """), {"cid": channel_id, "bank_id": bank_id, "content_type": form_type, "concept_id": concept_id})
        except IntegrityError:
            await s.rollback()
            async with AsyncSession(engine) as s2:
                active_row = (
                    await s2.execute(
                        text(
                            """
                            SELECT id, status
                            FROM content_runs
                            WHERE content_bank_id = :bid
                              AND status IN ('running', 'blocked', 'pending_review')
                            ORDER BY id DESC
                            LIMIT 1
                            """
                        ),
                        {"bid": bank_id},
                    )
                ).fetchone()
                if active_row:
                    await s2.execute(
                        text(
                            """
                            UPDATE content_bank
                            SET status = CASE
                                    WHEN :active_status IN ('running', 'blocked') THEN 'generating'
                                    ELSE status
                                END,
                                run_id = :rid
                            WHERE id = :id
                            """
                        ),
                        {"id": bank_id, "rid": active_row[0], "active_status": active_row[1]},
                    )
                    await s2.commit()
                    logger.warning(
                        "duplicate run prevented by active-run guard",
                        bank_id=bank_id,
                        existing_run_id=active_row[0],
                        existing_status=active_row[1],
                    )
                    return
            raise
        run_id = result.scalar_one()

        await s.execute(text("""
            UPDATE content_bank SET status = 'generating', run_id = :rid WHERE id = :id
        """), {"rid": run_id, "id": bank_id})
        await ensure_concept(
            channel_id=channel_id,
            title=title,
            concept_json=concept,
            origin="manual",
            status="running",
            form_type=form_type,
            concept_id=concept_id,
            content_bank_id=bank_id,
            run_id=run_id,
            session=s,
        )
        await s.commit()

    await ensure_run_bundle(
        run_id,
        concept=concept,
        channel_id=channel_id,
        pipeline_mode="default",
        trigger_type="scheduler",
        stage="queued",
        status="running",
    )
    await append_run_event(
        run_id,
        event_type="run_started",
        message=f"Started generation for {title}",
        stage="queued",
        data={"bank_id": bank_id, "concept_id": concept_id, "channel_id": channel_id},
    )

    # Reuse ONLY narration from previous failed attempts.
    # Visual artifacts from failed runs are too often stale after prompt/model/builder
    # changes and can silently poison a "fresh" retry.
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
            # Skip runs with no useful reusable narration
            has_content = (
                os.path.isdir(os.path.join(prev_dir, "narration"))
                and bool(os.listdir(os.path.join(prev_dir, "narration")))
            )
            if not has_content:
                continue  # try older run

            # Only narration is safe to reuse across failed retries.
            copied_something = False
            for subdir in ["narration"]:
                src = os.path.join(prev_dir, subdir)
                dst = os.path.join(new_dir, subdir)
                if os.path.isdir(src) and not os.path.isdir(dst):
                    try:
                        shutil.copytree(src, dst)
                        logger.info("reused files from previous run", prev_run=prev_id, subdir=subdir)
                        copied_something = True
                    except Exception as copy_err:
                        logger.warning("failed to reuse files, will regenerate", error=str(copy_err)[:100])
            for fname in ["concept.json"]:
                src_file = os.path.join(prev_dir, fname)
                dst_file = os.path.join(new_dir, fname)
                if os.path.exists(src_file) and not os.path.exists(dst_file):
                    try:
                        import shutil as _sh
                        _sh.copy2(src_file, dst_file)
                        logger.info("reused file from previous run", prev_run=prev_id, file=fname)
                    except Exception:
                        pass
            if copied_something:
                break  # found a good run to copy from

    logger.info("starting generation", run_id=run_id, bank_id=bank_id, title=title)
    await update_run_manifest(run_id, {"bank_id": bank_id, "concept_id": concept_id, "title": title})

    try:
        # Global timeout: 15 min for shorts, 30 min for long-form
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        pipeline_timeout = 7200  # 2 hours — includes time waiting for user image approval

        # Spawn pipeline as a subprocess — can be killed cleanly on timeout.
        # start_new_session=True detaches the child from this worker's process group,
        # so a hot-reload that SIGTERMs the worker does NOT kill in-flight pipelines.
        # stdout/stderr go to log files instead of parent pipes for the same reason —
        # if the parent dies, the child keeps writing to the file rather than dying on SIGPIPE.
        concept_json_str = json.dumps(concept)
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        log_dir = os.path.join(project_root, "output", f"run_{run_id}")
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, "pipeline.stdout.log")
        stderr_path = os.path.join(log_dir, "pipeline.stderr.log")
        cmd = [
            sys.executable, "-m", "apps.worker.pipeline_runner",
            "--run-id", str(run_id),
            "--concept", concept_json_str,
        ]

        stdout_file = open(stdout_path, "wb")
        stderr_file = open(stderr_path, "wb")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=stdout_file,
            stderr=stderr_file,
            cwd=project_root,
            start_new_session=True,
        )

        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=pipeline_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            stdout_file.close()
            stderr_file.close()
            # Force-update DB since the subprocess was killed
            async with AsyncSession(engine) as s:
                await s.execute(text(
                    "UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id AND status = 'running'"
                ), {"err": f"Pipeline timed out after {pipeline_timeout}s", "id": run_id})
                if concept_id:
                    await update_concept_status(concept_id, status="failed", latest_run_id=run_id, session=s)
                await s.commit()
            await append_run_event(
                run_id,
                event_type="run_failed",
                message=f"Pipeline timed out after {pipeline_timeout}s",
                stage="timeout",
                level="error",
            )
            raise RuntimeError(f"Pipeline timed out after {pipeline_timeout}s")
        finally:
            try: stdout_file.close()
            except Exception: pass
            try: stderr_file.close()
            except Exception: pass

        if process.returncode != 0:
            # Read the tail of the stderr log file for the error message
            try:
                with open(stderr_path, "rb") as _f:
                    _f.seek(0, 2)  # end
                    size = _f.tell()
                    _f.seek(max(0, size - 2000))
                    error_msg = _f.read().decode(errors="replace")[-500:]
            except Exception:
                error_msg = "Unknown error"
            if not error_msg.strip():
                error_msg = "Unknown error"
            # Force-update DB in case pipeline didn't
            async with AsyncSession(engine) as s:
                await s.execute(text(
                    "UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id AND status = 'running'"
                ), {"err": error_msg[-300:], "id": run_id})
                if concept_id:
                    await update_concept_status(concept_id, status="failed", latest_run_id=run_id, session=s)
                await s.commit()
            await append_run_event(
                run_id,
                event_type="run_failed",
                message=error_msg[-300:],
                stage="subprocess",
                level="error",
            )
            raise RuntimeError(f"Pipeline failed: {error_msg}")

        # Check if pipeline internally marked itself as failed
        async with AsyncSession(engine) as s:
            status_row = await s.execute(text(
                "SELECT status FROM content_runs WHERE id = :id"
            ), {"id": run_id})
            run_status = status_row.scalar()
        if run_status == 'failed':
            raise RuntimeError("Pipeline marked itself as failed")

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
            if concept_id:
                await update_concept_status(concept_id, status="ready", latest_run_id=run_id, session=s)
            await s.commit()

        logger.info("generation complete", run_id=run_id, bank_id=bank_id, title=title)
        await append_run_event(
            run_id,
            event_type="run_ready",
            message="Video generated and ready for review",
            stage="pending_review",
            data={"video_path": video_path},
        )
        await update_run_manifest(run_id, {"status": "pending_review", "stage": "pending_review", "final_video": video_path})
        await _maybe_auto_upload(engine, run_id, channel_id, concept)

    except Exception as e:
        logger.error("generation failed", run_id=run_id, bank_id=bank_id, error=str(e)[:300])

        async with AsyncSession(engine) as s:
            # Only requeue/fail if THIS run is still the one bound to the bank.
            # If another run has already taken over (race from an earlier duplicate claim),
            # leave the bank alone so we don't yank it out from under the live run.
            owner_check = await s.execute(text("""
                SELECT run_id FROM content_bank WHERE id = :id
            """), {"id": bank_id})
            owner = owner_check.scalar_one_or_none()
            if owner is not None and owner != run_id:
                logger.info(
                    "skipping requeue — another run owns this bank",
                    bank_id=bank_id, dead_run=run_id, live_run=owner,
                )
                return

            new_attempt = attempt_count + 1
            if new_attempt < 3:
                await s.execute(text("""
                    UPDATE content_bank
                    SET status = 'queued', locked_at = NULL, error = :err, attempt_count = :ac
                    WHERE id = :id
                """), {"id": bank_id, "err": str(e)[:500], "ac": new_attempt})
                if concept_id:
                    await update_concept_status(concept_id, status="queued", latest_run_id=run_id, session=s)
            else:
                await s.execute(text("""
                    UPDATE content_bank SET status = 'failed', error = :err, attempt_count = :ac
                    WHERE id = :id
                """), {"id": bank_id, "err": str(e)[:500], "ac": new_attempt})
                if concept_id:
                    await update_concept_status(concept_id, status="failed", latest_run_id=run_id, session=s)
            await s.commit()
        await append_run_event(
            run_id,
            event_type="run_failed",
            message=str(e)[:300],
            stage="worker",
            level="error",
            data={"attempt_count": attempt_count + 1},
        )
        await update_run_manifest(run_id, {"status": "failed", "error": str(e)[:300]})


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
    asset_info = await get_latest_rendered_asset(run_id)
    if not asset_info:
        logger.warning("no rendered video found for auto-upload", run_id=run_id)
        return

    _, asset = asset_info
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
            privacy_status=privacy if privacy != "scheduled" else "private",
            youtube_token_file=token_file,
            made_for_kids=False,
            publish_at=publish_at_iso,
        ))

        if result.get("published"):
            async with AsyncSession(engine) as s:
                concept_id = (
                    await s.execute(text("SELECT concept_id FROM content_runs WHERE id = :id"), {"id": run_id})
                ).scalar_one_or_none()
                await s.execute(text("""
                    UPDATE content_bank SET status = 'uploaded' WHERE run_id = :rid
                """), {"rid": run_id})
                await s.execute(text("""
                    UPDATE content_runs
                    SET status = 'published',
                        current_step = 'published',
                        completed_at = COALESCE(completed_at, NOW())
                    WHERE id = :rid
                """), {"rid": run_id})
                await s.execute(text("""
                    INSERT INTO assets (run_id, channel_id, asset_type, content)
                    VALUES (:rid, :cid, 'publish_result', :content)
                """), {
                    "rid": run_id, "cid": channel_id,
                    "content": json.dumps({**result, "publish_at": publish_at_iso}),
                })
                if concept_id:
                    await update_concept_status(concept_id, status="published", latest_run_id=run_id, published_run_id=run_id, session=s)
                await s.commit()

            await append_run_event(
                run_id,
                event_type="publish_succeeded",
                message="Auto-upload succeeded",
                stage="publish",
                data={"url": result.get("url"), "publish_at": publish_at_iso},
            )
            await update_run_manifest(run_id, {"status": "published", "publish_result": {**result, "publish_at": publish_at_iso}})
            logger.info("auto-uploaded, YouTube will publish at",
                        run_id=run_id, url=result.get("url"),
                        publish_at=publish_at_iso)
        else:
            logger.warning("auto-upload failed", run_id=run_id, result=result)
            await append_run_event(
                run_id,
                event_type="publish_failed",
                message="Auto-upload did not return a published result",
                stage="publish",
                level="warning",
                data=result,
            )

    except Exception as e:
        logger.error("auto-upload error", run_id=run_id, error=str(e)[:200])
        await append_run_event(
            run_id,
            event_type="publish_failed",
            message=str(e)[:200],
            stage="publish",
            level="error",
        )
