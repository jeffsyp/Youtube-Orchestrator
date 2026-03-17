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
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all runs, not just recent")
def status(show_all):
    """Dashboard — running pipelines, recent completions, review scores, and system health."""
    import os
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
                        WHERE cr.status IN ('completed', 'published', 'failed')
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
                elif status_val == "completed":
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
            ("Gemini 3 Pro", bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))),
            ("ElevenLabs", bool(os.getenv("ELEVENLABS_API_KEY"))),
            ("YouTube OAuth", os.path.exists("youtube_token.json")),
        ]
        for name, active in apis:
            click.echo(f"  {name:<18} {'ACTIVE' if active else 'NOT SET'}")
        click.echo()

    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
def qa_video(run_id):
    """Run video QA checks on a completed run."""
    async def _run():
        # Find the video path
        async with async_session() as session:
            result = await session.execute(
                text("SELECT content FROM assets WHERE run_id = :id AND asset_type = 'rendered_video' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            row = result.fetchone()

        if not row:
            click.echo(f"No rendered video found for run {run_id}.")
            return

        import json as json_mod
        render_info = json_mod.loads(row[0])
        video_path = render_info.get("path")

        if not video_path or not os.path.exists(video_path):
            click.echo(f"Video file not found: {video_path}")
            return

        voiceover_path = f"output/run_{run_id}/voiceover.mp3"
        vo_path = voiceover_path if os.path.exists(voiceover_path) else None

        click.echo(f"\n=== Video QA for Run #{run_id} ===")
        click.echo(f"Video: {video_path}\n")

        from apps.rendering_service.qa import run_all_checks
        report = run_all_checks(video_path, voiceover_path=vo_path)

        for check in report["details"]:
            status = "PASS" if check["passed"] else "FAIL"
            click.echo(f"  [{status}] {check['check']}")
            # Show key metrics
            for key, val in check.items():
                if key not in ("check", "passed", "issues"):
                    click.echo(f"         {key}: {val}")
            for issue in check.get("issues", []):
                click.echo(f"         !! {issue}")
            click.echo()

        overall = "PASSED" if report["passed"] else "FAILED"
        click.echo(f"Overall: {overall} ({report['checks_passed']}/{report['checks_run']} checks passed)")
        if report["issues"]:
            click.echo(f"\nIssues to fix:")
            for issue in report["issues"]:
                click.echo(f"  - {issue}")
        click.echo()

    import os
    run_async(_run())


@cli.command()
@click.argument("run_id", type=int)
@click.option("--public", is_flag=True, default=False, help="Upload as public (default: private)")
@click.option("--unlisted", is_flag=True, default=False, help="Upload as unlisted")
def upload(run_id, public, unlisted):
    """Upload a completed run's video to YouTube."""
    async def _run():
        # Get package metadata
        async with async_session() as session:
            pkg_result = await session.execute(
                text("SELECT title, description, tags, category FROM packages WHERE run_id = :id ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            pkg = pkg_result.fetchone()

            asset_result = await session.execute(
                text("SELECT content FROM assets WHERE run_id = :id AND asset_type = 'rendered_video' ORDER BY id DESC LIMIT 1"),
                {"id": run_id},
            )
            asset = asset_result.fetchone()

        if not pkg:
            click.echo(f"No package found for run {run_id}.")
            return

        if not asset:
            click.echo(f"No rendered video found for run {run_id}.")
            return

        render_info = json.loads(asset[0])
        video_path = render_info.get("path")

        if not video_path or not os.path.exists(video_path):
            click.echo(f"Video file not found: {video_path}")
            return

        tags = json.loads(pkg[2]) if pkg[2] else []
        output_dir = f"output/run_{run_id}"
        srt_path = os.path.join(output_dir, "subtitles.srt")
        captions = srt_path if os.path.exists(srt_path) else None
        thumb_path = os.path.join(output_dir, "thumbnail.png")
        thumbnail = thumb_path if os.path.exists(thumb_path) else None

        privacy = "public" if public else ("unlisted" if unlisted else "private")

        click.echo(f"\n=== Uploading to YouTube ===")
        click.echo(f"Title:     {pkg[0]}")
        click.echo(f"Privacy:   {privacy}")
        click.echo(f"Video:     {video_path}")
        click.echo(f"Thumbnail: {thumbnail or 'none'}")
        click.echo(f"Captions:  {captions or 'none'}")
        click.echo()

        from apps.publishing_service.uploader import upload_video, is_upload_configured

        if not is_upload_configured():
            click.echo("YouTube OAuth2 not configured. Run:")
            click.echo("  python -m apps.publishing_service.auth")
            return

        result = upload_video(
            video_path=video_path,
            title=pkg[0],
            description=pkg[1],
            tags=tags,
            category=pkg[3] or "Science & Technology",
            privacy_status=privacy,
            captions_path=captions,
            thumbnail_path=thumbnail,
        )

        if result.get("published"):
            click.echo(f"Uploaded! {result['url']}")
            click.echo(f"Privacy: {result['privacy']}")
        else:
            click.echo(f"Upload failed: {result.get('error', 'unknown error')}")
        click.echo()

    import os
    run_async(_run())


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


@cli.command()
@click.argument("channel_name", default="Signal Intel")
@click.option("--auto", "auto_pick", is_flag=True, default=False, help="Auto-pick highest scored topic (no human gate)")
@click.option("--public", is_flag=True, default=False, help="Publish as public (default: private)")
@click.option("--unlisted", is_flag=True, default=False, help="Publish as unlisted")
def make_short(channel_name, auto_pick, public, unlisted):
    """Create a YouTube Short for a channel. Runs the full pipeline.

    Routes to the correct workflow based on channel config:
    - Channels with "pipeline": "synthzoo" use SynthZooPipeline
    - All others use ShortsPipeline

    Examples:
        python -m admin.cli make-short "Signal Intel" --auto --public
        python -m admin.cli make-short "Synth Zoo" --auto
        python -m admin.cli make-short  # defaults to Signal Intel, manual topic pick
    """
    async def _run():
        import os
        from temporalio.client import Client

        # Find channel by name and get config
        async with async_session() as session:
            result = await session.execute(
                text("SELECT id, name, niche, config FROM channels WHERE LOWER(name) = LOWER(:name)"),
                {"name": channel_name},
            )
            channel = result.fetchone()

        if not channel:
            click.echo(f"Channel '{channel_name}' not found. Available channels:")
            async with async_session() as session:
                result = await session.execute(text("SELECT name FROM channels ORDER BY id"))
                for row in result.fetchall():
                    click.echo(f"  - {row[0]}")
            return

        channel_id = channel[0]
        channel_config = json.loads(channel[3]) if channel[3] else {}
        pipeline_type = channel_config.get("pipeline", "shorts")
        privacy = "public" if public else ("unlisted" if unlisted else "private")

        # Determine workflow and content_type based on channel config
        if pipeline_type == "synthzoo":
            workflow_name = "SynthZooPipeline"
            content_type = "synthzoo"
            signal_name = "select_concept"
            awaiting_status = "awaiting_concept_selection"
            item_label = "concepts"
        elif pipeline_type == "lad_stories":
            workflow_name = "LadStoriesPipeline"
            content_type = "lad_stories"
            signal_name = "select_concept"
            awaiting_status = "awaiting_concept_selection"
            item_label = "concepts"
        elif pipeline_type == "fundational":
            workflow_name = "FundationalPipeline"
            content_type = "fundational"
            signal_name = "select_concept"
            awaiting_status = "awaiting_concept_selection"
            item_label = "concepts"
        elif pipeline_type == "satisdefying":
            workflow_name = "SatisdefyingPipeline"
            content_type = "satisdefying"
            signal_name = "select_concept"
            awaiting_status = "awaiting_concept_selection"
            item_label = "concepts"
        elif pipeline_type == "yeah_thats_clean":
            workflow_name = "YeahThatsCleanPipeline"
            content_type = "yeah_thats_clean"
            signal_name = "select_concept"
            awaiting_status = "awaiting_concept_selection"
            item_label = "concepts"
        elif pipeline_type == "whistle_room":
            workflow_name = "WhistleRoomPipeline"
            content_type = "whistle_room"
            signal_name = "select_clip"
            awaiting_status = "awaiting_clip_selection"
            item_label = "clips"
        else:
            workflow_name = "ShortsPipeline"
            content_type = "short"
            signal_name = "select_topic"
            awaiting_status = "awaiting_topic_selection"
            item_label = "topics"

        click.echo(f"\n=== Making Short for {channel[1]} ({channel[2]}) ===")
        click.echo(f"Pipeline: {pipeline_type}")
        click.echo(f"Privacy: {privacy}")
        click.echo(f"Auto-pick: {'yes' if auto_pick else f'no (will wait for {item_label} selection)'}")
        click.echo()

        # Create content run
        async with async_session() as session:
            result = await session.execute(
                text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', :ct) RETURNING id"),
                {"cid": channel_id, "ct": content_type},
            )
            run_id = result.scalar_one()
            await session.commit()

        click.echo(f"Run #{run_id} created")

        # Start workflow
        host = os.getenv("TEMPORAL_HOST", "localhost:7233")
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        client = await Client.connect(host, namespace=namespace)

        handle = await client.start_workflow(
            workflow_name,
            args=[run_id, channel_id, auto_pick, privacy],
            id=f"{pipeline_type}-pipeline-run-{run_id}",
            task_queue="daily-content-pipeline",
        )

        click.echo(f"Workflow started: {handle.id}")

        if not auto_pick:
            # Wait for items to be generated, then show them
            import asyncio
            click.echo(f"\nWaiting for {item_label}...")
            for _ in range(30):
                await asyncio.sleep(2)
                try:
                    status = await handle.query("get_status")
                    if status == awaiting_status:
                        break
                except Exception:
                    pass

            # Show items
            async with async_session() as session:
                result = await session.execute(
                    text("SELECT title, hook, score FROM ideas WHERE run_id = :id ORDER BY score DESC"),
                    {"id": run_id},
                )
                items = result.fetchall()

            if items:
                click.echo(f"\n{item_label.title()}:")
                for i, t in enumerate(items, 1):
                    click.echo(f"  {i}. [{t[2]:.1f}] {t[0]}")
                    click.echo(f"     {t[1][:80]}")
                click.echo()

                choice = click.prompt(f"Pick a {item_label[:-1]}", type=int, default=1)
                await handle.signal(signal_name, choice)
                click.echo(f"{item_label.title()[:-1]} {choice} selected")
            else:
                click.echo(f"No {item_label} generated — check worker logs")
                return

        # Wait for completion
        click.echo("\nPipeline running...")
        result = await handle.result()

        # Mark complete
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status = 'completed', completed_at = NOW() WHERE id = :id"),
                {"id": run_id},
            )
            await session.commit()

        click.echo(f"\nDone!")
        click.echo(f"Topic: {result.get('topic', 'n/a')}")
        click.echo(f"Video: {result.get('video_path', 'n/a')}")
        if result.get("url"):
            click.echo(f"URL:   {result['url']}")
        click.echo(f"Privacy: {result.get('privacy', privacy)}")

    run_async(_run())


@cli.command()
@click.option("--channels", "-c", multiple=True, help="Channel names to run (default: all Shorts channels)")
@click.option("--public", is_flag=True, default=False, help="Publish as public")
@click.option("--unlisted", is_flag=True, default=False, help="Publish as unlisted")
def make_all(channels, public, unlisted):
    """Run make-short for multiple channels in parallel (auto-pick mode).

    Examples:
        python -m admin.cli make-all
        python -m admin.cli make-all -c "Synth Meow" -c "Satisdefying"
        python -m admin.cli make-all --public
    """
    async def _run():
        import os
        from temporalio.client import Client

        # Get channels
        async with async_session() as session:
            if channels:
                placeholders = ", ".join(f":c{i}" for i in range(len(channels)))
                params = {f"c{i}": name for i, name in enumerate(channels)}
                result = await session.execute(
                    text(f"SELECT id, name, niche, config FROM channels WHERE LOWER(name) IN ({', '.join(f'LOWER(:c{i})' for i in range(len(channels)))})"),
                    params,
                )
            else:
                # Default: all channels with a Shorts pipeline (not long-form)
                result = await session.execute(
                    text("SELECT id, name, niche, config FROM channels WHERE config::jsonb->>'pipeline' != 'shorts' OR config::jsonb->>'pipeline' IS NULL ORDER BY id"),
                )
            rows = result.fetchall()

        if not rows:
            click.echo("No matching channels found.")
            return

        # Pipeline name mapping
        pipeline_map = {
            "synthzoo": ("SynthZooPipeline", "synthzoo"),
            "satisdefying": ("SatisdefyingPipeline", "satisdefying"),
            "lad_stories": ("LadStoriesPipeline", "lad_stories"),
            "fundational": ("FundationalPipeline", "fundational"),
            "whistle_room": ("WhistleRoomPipeline", "whistle_room"),
            "yeah_thats_clean": ("YeahThatsCleanPipeline", "yeah_thats_clean"),
            "shorts": ("ShortsPipeline", "short"),
        }

        # Build channel list — all channels with a known pipeline
        channel_list = []
        for row in rows:
            config = json.loads(row[3]) if row[3] else {}
            pipeline = config.get("pipeline", "shorts")
            if pipeline in pipeline_map:
                channel_list.append({"id": row[0], "name": row[1], "niche": row[2], "config": config, "pipeline": pipeline})

        if not channel_list:
            click.echo("No channels with supported pipelines found.")
            return

        privacy = "public" if public else ("unlisted" if unlisted else "private")

        click.echo(f"\n=== Making Shorts for {len(channel_list)} channels ===")
        click.echo(f"Privacy: {privacy}\n")
        for ch in channel_list:
            click.echo(f"  - {ch['name']} ({ch['pipeline']})")
        click.echo()

        host = os.getenv("TEMPORAL_HOST", "localhost:7233")
        namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        client = await Client.connect(host, namespace=namespace)

        handles = []
        for ch in channel_list:
            workflow_name, content_type = pipeline_map[ch["pipeline"]]

            # Create run
            async with async_session() as session:
                result = await session.execute(
                    text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', :ct) RETURNING id"),
                    {"cid": ch["id"], "ct": content_type},
                )
                run_id = result.scalar_one()
                await session.commit()

            handle = await client.start_workflow(
                workflow_name,
                args=[run_id, ch["id"], True, privacy],
                id=f"{ch['pipeline']}-pipeline-run-{run_id}",
                task_queue="daily-content-pipeline",
            )
            handles.append((ch["name"], run_id, handle))
            click.echo(f"Started {ch['name']} run #{run_id}")

        # Wait for all to complete
        click.echo("\nAll pipelines running in parallel...")
        for name, run_id, handle in handles:
            try:
                result = await handle.result()
                async with async_session() as session:
                    await session.execute(
                        text("UPDATE content_runs SET status = 'completed', completed_at = NOW() WHERE id = :id"),
                        {"id": run_id},
                    )
                    await session.commit()
                click.echo(f"\n{name} done!")
                click.echo(f"  Topic: {result.get('topic', 'n/a')}")
                click.echo(f"  Video: {result.get('video_path', 'n/a')}")
                if result.get("url"):
                    click.echo(f"  URL:   {result['url']}")
            except Exception as e:
                click.echo(f"\n{name} FAILED: {e}")

        click.echo("\nAll done!")

    run_async(_run())


if __name__ == "__main__":
    cli()
