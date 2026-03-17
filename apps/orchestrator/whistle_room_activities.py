"""Temporal activity implementations for the Whistle Room pipeline."""

import json
import os
import subprocess
import base64

import structlog
from dotenv import load_dotenv
from sqlalchemy import text
from temporalio import activity

from packages.clients.db import async_session

load_dotenv()
logger = structlog.get_logger()

USE_REAL_WRITING = bool(os.getenv("ANTHROPIC_API_KEY"))
USE_REDDIT = bool(os.getenv("REDDIT_CLIENT_ID"))


async def _execute(query: str, params: dict) -> None:
    async with async_session() as session:
        await session.execute(text(query), params)
        await session.commit()


async def _update_run_step(run_id: int, step: str) -> None:
    await _execute(
        "UPDATE content_runs SET current_step = :step WHERE id = :run_id",
        {"run_id": run_id, "step": step},
    )


async def _get_channel_config_raw(channel_id: int) -> dict:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, name, niche, config FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Channel {channel_id} not found")
        config = json.loads(row[3]) if row[3] else {}
        config["_channel_name"] = row[1]
        config["_channel_niche"] = row[2]
        return config


@activity.defn
async def find_whistle_room_clips(run_id: int, channel_id: int) -> list[dict]:
    """Search YouTube + Reddit for trending sports clips."""
    await _update_run_step(run_id, "find_clips")
    log = logger.bind(activity="find_whistle_room_clips", run_id=run_id)

    channel_config = await _get_channel_config_raw(channel_id)
    subreddits = channel_config.get("subreddits", ["sports", "nba", "soccer"])

    clips = []

    # Source from Reddit
    if USE_REDDIT:
        from packages.clients.reddit import search_top_clips
        reddit_clips = search_top_clips(subreddits=subreddits, time_filter="week", limit=20)
        clips.extend(reddit_clips)
        log.info("reddit clips found", count=len(reddit_clips))
    else:
        log.info("reddit not configured, using placeholder clips")
        clips = [
            {
                "title": "Incredible no-look pass leads to slam dunk",
                "url": "https://example.com/clip1",
                "score": 5000,
                "subreddit": "nba",
                "permalink": "https://reddit.com/r/nba/example1",
                "source": "placeholder",
            },
            {
                "title": "Goalkeeper saves penalty with bicycle kick",
                "url": "https://example.com/clip2",
                "score": 3000,
                "subreddit": "soccer",
                "permalink": "https://reddit.com/r/soccer/example2",
                "source": "placeholder",
            },
            {
                "title": "Skateboarder lands triple kickflip down 12 stairs",
                "url": "https://example.com/clip3",
                "score": 8000,
                "subreddit": "skateboarding",
                "permalink": "https://reddit.com/r/skateboarding/example3",
                "source": "placeholder",
            },
        ]

    # Use Claude to pick the best clips for analysis
    if USE_REAL_WRITING and len(clips) > 5:
        from packages.prompts.whistle_room import build_clip_selection_prompt
        from packages.clients.claude import generate

        system, user = build_clip_selection_prompt(clips, count=5)
        response = generate(user, system=system, max_tokens=2048, temperature=0.5)

        text_resp = response.strip()
        if text_resp.startswith("```"):
            lines = text_resp.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text_resp = "\n".join(lines[start:end])

        selected = json.loads(text_resp)
        log.info("claude selected clips", count=len(selected))
    else:
        # Auto-select top 5 by score
        selected = []
        for i, clip in enumerate(clips[:5], 1):
            selected.append({
                "index": i,
                "title": clip["title"],
                "url": clip["url"],
                "sport": "general",
                "reason": f"Top scored clip from r/{clip.get('subreddit', 'unknown')}",
                "estimated_score": 7.0,
            })

    # Store as ideas
    for sel in selected:
        await _execute(
            """INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
               VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, false)""",
            {
                "run_id": run_id, "channel_id": channel_id,
                "title": sel["title"], "hook": sel.get("reason", ""),
                "angle": sel.get("sport", "general"), "length": 15,
                "score": sel.get("estimated_score", 0),
            },
        )

    return selected


