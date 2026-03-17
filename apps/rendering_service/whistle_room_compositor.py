"""Whistle Room compositor — sports clip breakdown Shorts.

Takes a source clip (usually landscape) and an analysis dict, produces a vertical
Short with freeze-frame breakdown, text overlays, score reveal, and background music.

Rendering format:
[0-4s]   Source clip at full speed — the raw play
[4-5s]   FREEZE — dark overlay + "WHISTLE ROOM" bar
[5-9s]   Slow-mo replay with 2-3 text callouts (staggered)
[9-12s]  Score reveal: "8.7/10" + "ELITE" tier
[12-15s] Hook caption
"""

import glob
import os
import random
import subprocess

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

WIDTH = 1080
HEIGHT = 1920

MAX_SHORT_DURATION = 59.0
MUSIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "music")


def render_whistle_room_short(
    clip_path: str,
    analysis: dict,
    output_dir: str,
) -> dict:
    """Render a Whistle Room Short from source clip + analysis.

    Args:
        clip_path: Path to the downloaded source clip.
        analysis: Dict with score, tier, callouts, caption.
        output_dir: Directory for output files.

    Returns:
        Dict with status, path, duration, resolution info.
    """
    log = logger.bind(service="whistle_room_rendering", clip=clip_path)
    log.info("starting whistle room render")

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(clip_path):
        raise RuntimeError(f"Source clip not found: {clip_path}")

    clip_duration = _get_duration(clip_path)
    clip_w, clip_h = _get_resolution(clip_path)

    # Step 1: Crop/pad source to vertical 1080x1920
    vertical_path = os.path.join(output_dir, "wr_vertical.mp4")
    _make_vertical(clip_path, vertical_path, clip_w, clip_h)

    # Step 2: Build the composite Short using FFmpeg filter graph
    composite_path = os.path.join(output_dir, "wr_composite.mp4")
    _build_composite(vertical_path, composite_path, analysis, clip_duration)

    # Step 3: Add background music
    music_path = os.path.join(output_dir, "wr_with_music.mp4")
    composite_duration = _get_duration(composite_path)
    music_track = _pick_music_track()
    if music_track:
        log.info("mixing background music", track=os.path.basename(music_track))
        _mix_music(composite_path, music_track, music_path, composite_duration)
        os.remove(composite_path)
    else:
        os.rename(composite_path, music_path)

    # Step 4: Burn in text overlays via ASS subtitles
    final_path = os.path.join(output_dir, "whistle_room_short.mp4")
    final_duration = _get_duration(music_path)
    ass_path = _generate_overlay_ass(analysis, final_duration, output_dir)
    _burn_subtitles(music_path, ass_path, final_path)
    os.remove(music_path)

    # Cleanup intermediate
    if os.path.exists(vertical_path):
        os.remove(vertical_path)

    final_duration = _get_duration(final_path)
    file_size = os.path.getsize(final_path)

    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "total_duration_seconds": round(final_duration),
        "resolution": f"{WIDTH}x{HEIGHT}",
        "content_type": "whistle_room_short",
        "music_track": os.path.basename(music_track) if music_track else None,
        "score": analysis.get("score"),
        "tier": analysis.get("tier"),
    }

    log.info("whistle room render complete",
             size_mb=round(file_size / 1024 / 1024, 1),
             duration=round(final_duration))
    return result


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _get_resolution(path: str) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    parts = result.stdout.strip().split(",")
    return int(parts[0]), int(parts[1])


def _has_audio(path: str) -> bool:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return bool(result.stdout.strip())


def _make_vertical(input_path: str, output_path: str, src_w: int, src_h: int):
    """Convert source clip to vertical 1080x1920.

    If landscape: center-crop to 9:16 with blurred background fill.
    If already vertical: scale to fit.
    """
    is_landscape = src_w > src_h

    if is_landscape:
        # Blurred background + center-cropped foreground
        filter_str = (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},boxblur=20:5[blurred];"
            f"[fg]scale=-2:{HEIGHT}:force_original_aspect_ratio=decrease[scaled];"
            f"[blurred][scaled]overlay=(W-w)/2:(H-h)/2[outv]"
        )
    else:
        # Already vertical — just scale
        filter_str = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black[outv]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high",
    ]

    # Preserve audio if present
    if _has_audio(input_path):
        cmd.extend(["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"])

    cmd.extend(["-movflags", "+faststart", output_path])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Vertical conversion failed: {result.stderr[-500:]}")


