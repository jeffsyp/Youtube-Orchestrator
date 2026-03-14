"""Video compositor — assembles stock footage, voiceover, and subtitles into a final MP4.

Pipeline:
1. For each shot, search Pexels for relevant stock footage
2. Trim clips to 2-4 seconds each
3. Concatenate with crossfade transitions
4. Mix in voiceover audio
5. Burn in subtitles
6. Output final MP4
"""

import os
import subprocess

import structlog

logger = structlog.get_logger()


def _run_ffmpeg(args: list[str], description: str = "") -> subprocess.CompletedProcess:
    """Run an FFmpeg command and handle errors."""
    cmd = ["ffmpeg", "-y"] + args
    log = logger.bind(service="rendering", action="ffmpeg")
    log.debug("running ffmpeg", description=description)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        log.error("ffmpeg failed", stderr=result.stderr[-500:] if result.stderr else "")
        raise RuntimeError(f"FFmpeg failed ({description}): {result.stderr[-200:]}")

    return result


def _get_video_duration(path: str) -> float:
    """Get duration of a video file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _generate_script_queries(script_content: str, target_duration: float, clip_duration: int = 6) -> list[str]:
    """Use Claude to generate footage search queries matched to script content."""
    import json as json_mod
    from packages.clients.claude import generate
    from packages.prompts.footage import generate_footage_queries_prompt

    log = logger.bind(service="rendering", action="generate_queries")
    log.info("generating script-matched footage queries")

    system, user = generate_footage_queries_prompt(script_content, target_duration, clip_duration)
    response = generate(user, system=system, max_tokens=2048, temperature=0.4)

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    queries = json_mod.loads(text)
    log.info("queries generated", count=len(queries))
    return queries


def download_stock_clips(shots: list[dict], output_dir: str, target_duration: float = 0, script_content: str | None = None) -> list[str]:
    """Download enough unique stock video clips to fill the target duration.

    If script_content is provided, uses Claude to generate search queries
    matched to what's being discussed at each point in the script.
    Otherwise falls back to shot descriptions.
    """
    from packages.clients.pexels import search_videos, download_video

    clips_dir = os.path.join(output_dir, "stock_clips")
    os.makedirs(clips_dir, exist_ok=True)
    log = logger.bind(service="rendering", action="download_stock")

    # Generate queries matched to script content if available
    if script_content and target_duration > 0:
        try:
            queries = _generate_script_queries(script_content, target_duration)
        except Exception as e:
            log.warning("script query generation failed, falling back", error=str(e))
            queries = [_description_to_query(s.get("description", "technology")) for s in shots]
    else:
        queries = [_description_to_query(s.get("description", "technology")) for s in shots]

    # Add filler queries in case we need more
    filler_queries = [
        "technology abstract", "computer code screen", "data center servers",
        "digital network connection", "circuit board macro", "city skyline night",
        "office workspace modern", "scientist laboratory", "world map digital",
        "futuristic interface", "coding programming", "cybersecurity lock",
        "satellite space", "factory robotics", "electronics manufacturing",
        "cloud computing", "fiber optic cable", "drone aerial view",
        "research development", "engineer working", "control room monitors",
    ]

    all_queries = queries + filler_queries
    paths = []
    seen_video_ids = set()
    clip_idx = 0
    query_idx = 0
    clips_duration = 0
    clip_length = 6  # seconds per clip

    # Calculate how many unique clips we need
    needed_duration = max(target_duration, sum(s.get("duration_seconds", 4) for s in shots))
    needed_clips = int(needed_duration / clip_length) + 5  # Some buffer

    log.info("downloading stock clips", needed_clips=needed_clips, needed_duration=round(needed_duration))

    while clip_idx < needed_clips and query_idx < len(all_queries):
        query = all_queries[query_idx]
        query_idx += 1

        results = search_videos(query, per_page=5)

        for video in results:
            if video["id"] in seen_video_ids:
                continue
            if clip_idx >= needed_clips:
                break

            seen_video_ids.add(video["id"])
            clip_path = os.path.join(clips_dir, f"stock_{clip_idx:03d}.mp4")

            try:
                download_video(video["download_url"], clip_path)
                paths.append(clip_path)
                clip_idx += 1
                clips_duration += clip_length
                log.info("clip downloaded", clip=clip_idx, query=query, video_id=video["id"])
            except Exception as e:
                log.warning("download failed", error=str(e), video_id=video["id"])

    log.info("stock clips downloaded", total=len(paths), unique_videos=len(seen_video_ids))
    return paths


def _description_to_query(description: str) -> str:
    """Convert a shot description to a Pexels search query.

    Extracts the most visual/searchable terms.
    """
    # Remove common filler words
    skip = {"the", "a", "an", "of", "in", "on", "with", "and", "or", "for", "to", "is", "are",
            "that", "this", "from", "by", "at", "as", "it", "its", "be", "was", "were", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
            "may", "might", "shall", "can", "scene", "shot", "showing", "shows", "display",
            "displays", "featuring", "features", "animated", "animation"}

    words = description.lower().split()
    key_words = [w for w in words if w not in skip and len(w) > 2]

    # Take first 3-4 meaningful words
    return " ".join(key_words[:4])


def trim_clip(input_path: str, output_path: str, duration: float, start: float = 0) -> str:
    """Trim a video clip to a specific duration with forced re-encode."""
    _run_ffmpeg(
        [
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1:color=black,fps=30",
            "-c:v", "libx264",
            "-preset", "fast",
            "-an",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-video_track_timescale", "30000",
            output_path,
        ],
        description=f"trim {os.path.basename(input_path)} to {duration}s",
    )
    return output_path


def concatenate_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate clips using simple concat demuxer."""
    log = logger.bind(service="rendering", action="concat")

    if len(clip_paths) == 0:
        raise ValueError("No clips to concatenate")

    if len(clip_paths) == 1:
        os.rename(clip_paths[0], output_path)
        return output_path

    log.info("concatenating clips", count=len(clip_paths))

    concat_file = output_path + ".concat.txt"
    with open(concat_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run_ffmpeg(
        [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ],
        description="concat clips",
    )

    os.remove(concat_file)
    return output_path


def mix_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """Mix voiceover audio onto the video."""
    log = logger.bind(service="rendering", action="mix_audio")
    log.info("mixing audio")

    # Use -t to force duration to match audio length
    audio_duration = _get_video_duration(audio_path)

    _run_ffmpeg(
        [
            "-i", video_path,
            "-i", audio_path,
            "-t", str(audio_duration),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            output_path,
        ],
        description="mix audio",
    )
    return output_path


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    """Burn SRT subtitles into the video."""
    log = logger.bind(service="rendering", action="burn_subtitles")
    log.info("burning subtitles")

    escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    _run_ffmpeg(
        [
            "-i", video_path,
            "-vf", (
                f"subtitles='{escaped_srt}'"
                ":force_style='FontName=DejaVu Sans,FontSize=13,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,Outline=1,Shadow=1,MarginV=25'"
            ),
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path,
        ],
        description="burn subtitles",
    )
    return output_path


def render_video(
    shots: list[dict],
    voiceover_path: str | None,
    srt_content: str | None,
    output_dir: str,
    script_content: str | None = None,
) -> dict:
    """Full rendering pipeline: stock footage → trim → concat → audio → overlays → MP4.

    Args:
        shots: List of shot dicts from VisualPlan.
        voiceover_path: Path to voiceover MP3 (or None).
        srt_content: SRT subtitle text (or None).
        output_dir: Directory for all output files.
        script_content: Full script text (used to generate text overlays).

    Returns:
        Dict with status, final video path, and metadata.
    """
    log = logger.bind(service="rendering", action="render_video")
    log.info("starting video render", shots=len(shots))

    os.makedirs(output_dir, exist_ok=True)
    trimmed_dir = os.path.join(output_dir, "trimmed")
    os.makedirs(trimmed_dir, exist_ok=True)

    # Calculate target video duration from voiceover if available
    target_duration = 0
    if voiceover_path and os.path.exists(voiceover_path):
        target_duration = _get_video_duration(voiceover_path)
        log.info("target duration from voiceover", seconds=target_duration)

    # Step 1: Download enough unique stock clips to fill the duration
    stock_paths = download_stock_clips(shots, output_dir, target_duration=target_duration, script_content=script_content)
    log.info("stock clips downloaded", count=len(stock_paths))

    if not stock_paths:
        raise RuntimeError("No stock footage found for any shot")

    # Step 2: Trim each clip to 6 seconds
    clip_duration = 6
    trimmed_paths = []
    for i, stock_path in enumerate(stock_paths):
        source_duration = _get_video_duration(stock_path)
        use_duration = min(source_duration, clip_duration)
        start = min(1.0, max(0, source_duration - use_duration - 0.5))

        trimmed_path = os.path.join(trimmed_dir, f"trimmed_{i:03d}.mp4")
        trim_clip(stock_path, trimmed_path, use_duration, start=start)
        trimmed_paths.append(trimmed_path)

    log.info("clips trimmed", count=len(trimmed_paths))

    # Step 3: Generate intro/outro
    from apps.rendering_service.branding import generate_intro, generate_outro
    intro_path = os.path.join(output_dir, "intro.mp4")
    outro_path = os.path.join(output_dir, "outro.mp4")
    channel_name = os.getenv("CHANNEL_NAME", "TechPulse")
    generate_intro(channel_name, intro_path)
    generate_outro(channel_name, outro_path)

    # Step 4: Concatenate: intro + clips + outro
    all_clips = [intro_path] + trimmed_paths + [outro_path]
    concat_path = os.path.join(output_dir, "concat.mp4")
    concatenate_clips(all_clips, concat_path)
    log.info("clips concatenated with intro/outro", total_clips=len(all_clips))

    # Step 4: Mix voiceover
    if voiceover_path and os.path.exists(voiceover_path):
        with_audio_path = os.path.join(output_dir, "with_audio.mp4")
        mix_audio(concat_path, voiceover_path, with_audio_path)
        current_video = with_audio_path
        log.info("audio mixed")
    else:
        current_video = concat_path
        log.info("no voiceover, skipping audio mix")

    # Step 5: Generate and apply text overlays
    if script_content and target_duration > 0:
        try:
            from apps.rendering_service.overlays import generate_cues, apply_overlays
            cues = generate_cues(script_content, target_duration)
            if cues:
                with_overlays_path = os.path.join(output_dir, "with_overlays.mp4")
                apply_overlays(current_video, with_overlays_path, cues)
                current_video = with_overlays_path
                log.info("text overlays applied", cues=len(cues))

                # Save cues for reference
                import json as json_mod
                with open(os.path.join(output_dir, "overlay_cues.json"), "w") as f:
                    json_mod.dump(cues, f, indent=2)
        except Exception as e:
            log.warning("overlay generation failed, continuing without", error=str(e))

    # Step 6: Save SRT file separately (for YouTube upload, not burned in)
    final_path = os.path.join(output_dir, "final.mp4")
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        log.info("srt saved separately", path=srt_path)

    os.rename(current_video, final_path)

    file_size = os.path.getsize(final_path)
    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(trimmed_paths),
        "total_duration_seconds": sum(min(s.get("duration_seconds", 3), 4) for s in shots),
    }

    log.info("video render complete", **result)
    return result