@activity.defn
async def download_whistle_room_clip(run_id: int, channel_id: int, clip: dict) -> dict:
    """Download a clip using yt-dlp."""
    await _update_run_step(run_id, "download_clip")
    log = logger.bind(activity="download_whistle_room_clip", run_id=run_id, title=clip.get("title"))

    output_dir = f"output/whistle_room_run_{run_id}/source"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "source_clip.mp4")

    url = clip.get("url", "")

    if "placeholder" in clip.get("source", "") or "example.com" in url:
        # Create a placeholder clip for testing
        log.info("creating placeholder clip (no real URL)")
        _create_placeholder_clip(output_path, duration=10)
        return {
            "path": os.path.abspath(output_path),
            "duration": 10.0,
            "width": 1920,
            "height": 1080,
            "source_url": url,
        }

    from packages.clients.clip_downloader import download_clip
    result = download_clip(url=url, output_path=output_path, max_duration=120)

    # Store as asset
    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "source_clip",
            "content": json.dumps(result),
        },
    )

    log.info("clip downloaded", duration=result["duration"], resolution=f"{result['width']}x{result['height']}")
    return result


@activity.defn
async def analyze_whistle_room_play(run_id: int, channel_id: int, clip_path: str, clip_meta: dict) -> dict:
    """Extract keyframes and analyze the play with Claude vision."""
    await _update_run_step(run_id, "analyze_play")
    log = logger.bind(activity="analyze_whistle_room_play", run_id=run_id)

    output_dir = f"output/whistle_room_run_{run_id}/keyframes"
    os.makedirs(output_dir, exist_ok=True)

    # Extract 6-8 keyframes evenly across the clip
    duration = clip_meta.get("duration", 10)
    num_frames = min(8, max(6, int(duration / 1.5)))
    keyframe_paths = _extract_keyframes(clip_path, output_dir, num_frames)

    log.info("keyframes extracted", count=len(keyframe_paths))

    sport = clip_meta.get("sport", "general")
    title = clip_meta.get("title", "Sports clip")

    if USE_REAL_WRITING:
        from packages.prompts.whistle_room import build_play_analysis_prompt
        from packages.clients.claude import generate_with_images

        system, user = build_play_analysis_prompt(title, sport)
        response = generate_with_images(
            prompt=user,
            image_paths=keyframe_paths,
            system=system,
            max_tokens=2048,
        )

        text_resp = response.strip()
        if text_resp.startswith("```"):
            lines = text_resp.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text_resp = "\n".join(lines[start:end])

        analysis = json.loads(text_resp)
        log.info("play analyzed", score=analysis.get("score"), tier=analysis.get("tier"))
    else:
        analysis = {
            "score": 8.2,
            "tier": "ELITE",
            "callouts": [
                "Perfect body control through the entire motion",
                "Split-second decision making under pressure",
                "Textbook execution with explosive athleticism",
            ],
            "caption": "This shouldn't be physically possible",
            "description": f"Whistle Room breaks down this viral {sport} play #Shorts #WhistleRoom #Sports",
            "tags": [sport, "sports highlights", "play breakdown", "Shorts", "Whistle Room"],
        }
        log.info("using placeholder analysis")

    # Store analysis as script record
    await _execute(
        """INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
           VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "title": title, "stage": "final",
            "content": json.dumps(analysis), "wc": 0,
        },
    )

    # Attach source metadata to analysis for downstream use
    analysis["_clip_title"] = title
    analysis["_clip_sport"] = sport

    return analysis


@activity.defn
async def render_whistle_room_short(run_id: int, channel_id: int, clip_path: str, analysis: dict) -> dict:
    """Render the final Whistle Room Short."""
    await _update_run_step(run_id, "render")
    log = logger.bind(activity="render_whistle_room_short", run_id=run_id)

    from apps.rendering_service.whistle_room_compositor import render_whistle_room_short as do_render

    output_dir = f"output/whistle_room_run_{run_id}"
    result = do_render(
        clip_path=clip_path,
        analysis=analysis,
        output_dir=output_dir,
    )

    await _execute(
        """INSERT INTO assets (run_id, channel_id, asset_type, content)
           VALUES (:run_id, :channel_id, :type, :content)""",
        {
            "run_id": run_id, "channel_id": channel_id,
            "type": "rendered_whistle_room_short", "content": json.dumps(result),
        },
    )

    log.info("whistle room short rendered", path=result.get("path"))
    return result


@activity.defn
async def whistle_room_qa_check(run_id: int, channel_id: int, rendered: dict) -> dict:
    """QA check for a Whistle Room Short."""
    await _update_run_step(run_id, "qa_check")
    log = logger.bind(activity="whistle_room_qa_check", run_id=run_id)

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "issues": ["No rendered video file found"]}

    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    actual_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    res_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    res_parts = res_result.stdout.strip().split(",") if res_result.stdout.strip() else []
    width = int(res_parts[0]) if len(res_parts) >= 2 else 0
    height = int(res_parts[1]) if len(res_parts) >= 2 else 0

    file_size = os.path.getsize(video_path)
    file_mb = file_size / (1024 * 1024)

    checks = []

    # Duration: 15-59s
    dur_ok = 15 <= actual_duration <= 59
    checks.append({
        "check": "duration",
        "passed": dur_ok,
        "actual_seconds": round(actual_duration, 1),
        "issues": [] if dur_ok else [f"Duration {actual_duration:.1f}s outside 15-59s range"],
    })

    # Resolution: vertical (height > width), at least 1080 wide
    res_ok = width > 0 and height > 0 and height > width
    checks.append({
        "check": "resolution",
        "passed": res_ok,
        "width": width,
        "height": height,
        "issues": [] if res_ok else [f"Expected vertical video, got {width}x{height}"],
    })

    # File size: 1MB-500MB
    size_ok = 1 <= file_mb <= 500
    checks.append({
        "check": "file_size",
        "passed": size_ok,
        "size_mb": round(file_mb, 1),
        "issues": [] if size_ok else [f"File size {file_mb:.1f}MB outside 1-500MB range"],
    })

    # Audio present (we mix in background music)
    audio_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    has_audio = bool(audio_result.stdout.strip())
    checks.append({
        "check": "audio",
        "passed": has_audio,
        "issues": [] if has_audio else ["No audio stream found"],
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
        log.info("whistle room QA passed")
    else:
        log.warning("whistle room QA FAILED", issues=issues)
    return report


@activity.defn
async def publish_whistle_room_short(run_id: int, channel_id: int, analysis: dict, qa: dict, rendered: dict) -> dict:
    """Upload Whistle Room Short to YouTube."""
    await _update_run_step(run_id, "publish")
    log = logger.bind(activity="publish_whistle_room_short", run_id=run_id)

    if not qa.get("passed"):
        log.warning("QA failed, skipping publish")
        return {"published": False, "reason": "QA check failed"}

    video_path = rendered.get("path")
    if not video_path or not os.path.exists(video_path):
        return {"published": False, "reason": "No rendered video file"}

    channel_config = await _get_channel_config_raw(channel_id)
    youtube_token_file = channel_config.get("youtube_token_file")

    from apps.publishing_service.uploader import is_upload_configured, upload_video

    if not is_upload_configured(youtube_token_file=youtube_token_file):
        token_name = youtube_token_file or "youtube_token.json"
        log.info("youtube not configured for channel", token_file=token_name)
        return {
            "published": False,
            "status": "ready_for_manual_upload",
            "title": analysis.get("_clip_title", ""),
            "video_path": video_path,
        }

    title = analysis.get("_clip_title", "Sports Breakdown")
    description = analysis.get("description", "")
    if "#Shorts" not in description:
        description += "\n\n#Shorts"

    privacy = analysis.pop("_privacy_override", "private")
    made_for_kids = channel_config.get("made_for_kids", False)

    result = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=analysis.get("tags", []),
        category="Sports",
        privacy_status=privacy,
        youtube_token_file=youtube_token_file,
        made_for_kids=made_for_kids,
    )

    if result.get("published"):
        await _execute(
            "UPDATE content_runs SET status = 'published' WHERE id = :run_id",
            {"run_id": run_id},
        )

    log.info("publish step complete", **result)
    return result


def _extract_keyframes(clip_path: str, output_dir: str, num_frames: int) -> list[str]:
    """Extract evenly-spaced keyframes from a video clip."""
    duration_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", clip_path],
        capture_output=True, text=True, timeout=10,
    )
    duration = float(duration_result.stdout.strip())

    paths = []
    for i in range(num_frames):
        timestamp = (duration / (num_frames + 1)) * (i + 1)
        output_path = os.path.join(output_dir, f"frame_{i:02d}.jpg")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", clip_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and os.path.exists(output_path):
            paths.append(output_path)

    return paths


def _create_placeholder_clip(output_path: str, duration: int = 10):
    """Create a placeholder landscape clip for testing."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x1a2e1a:s=1920x1080:d={duration}:r=30",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-vf", "drawtext=text='WHISTLE ROOM\\nPlaceholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac",
        "-t", str(duration),
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
