"""Admin CLI for viewing pipeline runs and managing the unified pipeline."""

import asyncio
import json
import os

import click
from sqlalchemy import text

from packages.clients.db import async_session


def run_async(coro):
    return asyncio.run(coro)


@click.group()
def cli():
    """YouTube Orchestrator Admin CLI"""
    pass


@cli.command()
def list_channels():
    """List all configured channels."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(text("SELECT id, name, niche, created_at FROM channels ORDER BY id"))
            rows = result.fetchall()

        if not rows:
            click.echo("No channels found.")
            return

        click.echo(f"{'ID':<5} {'Name':<20} {'Niche':<25} {'Created'}")
        click.echo("-" * 70)
        for row in rows:
            click.echo(f"{row[0]:<5} {row[1]:<20} {row[2]:<25} {row[3]}")

    run_async(_run())


@cli.command()
def list_runs():
    """List all content pipeline runs."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(
                text("""SELECT cr.id, c.name, cr.status, cr.current_step, cr.started_at, cr.completed_at
                        FROM content_runs cr
                        JOIN channels c ON c.id = cr.channel_id
                        ORDER BY cr.id DESC""")
            )
            rows = result.fetchall()

        if not rows:
            click.echo("No runs found.")
            return

        click.echo(f"{'Run':<5} {'Channel':<15} {'Status':<15} {'Step':<25} {'Started':<22} {'Completed'}")
        click.echo("-" * 100)
        for row in rows:
            click.echo(
                f"{row[0]:<5} {row[1]:<15} {row[2]:<15} {(row[3] or ''):<25} "
                f"{str(row[4] or ''):<22} {str(row[5] or '')}"
            )

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
def show_run(run_id):
    """Show detailed state of a specific run."""
    async def _run():
        async with async_session() as session:
            # Run info
            result = await session.execute(
                text("SELECT id, channel_id, status, current_step, started_at, completed_at, error FROM content_runs WHERE id = :id"),
                {"id": run_id},
            )
            run = result.fetchone()
            if not run:
                click.echo(f"Run {run_id} not found.")
                return

            click.echo(f"\n=== Run #{run[0]} ===")
            click.echo(f"Channel ID: {run[1]}")
            click.echo(f"Status:     {run[2]}")
            click.echo(f"Step:       {run[3]}")
            click.echo(f"Started:    {run[4]}")
            click.echo(f"Completed:  {run[5]}")
            if run[6]:
                click.echo(f"Error:      {run[6]}")

            # Assets
            result = await session.execute(
                text("SELECT asset_type, content FROM assets WHERE run_id = :id"),
                {"id": run_id},
            )
            assets = result.fetchall()
            if assets:
                click.echo(f"\n--- Assets ({len(assets)}) ---")
                for a in assets:
                    click.echo(f"  {a[0]}")

            click.echo()

    run_async(_run())


