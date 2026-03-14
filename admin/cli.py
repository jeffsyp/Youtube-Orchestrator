"""Admin CLI for viewing pipeline runs, reviewing candidates, and managing approvals."""

import asyncio
import json

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

            # Candidates
            result = await session.execute(
                text("SELECT title, channel_name, views, channel_subscribers, breakout_score FROM source_candidates WHERE run_id = :id ORDER BY breakout_score DESC"),
                {"id": run_id},
            )
            candidates = result.fetchall()
            if candidates:
                click.echo(f"\n--- Candidates ({len(candidates)}) ---")
                for c in candidates:
                    ratio = f"{c[2]/c[3]:.1f}x" if c[3] > 0 else "n/a"
                    click.echo(f"  [{c[4]:>6.1f}] {c[0][:50]:<52} {c[2]:>10,} views  ({c[1]}, {ratio})")

            # Templates
            result = await session.execute(
                text("SELECT pattern_name, description, hook_style FROM templates WHERE run_id = :id"),
                {"id": run_id},
            )
            templates = result.fetchall()
            if templates:
                click.echo(f"\n--- Templates ({len(templates)}) ---")
                for t in templates:
                    click.echo(f"  {t[0]}: {t[1][:70]}")
                    click.echo(f"    Hook: {t[2]}")

            # Ideas
            result = await session.execute(
                text("SELECT title, hook, score, selected FROM ideas WHERE run_id = :id ORDER BY score DESC"),
                {"id": run_id},
            )
            ideas = result.fetchall()
            if ideas:
                click.echo(f"\n--- Ideas ({len(ideas)}) ---")
                for i in ideas:
                    marker = " ** SELECTED **" if i[3] else ""
                    click.echo(f"  [{i[2]:>4.1f}] {i[0]}{marker}")
                    click.echo(f"         {i[1][:80]}")

            # Scripts
            result = await session.execute(
                text("SELECT stage, idea_title, word_count, critique_notes FROM scripts WHERE run_id = :id ORDER BY id"),
                {"id": run_id},
            )
            scripts = result.fetchall()
            if scripts:
                click.echo(f"\n--- Scripts ({len(scripts)}) ---")
                for s in scripts:
                    click.echo(f"  [{s[0]:<10}] {s[1]} ({s[2]} words)")
                    if s[3]:
                        # Show first 2 lines of critique
                        lines = s[3].strip().split("\n")[:3]
                        for line in lines:
                            click.echo(f"              {line[:80]}")

            # Assets
            result = await session.execute(
                text("SELECT asset_type, content FROM assets WHERE run_id = :id"),
                {"id": run_id},
            )
            assets = result.fetchall()
            if assets:
                click.echo(f"\n--- Assets ({len(assets)}) ---")
                for a in assets:
                    if a[0] == "shot":
                        shot = json.loads(a[1])
                        click.echo(f"  Shot {shot.get('scene_number', '?')}: {shot.get('description', '')[:60]}")
                    else:
                        click.echo(f"  {a[0]}")

            # Packages
            result = await session.execute(
                text("SELECT title, description, tags, category, status FROM packages WHERE run_id = :id"),
                {"id": run_id},
            )
            packages = result.fetchall()
            if packages:
                click.echo(f"\n--- Packages ({len(packages)}) ---")
                for p in packages:
                    click.echo(f"  Title:    {p[0]}")
                    click.echo(f"  Category: {p[3]}")
                    click.echo(f"  Status:   {p[4]}")
                    tags = json.loads(p[2]) if p[2] else []
                    click.echo(f"  Tags:     {', '.join(tags[:8])}")

            click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
