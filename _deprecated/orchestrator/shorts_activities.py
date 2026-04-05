"""Temporal activity implementations for the Shorts pipeline."""

import json
import os

import structlog
from dotenv import load_dotenv
from sqlalchemy import text
from temporalio import activity

from packages.clients.db import async_session

load_dotenv()
logger = structlog.get_logger()

USE_REAL_WRITING = bool(os.getenv("ANTHROPIC_API_KEY"))
USE_GEMINI = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


async def _execute(query: str, params: dict) -> None:
    async with async_session() as session:
        await session.execute(text(query), params)
        await session.commit()


async def _update_run_step(run_id: int, step: str) -> None:
    await _execute(
        "UPDATE content_runs SET current_step = :step WHERE id = :run_id",
        {"run_id": run_id, "step": step},
    )


async def _get_channel_config(channel_id: int):
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
            channel_id=row[0], name=row[1], niche=row[2],
            search_terms=config_json.get("search_terms", []),
            tone=config_json.get("tone", "informative and engaging"),
            scoring_weights=config_json.get("scoring_weights", {
                "views_ratio": 0.4, "recency": 0.3, "topic_relevance": 0.3,
            }),
        )


async def _get_past_shorts_titles(channel_id: int, limit: int = 50) -> list[str]:
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT DISTINCT s.idea_title FROM scripts s
                    JOIN content_runs cr ON cr.id = s.run_id
                    WHERE s.channel_id = :cid AND cr.content_type = 'short'
                    ORDER BY s.idea_title LIMIT :lim"""),
            {"cid": channel_id, "lim": limit},
        )
        return [row[0] for row in result.fetchall()]


@activity.defn
async def pick_shorts_topics(run_id: int, channel_id: int) -> list[dict]:
    """Generate topic ideas for Shorts."""
    await _update_run_step(run_id, "pick_topics")
    log = logger.bind(activity="pick_shorts_topics", run_id=run_id)

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        past_titles = await _get_past_shorts_titles(channel_id)
        from apps.writing_service.shorts_writer import pick_shorts_topics as pick
        topics = pick(channel_config.niche, channel_config.tone, past_titles)
        log.info("generated real topics", count=len(topics))
    else:
        topics = [
            {"topic": "3 AI tools that replaced junior devs this month", "hook_angle": "Job displacement fear", "format": "three_tips", "score": 8.5},
            {"topic": "You're using ChatGPT wrong", "hook_angle": "Common mistake callout", "format": "wrong_way", "score": 8.2},
            {"topic": "This free app does what Photoshop can't", "hook_angle": "Underdog vs giant", "format": "before_after", "score": 7.9},
        ]
        log.info("using fake topics")

    # Store topics as ideas
    for t in topics:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, false)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": t["topic"], "hook": t.get("hook_angle", ""),
                "angle": t.get("format", ""), "length": 60,
                "score": t.get("score", 0),
            },
        )

    return topics


@activity.defn
async def write_shorts_script(run_id: int, channel_id: int, topic: dict) -> dict:
    """Write a Shorts script in one pass."""
    await _update_run_step(run_id, "write_script")
    log = logger.bind(activity="write_shorts_script", run_id=run_id)

    if USE_REAL_WRITING:
        channel_config = await _get_channel_config(channel_id)
        past_titles = await _get_past_shorts_titles(channel_id)
        from apps.writing_service.shorts_writer import write_shorts_script as write
        script = write(topic["topic"], channel_config.niche, channel_config.tone, past_titles)
        log.info("real script written", title=script.get("title"), words=script.get("word_count"))
    else:
        script = {
            "title": "3 AI Tools That Replaced Junior Devs",
            "format": "three_tips",
            "hook": {"text": "Three AI tools just replaced an entire junior dev team.", "style": "bold_claim"},
            "script": "Three AI tools just replaced an entire junior dev team. [CUT] And no, I'm not exaggerating. [CUT] First up — Cursor. It writes, refactors, and debugs code faster than most interns. [CUT] Second — v0 by Vercel. Full UI components from a text prompt. [CUT] Third — Devin. An actual AI software engineer that plans and ships features solo. [CUT] Now before you panic... these tools still need a human steering the ship. [CUT] But if you're not learning how to use them? Someone who is will take your job.",
            "loop_ending": "Someone who is will take your job.",
            "word_count": 89,
            "description": "3 AI tools that are changing software development forever. #Shorts #AI #Tech",
            "tags": ["AI", "coding", "software engineering", "tech", "Shorts"],
        }
        log.info("using fake script")

    # Store script
    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": script.get("title", topic["topic"]), "stage": "final",
            "content": script.get("script", ""), "wc": script.get("word_count", 0),
        },
    )

    return script


@activity.defn
async def build_shorts_visual_plan(run_id: int, channel_id: int, script: dict) -> list[dict]:
    """Create a fast-cut visual plan for a Short."""
    await _update_run_step(run_id, "visual_plan")
    log = logger.bind(activity="build_shorts_visual_plan", run_id=run_id)

    if USE_REAL_WRITING:
        from packages.prompts.shorts import build_shorts_visual_plan_prompt
        from packages.clients.claude import generate
        system, user = build_shorts_visual_plan_prompt(
            script.get("script", ""), script.get("title", "")
        )
        response = generate(user, system=system, max_tokens=4096, temperature=0.5)

        # Parse JSON
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end])
        try:
            scenes = json.loads(text)
        except json.JSONDecodeError:
            fixed = text.rstrip()
            if fixed.count('"') % 2 != 0:
                fixed += '"'
            fixed += "}" * (fixed.count("{") - fixed.count("}"))
            fixed += "]" * (fixed.count("[") - fixed.count("]"))
            scenes = json.loads(fixed)

        # Validate scenes
        valid = []
        for s in scenes:
            if "type" not in s:
                continue
            s["duration"] = max(1.5, min(4, float(s.get("duration", 3))))
            valid.append(s)
        scenes = valid

        log.info("real visual plan", scenes=len(scenes))
    else:
        scenes = [
            {"type": "hook_card", "duration": 2, "text": "3 AI tools just replaced junior devs"},
            {"type": "footage", "duration": 3, "search_query": "person coding laptop"},
            {"type": "text_punch", "duration": 2, "text": "Cursor AI"},
            {"type": "footage", "duration": 3, "search_query": "software code screen"},
            {"type": "text_punch", "duration": 2, "text": "v0 by Vercel"},
            {"type": "footage", "duration": 3, "search_query": "web design interface"},
            {"type": "text_punch", "duration": 2, "text": "Devin AI"},
            {"type": "footage", "duration": 3, "search_query": "robot artificial intelligence"},
        ]
        log.info("using fake visual plan")

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "shorts_visual_plan",
            "content": json.dumps(scenes),
        },
    )

    return scenes


@activity.defn
async def generate_shorts_voiceover(run_id: int, channel_id: int, script: dict) -> dict:
    """Generate voiceover for a Short."""
    await _update_run_step(run_id, "voiceover")
    log = logger.bind(activity="generate_shorts_voiceover", run_id=run_id)

    use_voice = bool(os.getenv("ELEVENLABS_API_KEY"))
    if not use_voice:
        log.info("elevenlabs not configured, skipping voiceover")
        return {"status": "skipped", "reason": "ELEVENLABS_API_KEY not set"}

    from apps.media_service.planner import generate_voiceover as gen_voice

    output_dir = f"output/short_run_{run_id}"
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/voiceover.mp3"

    # Strip [CUT] markers from script for voiceover
    narration = script.get("script", "").replace("[CUT]", " ").strip()

    try:
        result = gen_voice(narration, output_path)
    except Exception as e:
        log.warning("voiceover failed", error=str(e))
        return {"status": "failed", "error": str(e)}

    if result.get("status") == "generated":
        await _execute(
            """INSERT INTO assets (run_id, channel_id, asset_type, content)
               VALUES (:run_id, :channel_id, :type, :content)""",
            {"run_id": run_id, "channel_id": channel_id,
             "type": "shorts_voiceover", "content": json.dumps(result)},
        )

    log.info("shorts voiceover complete", **result)
    return result


@activity.defn
async def generate_shorts_srt(run_id: int, script: dict) -> str | None:
    """Generate SRT subtitles from a Shorts script."""
    narration = script.get("script", "").replace("[CUT]", " ").strip()
    if not narration:
        return None
    from apps.media_service.planner import generate_srt
    return generate_srt(narration)


@activity.defn
async def render_short(run_id: int, channel_id: int, scenes: list[dict], voiceover: dict, srt_content: str | None, script_text: str | None = None) -> dict:
    """Render the final vertical Short video."""
    await _update_run_step(run_id, "render_short")
    log = logger.bind(activity="render_short", run_id=run_id)
    log.info("rendering short")

    from apps.rendering_service.shorts_compositor import render_short as do_render

    output_dir = f"output/short_run_{run_id}"
    os.makedirs(output_dir, exist_ok=True)
    voiceover_path = voiceover.get("path") if voiceover.get("status") == "generated" else None

    # Save SRT to disk for YouTube captions upload
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        log.info("srt saved", path=srt_path)

    result = do_render(
        scenes=scenes,
        voiceover_path=voiceover_path,
        srt_content=srt_content,
        output_dir=output_dir,
        script_text=script_text,
    )

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id,
         "type": "rendered_short", "content": json.dumps(result)},
    )

    log.info("short rendered", path=result.get("path"))
    return result


@activity.defn
async def shorts_qa_check(run_id: int, channel_id: int, rendered: dict) -> dict:
    """QA check for a Short — vertical resolution, duration 15-90s."""
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="shorts_qa_check", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "issues": ["No rendered video file found"]}

    from apps.rendering_service.qa import (
        check_duration, check_resolution, check_audio_present, check_file_size,
    )

    # Check actual duration is ≤ 60s (YouTube Shorts requirement)
    import subprocess
    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    actual_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    checks = [
        check_duration(video_path, f"output/short_run_{run_id}/voiceover.mp3", tolerance=5.0),
        check_resolution(video_path, expected_width=1080, expected_height=1920),
        check_audio_present(video_path),
        check_file_size(video_path, min_mb=1, max_mb=500),
    ]

    # Hard fail if over 60 seconds — won't be classified as a Short
    if actual_duration > 60:
        checks.append({
            "check": "shorts_max_duration",
            "passed": False,
            "issues": [f"Duration {actual_duration:.1f}s exceeds 60s Shorts limit"],
        })

    all_passed = all(c["passed"] for c in checks)
    issues = [f"[{c['check']}] {issue}" for c in checks for issue in c.get("issues", [])]

    report = {
        "passed": all_passed,
        "checks_run": len(checks),
        "issues": issues,
        "details": checks,
    }

    if all_passed:
        log.info("shorts QA passed")
    else:
        log.warning("shorts QA FAILED", issues=issues)
    return report


@activity.defn
async def publish_short(run_id: int, channel_id: int, script: dict, qa: dict, rendered: dict) -> dict:
    """Upload Short to YouTube."""
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish_short", run_id=run_id)

    if not qa.get("passed"):
        log.warning("QA failed, skipping publish")
        return {"published": False, "reason": "QA check failed"}

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"published": False, "reason": "No rendered video file"}

    if not is_upload_configured():
        log.info("youtube not configured, marking ready for manual upload")
        return {
            "published": False,
            "status": "ready_for_manual_upload",
            "title": script.get("title"),
            "video_path": video_path,
        }

    # Build description with #Shorts tag
    description = script.get("description", "")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"

    run_dir = f"output/short_run_{run_id}"
    captions_path = os.path.join(run_dir, "subtitles.srt")
    captions = captions_path if os.path.exists(captions_path) else None

    privacy = script.pop("_privacy_override", "private")

    result = upload_video(
        video_path=video_path,
        title=script.get("title", ""),
        description=description,
        tags=script.get("tags", []),
        category="Science & Technology",
        privacy_status=privacy,
        captions_path=captions,
    )

    # Store publish result as asset for URL tracking
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "publish_result", "content": json.dumps(result),
        },
    )

    if result.get("published"):
        await _execute(
            "UPDATE content_runs SET status = 'published' WHERE id = :run_id",
            {"run_id": run_id},
        )

    log.info("publish step complete", **result)
    return result


@activity.defn
async def review_shorts_video(run_id: int, channel_id: int, rendered: dict, script: dict) -> dict:
    """Use Gemini to watch and critique the final Signal Intel Short."""
    await _update_run_step(run_id, "video_review")
    log = logger.bind(activity="review_shorts_video", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"reviewed": False, "reason": "No video file"}

    if not USE_GEMINI:
        return {"reviewed": False, "reason": "GEMINI_API_KEY not set", "overall_score": 0}

    from packages.clients.gemini import review_video

    title = script.get("title", "Unknown")

    from packages.prompts.video_review import build_review_prompt
    from apps.orchestrator.concept_engine import get_video_feedback
    video_fb = await get_video_feedback(channel_id)
    prompt = build_review_prompt(script, "Signal Intel", "Tech explainers", video_feedback=video_fb or None)

    try:
        response = review_video(video_path, prompt)
        text_resp = response.strip()
        if text_resp.startswith("```"):
            lines = text_resp.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text_resp = "\n".join(lines[start:end])
        review = json.loads(text_resp)
        review["reviewed"] = True
    except Exception as e:
        log.warning("review failed", error=str(e))
        review = {"reviewed": False, "reason": str(e), "overall_score": 0}

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {"run_id": run_id, "channel_id": channel_id, "type": "video_review", "content": json.dumps(review)},
    )

    # Store feedback for the feedback loop
    from apps.orchestrator.feedback_loop import store_feedback
    await store_feedback(channel_id, review)

    log.info("review complete", overall=review.get("overall_score"))
    return review