@cli.command()
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all runs, not just recent")
def status(show_all):
    """Dashboard -- running pipelines, recent completions, review scores, and system health."""
    from dotenv import load_dotenv
    load_dotenv()

    async def _run():
        async with async_session() as session:
            # Running pipelines
            running = await session.execute(
                text("""SELECT cr.id, c.name, cr.current_step, cr.started_at,
                        EXTRACT(EPOCH FROM (NOW() - cr.started_at))::int as elapsed_seconds
                        FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                        WHERE cr.status = 'running' ORDER BY cr.id""")
            )
            running_rows = running.fetchall()

            # Recent completed/published (last 20)
            limit = 100 if show_all else 20
            recent = await session.execute(
                text(f"""SELECT cr.id, c.name, cr.status, cr.current_step, cr.completed_at, cr.error,
                        (SELECT content FROM assets WHERE run_id = cr.id AND asset_type = 'video_review' ORDER BY id DESC LIMIT 1) as review
                        FROM content_runs cr JOIN channels c ON c.id = cr.channel_id
                        WHERE cr.status IN ('completed', 'published', 'failed', 'pending_review')
                        ORDER BY cr.id DESC LIMIT {limit}""")
            )
            recent_rows = recent.fetchall()

            # Channel stats
            stats = await session.execute(
                text("""SELECT c.name,
                        COUNT(cr.id) FILTER (WHERE cr.status = 'published') as published,
                        COUNT(cr.id) FILTER (WHERE cr.status = 'completed') as completed,
                        COUNT(cr.id) FILTER (WHERE cr.status = 'failed') as failed,
                        COUNT(cr.id) as total
                        FROM channels c
                        LEFT JOIN content_runs cr ON cr.channel_id = c.id
                        GROUP BY c.name ORDER BY c.name""")
            )
            stats_rows = stats.fetchall()

        # === RUNNING ===
        if running_rows:
            click.echo(f"\n{'='*60}")
            click.echo(f"  RUNNING ({len(running_rows)} pipelines)")
            click.echo(f"{'='*60}")
            for row in running_rows:
                elapsed = row[4] or 0
                mins = elapsed // 60
                step = row[2] or "starting..."
                click.echo(f"  #{row[0]:<4} {row[1]:<18} {step:<20} {mins}m elapsed")
        else:
            click.echo(f"\n  No pipelines running.")

        # === RECENT ===
        click.echo(f"\n{'='*60}")
        click.echo(f"  RECENT RUNS")
        click.echo(f"{'='*60}")

        if not recent_rows:
            click.echo("  No recent runs.")
        else:
            for row in recent_rows:
                run_id, name, status_val, step, completed, error, review_json = row

                # Parse review score
                score_str = ""
                if review_json:
                    try:
                        review = json.loads(review_json)
                        score = review.get("overall_score", 0)
                        if review.get("reviewed") and score > 0:
                            rec = review.get("publish_recommendation", "")
                            score_str = f" [{score}/10 {rec}]"
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Status icon
                if status_val == "published":
                    icon = "PUB"
                elif status_val == "completed" or status_val == "pending_review":
                    icon = "OK "
                else:
                    icon = "FAIL"

                line = f"  #{run_id:<4} {icon} {name:<18}{score_str}"
                if status_val == "failed" and error:
                    line += f" ERR: {error[:40]}"
                click.echo(line)

        # === CHANNEL STATS ===
        click.echo(f"\n{'='*60}")
        click.echo(f"  CHANNEL STATS")
        click.echo(f"{'='*60}")
        click.echo(f"  {'Channel':<18} {'Published':>9} {'Done':>6} {'Failed':>7} {'Total':>6}")
        click.echo(f"  {'-'*50}")
        for row in stats_rows:
            click.echo(f"  {row[0]:<18} {row[1]:>9} {row[2]:>6} {row[3]:>7} {row[4]:>6}")

        # === SYSTEM ===
        click.echo(f"\n{'='*60}")
        click.echo(f"  SYSTEM")
        click.echo(f"{'='*60}")
        apis = [
            ("Claude (Opus)", bool(os.getenv("ANTHROPIC_API_KEY"))),
            ("Sora 2 Pro", bool(os.getenv("OPENAI_API_KEY"))),
            ("Gemini", bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))),
            ("ElevenLabs", bool(os.getenv("ELEVENLABS_API_KEY"))),
            ("YouTube OAuth", os.path.exists("youtube_token.json")),
        ]
        for name, active in apis:
            click.echo(f"  {name:<18} {'ACTIVE' if active else 'NOT SET'}")
        click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
@click.option("--public", is_flag=True, default=False, help="Upload as public (default: private)")
@click.option("--unlisted", is_flag=True, default=False, help="Upload as unlisted")
def upload(run_id, public, unlisted):
    """Upload a completed run's video to YouTube."""
    async def _run():
        # Get publish metadata from assets
        async with async_session() as session:
            metadata_result = await session.execute(
                text("SELECT content FROM assets WHERE run_id = :id AND asset_type = 'publish_metadata' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            metadata_row = metadata_result.fetchone()

            asset_result = await session.execute(
                text("SELECT content FROM assets WHERE run_id = :id AND asset_type LIKE 'rendered%%' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            asset = asset_result.fetchone()

        if not asset:
            click.echo(f"No rendered video found for run {run_id}.")
            return

        render_info = json.loads(asset[0])
        video_path = render_info.get("path")

        if not video_path or not os.path.exists(video_path):
            click.echo(f"Video file not found: {video_path}")
            return

        metadata = json.loads(metadata_row[0]) if metadata_row else {}
        title = metadata.get("title", "Untitled")
        description = metadata.get("description", "")
        tags = metadata.get("tags", [])
        category = metadata.get("category", "Entertainment")

        privacy = "public" if public else ("unlisted" if unlisted else "private")

        click.echo(f"\n=== Uploading to YouTube ===")
        click.echo(f"Title:     {title}")
        click.echo(f"Privacy:   {privacy}")
        click.echo(f"Video:     {video_path}")
        click.echo()

        from apps.publishing_service.uploader import upload_video, is_upload_configured

        if not is_upload_configured():
            click.echo("YouTube OAuth2 not configured. Run:")
            click.echo("  python -m apps.publishing_service.auth")
            return

        result = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category=category,
            privacy_status=privacy,
        )

        if result.get("published"):
            click.echo(f"Uploaded! {result['url']}")
            click.echo(f"Privacy: {result['privacy']}")
        else:
            click.echo(f"Upload failed: {result.get('error', 'unknown error')}")
        click.echo()

    run_async(_run())


if __name__ == "__main__":
    cli()
