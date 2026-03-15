"""Video compositor — assembles footage, cards, overlays, and audio into a final MP4.

Uses the Director Agent's scene plan to render each scene appropriately:
- Footage scenes: download from Pexels, trim, speed-normalize
- Stat cards: render with Pillow
- Title cards: render with Pillow

Then concatenates with intro/outro, mixes voiceover, applies text overlays.
"""

import os
import subprocess

import structlog

logger = structlog.get_logger()


def _run_ffmpeg(args: list[str], description: str = "", timeout: int = 600) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y"] + args
    log = logger.bind(service="rendering", action="ffmpeg")
    log.debug("running ffmpeg", description=description)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        log.error("ffmpeg failed", stderr=result.stderr[-300:] if result.stderr else "")
        raise RuntimeError(f"FFmpeg failed ({description}): {result.stderr[-200:]}")
    return result


def _get_video_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _get_fps(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        num, den = result.stdout.strip().split("/")
        return int(num) / int(den)
    except (ValueError, ZeroDivisionError):
        return 30


def trim_and_normalize(input_path: str, output_path: str, duration: float) -> str:
    """Trim a stock clip and speed up to 1.5x for energy (also fixes slow-mo)."""
    source_dur = _get_video_duration(input_path)
    source_fps = _get_fps(input_path)

    # Speed up: 1.5x for normal clips, 2.5x for high-fps (slow-mo) clips
    speed = 2.5 if source_fps >= 48 else 1.5
    # Need more source material since we're speeding up
    source_needed = duration * speed
    start = min(0.5, max(0, source_dur - source_needed - 0.5))

    _run_ffmpeg(
        [
            "-ss", str(start),
            "-i", input_path,
            "-t", str(source_needed),
            "-vf", f"setpts={1/speed}*PTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1:color=black,fps=30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-an", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-video_track_timescale", "30000",
            output_path,
        ],
        description=f"trim+speed {os.path.basename(input_path)}",
    )
    return output_path


def render_scene(scene: dict, index: int, output_dir: str) -> str | None:
    """Render a single scene based on its type."""
    log = logger.bind(service="rendering", scene=index, type=scene["type"])
    clip_path = os.path.join(output_dir, "scenes", f"scene_{index:03d}.mp4")
    os.makedirs(os.path.dirname(clip_path), exist_ok=True)

    if scene["type"] == "footage":
        from packages.clients.pexels import search_and_download
        stock_path = os.path.join(output_dir, "stock_clips", f"stock_{index:03d}.mp4")
        os.makedirs(os.path.dirname(stock_path), exist_ok=True)

        query = scene.get("search_query", "technology")
        result = search_and_download(query, stock_path)
        if not result:
            # Fallback queries
            for fallback in ["technology office", "people working", "city street"]:
                result = search_and_download(fallback, stock_path)
                if result:
                    break

        if not result:
            log.warning("no footage found", query=query)
            return None

        trim_and_normalize(stock_path, clip_path, scene["duration"])
        log.info("footage scene rendered", query=query)
        return clip_path

    elif scene["type"] == "stat_card":
        from apps.rendering_service.cards import generate_stat_card
        generate_stat_card(
            stat_text=scene.get("stat_text", ""),
            subtitle=scene.get("subtitle", ""),
            output_path=clip_path,
            duration=scene["duration"],
        )
        log.info("stat card rendered", stat=scene.get("stat_text"))
        return clip_path

    elif scene["type"] == "title_card":
        from apps.rendering_service.cards import generate_title_card
        generate_title_card(
            title_text=scene.get("title_text", ""),
            output_path=clip_path,
            duration=scene["duration"],
        )
        log.info("title card rendered", title=scene.get("title_text"))
        return clip_path

    return None


def render_video(
    shots: list[dict],
    voiceover_path: str | None,
    srt_content: str | None,
    output_dir: str,
    script_content: str | None = None,
) -> dict:
    """Full rendering pipeline using the Director Agent's scene plan."""
    log = logger.bind(service="rendering", action="render_video")
    log.info("starting video render")

    os.makedirs(output_dir, exist_ok=True)

    # Get target duration from voiceover
    target_duration = 0
    if voiceover_path and os.path.exists(voiceover_path):
        target_duration = _get_video_duration(voiceover_path)
        log.info("target duration from voiceover", seconds=round(target_duration))

    # Step 1: Use Director Agent to create unified scene plan
    if script_content and target_duration > 0:
        from apps.rendering_service.director import create_visual_plan
        scenes = create_visual_plan(script_content, target_duration, "Video")
        log.info("director plan created", scenes=len(scenes))
    else:
        # Fallback to old shot-based approach
        scenes = [{"type": "footage", "duration": 6, "search_query": s.get("description", "technology")[:30]} for s in shots]

    # Step 2: Render each scene
    scene_clips = []
    for i, scene in enumerate(scenes):
        clip = render_scene(scene, i, output_dir)
        if clip:
            scene_clips.append(clip)

    if not scene_clips:
        raise RuntimeError("No scenes rendered")

    log.info("scenes rendered", count=len(scene_clips))

    # Step 3: Generate intro/outro
    from apps.rendering_service.branding import generate_intro, generate_outro
    intro_path = os.path.join(output_dir, "intro.mp4")
    outro_path = os.path.join(output_dir, "outro.mp4")
    channel_name = os.getenv("CHANNEL_NAME", "Signal Intel")
    generate_intro(channel_name, intro_path)
    generate_outro(channel_name, outro_path)

    # Step 4: Concatenate: intro + scenes + outro
    all_clips = [intro_path] + scene_clips + [outro_path]
    concat_path = os.path.join(output_dir, "concat.mp4")
    concat_file = concat_path + ".txt"
    with open(concat_file, "w") as f:
        for p in all_clips:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", concat_file,
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "30",
         "-movflags", "+faststart", concat_path],
        description="concat all scenes",
        timeout=1800,
    )
    os.remove(concat_file)
    log.info("scenes concatenated", clips=len(all_clips))

    # Step 5: Mix voiceover audio
    current_video = concat_path
    if voiceover_path and os.path.exists(voiceover_path):
        with_audio_path = os.path.join(output_dir, "with_audio.mp4")
        audio_duration = _get_video_duration(voiceover_path)
        _run_ffmpeg(
            ["-i", current_video, "-i", voiceover_path,
             "-t", str(audio_duration),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-map", "0:v:0", "-map", "1:a:0",
             with_audio_path],
            description="mix audio",
        )
        current_video = with_audio_path
        log.info("audio mixed")

    # Step 6: Apply text overlays from footage scenes
    overlay_cues = []
    elapsed = 3.0  # Skip intro duration
    for scene in scenes:
        if scene["type"] == "footage" and scene.get("text_overlay"):
            overlay_cues.append({
                "start_seconds": elapsed + 0.5,
                "duration": min(3, scene["duration"] - 1),
                "text": scene["text_overlay"],
                "style": "key_fact",
            })
        elapsed += scene["duration"]

    if overlay_cues:
        try:
            from apps.rendering_service.overlays import apply_overlays
            with_overlays = os.path.join(output_dir, "with_overlays.mp4")
            apply_overlays(current_video, with_overlays, overlay_cues)
            current_video = with_overlays
            log.info("text overlays applied", count=len(overlay_cues))
        except Exception as e:
            log.warning("overlays failed", error=str(e))

    # Step 7: Finalize
    final_path = os.path.join(output_dir, "final.mp4")
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        log.info("srt saved", path=srt_path)

    os.rename(current_video, final_path)

    file_size = os.path.getsize(final_path)
    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(scene_clips),
        "total_duration_seconds": sum(s["duration"] for s in scenes),
    }

    log.info("video render complete", **result)
    return result
