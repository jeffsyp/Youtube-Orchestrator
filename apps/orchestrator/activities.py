"""Temporal activity implementations for the daily content pipeline.

Phase 1: All activities can fall back to fake data when API keys aren't set.
Phase 2: Research (discover, score) uses real YouTube API when YOUTUBE_API_KEY is set.
Phase 3: Writing (templates, ideas, outline, script, critique, revision) uses Claude when ANTHROPIC_API_KEY is set.
Phase 4: Media (visual plan, voice plan, SRT, packaging) uses Claude when ANTHROPIC_API_KEY is set.
"""

import json
import os
from datetime import datetime, timezone

import structlog
from dotenv import load_dotenv
from sqlalchemy import text
from temporalio import activity

from packages.clients.db import async_session

load_dotenv()
logger = structlog.get_logger()

USE_REAL_RESEARCH = bool(os.getenv("YOUTUBE_API_KEY"))
USE_REAL_WRITING = bool(os.getenv("ANTHROPIC_API_KEY"))


async def _execute(query: str, params: dict) -> None:
    async with async_session() as session:
        await session.execute(text(query), params)
        await session.commit()


async def _get_channel_config(channel_id: int):
    """Load channel config from DB and return as ChannelConfig."""
    from packages.schemas.channel import ChannelConfig
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, name, niche, config FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Channel {channel_id} not found")

        config_json = json.loads(row[3]) if row[3] else {}
        return ChannelConfig(
            channel_id=row[0],
            name=row[1],
            niche=row[2],
            search_terms=config_json.get("search_terms", []),
            tone=config_json.get("tone", "informative and engaging"),
            scoring_weights=config_json.get("scoring_weights", {
                "views_ratio": 0.4,
                "recency": 0.3,
                "topic_relevance": 0.3,
            }),
        )


async def _update_run_step(run_id: int, step: str) -> None:
    await _execute(
        "UPDATE content_runs SET current_step = :step WHERE id = :run_id",
        {"run_id": run_id, "step": step},
    )


async def _get_past_idea_titles(channel_id: int, limit: int = 50) -> list[str]:
    """Get titles of previously generated ideas to avoid repeats."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT DISTINCT title FROM ideas WHERE channel_id = :cid ORDER BY title LIMIT :lim"),
            {"cid": channel_id, "lim": limit},
        )
        return [row[0] for row in result.fetchall()]


@activity.defn
async def mark_run_awaiting_approval(run_id: int, step: str) -> None:
    """Mark a run as awaiting human approval."""
    await _execute(
        "UPDATE content_runs SET status = 'awaiting_approval', current_step = :step WHERE id = :run_id",
        {"run_id": run_id, "step": step},
    )
    log = logger.bind(activity="mark_run_awaiting_approval", run_id=run_id, step=step)
    log.info("run awaiting approval")


# ---------------------------------------------------------------------------
# Phase 2: Research activities
# ---------------------------------------------------------------------------


@activity.defn
async def discover_candidates(run_id: int, channel_id: int) -> list[dict]:
    await _update_run_step(run_id, "discover_candidates")
    log = logger.bind(activity="discover_candidates", run_id=run_id, channel_id=channel_id)

    if USE_REAL_RESEARCH:
        channel_config = await _get_channel_config(channel_id)
        from apps.research_service.discovery import discover_candidates as discover
        candidates = discover(channel_config)
        log.info("discovered real candidates", count=len(candidates))
    else:
        from apps.orchestrator.fake_data import FAKE_CANDIDATES
        candidates = FAKE_CANDIDATES
        log.info("using fake candidates", count=len(candidates))

    for c in candidates:
        await _execute(
            """INSERT INTO source_candidates
               (run_id, channel_id, video_id, title, channel_name, channel_subscribers,
                views, published_at, duration_seconds, tags, breakout_score)
               VALUES (:run_id, :channel_id, :video_id, :title, :channel_name, :subs,
                :views, :published_at, :duration, :tags, :score)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "video_id": c.video_id, "title": c.title,
                "channel_name": c.channel_name, "subs": c.channel_subscribers,
                "views": c.views, "published_at": c.published_at,
                "duration": c.duration_seconds, "tags": json.dumps(c.tags),
                "score": c.breakout_score,
            },
        )

    log.info("candidates stored", count=len(candidates))
    return [c.model_dump(mode="json") for c in candidates]


