"""Video compositor — assembles slides, voiceover, and subtitles into a final MP4.

Uses FFmpeg to:
1. Convert each slide into a video clip with Ken Burns (slow zoom) effect
2. Concatenate all clips
3. Mix in voiceover audio
4. Burn in subtitles from SRT file
5. Output a final MP4 ready for YouTube upload
"""

import os
import subprocess
import tempfile

import structlog

logger = structlog.get_logger()


def _run_ffmpeg(args: list[str], description: str = "") -> subprocess.CompletedProcess:
    """Run an FFmpeg command and handle errors."""
    cmd = ["ffmpeg", "-y"] + args
    log = logger.bind(service="rendering", action="ffmpeg")
    log.debug("running ffmpeg", description=description)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        log.error("ffmpeg failed", stderr=result.stderr[-500:] if result.stderr else "")
        raise RuntimeError(f"FFmpeg failed ({description}): {result.stderr[-200:]}")

    return result


def create_slide_clip(
    image_path: str,
    duration: float,
    output_path: str,
    zoom_speed: float = 0.0003,
) -> str:
    """Create a video clip from a static image with Ken Burns zoom effect.

    Args:
        image_path: Path to the PNG slide.
        duration: Clip duration in seconds.
        output_path: Where to save the MP4 clip.
        zoom_speed: Zoom speed (higher = faster zoom). 0.0003 is subtle.

    Returns:
        Path to the output clip.
    """
    fps = 30
    total_frames = int(duration * fps)

    # Ken Burns: slow zoom from 1.0x to ~1.05x, centered
    _run_ffmpeg(
        [
            "-loop", "1",
            "-i", image_path,
            "-vf", (
                f"zoompan=z='1+{zoom_speed}*in':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={total_frames}:s=1920x1080:fps={fps}"
            ),
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            output_path,
        ],
        description=f"slide clip {os.path.basename(image_path)}",
    )
    return output_path


def concatenate_clips(clip_paths: list[str], output_path: str) -> str:
    """Concatenate multiple video clips into one.

    Args:
        clip_paths: List of MP4 clip file paths.
        output_path: Where to save the concatenated video.

    Returns:
        Path to the output file.
    """
    log = logger.bind(service="rendering", action="concatenate")
    log.info("concatenating clips", count=len(clip_paths))

    # Write concat file list
    concat_file = output_path + ".concat.txt"
    with open(concat_file, "w") as f:
        for path in clip_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")

    _run_ffmpeg(
        [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ],
        description="concatenate clips",
    )

    os.remove(concat_file)
    return output_path


def mix_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """Mix voiceover audio onto the video.

    The audio track replaces any existing audio. If the audio is shorter
    than the video, the video is trimmed to match the audio duration.

    Args:
        video_path: Path to the video (no audio or silent).
        audio_path: Path to the voiceover MP3.
        output_path: Where to save the output.

    Returns:
        Path to the output file.
    """
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
    """Burn SRT subtitles into the video.

    Args:
        video_path: Path to the video with audio.
        srt_path: Path to the SRT subtitle file.
        output_path: Where to save the output.

    Returns:
        Path to the output file.
    """
    log = logger.bind(service="rendering", action="burn_subtitles")
    log.info("burning subtitles")

    # Escape special characters in path for FFmpeg subtitles filter
    escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    _run_ffmpeg(
        [
            "-i", video_path,
            "-vf", (
                f"subtitles='{escaped_srt}'"
                ":force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,Outline=2,Shadow=1,MarginV=40'"
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
    """Full rendering pipeline: slides → clips → concatenate → audio → subtitles → MP4.

    Args:
        shots: List of shot dicts from VisualPlan (scene_number, description, duration_seconds, etc.)
        voiceover_path: Path to voiceover MP3 (or None to skip audio).
        srt_content: SRT subtitle text (or None to skip subtitles).
        output_dir: Directory for all output files.

    Returns:
        Dict with status, final video path, and metadata.
    """
    log = logger.bind(service="rendering", action="render_video")
    log.info("starting video render", shots=len(shots))

    os.makedirs(output_dir, exist_ok=True)
    slides_dir = os.path.join(output_dir, "slides")
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(slides_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    # Step 1: Generate slides
    from apps.rendering_service.image_gen import generate_all_slides
    slide_paths = generate_all_slides(shots, slides_dir)
    log.info("slides generated", count=len(slide_paths))

    # Step 2: Convert each slide to a video clip with Ken Burns effect
    clip_paths = []
    for i, (slide_path, shot) in enumerate(zip(slide_paths, shots)):
        duration = shot.get("duration_seconds", 10)
        clip_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")
        create_slide_clip(slide_path, duration, clip_path)
        clip_paths.append(clip_path)
        log.info("clip created", scene=i + 1, duration=duration)

    # Step 3: Concatenate all clips
    concat_path = os.path.join(output_dir, "concat.mp4")
    concatenate_clips(clip_paths, concat_path)
    log.info("clips concatenated")

    # Step 4: Mix in voiceover audio
    if voiceover_path and os.path.exists(voiceover_path):
        with_audio_path = os.path.join(output_dir, "with_audio.mp4")
        mix_audio(concat_path, voiceover_path, with_audio_path)
        current_video = with_audio_path
        log.info("audio mixed")
    else:
        current_video = concat_path
        log.info("no voiceover, skipping audio mix")

    # Step 5: Burn in subtitles
    final_path = os.path.join(output_dir, "final.mp4")
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        burn_subtitles(current_video, srt_path, final_path)
        log.info("subtitles burned")
    else:
        # Just copy/rename
        os.rename(current_video, final_path)
        log.info("no subtitles, video finalized")

    # Get file size
    file_size = os.path.getsize(final_path)

    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "slides_count": len(slide_paths),
        "total_duration_seconds": sum(s.get("duration_seconds", 10) for s in shots),
    }

    log.info("video render complete", **result)
    return result
