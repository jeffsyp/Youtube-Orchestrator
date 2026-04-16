"""Pipeline monitor agent — runs every 30 minutes to check and fix issues.

Uses Claude Opus 4.6 to diagnose and resolve pipeline problems.
Run with: uv run python -m apps.worker.monitor
"""

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta

import structlog
from anthropic import Anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from packages.clients.db import get_engine

load_dotenv()
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger()

MONITOR_INTERVAL = 1800  # 30 minutes
STUCK_THRESHOLD_MINUTES = 45  # default for short-form
STUCK_THRESHOLD_LONG_MINUTES = 120  # for long-form (20+ beats)
MAX_RETRIES = 3

# Steps that legitimately wait on human input — never auto-kill these.
# The pipeline subprocess is fine; the user just hasn't clicked yet.
HUMAN_WAIT_STEPS = {
    "images ready for review",
    "script ready for review",
    "pending_review",
}


def _get_engine():
    return get_engine()


async def run_monitor_loop():
    """Main monitor loop."""
    logger.info("pipeline monitor started", interval_min=MONITOR_INTERVAL // 60)
    while True:
        try:
            await _monitor_cycle()
        except Exception as e:
            logger.error("monitor cycle error", error=str(e)[:300])
        await asyncio.sleep(MONITOR_INTERVAL)


async def _monitor_cycle():
    """One monitoring cycle — check everything and fix what we can."""
    engine = _get_engine()
    issues = []
    actions_taken = []

    # 1. Check for stuck runs
    async with AsyncSession(engine) as s:
        # Use the shorter threshold to find candidates, then check individually
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        result = await s.execute(text("""
            SELECT cr.id, cr.channel_id, cr.current_step, cr.started_at, cr.content_bank_id,
                   cb.concept_json
            FROM content_runs cr
            LEFT JOIN content_bank cb ON cb.run_id = cr.id
            WHERE cr.status = 'running' AND cr.started_at < :cutoff
        """), {"cutoff": cutoff})
        stuck_candidates = result.fetchall()

    stuck_runs = []
    for run in stuck_candidates:
        run_id, channel_id, step, started_at, bank_id, concept_json = run
        elapsed = (datetime.now(timezone.utc) - started_at.replace(tzinfo=timezone.utc)).total_seconds() / 60

        # Skip human-in-loop steps — the pipeline is alive, waiting on user approval.
        # Auto-killing these destroys the user's review session.
        if step in HUMAN_WAIT_STEPS:
            continue

        # Determine threshold based on content type (long-form gets more time)
        threshold = STUCK_THRESHOLD_MINUTES
        if concept_json:
            try:
                concept = json.loads(concept_json) if isinstance(concept_json, str) else concept_json
                is_long = (
                    concept.get("long_form", False)
                    or len(concept.get("narration", [])) >= 20
                    or len(concept.get("beats", [])) >= 20
                )
                if is_long:
                    threshold = STUCK_THRESHOLD_LONG_MINUTES
            except (json.JSONDecodeError, TypeError):
                pass

        if elapsed >= threshold:
            stuck_runs.append((run_id, channel_id, step, started_at, bank_id))
            issues.append(f"Run #{run_id} stuck at '{step}' for {elapsed:.0f} minutes (threshold: {threshold}min)")

            # Auto-fix: mark as failed
            async with AsyncSession(engine) as s:
                await s.execute(text("""
                    UPDATE content_runs SET status = 'failed', error = :err WHERE id = :id AND status = 'running'
                """), {"id": run_id, "err": f"Monitor: stuck at {step} for {elapsed:.0f}min"})
                # Reset content_bank item for retry if applicable
                if bank_id:
                    await s.execute(text("""
                        UPDATE content_bank SET status = 'queued', locked_at = NULL,
                            error = 'Auto-retry after stuck run', attempt_count = attempt_count + 1
                        WHERE id = :id AND attempt_count < :max
                    """), {"id": bank_id, "max": MAX_RETRIES})
                await s.commit()

            actions_taken.append(f"Marked run #{run_id} as failed, reset content bank for retry")

    # 2. Check for failed runs that should be retried
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT cb.id, cb.title, cb.attempt_count, cb.error, c.name
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            WHERE cb.status = 'failed' AND cb.attempt_count < :max
        """), {"max": MAX_RETRIES})
        retryable = result.fetchall()

    for item in retryable:
        bank_id, title, attempts, error, channel = item
        issues.append(f"Content bank #{bank_id} '{title}' ({channel}) failed {attempts} times: {str(error)[:100]}")

        # Auto-fix: reset to queued for retry
        async with AsyncSession(engine) as s:
            await s.execute(text("""
                UPDATE content_bank SET status = 'queued', locked_at = NULL WHERE id = :id
            """), {"id": bank_id})
            await s.commit()

        actions_taken.append(f"Reset '{title}' for retry (attempt {attempts + 1})")

    # 2b. Check for orphaned locks (locked for >15 min with no running pipeline)
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT cb.id, cb.title, cb.locked_at
            FROM content_bank cb
            WHERE cb.status = 'locked'
            AND cb.locked_at < NOW() - INTERVAL '15 minutes'
        """))
        orphaned = result.fetchall()
        for bank_id, title, locked_at in orphaned:
            await s.execute(text("""
                UPDATE content_bank SET status = 'queued', locked_at = NULL WHERE id = :id
            """), {"id": bank_id})
            issues.append(f"Reset orphaned lock on '{title}' (locked since {locked_at})")
            actions_taken.append(f"Reset orphaned lock #{bank_id}")
        if orphaned:
            await s.commit()

    # 2c. Check for content_bank items stuck as 'generating' with failed runs
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT cb.id, cb.title, cb.attempt_count
            FROM content_bank cb
            JOIN content_runs cr ON cr.id = cb.run_id
            WHERE cb.status = 'generating' AND cr.status = 'failed'
        """))
        stuck = result.fetchall()
        for bank_id, title, attempts in stuck:
            if attempts >= 3:
                await s.execute(text(
                    "UPDATE content_bank SET status = 'failed' WHERE id = :id"
                ), {"id": bank_id})
            else:
                await s.execute(text(
                    "UPDATE content_bank SET status = 'queued', attempt_count = attempt_count + 1 WHERE id = :id"
                ), {"id": bank_id})
            issues.append(f"Reset stuck generating '{title}'")
            actions_taken.append(f"Reset stuck generating #{bank_id}")
        if stuck:
            await s.commit()

    # 2d. Recover completed videos with missing DB records
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT cr.id, cr.channel_id, cb.concept_json, cb.id as bank_id
            FROM content_runs cr
            LEFT JOIN content_bank cb ON cb.run_id = cr.id
            WHERE cr.status = 'failed' AND (cr.error IS NULL OR cr.error = '')
        """))
        orphans = result.fetchall()
        for run_id, channel_id, concept_json, bank_id in orphans:
            # Check if final.mp4 exists
            final_path = None
            for prefix in ["run_", "deity_run_", "unified_run_"]:
                p = f"output/{prefix}{run_id}/final.mp4"
                if os.path.isfile(p):
                    final_path = p
                    break
            if not final_path:
                continue

            # Video exists but DB doesn't know — fix it
            file_size = os.path.getsize(final_path)

            # Check if assets already exist
            existing = await s.execute(text(
                "SELECT asset_type FROM assets WHERE run_id = :rid"
            ), {"rid": run_id})
            existing_types = {r[0] for r in existing.fetchall()}

            if "rendered_unified_short" not in existing_types:
                await s.execute(text(
                    "INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, 'rendered_unified_short', :c)"
                ), {"rid": run_id, "cid": channel_id,
                    "c": json.dumps({"path": final_path, "file_size_bytes": file_size})})

            if "publish_metadata" not in existing_types and concept_json:
                try:
                    concept = json.loads(concept_json) if isinstance(concept_json, str) else concept_json
                    await s.execute(text(
                        "INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, 'publish_metadata', :c)"
                    ), {"rid": run_id, "cid": channel_id,
                        "c": json.dumps({"title": concept.get("title", ""), "description": concept.get("caption", ""),
                                         "tags": concept.get("tags", []), "category": "Entertainment"})})
                except (json.JSONDecodeError, TypeError):
                    pass

            await s.execute(text(
                "UPDATE content_runs SET status = 'pending_review', current_step = 'pending_review', completed_at = NOW() WHERE id = :rid"
            ), {"rid": run_id})
            if bank_id:
                await s.execute(text(
                    "UPDATE content_bank SET status = 'generated' WHERE id = :bid"
                ), {"bid": bank_id})

            issues.append(f"Recovered orphaned video run #{run_id} — final.mp4 existed but DB wasn't updated")
            actions_taken.append(f"Recovered run #{run_id} to pending_review")

        if orphans:
            await s.commit()

    # 3. Check worker health — are there queued items but nothing generating?
    async with AsyncSession(engine) as s:
        result = await s.execute(text("""
            SELECT COUNT(*) FROM content_bank WHERE status = 'queued' AND priority <= 10
        """))
        urgent_queued = result.scalar()

        result = await s.execute(text("""
            SELECT COUNT(*) FROM content_runs WHERE status = 'running'
        """))
        currently_running = result.scalar()

    if urgent_queued > 0 and currently_running == 0:
        issues.append(f"{urgent_queued} urgent items queued but nothing generating — worker may be down")

    # 4. If there are complex issues, ask Claude for help
    if issues:
        logger.info("monitor found issues", count=len(issues), actions=len(actions_taken))
        for issue in issues:
            logger.warning("issue", detail=issue)
        for action in actions_taken:
            logger.info("action taken", detail=action)

        # For complex/recurring issues, consult Claude
        unresolved = [i for i in issues if "worker may be down" in i or "failed 3 times" in str(i)]
        if unresolved:
            await _consult_claude(engine, unresolved, actions_taken)
    else:
        logger.info("monitor check complete — no issues found")


