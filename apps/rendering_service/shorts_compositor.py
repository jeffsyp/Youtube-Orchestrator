"""Shorts compositor — assembles vertical (9:16) videos for YouTube Shorts.

Every scene has footage running — text overlays appear on top of video,
never on static backgrounds. This matches the visual style of high-performing
Shorts channels where there's always motion on screen.

Memory-optimized: renders each scene to a temp file individually,
then concatenates with FFmpeg. Only one scene in memory at a time.
"""

import gc
import json
import os
import random
import re
import subprocess
import textwrap

import numpy as np
import structlog
from dotenv import load_dotenv

# Fix Pillow compatibility for MoviePy (ANTIALIAS removed in Pillow 10+)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

load_dotenv()
logger = structlog.get_logger()

# Vertical dimensions (9:16)
WIDTH = 1080
HEIGHT = 1920

# Brand colors
ACCENT_COLOR = (0, 168, 255)  # Signal Intel blue
TEXT_COLOR = (255, 255, 255)

# Ken Burns focal points optimized for vertical
FOCAL_POINTS = [
    (0.50, 0.35),  # center-high
    (0.50, 0.50),  # center
    (0.50, 0.65),  # center-low
    (0.35, 0.40),  # left-high
    (0.65, 0.40),  # right-high
]


def _download_stock_clip(query: str, output_path: str) -> str | None:
    """Download a portrait-orientation stock clip from Pexels."""
    from packages.clients.pexels import search_and_download_portrait
    result = search_and_download_portrait(query, output_path)
    if not result:
        for fallback in ["person using phone", "hands typing keyboard", "close up technology"]:
            result = search_and_download_portrait(fallback, output_path)
            if result:
                break
    return result


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _render_clip_to_file(clip, output_path: str):
    """Render a single MoviePy clip to an mp4 file and close it."""
    clip.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="6000k",
        preset="medium",
        threads=4,
        logger=None,
        ffmpeg_params=["-crf", "20", "-profile:v", "high", "-level", "4.1"],
    )
    clip.close()
    gc.collect()


def _ffmpeg_concat(scene_files: list[str], output_path: str):
    """Concatenate mp4 files using FFmpeg concat demuxer (no re-encode)."""
    list_path = output_path + ".concat.txt"
    with open(list_path, "w") as f:
        for path in scene_files:
            f.write(f"file '{os.path.abspath(path)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    os.remove(list_path)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {result.stderr[-300:]}")