def show_script(run_id):
    """Show the full final script for a run."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(
                text("SELECT idea_title, content, word_count FROM scripts WHERE run_id = :id AND stage = 'final' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            row = result.fetchone()
            if not row:
                click.echo(f"No final script found for run {run_id}.")
                return

            click.echo(f"\n=== {row[0]} ({row[2]} words) ===\n")
            click.echo(row[1])
            click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
def show_critique(run_id):
    """Show the critique notes for a run."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(
                text("SELECT idea_title, critique_notes FROM scripts WHERE run_id = :id AND stage = 'critique' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            row = result.fetchone()
            if not row:
                click.echo(f"No critique found for run {run_id}.")
                return

            click.echo(f"\n=== Critique: {row[0]} ===\n")
            click.echo(row[1])
            click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
def show_package(run_id):
    """Show the full package details for a run."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(
                text("SELECT title, description, tags, category, status FROM packages WHERE run_id = :id ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            row = result.fetchone()
            if not row:
                click.echo(f"No package found for run {run_id}.")
                return

            click.echo(f"\n=== Package ===")
            click.echo(f"Title:    {row[0]}")
            click.echo(f"Category: {row[3]}")
            click.echo(f"Status:   {row[4]}")
            tags = json.loads(row[2]) if row[2] else []
            click.echo(f"Tags:     {', '.join(tags)}")
            click.echo(f"\nDescription:\n{row[1]}")
            click.echo()

    run_async(_run())


@cli.command()
def status():
    """Show system status — what API integrations are active."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    click.echo("\n=== System Status ===")
    click.echo(f"YouTube API:   {'ACTIVE' if os.getenv('YOUTUBE_API_KEY') else 'NOT SET (using fake research)'}")
    click.echo(f"Anthropic API: {'ACTIVE' if os.getenv('ANTHROPIC_API_KEY') else 'NOT SET (using fake writing/media)'}")
    click.echo(f"YouTube OAuth: {'CONFIGURED' if os.path.exists(os.getenv('YOUTUBE_TOKEN_FILE', 'youtube_token.json')) else 'NOT SET (manual upload only)'}")
    click.echo(f"ElevenLabs:    {'ACTIVE' if os.getenv('ELEVENLABS_API_KEY') else 'NOT SET'}")

    async def _counts():
        async with async_session() as session:
            channels = (await session.execute(text("SELECT COUNT(*) FROM channels"))).scalar()
            runs = (await session.execute(text("SELECT COUNT(*) FROM content_runs"))).scalar()
            candidates = (await session.execute(text("SELECT COUNT(*) FROM source_candidates"))).scalar()
            scripts = (await session.execute(text("SELECT COUNT(*) FROM scripts WHERE stage = 'final'"))).scalar()
            packages = (await session.execute(text("SELECT COUNT(*) FROM packages"))).scalar()

        click.echo(f"\n--- Data ---")
        click.echo(f"Channels:   {channels}")
        click.echo(f"Runs:       {runs}")
        click.echo(f"Candidates: {candidates}")
        click.echo(f"Scripts:    {scripts}")
        click.echo(f"Packages:   {packages}")
        click.echo()

    run_async(_counts())


@cli.command()
@click.argument("run_id", type=int)
def show_ideas(run_id):
    """Show generated ideas for a run, ready for selection."""
    async def _run():
        async with async_session() as session:
            result = await session.execute(
                text("SELECT id, title, hook, angle, target_length_seconds, score FROM ideas WHERE run_id = :id ORDER BY score DESC"),
                {"id": run_id},
            )
            ideas = result.fetchall()

            run_result = await session.execute(
                text("SELECT status, current_step FROM content_runs WHERE id = :id"),
                {"id": run_id},
            )
            run_row = run_result.fetchone()

        if not ideas:
            click.echo(f"No ideas found for run {run_id}.")
            return

        is_waiting = run_row and run_row[0] == "awaiting_approval" and run_row[1] == "select_best_idea"

        click.echo(f"\n=== Ideas for Run #{run_id} ===")
        if is_waiting:
            click.echo("STATUS: Waiting for your selection\n")
        click.echo()

        for i, idea in enumerate(ideas, 1):
            click.echo(f"  [{i}] {idea[1]} (score: {idea[5]})")
            click.echo(f"      Hook:  {idea[2][:80]}")
            click.echo(f"      Angle: {idea[3][:80]}")
            click.echo(f"      Length: {idea[4]}s")
            click.echo()

        if is_waiting:
            click.echo(f"To select an idea, run:")
            click.echo(f"  python -m admin.cli pick-idea {run_id} <number>")
            click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
@click.argument("idea_number", type=int)
def pick_idea(run_id, idea_number):
    """Select an idea for a waiting run. IDEA_NUMBER is 1-based (from show-ideas)."""
    async def _run():
        import os
        from temporalio.client import Client

        # Verify the run is actually waiting
        async with async_session() as session:
            result = await session.execute(
                text("SELECT status, current_step FROM content_runs WHERE id = :id"),
                {"id": run_id},
            )
            run_row = result.fetchone()

        if not run_row:
            click.echo(f"Run {run_id} not found.")
            return

        if run_row[0] != "awaiting_approval":
            click.echo(f"Run {run_id} is not waiting for approval (status: {run_row[0]}).")
            return

        # Send the signal to the Temporal workflow
        host = os.getenv("TEMPORAL_HOST", "localhost:7233")
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        client = await Client.connect(host, namespace=namespace)

        handle = client.get_workflow_handle(f"daily-pipeline-run-{run_id}")
        await handle.signal("select_idea", idea_number)

        # Update run status back to running
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'running' WHERE id = :id"),
                {"id": run_id},
            )
            await session.commit()

        click.echo(f"Idea #{idea_number} selected for run {run_id}. Pipeline resuming...")

    run_async(_run())


if __name__ == "__main__":
    cli()