async def _consult_claude(engine, issues: list[str], actions_taken: list[str]):
    """Ask Claude Opus 4.6 to analyze unresolved issues and suggest fixes."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping Claude consultation")
        return

    client = Anthropic(api_key=api_key)

    # Gather context
    async with AsyncSession(engine) as s:
        # Recent failed runs
        result = await s.execute(text("""
            SELECT id, channel_id, current_step, error, started_at
            FROM content_runs WHERE status = 'failed'
            ORDER BY id DESC LIMIT 5
        """))
        recent_failures = [
            {"run_id": r[0], "step": r[2], "error": str(r[3])[:200], "started": str(r[4])}
            for r in result.fetchall()
        ]

        # Queue status
        result = await s.execute(text("""
            SELECT c.name, COUNT(*) as queued
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            WHERE cb.status = 'queued'
            GROUP BY c.name
        """))
        queue_status = {r[0]: r[1] for r in result.fetchall()}

    context = {
        "issues": issues,
        "actions_already_taken": actions_taken,
        "recent_failures": recent_failures,
        "queue_status": queue_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system="You are a pipeline monitoring agent for a YouTube content factory. Analyze issues and provide specific actionable fixes. Be concise. If the issue is transient (API timeout, rate limit), suggest waiting. If systemic (code bug, config error), describe the fix needed. Output JSON with keys: diagnosis, severity (low/medium/high), recommended_action, requires_human (bool).",
            messages=[{
                "role": "user",
                "content": f"Pipeline monitor detected these unresolved issues:\n\n{json.dumps(context, indent=2)}\n\nDiagnose and recommend action.",
            }],
        )

        diagnosis = response.content[0].text
        logger.info("claude diagnosis", response=diagnosis[:500])

        # Parse and log the diagnosis
        try:
            parsed = json.loads(diagnosis)
            if parsed.get("requires_human"):
                logger.warning("HUMAN INTERVENTION NEEDED", diagnosis=parsed.get("diagnosis"), action=parsed.get("recommended_action"))
            else:
                logger.info("claude recommendation", severity=parsed.get("severity"), action=parsed.get("recommended_action"))
        except json.JSONDecodeError:
            logger.info("claude response (not JSON)", text=diagnosis[:300])

    except Exception as e:
        logger.error("claude consultation failed", error=str(e)[:200])


async def main():
    logger.info("starting pipeline monitor agent (Opus 4.6)")
    await run_monitor_loop()


if __name__ == "__main__":
    asyncio.run(main())