def _render_text_overlay(text: str, font_size: int, position: str = "center",
                         color: tuple = TEXT_COLOR, outline_color: tuple = (0, 0, 0),
                         outline_width: int = 6, darken_bg: float = 0.45) -> np.ndarray:
    """Render text overlay as an RGBA numpy array to composite onto footage.

    Returns an RGBA frame the same size as the video (WIDTH x HEIGHT).
    The alpha channel controls where text appears over footage.
    """
    from PIL import Image, ImageDraw
    from apps.rendering_service.fonts import get_font

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Semi-transparent darken layer behind text area for readability
    if darken_bg > 0:
        dark = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * darken_bg)))
        img = Image.alpha_composite(img, dark)
        draw = ImageDraw.Draw(img)

    font = get_font(font_size)
    max_chars = max(8, int(WIDTH / (font_size * 0.55)))
    wrapped = textwrap.fill(text, width=max_chars)
    lines = wrapped.split("\n")

    line_height = int(font_size * 1.3)
    total_h = len(lines) * line_height

    if position == "center":
        start_y = (HEIGHT - total_h) // 2
    elif position == "upper":
        start_y = int(HEIGHT * 0.18)
    elif position == "lower":
        start_y = int(HEIGHT * 0.55)
    else:
        start_y = (HEIGHT - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = start_y + i * line_height

        # Thick outline for readability over footage
        for ox in range(-outline_width, outline_width + 1):
            for oy in range(-outline_width, outline_width + 1):
                if ox * ox + oy * oy <= outline_width * outline_width:
                    draw.text((x + ox, y + oy), line, fill=outline_color + (255,), font=font)

        # Main text
        draw.text((x, y), line, fill=color + (255,), font=font)

    return np.array(img)


def render_short(
    scenes: list[dict],
    voiceover_path: str | None,
    srt_content: str | None,
    output_dir: str,
    script_text: str | None = None,
) -> dict:
    """Render a vertical YouTube Short.

    Every scene has footage running with text overlaid on top.
    Memory-optimized: each scene rendered to a temp file individually.
    """
    log = logger.bind(service="shorts_rendering", action="render_short")
    log.info("starting shorts render")

    os.makedirs(output_dir, exist_ok=True)
    stock_dir = os.path.join(output_dir, "stock_clips")
    os.makedirs(stock_dir, exist_ok=True)
    scenes_dir = os.path.join(output_dir, "scene_clips")
    os.makedirs(scenes_dir, exist_ok=True)

    # Get target duration from voiceover
    target_duration = 0
    if voiceover_path and os.path.exists(voiceover_path):
        target_duration = _get_duration(voiceover_path)
        log.info("target duration", seconds=round(target_duration))

    # If no scenes provided, create a simple plan from script
    if not scenes and script_text:
        scenes = _fallback_plan(script_text, target_duration)

    # Normalize scene durations to match voiceover
    if target_duration > 0 and scenes:
        scene_total = sum(s.get("duration", 3) for s in scenes)
        if scene_total > 0 and abs(scene_total - target_duration) > 3:
            scale = target_duration / scene_total
            for s in scenes:
                s["duration"] = max(1.5, round(s["duration"] * scale, 1))

    # Render each scene to a temp file individually (memory-safe)
    scene_files = []
    for i, scene in enumerate(scenes):
        log.info("rendering scene", scene=i + 1, total=len(scenes), type=scene.get("type"))
        scene_path = os.path.join(scenes_dir, f"scene_{i:03d}.mp4")
        try:
            clip = _make_scene_clip(scene, i, stock_dir)
            if clip is not None:
                _render_clip_to_file(clip, scene_path)
                scene_files.append(scene_path)
                log.info("scene rendered to file", scene=i + 1, path=scene_path)
        except Exception as e:
            log.warning("scene failed, skipping", scene=i, error=str(e))
            gc.collect()

    if not scene_files:
        raise RuntimeError("No clips rendered for Short")

    log.info("all scenes rendered", count=len(scene_files))

    # Concatenate scene files with FFmpeg (no re-encode, very fast)
    concat_path = os.path.join(output_dir, "short_concat.mp4")
    _ffmpeg_concat(scene_files, concat_path)

    # Trim to voiceover duration and add audio (hard cap at 59s for Shorts)
    MAX_SHORT_DURATION = 59.0
    trimmed_path = os.path.join(output_dir, "short_trimmed.mp4")
    if voiceover_path and os.path.exists(voiceover_path):
        voice_dur = _get_duration(voiceover_path)
        concat_dur = _get_duration(concat_path)
        final_dur = min(concat_dur, voice_dur + 0.5, MAX_SHORT_DURATION)

        cmd = [
            "ffmpeg", "-y",
            "-i", concat_path,
            "-i", voiceover_path,
            "-t", str(final_dur),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-movflags", "+faststart",
            "-shortest",
            trimmed_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log.warning("audio merge failed, using video only", stderr=result.stderr[-200:])
            os.rename(concat_path, trimmed_path)
        else:
            os.remove(concat_path)
    else:
        # No voiceover — still enforce max duration
        concat_dur = _get_duration(concat_path)
        if concat_dur > MAX_SHORT_DURATION:
            cmd = [
                "ffmpeg", "-y", "-i", concat_path,
                "-t", str(MAX_SHORT_DURATION),
                "-c", "copy", "-movflags", "+faststart",
                trimmed_path,
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            os.remove(concat_path)
        else:
            os.rename(concat_path, trimmed_path)

    # Burn in voice-synced text — big bold centered captions timed to voiceover
    final_path = os.path.join(output_dir, "short.mp4")
    if voiceover_path and os.path.exists(voiceover_path) and script_text:
        voice_dur = _get_duration(voiceover_path)
        ass_path = _generate_voice_synced_ass(script_text, voice_dur, output_dir,
                                               voiceover_path=voiceover_path)
        if ass_path:
            log.info("burning in voice-synced text")
            _burn_subtitles(trimmed_path, ass_path, final_path)
            os.remove(trimmed_path)
        else:
            os.rename(trimmed_path, final_path)
    else:
        os.rename(trimmed_path, final_path)

    # Clean up temp scene files
    for sf in scene_files:
        try:
            os.remove(sf)
        except OSError:
            pass

    final_dur = _get_duration(final_path)
    file_size = os.path.getsize(final_path)
    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(scene_files),
        "total_duration_seconds": round(final_dur),
        "resolution": f"{WIDTH}x{HEIGHT}",
        "content_type": "short",
    }

    log.info("short render complete", size_mb=round(file_size / 1024 / 1024), clips=len(scene_files))
    return result


def _make_scene_clip(scene: dict, index: int, stock_dir: str):
    """Create a scene clip — always footage-based, with optional text overlay.

    Every scene type gets stock footage. text_punch and hook_card scenes
    additionally get bold text composited on top of the footage.
    """
    from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx
    import cv2

    scene_type = scene.get("type", "footage")
    query = scene.get("search_query", "technology abstract close up")
    duration = scene.get("duration", 3)
    overlay_text = scene.get("text", "")

    # Download stock footage for this scene
    stock_path = os.path.join(stock_dir, f"stock_{index:03d}.mp4")
    if not _download_stock_clip(query, stock_path):
        # If download fails and there's text, fall back to a generic query
        if overlay_text:
            for fallback_q in ["abstract dark background", "cinematic dark texture", "smoke dark background"]:
                if _download_stock_clip(fallback_q, stock_path):
                    break
        if not os.path.exists(stock_path):
            return None

    clip = VideoFileClip(stock_path)
    if clip.duration < 1:
        clip.close()
        return None

    # Speed up slightly for energy
    clip = clip.fx(vfx.speedx, 1.2)

    # Fill duration
    if clip.duration >= duration:
        clip = clip.subclip(0, duration)
    else:
        loops = int(duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * loops).subclip(0, duration)

    # Resize to fill vertical 1080x1920
    w, h = clip.size
    scale = max(WIDTH / w, HEIGHT / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    clip = clip.resize(newsize=(new_w, new_h))

    # Center crop to exact dimensions
    if new_w != WIDTH or new_h != HEIGHT:
        x1 = (new_w - WIDTH) // 2
        y1 = (new_h - HEIGHT) // 2
        clip = clip.crop(x1=x1, y1=y1, width=WIDTH, height=HEIGHT)

    # Ken Burns + color grade in a single .fl() pass
    clip_dur = clip.duration
    zoom_in = (index % 2 == 0)
    focal = FOCAL_POINTS[index % len(FOCAL_POINTS)]
    zoom_amount = random.uniform(0.04, 0.08)

    # All text is now handled by ASS subtitle burn-in (synced to voiceover).
    # Scene clips are pure footage — slight darken so text is readable over any footage.
    darken_amount = 0.20

    def zoom_grade_darken(get_frame, t):
        frame = get_frame(t)
        fh, fw = frame.shape[:2]

        # Ken Burns zoom
        progress = t / max(clip_dur, 0.1)
        if zoom_in:
            sc = 1.0 + zoom_amount * progress
        else:
            sc = (1.0 + zoom_amount) - zoom_amount * progress
        nw = int(fw / sc)
        nh = int(fh / sc)
        mx = fw - nw
        my = fh - nh
        x = max(0, min(int(mx * focal[0]), fw - nw))
        y = max(0, min(int(my * focal[1]), fh - nh))
        cropped = frame[y:y + nh, x:x + nw]
        frame = cv2.resize(cropped, (fw, fh), interpolation=cv2.INTER_LANCZOS4)

        # Color grading — slightly cooler, higher contrast
        frame = frame.astype(np.float32)
        gray = 0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]
        sat = 0.78
        for c in range(3):
            frame[:, :, c] = frame[:, :, c] * sat + gray * (1 - sat)
        frame[:, :, 0] *= 0.93  # red down
        frame[:, :, 2] = np.minimum(frame[:, :, 2] * 1.10, 255)  # blue up
        frame = ((frame - 128) * 1.08 + 128)

        # Darken footage for text scenes so overlay text is readable
        if darken_amount > 0:
            frame *= (1.0 - darken_amount)

        return np.clip(frame, 0, 255).astype(np.uint8)

    clip = clip.fl(zoom_grade_darken)
    clip = clip.without_audio()

    return clip


def _fallback_plan(script_text: str, target_duration: float) -> list[dict]:
    """Create a simple visual plan when no director plan is available."""
    if "[CUT]" in script_text:
        segments = [s.strip() for s in script_text.split("[CUT]") if s.strip()]
    else:
        segments = re.split(r'(?<=[.!?])\s+', script_text.strip())

    scenes = []
    seg_duration = target_duration / max(len(segments), 1) if target_duration > 0 else 3

    # Hook card first
    if segments:
        first_sentence = segments[0].split(".")[0] if "." in segments[0] else segments[0][:60]
        scenes.append({
            "type": "hook_card", "duration": 2.5,
            "text": first_sentence,
            "search_query": "dramatic close up technology",
        })

    for i, seg in enumerate(segments):
        if i % 3 == 0 and i > 0:
            words = seg.split()[:6]
            scenes.append({
                "type": "text_punch", "duration": 2,
                "text": " ".join(words),
                "search_query": " ".join(seg.split()[:3]) + " close up",
            })
        else:
            words = seg.split()
            query_words = words[:4]
            # Pick 1-2 interesting words as keyword
            keyword_words = [w for w in words if len(w) > 4][:2]
            scenes.append({
                "type": "footage", "duration": min(4, max(2, seg_duration)),
                "search_query": " ".join(query_words),
                "keyword": " ".join(keyword_words) if keyword_words else "",
            })

    return scenes


def _generate_voice_synced_ass(script_text: str, voiceover_duration: float, output_dir: str,
                                voiceover_path: str | None = None) -> str | None:
    """Generate ASS subtitles synced to voiceover using word-level timestamps.

    Uses faster-whisper to transcribe the voiceover and get exact word timing.
    Shows 2-4 words at a time — modern Shorts caption style.
    """
    from apps.rendering_service.fonts import FONT_PATH_STR

    font_name = "Inter"
    if "dejavu" in FONT_PATH_STR.lower():
        font_name = "DejaVu Sans"

    log = logger.bind(action="voice_sync_ass")

    # Get word-level timestamps from voiceover audio
    word_timestamps = []
    if voiceover_path and os.path.exists(voiceover_path):
        try:
            from faster_whisper import WhisperModel
            log.info("transcribing voiceover for word timestamps")
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(voiceover_path, word_timestamps=True)
            for segment in segments:
                if segment.words:
                    for w in segment.words:
                        word_timestamps.append({
                            "word": w.word.strip(),
                            "start": w.start,
                            "end": w.end,
                        })
            log.info("transcription complete", words=len(word_timestamps))
        except Exception as e:
            log.warning("whisper transcription failed, falling back", error=str(e))

    if not word_timestamps:
        return None

    # Group words into chunks of 2-4 for display
    chunks = []
    i = 0
    while i < len(word_timestamps):
        remaining = len(word_timestamps) - i
        if remaining <= 4:
            chunk_size = remaining
        elif remaining <= 6:
            chunk_size = 3
        else:
            chunk_size = random.choice([2, 3, 3, 4])

        chunk_words = word_timestamps[i:i + chunk_size]
        chunks.append({
            "text": " ".join(w["word"] for w in chunk_words),
            "start": chunk_words[0]["start"],
            "end": chunk_words[-1]["end"],
        })
        i += chunk_size

    ass_content = f"""[Script Info]
Title: Shorts Voice Sync
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,0,5,80,80,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    for chunk in chunks:
        start = _fmt(chunk["start"])
        end = _fmt(chunk["end"])
        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{chunk['text'].upper()}\n"

    ass_path = os.path.join(output_dir, "voice_sync.ass")
    with open(ass_path, "w") as f:
        f.write(ass_content)

    log.info("voice-synced ASS generated", chunks=len(chunks))
    return ass_path


def _generate_shorts_ass(srt_content: str, output_dir: str) -> str | None:
    """Generate ASS subtitles optimized for Shorts — large, bold, centered."""
    from apps.rendering_service.fonts import FONT_PATH_STR

    font_name = "Inter"
    if "dejavu" in FONT_PATH_STR.lower():
        font_name = "DejaVu Sans"

    ass_content = f"""[Script Info]
Title: Short Subtitles
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},48,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,1,0,1,3,1,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    entries = re.split(r'\n\n+', srt_content.strip())
    for entry in entries:
        lines = entry.strip().split('\n')
        if len(lines) < 3:
            continue

        time_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        g = time_match.groups()
        start = f"{g[0]}:{g[1]}:{g[2]}.{g[3][:2]}"
        end = f"{g[4]}:{g[5]}:{g[6]}.{g[7][:2]}"

        text_lines = " ".join(lines[2:]).split()
        chunks = []
        for j in range(0, len(text_lines), 3):
            chunks.append(" ".join(text_lines[j:j + 3]))
        text = "\\N".join(chunks)

        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    ass_path = os.path.join(output_dir, "subtitles.ass")
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