@activity.defn
async def score_breakouts(run_id: int, channel_id: int, candidates: list[dict]) -> list[dict]:
    await _update_run_step(run_id, "score_breakouts")
    log = logger.bind(activity="score_breakouts", run_id=run_id)
    log.info("scoring candidates")

    if USE_REAL_RESEARCH:
        from packages.schemas.research import CandidateVideo
        from apps.research_service.scoring import score_candidates

        channel_config = await _get_channel_config(channel_id)
        candidate_objs = [CandidateVideo(**c) for c in candidates]
        scored = score_candidates(candidate_objs, channel_config)
    else:
        from apps.orchestrator.fake_data import FAKE_SCORED_CANDIDATES
        scored = FAKE_SCORED_CANDIDATES

    for c in scored:
        await _execute(
            "UPDATE source_candidates SET breakout_score = :score WHERE run_id = :run_id AND video_id = :vid",
            {"score": c.breakout_score, "run_id": run_id, "vid": c.video_id},
        )

    log.info("scoring complete")
    return [c.model_dump(mode="json") for c in scored]


# ---------------------------------------------------------------------------
# Phase 3: Writing activities (Claude-powered when ANTHROPIC_API_KEY is set)
# ---------------------------------------------------------------------------


@activity.defn
async def extract_templates(run_id: int, channel_id: int, scored_candidates: list[dict]) -> list[dict]:
    await _update_run_step(run_id, "extract_templates")
    log = logger.bind(activity="extract_templates", run_id=run_id)

    if USE_REAL_WRITING:
        from packages.schemas.research import CandidateVideo
        from apps.research_service.analysis import extract_templates as extract

        channel_config = await _get_channel_config(channel_id)
        candidate_objs = [CandidateVideo(**c) for c in scored_candidates]
        templates = extract(candidate_objs, channel_config.niche)
        log.info("extracted real templates", count=len(templates))
    else:
        from apps.orchestrator.fake_data import FAKE_TEMPLATES
        templates = FAKE_TEMPLATES
        log.info("using fake templates", count=len(templates))

    for t in templates:
        await _execute(
            """INSERT INTO templates (run_id, channel_id, pattern_name, description, hook_style, structure, source_video_ids)
               VALUES (:run_id, :channel_id, :name, :desc, :hook, :structure, :source_ids)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "name": t.pattern_name, "desc": t.description,
                "hook": t.hook_style, "structure": json.dumps(t.structure),
                "source_ids": json.dumps(t.source_video_ids),
            },
        )

    log.info("templates stored")
    return [t.model_dump(mode="json") for t in templates]


@activity.defn
async def generate_variants(run_id: int, channel_id: int, templates: list[dict]) -> list[dict]:
    await _update_run_step(run_id, "generate_variants")
    log = logger.bind(activity="generate_variants", run_id=run_id)

    if USE_REAL_WRITING:
        from packages.schemas.research import CandidateVideo, TemplatePattern
        from apps.research_service.analysis import generate_ideas

        channel_config = await _get_channel_config(channel_id)
        template_objs = [TemplatePattern(**t) for t in templates]

        # Get scored candidates from DB for context
        async with async_session() as session:
            result = await session.execute(
                text("SELECT video_id, title, channel_name, channel_subscribers, views, published_at, duration_seconds, tags, breakout_score FROM source_candidates WHERE run_id = :run_id ORDER BY breakout_score DESC"),
                {"run_id": run_id},
            )
            rows = result.fetchall()
        candidate_objs = [
            CandidateVideo(
                video_id=r[0], title=r[1], channel_name=r[2], channel_subscribers=r[3],
                views=r[4], published_at=r[5], duration_seconds=r[6],
                tags=json.loads(r[7]) if r[7] else [], breakout_score=r[8],
            ) for r in rows
        ]

        # Get past ideas to avoid repeats
        past_titles = await _get_past_idea_titles(channel_id)
        ideas = generate_ideas(template_objs, candidate_objs, channel_config.niche, channel_config.tone, past_titles)
        log.info("generated real ideas", count=len(ideas), past_avoided=len(past_titles))
    else:
        from apps.orchestrator.fake_data import FAKE_IDEAS
        ideas = FAKE_IDEAS
        log.info("using fake ideas", count=len(ideas))

    for idea in ideas:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, :selected)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": idea.title, "hook": idea.hook, "angle": idea.angle,
                "length": idea.target_length_seconds, "score": idea.score,
                "selected": idea.selected,
            },
        )

    log.info("ideas stored")
    return [i.model_dump(mode="json") for i in ideas]


@activity.defn
async def select_best_idea(run_id: int, channel_id: int, ideas: list[dict]) -> dict:
    """Auto-selects the highest-scored idea. Human gate can be added later."""
    await _update_run_step(run_id, "select_best_idea")
    log = logger.bind(activity="select_best_idea", run_id=run_id)

    # Find the selected idea (already marked during generation)
    selected = next((i for i in ideas if i.get("selected")), None)
    if not selected:
        # Fallback: pick highest score
        selected = max(ideas, key=lambda i: i.get("score", 0))

    log.info("idea selected", title=selected["title"])
    return selected


@activity.defn
async def build_outline(run_id: int, channel_id: int, idea: dict) -> dict:
    await _update_run_step(run_id, "build_outline")
    log = logger.bind(activity="build_outline", run_id=run_id)
    log.info("building outline", idea=idea["title"])

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        from apps.writing_service.writer import build_outline as gen_outline
        outline = gen_outline(idea, channel_config.niche)
    else:
        from apps.orchestrator.fake_data import FAKE_OUTLINE
        outline = FAKE_OUTLINE

    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": outline.idea_title, "stage": "outline",
            "content": json.dumps(outline.model_dump(mode="json")),
            "wc": 0,
        },
    )

    log.info("outline stored")
    return outline.model_dump(mode="json")


@activity.defn
async def write_script(run_id: int, channel_id: int, outline: dict) -> dict:
    await _update_run_step(run_id, "write_script")
    log = logger.bind(activity="write_script", run_id=run_id)
    log.info("writing script draft")

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        from apps.writing_service.writer import write_script as gen_script
        script = gen_script(outline, channel_config.niche, channel_config.tone)
    else:
        from apps.orchestrator.fake_data import FAKE_SCRIPT_DRAFT
        script = FAKE_SCRIPT_DRAFT

    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": script.idea_title, "stage": "draft",
            "content": script.content, "wc": script.word_count,
        },
    )

    log.info("draft stored", word_count=script.word_count)
    return script.model_dump(mode="json")


@activity.defn
async def critique_script(run_id: int, channel_id: int, script: dict) -> dict:
    await _update_run_step(run_id, "critique_script")
    log = logger.bind(activity="critique_script", run_id=run_id)
    log.info("critiquing script")

    if USE_REAL_WRITING:
        from apps.writing_service.writer import critique_script as gen_critique
        result = gen_critique(script)
    else:
        from apps.orchestrator.fake_data import FAKE_SCRIPT_CRITIQUE
        result = FAKE_SCRIPT_CRITIQUE

    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count, critique_notes)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc, :notes)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": result.idea_title, "stage": "critique",
            "content": result.content,
            "wc": result.word_count,
            "notes": result.critique_notes,
        },
    )

    log.info("critique stored")
    return result.model_dump(mode="json")


@activity.defn
async def revise_script(run_id: int, channel_id: int, critique: dict) -> dict:
    await _update_run_step(run_id, "revise_script")
    log = logger.bind(activity="revise_script", run_id=run_id)
    log.info("revising script")

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        from apps.writing_service.writer import revise_script as gen_revise
        result = gen_revise(critique, channel_config.tone)
    else:
        from apps.orchestrator.fake_data import FAKE_SCRIPT_FINAL
        result = FAKE_SCRIPT_FINAL

    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": result.idea_title, "stage": "final",
            "content": result.content, "wc": result.word_count,
        },
    )

    log.info("final script stored", word_count=result.word_count)
    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Phase 4: Media activities (Claude-powered when ANTHROPIC_API_KEY is set)
# ---------------------------------------------------------------------------


@activity.defn
async def build_visual_plan(run_id: int, channel_id: int, script: dict) -> dict:
    await _update_run_step(run_id, "build_visual_plan")
    log = logger.bind(activity="build_visual_plan", run_id=run_id)
    log.info("building visual plan")

    if USE_REAL_WRITING:
        from apps.media_service.planner import build_visual_plan as gen_visual
        plan = gen_visual(script["content"], script["idea_title"])
    else:
        from apps.orchestrator.fake_data import FAKE_VISUAL_PLAN
        plan = FAKE_VISUAL_PLAN

    for shot in plan.shots:
        await _execute(
            """INSERT INTO assets (run_id, channel_id, asset_type, content)
               VALUES (:run_id, :channel_id, :type, :content)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "type": "shot", "content": json.dumps(shot.model_dump(mode="json")),
            },
        )

    log.info("visual plan stored", shots=len(plan.shots))
    return plan.model_dump(mode="json")


