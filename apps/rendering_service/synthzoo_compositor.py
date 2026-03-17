"""Synth Zoo compositor — assembles Sora-generated clips into YouTube Shorts.

Renders with cross-dissolves between clips, color normalization for visual
consistency, background music mix, and caption burn-in.
"""

import glob
import os
import random
import subprocess

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

# Vertical dimensions (9:16) — matches Sora output
WIDTH = 720
HEIGHT = 1280

MAX_SHORT_DURATION = 59.0
CROSSFADE_DURATION = 0.8  # seconds of crossfade between clips

# Background music directory — bundled royalty-free tracks (Mixkit license)
MUSIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")


def render_synthzoo_short(
    clips: list[str],
    caption_text: str,
    output_dir: str,
    music_volume: float = 0.15,
    sora_volume: float = 0.85,
    content_type: str = "synthzoo_short",
    output_filename: str = "synthzoo_short.mp4",
) -> dict:
    """Render a Synth Zoo Short from Sora-generated clips.

    Args:
        clips: List of paths to Sora-generated MP4 files.
        caption_text: Single caption line to burn in (lower third).
        output_dir: Directory for output files.

    Returns:
        Dict with status, path, duration, resolution info.
    """
    log = logger.bind(service="synthzoo_rendering", clips=len(clips))
    log.info("starting synthzoo render")

    os.makedirs(output_dir, exist_ok=True)

    if not clips:
        raise RuntimeError("No clips provided for Synth Zoo render")

    # Filter to clips that actually exist
    valid_clips = [c for c in clips if os.path.exists(c)]
    if not valid_clips:
        raise RuntimeError("None of the provided clip files exist")

    log.info("valid clips", count=len(valid_clips))

    # Step 1: Normalize all clips — consistent resolution, frame rate, color
    normalized = []
    for i, clip in enumerate(valid_clips):
        norm_path = os.path.join(output_dir, f"norm_{i:02d}.mp4")
        _normalize_clip(clip, norm_path)
        normalized.append(norm_path)

    # Step 2: Concat with cross-dissolves
    concat_path = os.path.join(output_dir, "synthzoo_concat.mp4")
    if len(normalized) == 1:
        _ffmpeg_copy(normalized[0], concat_path)
    else:
        _ffmpeg_crossfade_concat(normalized, concat_path)

    # Cleanup normalized intermediates
    for n in normalized:
        if os.path.exists(n):
            os.remove(n)

    # Step 3: Enforce max duration
    trimmed_path = os.path.join(output_dir, "synthzoo_trimmed.mp4")
    duration = _get_duration(concat_path)
    if duration > MAX_SHORT_DURATION:
        log.info("trimming to max duration", original=round(duration), max=MAX_SHORT_DURATION)
        _ffmpeg_trim(concat_path, trimmed_path, MAX_SHORT_DURATION)
        os.remove(concat_path)
    else:
        os.rename(concat_path, trimmed_path)

    # Step 4: Mix in background music under Sora's native audio
    music_path = os.path.join(output_dir, "synthzoo_with_music.mp4")
    video_duration = _get_duration(trimmed_path)
    music_track = _pick_music_track()
    if music_track:
        log.info("mixing background music", track=os.path.basename(music_track))
        _mix_background_music(trimmed_path, music_track, music_path, video_duration,
                              music_volume=music_volume, sora_volume=sora_volume)
        os.remove(trimmed_path)
    else:
        log.info("no music tracks found, using Sora audio only")
        os.rename(trimmed_path, music_path)

    # Step 5: Burn in caption (lower third, large bold text, full duration)
    final_path = os.path.join(output_dir, output_filename)
    if caption_text:
        final_duration = _get_duration(music_path)
        ass_path = _generate_caption_ass(caption_text, final_duration, output_dir)
        _burn_subtitles(music_path, ass_path, final_path)
        os.remove(music_path)
    else:
        os.rename(music_path, final_path)

    final_duration = _get_duration(final_path)
    file_size = os.path.getsize(final_path)

    # Generate thumbnail from rendered video
    thumbnail_path = None
    try:
        from apps.rendering_service.thumbnail import generate_shorts_thumbnail
        thumb_out = os.path.join(output_dir, "thumbnail.png")
        thumbnail_path = generate_shorts_thumbnail(
            video_path=os.path.abspath(final_path),
            title=caption_text or "Synth Zoo",
            output_path=thumb_out,
        )
        log.info("thumbnail generated", path=thumbnail_path)
    except Exception as e:
        log.warning("thumbnail generation failed, continuing without", error=str(e))

    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(valid_clips),
        "total_duration_seconds": round(final_duration),
        "resolution": f"{WIDTH}x{HEIGHT}",
        "content_type": content_type,
        "music_track": os.path.basename(music_track) if music_track else None,
        "thumbnail_path": thumbnail_path,
    }

    log.info("synthzoo render complete",
             size_mb=round(file_size / 1024 / 1024, 1),
             duration=round(final_duration))
    return result


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _has_audio(path: str) -> bool:
    """Check if a file has an audio stream."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return bool(result.stdout.strip())


def _pick_music_track() -> str | None:
    """Pick a random background music track from the bundled library."""
    music_dir = os.path.normpath(MUSIC_DIR)
    if not os.path.isdir(music_dir):
        return None
    tracks = glob.glob(os.path.join(music_dir, "*.mp3"))
    if not tracks:
        return None
    return random.choice(tracks)


def _normalize_clip(input_path: str, output_path: str):
    """Normalize a clip to consistent resolution, frame rate, color, and audio.

    - Scale to 720x1280
    - Force 30fps
    - Apply color normalization (normalize brightness/contrast range)
    - Ensure consistent pixel format (yuv420p)
    - Force audio to aac, 44100 Hz, stereo (add silent track if missing)
    """
    # Color normalization: normalize histogram to smooth out lighting differences
    # between independently generated Sora clips
    vf_filters = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"colorlevels=rimin=0.02:gimin=0.02:bimin=0.02:rimax=0.98:gimax=0.98:bimax=0.98,"
        f"eq=contrast=1.05:saturation=1.1,"
        f"fps=30,"
        f"format=yuv420p"
    )

    has_audio = _has_audio(input_path)

    if has_audio:
        # Clip has audio — re-encode to consistent format
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf_filters,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            output_path,
        ]
    else:
        # No audio — generate a silent audio track as a second input.
        # The anullsrc input MUST come before any output options.
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", vf_filters,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Normalize failed: {result.stderr[-300:]}")


def _ffmpeg_crossfade_concat(clip_paths: list[str], output_path: str):
    """Concatenate clips with cross-dissolve transitions between them.

    Uses xfade (video) and acrossfade (audio) filters for smooth transitions.
    All clips MUST be pre-normalized to identical codecs, frame rate (30fps),
    pixel format (yuv420p), audio sample rate (44100 Hz), and channel layout
    (stereo) by _normalize_clip before calling this function.

    The xfade offset for stage i is:
        offset_i = sum(durations[0..i]) - (i + 1) * fade_dur
    Each xfade shortens the merged output by fade_dur, so the next offset
    must account for all previous overlaps.
    """
    n = len(clip_paths)
    if n < 2:
        _ffmpeg_copy(clip_paths[0], output_path)
        return

    # Get durations for calculating crossfade offsets
    durations = [_get_duration(p) for p in clip_paths]

    # Clamp fade duration so it never exceeds any clip's duration
    fade_dur = min(CROSSFADE_DURATION, min(durations) - 0.1)
    if fade_dur <= 0:
        logger.warning("clips too short for crossfade, using hard cut")
        _ffmpeg_concat_hardcut(clip_paths, output_path)
        return

    # Build inputs list
    inputs = []
    for path in clip_paths:
        inputs.extend(["-i", path])

    # Build the filter graph: N-1 chained xfade + acrossfade stages.
    # Each xfade consumes the merged output of all previous stages as its
    # first input and the next raw clip as its second input.
    v_parts = []
    a_parts = []
    running_duration_sum = 0.0

    for i in range(n - 1):
        # Input labels
        if i == 0:
            v_in1 = "[0:v]"
            a_in1 = "[0:a]"
        else:
            v_in1 = f"[v{i - 1:02d}]"
            a_in1 = f"[a{i - 1:02d}]"
        v_in2 = f"[{i + 1}:v]"
        a_in2 = f"[{i + 1}:a]"

        # Output labels
        if i == n - 2:
            v_out = "[outv]"
            a_out = "[outa]"
        else:
            v_out = f"[v{i:02d}]"
            a_out = f"[a{i:02d}]"

        # Offset = total duration of clips merged so far, minus accumulated overlap
        running_duration_sum += durations[i]
        offset = running_duration_sum - (i + 1) * fade_dur
        offset = max(0, offset)  # safety clamp

        v_parts.append(
            f"{v_in1}{v_in2}xfade=transition=fade:duration={fade_dur}:offset={offset}{v_out}"
        )
        # acrossfade can change sample format/rate, so force aformat after each
        # stage to keep the chain consistent for subsequent acrossfade inputs.
        a_parts.append(
            f"{a_in1}{a_in2}acrossfade=d={fade_dur}:c1=tri:c2=tri[atmp{i:02d}];"
            f"[atmp{i:02d}]aformat=sample_rates=44100:channel_layouts=stereo{a_out}"
        )

    filter_str = ";".join(v_parts + a_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # Fallback to hard cut concat if crossfade fails
        logger.warning("crossfade failed, falling back to hard cut", stderr=result.stderr[-300:])
        _ffmpeg_concat_hardcut(clip_paths, output_path)


def _ffmpeg_concat_hardcut(clip_paths: list[str], output_path: str):
    """Fallback: concatenate with hard cuts (no crossfade)."""
    inputs = []
    v_parts = []
    a_parts = []
    for i, path in enumerate(clip_paths):
        inputs.extend(["-i", path])
        v_parts.append(f"[{i}:v:0]")
        a_parts.append(f"[{i}:a:0]")

    filter_str = (
        "".join(v_parts) + f"concat=n={len(clip_paths)}:v=1:a=0[outv];"
        + "".join(a_parts) + f"concat=n={len(clip_paths)}:v=0:a=1[outa]"
    )

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # Last resort: video-only
        logger.warning("audio concat failed, trying video-only", stderr=result.stderr[-200:])
        _ffmpeg_concat_video_only(clip_paths, output_path)


def _ffmpeg_concat_video_only(clip_paths: list[str], output_path: str):
    """Last resort: concat with video only (no audio)."""
    inputs = []
    filter_parts = []
    for i, path in enumerate(clip_paths):
        inputs.extend(["-i", path])
        filter_parts.append(f"[{i}:v:0]")

    filter_str = "".join(filter_parts) + f"concat=n={len(clip_paths)}:v=1:a=0[outv]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {result.stderr[-300:]}")


def _ffmpeg_copy(input_path: str, output_path: str):
    """Copy a single file with faststart."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg copy failed: {result.stderr[-300:]}")


