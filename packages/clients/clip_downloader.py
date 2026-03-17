"""yt-dlp wrapper for downloading video clips from any URL."""

import os
import subprocess

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()


def download_clip(
    url: str,
    output_path: str,
    max_duration: int = 120,
) -> dict:
    """Download a video clip using yt-dlp.

    Args:
        url: Video URL (YouTube, Reddit, Twitter, Streamable, etc.).
        output_path: Output file path (should end in .mp4).
        max_duration: Max allowed duration in seconds. Rejects longer clips.

    Returns:
        Dict with path, duration, width, height, source_url.
    """
    log = logger.bind(url=url, output_path=output_path)
    log.info("downloading clip")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # First, probe duration without downloading
    probe_cmd = [
        "yt-dlp",
        "--no-download",
        "--print", "duration",
        "--no-warnings",
        url,
    ]
    probe_result = subprocess.run(
        probe_cmd, capture_output=True, text=True, timeout=30,
    )
    if probe_result.stdout.strip():
        try:
            duration = float(probe_result.stdout.strip())
            if duration > max_duration:
                raise ValueError(
                    f"Clip duration {duration:.0f}s exceeds max {max_duration}s"
                )
        except ValueError as e:
            if "exceeds" in str(e):
                raise
            # Duration might not be available for all sources; proceed anyway

    # Download best quality up to 1080p
    download_cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--no-warnings",
        "-o", output_path,
        url,
    ]

    result = subprocess.run(
        download_cmd, capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError(f"Download completed but file not found: {output_path}")

    # Probe the downloaded file for metadata
    info = _probe_video(output_path)
    info["source_url"] = url

    log.info("clip downloaded", **info)
    return info


def _probe_video(path: str) -> dict:
    """Get video metadata using ffprobe."""
    # Duration
    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    # Resolution
    res_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    parts = res_result.stdout.strip().split(",") if res_result.stdout.strip() else []
    width = int(parts[0]) if len(parts) >= 2 else 0
    height = int(parts[1]) if len(parts) >= 2 else 0

    return {
        "path": os.path.abspath(path),
        "duration": round(duration, 1),
        "width": width,
        "height": height,
    }
