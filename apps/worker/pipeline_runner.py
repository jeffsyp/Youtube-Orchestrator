"""Standalone pipeline entry point — invoked as a subprocess by the worker.

Usage:
    python -m apps.worker.pipeline_runner --run-id 123 --concept '{"title": "...", ...}'

Exits 0 on success, 1 on failure (error printed to stderr).
"""

import argparse
import asyncio
import json
import sys
import traceback

from dotenv import load_dotenv

load_dotenv(override=True)


def main():
    parser = argparse.ArgumentParser(description="Run deity pipeline for a single video")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--concept", type=str, required=True, help="JSON string of concept")
    args = parser.parse_args()

    try:
        concept = json.loads(args.concept)
    except json.JSONDecodeError as e:
        print(f"Invalid concept JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from apps.orchestrator.pipeline import run_pipeline
        asyncio.run(run_pipeline(args.run_id, concept))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    # The pipeline catches its own exceptions and marks the run as 'failed' in DB
    # without re-raising. Check DB status so the worker sees a non-zero exit code.
    try:
        import os
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy import text as sa_text

        db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator")
        if "asyncpg" not in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        async def _check_status():
            eng = create_async_engine(db_url, pool_size=1, max_overflow=0)
            try:
                async with AsyncSession(eng) as sess:
                    row = (await sess.execute(
                        sa_text("SELECT status, error FROM content_runs WHERE id = :id"),
                        {"id": args.run_id},
                    )).fetchone()
                return row
            finally:
                await eng.dispose()

        row = asyncio.run(_check_status())
        if row and row[0] == "failed":
            err = row[1] or "Pipeline marked as failed"
            print(f"Pipeline failed: {err}", file=sys.stderr)
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as check_err:
        # If we can't check, assume success — runner.py will verify the video file exists
        print(f"Warning: could not verify pipeline status: {check_err}", file=sys.stderr)


if __name__ == "__main__":
    main()
