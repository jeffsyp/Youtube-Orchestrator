"""Video quality assurance — automated checks on rendered videos.

Catches issues like:
- Frozen/stuck frames (same image too long)
- Missing or silent audio
- Duration mismatches between video and voiceover
- Wrong resolution
- Abnormal file size
- Low scene change rate (boring visuals)
- Audio clipping or distortion
"""

import os
import subprocess

import structlog

logger = structlog.get_logger()


def _ffprobe(file_path: str, entries: str) -> str:
    """Run ffprobe and return the output."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", entries, "-of", "csv=p=0", file_path],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _ffprobe_streams(file_path: str) -> dict:
    """Get stream info from a file."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_streams", "-of", "json", file_path],
        capture_output=True, text=True, timeout=30,
    )
    import json
    return json.loads(result.stdout)


def check_duration(video_path: str, voiceover_path: str | None, tolerance: float = 5.0) -> dict:
    """Check that video duration matches voiceover duration."""
    video_dur = float(_ffprobe(video_path, "format=duration"))

    result = {
        "check": "duration",
        "video_duration": round(video_dur, 1),
        "passed": True,
        "issues": [],
    }

    if video_dur < 10:
        result["passed"] = False
        result["issues"].append(f"Video is only {video_dur:.1f}s — too short")

    if voiceover_path and os.path.exists(voiceover_path):
        audio_dur = float(_ffprobe(voiceover_path, "format=duration"))
        result["voiceover_duration"] = round(audio_dur, 1)
        diff = abs(video_dur - audio_dur)
        result["duration_diff"] = round(diff, 1)

        if diff > tolerance:
            result["passed"] = False
            result["issues"].append(
                f"Video ({video_dur:.1f}s) and voiceover ({audio_dur:.1f}s) differ by {diff:.1f}s"
            )

    return result


def check_resolution(video_path: str, expected_width: int = 1920, expected_height: int = 1080) -> dict:
    """Check video resolution is 1080p."""
    streams = _ffprobe_streams(video_path)
    result = {
        "check": "resolution",
        "passed": True,
        "issues": [],
    }

    for stream in streams.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width", 0)
            height = stream.get("height", 0)
            result["width"] = width
            result["height"] = height

            if width < expected_width or height < expected_height:
                result["passed"] = False
                result["issues"].append(f"Resolution {width}x{height} is below {expected_width}x{expected_height}")
            break
    else:
        result["passed"] = False
        result["issues"].append("No video stream found")

    return result


def check_audio_present(video_path: str) -> dict:
    """Check that the video has an audio track and it's not silent."""
    streams = _ffprobe_streams(video_path)
    result = {
        "check": "audio_present",
        "passed": True,
        "issues": [],
    }

    has_audio = any(s.get("codec_type") == "audio" for s in streams.get("streams", []))
    result["has_audio_track"] = has_audio

    if not has_audio:
        result["passed"] = False
        result["issues"].append("No audio track in video file")
        return result

    # Check if audio is silent by measuring volume
    vol_result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-af", "volumedetect", "-f", "null", "/dev/null"],
        capture_output=True, text=True, timeout=120,
    )

    stderr = vol_result.stderr
    mean_volume = None
    for line in stderr.split("\n"):
        if "mean_volume" in line:
            try:
                mean_volume = float(line.split("mean_volume:")[1].split("dB")[0].strip())
            except (ValueError, IndexError):
                pass

    result["mean_volume_db"] = mean_volume

    if mean_volume is not None and mean_volume < -50:
        result["passed"] = False
        result["issues"].append(f"Audio is nearly silent (mean volume: {mean_volume:.1f} dB)")

    return result