@activity.defn
async def build_voice_plan(run_id: int, channel_id: int, script: dict) -> dict:
    await _update_run_step(run_id, "build_voice_plan")
    log = logger.bind(activity="build_voice_plan", run_id=run_id)
    log.info("building voice plan")

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        from apps.media_service.planner import build_voice_plan as gen_voice
        plan = gen_voice(script["content"], script["idea_title"], channel_config.tone)
    else:
        from apps.orchestrator.fake_data import FAKE_VOICE_PLAN
        plan = FAKE_VOICE_PLAN

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "voice_plan",
            "content": json.dumps(plan.model_dump(mode="json")),
        },
    )

    log.info("voice plan stored")
    return plan.model_dump(mode="json")


@activity.defn
async def generate_voiceover(run_id: int, channel_id: int, script: dict) -> dict:
    """Generate voiceover audio from the final script using ElevenLabs."""
    await _update_run_step(run_id, "generate_voiceover")
    log = logger.bind(activity="generate_voiceover", run_id=run_id)

    use_voice = bool(os.getenv("ELEVENLABS_API_KEY"))
    if not use_voice:
        log.info("elevenlabs not configured, skipping voiceover")
        return {"status": "skipped", "reason": "ELEVENLABS_API_KEY not set"}

    from apps.media_service.planner import generate_voiceover as gen_voice

    output_dir = f"output/run_{run_id}"
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/voiceover.mp3"

    try:
        result = gen_voice(script["content"], output_path)
    except Exception as e:
        log.warning("voiceover failed, continuing without it", error=str(e))
        result = {"status": "failed", "error": str(e)}

    if result.get("status") == "generated":
        await _execute(
            """INSERT INTO assets (run_id, channel_id, asset_type, content)
               VALUES (:run_id, :channel_id, :type, :content)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "type": "voiceover",
                "content": json.dumps(result),
            },
        )

    log.info("voiceover step complete", **result)
    return result


@activity.defn
async def render_video(run_id: int, channel_id: int, visual: dict, voiceover: dict, srt_content: str | None, script_content: str | None = None) -> dict:
    """Render the final video — stock footage + voiceover + text overlays."""
    await _update_run_step(run_id, "render_video")
    log = logger.bind(activity="render_video", run_id=run_id)
    log.info("rendering video")

    from apps.rendering_service.compositor import render_video as do_render

    output_dir = f"output/run_{run_id}"
    voiceover_path = voiceover.get("path") if voiceover.get("status") == "generated" else None

    result = do_render(
        shots=visual.get("shots", []),
        voiceover_path=voiceover_path,
        srt_content=srt_content,
        output_dir=output_dir,
        script_content=script_content,
    )

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "rendered_video",
            "content": json.dumps(result),
        },
    )

    log.info("video rendered", path=result.get("path"))
    return result


@activity.defn
async def package_video(run_id: int, channel_id: int, script: dict, visual: dict, voice: dict) -> dict:
    await _update_run_step(run_id, "package_video")
    log = logger.bind(activity="package_video", run_id=run_id)
    log.info("packaging video")

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        from apps.media_service.planner import build_package, generate_srt
        srt = generate_srt(script["content"])
        package = build_package(script["idea_title"], script["content"], channel_config.niche, srt)
    else:
        from apps.orchestrator.fake_data import FAKE_PACKAGE
        package = FAKE_PACKAGE

    await _execute(
        """INSERT INTO packages (run_id, channel_id, title, description, tags, category, status)
           VALUES (:run_id, :channel_id, :title, :desc, :tags, :cat, :status)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": package.title, "desc": package.description,
            "tags": json.dumps(package.tags), "cat": package.category,
            "status": package.status,
        },
    )

    log.info("package stored")
    return package.model_dump(mode="json")


