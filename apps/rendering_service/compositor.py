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


def download_stock_clips(shots: list[dict], output_dir: str) -> list[str]:
    """Download stock video clips from Pexels for each shot.

    Falls back to a generic tech query if the specific description finds nothing.
    """
    from packages.clients.pexels import search_and_download

    clips_dir = os.path.join(output_dir, "stock_clips")
    os.makedirs(clips_dir, exist_ok=True)
    log = logger.bind(service="rendering", action="download_stock")
    log.info("downloading stock clips", count=len(shots))

    paths = []
    fallback_queries = ["technology", "computer", "digital", "abstract light", "circuit board", "data"]
    fallback_idx = 0

    for i, shot in enumerate(shots):
        clip_path = os.path.join(clips_dir, f"stock_{i:03d}.mp4")
        desc = shot.get("description", "technology")

        # Extract key visual terms from description
        query = _description_to_query(desc)
        result = search_and_download(query, clip_path)

        if not result:
            # Fallback to generic tech footage
            fb_query = fallback_queries[fallback_idx % len(fallback_queries)]
            fallback_idx += 1
            log.info("using fallback query", original=query, fallback=fb_query)
            result = search_and_download(fb_query, clip_path)

        if result:
            paths.append(result)
            log.info("clip downloaded", scene=i + 1, query=query)
        else:
            log.warning("no clip found", scene=i + 1)

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
    """Trim a video clip to a specific duration."""
    _run_ffmpeg(
        [
            "-ss", str(start),
            "-i", input_path,
            "-t", str(duration),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1:color=black",
            "-c:v", "libx264",
            "-preset", "fast",
            "-an",  # Strip audio from stock clips
            "-pix_fmt", "yuv420p",
            output_path,
        ],
        description=f"trim {os.path.basename(input_path)} to {duration}s",
    )
    return output_path


def concatenate_with_crossfades(clip_paths: list[str], output_path: str, fade_duration: float = 0.3) -> str:
    """Concatenate clips with fade-in/fade-out on each clip for smooth transitions."""
    log = logger.bind(service="rendering", action="crossfade")

    if len(clip_paths) == 0:
        raise ValueError("No clips to concatenate")

    if len(clip_paths) == 1:
        os.rename(clip_paths[0], output_path)
        return output_path

    log.info("concatenating with fades", clips=len(clip_paths), fade=fade_duration)

    # Add fade-in/fade-out to each clip, then concat
    faded_dir = os.path.dirname(clip_paths[0])
    faded_paths = []

    for i, path in enumerate(clip_paths):
        duration = _get_video_duration(path)
        fade_out_start = max(0, duration - fade_duration)
        faded_path = os.path.join(faded_dir, f"faded_{i:03d}.mp4")

        _run_ffmpeg(
            [
                "-i", path,
                "-vf", f"fade=in:st=0:d={fade_duration},fade=out:st={fade_out_start}:d={fade_duration}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-an",
                faded_path,
            ],
            description=f"fade clip {i}",
        )
        faded_paths.append(faded_path)

    # Simple concat
    concat_file = output_path + ".concat.txt"
    with open(concat_file, "w") as f:
        for p in faded_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run_ffmpeg(
        [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ],
        description="concat faded clips",
    )

    os.remove(concat_file)
    return output_path


def mix_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """Mix voiceover audio onto the video."""
    log = logger.bind(service="rendering", action="mix_audio")
    log.info("mixing audio")

    _run_ffmpeg(
        [
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
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
) -> dict:
    """Full rendering pipeline: stock footage → trim → crossfade → audio → subtitles → MP4.

    Args:
        shots: List of shot dicts from VisualPlan.
        voiceover_path: Path to voiceover MP3 (or None).
        srt_content: SRT subtitle text (or None).
        output_dir: Directory for all output files.

    Returns:
        Dict with status, final video path, and metadata.
    """
    log = logger.bind(service="rendering", action="render_video")
    log.info("starting video render", shots=len(shots))

    os.makedirs(output_dir, exist_ok=True)
    trimmed_dir = os.path.join(output_dir, "trimmed")
    os.makedirs(trimmed_dir, exist_ok=True)

    # Step 1: Download stock clips
    stock_paths = download_stock_clips(shots, output_dir)
    log.info("stock clips downloaded", count=len(stock_paths))

    if not stock_paths:
        raise RuntimeError("No stock footage found for any shot")

    # Step 2: Trim each clip to target duration (2-4 seconds for fast cuts)
    trimmed_paths = []
    for i, (stock_path, shot) in enumerate(zip(stock_paths, shots)):
        target_duration = min(shot.get("duration_seconds", 3), 4)  # Cap at 4s for fast cuts
        clip_duration = _get_video_duration(stock_path)

        # Start from a random-ish point if clip is longer than needed
        start = min(1.0, max(0, clip_duration - target_duration - 1))

        trimmed_path = os.path.join(trimmed_dir, f"trimmed_{i:03d}.mp4")
        trim_clip(stock_path, trimmed_path, target_duration, start=start)
        trimmed_paths.append(trimmed_path)
        log.info("clip trimmed", scene=i + 1, duration=target_duration)

    # Step 3: Concatenate with crossfades
    concat_path = os.path.join(output_dir, "concat.mp4")
    concatenate_with_crossfades(trimmed_paths, concat_path, fade_duration=0.4)
    log.info("clips concatenated with crossfades")

    # Step 4: Mix voiceover
    if voiceover_path and os.path.exists(voiceover_path):
        with_audio_path = os.path.join(output_dir, "with_audio.mp4")
        mix_audio(concat_path, voiceover_path, with_audio_path)
        current_video = with_audio_path
        log.info("audio mixed")
    else:
        current_video = concat_path
        log.info("no voiceover, skipping audio mix")

    # Step 5: Burn subtitles
    final_path = os.path.join(output_dir, "final.mp4")
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        burn_subtitles(current_video, srt_path, final_path)
        log.info("subtitles burned")
    else:
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