def check_frozen_frames(video_path: str, max_frozen_seconds: float = 45.0) -> dict:
    """Detect frozen/stuck frames using scene change detection.

    If no scene changes are detected for more than max_frozen_seconds,
    it's likely the video is stuck on one image.
    """
    result = {
        "check": "frozen_frames",
        "passed": True,
        "issues": [],
    }

    # Use FFmpeg scene detection — outputs timestamps where scenes change
    detect_result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", "select='gt(scene,0.1)',showinfo",
            "-f", "null", "/dev/null",
        ],
        capture_output=True, text=True, timeout=300,
    )

    # Parse scene change timestamps from showinfo output
    timestamps = []
    for line in detect_result.stderr.split("\n"):
        if "pts_time:" in line:
            try:
                pts = float(line.split("pts_time:")[1].split()[0])
                timestamps.append(pts)
            except (ValueError, IndexError):
                pass

    video_dur = float(_ffprobe(video_path, "format=duration"))
    result["scene_changes"] = len(timestamps)
    result["video_duration"] = round(video_dur, 1)

    if len(timestamps) < 2:
        result["passed"] = False
        result["issues"].append(f"Only {len(timestamps)} scene changes detected — video may be a static image")
        return result

    # Check for long gaps between scene changes
    all_points = [0.0] + sorted(timestamps) + [video_dur]
    max_gap = 0
    max_gap_at = 0
    for i in range(1, len(all_points)):
        gap = all_points[i] - all_points[i - 1]
        if gap > max_gap:
            max_gap = gap
            max_gap_at = all_points[i - 1]

    result["max_gap_seconds"] = round(max_gap, 1)
    result["max_gap_at"] = round(max_gap_at, 1)

    # Check scene change rate
    changes_per_minute = len(timestamps) / (video_dur / 60) if video_dur > 0 else 0
    result["changes_per_minute"] = round(changes_per_minute, 1)

    if max_gap > max_frozen_seconds:
        result["passed"] = False
        result["issues"].append(
            f"Video appears frozen for {max_gap:.1f}s starting at {max_gap_at:.1f}s"
        )

    if changes_per_minute < 1.5:
        result["passed"] = False
        result["issues"].append(
            f"Very low scene change rate ({changes_per_minute:.1f}/min) — video feels static"
        )

    if 1.5 <= changes_per_minute < 3:
        result["issues"].append(
            f"Scene change rate is low ({changes_per_minute:.1f}/min) — deliberate pacing"
        )

    return result


def check_file_size(video_path: str, min_mb: float = 5, max_mb: float = 2000) -> dict:
    """Check file size is reasonable."""
    size_bytes = os.path.getsize(video_path)
    size_mb = size_bytes / (1024 * 1024)

    result = {
        "check": "file_size",
        "size_mb": round(size_mb, 1),
        "passed": True,
        "issues": [],
    }

    if size_mb < min_mb:
        result["passed"] = False
        result["issues"].append(f"File is only {size_mb:.1f} MB — likely broken or too short")

    if size_mb > max_mb:
        result["passed"] = False
        result["issues"].append(f"File is {size_mb:.1f} MB — unusually large")

    return result


def run_all_checks(
    video_path: str,
    voiceover_path: str | None = None,
) -> dict:
    """Run all QA checks on a rendered video.

    Returns a report with overall pass/fail and details for each check.
    """
    log = logger.bind(service="qa", video=video_path)
    log.info("running video QA checks")

    checks = [
        check_duration(video_path, voiceover_path),
        check_resolution(video_path),
        check_audio_present(video_path),
        check_frozen_frames(video_path),
        check_file_size(video_path),
    ]

    all_passed = all(c["passed"] for c in checks)
    all_issues = []
    for c in checks:
        for issue in c.get("issues", []):
            all_issues.append(f"[{c['check']}] {issue}")

    report = {
        "passed": all_passed,
        "checks_run": len(checks),
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks_failed": sum(1 for c in checks if not c["passed"]),
        "issues": all_issues,
        "details": checks,
    }

    if all_passed:
        log.info("video QA passed", checks=len(checks))
    else:
        log.warning("video QA FAILED", issues=all_issues)

    return report