def _build_composite(vertical_path: str, output_path: str, analysis: dict, clip_duration: float):
    """Build the composite Short: full speed + freeze + slow-mo.

    Uses FFmpeg to concatenate segments with different playback speeds.
    Clips are trimmed from the source to create the breakdown structure.
    """
    # Calculate segment timings based on source clip duration
    # Use up to first 5s of clip at full speed, then freeze + slow-mo from the key moment
    full_speed_end = min(4.0, clip_duration * 0.4)
    freeze_point = full_speed_end  # Freeze at the end of full-speed segment

    # Segment 1: Full speed (0 to full_speed_end)
    seg1_path = output_path.replace(".mp4", "_seg1.mp4")
    _ffmpeg_trim_segment(vertical_path, seg1_path, 0, full_speed_end)

    # Segment 2: Freeze frame (1 second of the freeze point)
    seg2_path = output_path.replace(".mp4", "_seg2.mp4")
    _create_freeze_frame(vertical_path, seg2_path, freeze_point, duration=1.0)

    # Segment 3: Slow-mo replay (0.4x speed) of the key moment
    seg3_path = output_path.replace(".mp4", "_seg3.mp4")
    slowmo_start = max(0, freeze_point - 1.0)
    slowmo_end = min(clip_duration, freeze_point + 3.0)
    _create_slowmo(vertical_path, seg3_path, slowmo_start, slowmo_end, speed=0.4)

    # Segment 4: Score reveal (2s freeze with dark overlay — text added later via ASS)
    seg4_path = output_path.replace(".mp4", "_seg4.mp4")
    _create_freeze_frame(vertical_path, seg4_path, freeze_point, duration=3.0, darken=0.6)

    # Segment 5: Caption hold (2s)
    seg5_path = output_path.replace(".mp4", "_seg5.mp4")
    _create_freeze_frame(vertical_path, seg5_path, freeze_point, duration=2.0, darken=0.4)

    # Concatenate all segments
    segments = [seg1_path, seg2_path, seg3_path, seg4_path, seg5_path]
    valid_segments = [s for s in segments if os.path.exists(s)]

    _ffmpeg_concat_segments(valid_segments, output_path)

    # Cleanup segments
    for seg in segments:
        if os.path.exists(seg):
            os.remove(seg)