def _mix_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    video_duration: float,
    music_volume: float = 0.15,
    sora_volume: float = 0.85,
    fade_out_seconds: float = 2.0,
):
    """Mix a background music track under the video's existing audio."""
    fade_start = max(0, video_duration - fade_out_seconds)
    has_video_audio = _has_audio(video_path)

    if has_video_audio:
        filter_str = (
            f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
            f"volume={music_volume},afade=t=out:st={fade_start}:d={fade_out_seconds}[music];"
            f"[0:a]volume={sora_volume}[sora];"
            f"[sora][music]amix=inputs=2:duration=first:dropout_transition=0[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ]
    else:
        filter_str = (
            f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
            f"volume={music_volume * 3},afade=t=out:st={fade_start}:d={fade_out_seconds}[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.warning("music mix failed, using original audio", stderr=result.stderr[-300:])
        if video_path != output_path:
            _ffmpeg_copy(video_path, output_path)


def _ffmpeg_trim(input_path: str, output_path: str, max_duration: float):
    """Trim video to max duration."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-t", str(max_duration),
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg trim failed: {result.stderr[-300:]}")


def _generate_caption_ass(caption_text: str, duration: float, output_dir: str) -> str:
    """Generate an ASS subtitle file with a dynamic caption.

    Caption fades in at 60% through the video and stays until the end.
    This creates a "punchline reveal" effect rather than a static overlay.
    """
    from apps.rendering_service.fonts import FONT_PATH_STR

    font_name = "Inter"
    if "dejavu" in FONT_PATH_STR.lower():
        font_name = "DejaVu Sans"

    def _fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # Caption appears at 60% through, fades in over 0.4s
    caption_start = duration * 0.6
    start_time = _fmt(caption_start)
    end_time = _fmt(duration)

    ass_content = f"""[Script Info]
Title: Synth Zoo Caption
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font_name},42,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,40,40,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{start_time},{end_time},Caption,,0,0,0,,{{\\fad(400,0)}}{caption_text}
"""

    ass_path = os.path.join(output_dir, "caption.ass")
    with open(ass_path, "w") as f:
        f.write(ass_content)

    return ass_path


def _burn_subtitles(input_path: str, ass_path: str, output_path: str):
    """Burn ASS subtitles into video using FFmpeg."""
    ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-profile:v", "high",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.warning("subtitle burn failed, using raw video", stderr=result.stderr[-300:])
        os.rename(input_path, output_path)