# ---------------------------------------------------------------------------
# QA and Publishing (Phase 5)
# ---------------------------------------------------------------------------


@activity.defn
async def qa_check(run_id: int, channel_id: int, package: dict, rendered: dict) -> dict:
    """Run QA checks on both the package metadata and the rendered video."""
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="qa_check", run_id=run_id)
    log.info("running QA checks")

    # Package metadata checks
    package_checks = {
        "has_title": bool(package.get("title")),
        "has_description": bool(package.get("description")),
        "has_tags": bool(package.get("tags")),
    }
    package_passed = all(package_checks.values())

    # Video QA checks
    video_qa = {"passed": True, "issues": []}
    video_path = rendered.get("path")
    if video_path and os.path.exists(video_path):
        from apps.rendering_service.qa import run_all_checks
        voiceover_path = f"output/run_{run_id}/voiceover.mp3"
        vo_path = voiceover_path if os.path.exists(voiceover_path) else None
        video_qa = run_all_checks(video_path, voiceover_path=vo_path)
    else:
        video_qa["passed"] = False
        video_qa["issues"] = ["No rendered video file found"]

    result = {
        "package_checks": package_checks,
        "package_passed": package_passed,
        "video_qa": video_qa,
        "passed": package_passed and video_qa["passed"],
        "issues": video_qa.get("issues", []),
    }

    if result["passed"]:
        log.info("QA passed", checks=video_qa.get("checks_run", 0))
    else:
        log.warning("QA FAILED", issues=result["issues"])

    return result


@activity.defn
async def publish(run_id: int, channel_id: int, package: dict, qa: dict) -> dict:
    """Phase 5: Will upload to YouTube. Currently logs as ready-to-publish."""
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish", run_id=run_id)

    if not qa.get("passed"):
        log.warning("QA check failed, skipping publish")
        return {"published": False, "reason": "QA check failed"}

    # Phase 5 TODO: Real YouTube upload using OAuth2
    # For now, mark as ready for manual upload
    result = {
        "published": False,
        "status": "ready_for_manual_upload",
        "title": package.get("title"),
        "message": "Package is ready. YouTube upload requires OAuth2 setup (Phase 5).",
    }

    log.info("publish step complete", **result)
    return result