def _ffmpeg_trim_segment(input_path: str, output_path: str, start: float, end: float):
    """Trim a segment from the video."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-to", str(end),
        "-i", input_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Trim failed: {result.stderr[-300:]}")


def _create_freeze_frame(input_path: str, output_path: str, timestamp: float,
                         duration: float = 1.0, darken: float = 0.0):
    """Extract a frame and create a still video segment."""
    darken_filter = f",colorlevels=rimax={1.0 - darken}:gimax={1.0 - darken}:bimax={1.0 - darken}" if darken > 0 else ""

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", input_path,
        "-vframes", "1",
        "-vf", f"scale={WIDTH}:{HEIGHT}{darken_filter}",
        "-f", "image2pipe",
        "-c:v", "png",
        "pipe:1",
    ]
    frame_result = subprocess.run(cmd, capture_output=True, timeout=10)
    if frame_result.returncode != 0:
        raise RuntimeError("Failed to extract freeze frame")

    # Create video from still frame
    frame_path = output_path.replace(".mp4", "_frame.png")
    with open(frame_path, "wb") as f:
        f.write(frame_result.stdout)

    cmd2 = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", frame_path,
        "-t", str(duration),
        "-vf", f"scale={WIDTH}:{HEIGHT}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        # Silent audio track for concat compatibility
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
    os.remove(frame_path)
    if result.returncode != 0:
        raise RuntimeError(f"Freeze frame video failed: {result.stderr[-300:]}")


def _create_slowmo(input_path: str, output_path: str, start: float, end: float, speed: float = 0.4):
    """Create a slow-motion segment."""
    setpts = f"PTS/{speed}"
    atempo = speed  # For audio

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start), "-to", str(end),
        "-i", input_path,
        "-filter_complex",
        f"[0:v]setpts={setpts}[v];[0:a]atempo={atempo}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        # Fallback: try without audio (source might not have audio)
        cmd_fallback = [
            "ffmpeg", "-y",
            "-ss", str(start), "-to", str(end),
            "-i", input_path,
            "-vf", f"setpts={setpts}",
            "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str((end - start) / speed),
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=120)
        if result2.returncode != 0:
            raise RuntimeError(f"Slow-mo failed: {result2.stderr[-300:]}")


def _ffmpeg_concat_segments(segments: list[str], output_path: str):
    """Concatenate video segments using concat demuxer."""
    concat_list = output_path.replace(".mp4", "_list.txt")
    with open(concat_list, "w") as f:
        for seg in segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    os.remove(concat_list)
    if result.returncode != 0:
        raise RuntimeError(f"Concat failed: {result.stderr[-300:]}")


def _pick_music_track() -> str | None:
    music_dir = os.path.normpath(MUSIC_DIR)
    if not os.path.isdir(music_dir):
        return None
    tracks = glob.glob(os.path.join(music_dir, "*.mp3"))
    return random.choice(tracks) if tracks else None


def _mix_music(video_path: str, music_path: str, output_path: str, video_duration: float):
    """Mix background music under the video's audio."""
    fade_start = max(0, video_duration - 2.0)
    has_audio = _has_audio(video_path)

    if has_audio:
        filter_str = (
            f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
            f"volume=0.12,afade=t=out:st={fade_start}:d=2.0[music];"
            f"[0:a]volume=0.9[orig];"
            f"[orig][music]amix=inputs=2:duration=first:dropout_transition=0[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path, "-i", music_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest",
            output_path,
        ]
    else:
        filter_str = (
            f"[1:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS,"
            f"volume=0.35,afade=t=out:st={fade_start}:d=2.0[outa]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path, "-i", music_path,
            "-filter_complex", filter_str,
            "-map", "0:v:0", "-map", "[outa]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest",
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.warning("music mix failed, using original", stderr=result.stderr[-300:])
        _ffmpeg_copy(video_path, output_path)


def _ffmpeg_copy(input_path: str, output_path: str):
    cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", "-movflags", "+faststart", output_path]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _generate_overlay_ass(analysis: dict, duration: float, output_dir: str) -> str:
    """Generate ASS subtitle file with all text overlays for the Short.

    Timeline:
    [4-5s]   "WHISTLE ROOM" title bar
    [5-9s]   Callout texts (staggered appearance)
    [9-12s]  Score + tier reveal
    [12-15s] Caption/hook
    """
    from apps.rendering_service.fonts import FONT_PATH_STR

    font_name = "Inter"
    if "dejavu" in FONT_PATH_STR.lower():
        font_name = "DejaVu Sans"

    score = analysis.get("score", 7.0)
    tier = analysis.get("tier", "SOLID")
    callouts = analysis.get("callouts", [])
    caption = analysis.get("caption", "")

    # Tier colors (ASS format: &HBBGGRR)
    tier_colors = {
        "FILTHY": "&H004FFFFF",   # gold/yellow
        "ELITE": "&H0000FF00",    # green
        "SOLID": "&H00FFFFFF",    # white
        "MEH": "&H0080FFFF",     # orange-yellow
        "BRICK": "&H000000FF",    # red
    }
    tier_color = tier_colors.get(tier, "&H00FFFFFF")

    def _fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    events = []

    # "WHISTLE ROOM" title bar (during freeze)
    events.append(
        f"Dialogue: 0,{_fmt(4.0)},{_fmt(5.0)},Title,,0,0,0,,"
        f"{{\\an8\\pos({WIDTH // 2},180)\\fad(200,200)}}WHISTLE ROOM"
    )

    # Callout texts during slow-mo (staggered, 5-9s)
    for i, callout in enumerate(callouts[:3]):
        start = 5.0 + i * 1.3
        end = min(9.0, start + 3.5)
        y_pos = 600 + i * 200
        # Escape ASS special chars
        safe_text = callout.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        events.append(
            f"Dialogue: 0,{_fmt(start)},{_fmt(end)},Callout,,0,0,0,,"
            f"{{\\an4\\pos(80,{y_pos})\\fad(300,200)}}{safe_text}"
        )

    # Score reveal (9-12s)
    events.append(
        f"Dialogue: 0,{_fmt(9.0)},{_fmt(12.0)},Score,,0,0,0,,"
        f"{{\\an5\\pos({WIDTH // 2},{HEIGHT // 2 - 80})\\fad(400,300)}}{score}/10"
    )
    events.append(
        f"Dialogue: 0,{_fmt(9.5)},{_fmt(12.0)},Tier,,0,0,0,,"
        f"{{\\an5\\pos({WIDTH // 2},{HEIGHT // 2 + 100})\\fad(400,300)}}{tier}"
    )

    # Hook caption (12-15s or to end)
    caption_end = min(duration, 15.0)
    if caption:
        safe_caption = caption.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        events.append(
            f"Dialogue: 0,{_fmt(12.0)},{_fmt(caption_end)},Caption,,0,0,0,,"
            f"{{\\an2\\pos({WIDTH // 2},{HEIGHT - 200})\\fad(300,300)}}{safe_caption}"
        )

    ass_content = f"""[Script Info]
Title: Whistle Room Overlay
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font_name},72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,5,3,8,40,40,40,1
Style: Callout,{font_name},36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,4,40,40,40,1
Style: Score,{font_name},120,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,3,0,1,6,4,5,40,40,40,1
Style: Tier,{font_name},64,{tier_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,3,0,1,5,3,5,40,40,40,1
Style: Caption,{font_name},44,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,40,40,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(events) + "\n"

    ass_path = os.path.join(output_dir, "whistle_room_overlay.ass")
    with open(ass_path, "w") as f:
        f.write(ass_content)

    return ass_path


def _burn_subtitles(input_path: str, ass_path: str, output_path: str):
    """Burn ASS subtitles into video."""
    ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-profile:v", "high",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.warning("subtitle burn failed, using raw video", stderr=result.stderr[-300:])
        os.rename(input_path, output_path)
