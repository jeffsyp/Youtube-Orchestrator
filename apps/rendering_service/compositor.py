"""Video compositor — assembles all scenes into a final video using MoviePy.

Single render pass: footage + cards + transitions + text overlays + audio.
No multi-pass re-encoding. Crossfades between scenes. Ken Burns on footage.
"""

import os
import random
import subprocess

import numpy as np
import structlog
from dotenv import load_dotenv

# Fix Pillow compatibility for MoviePy (ANTIALIAS removed in Pillow 10+)
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

load_dotenv()
logger = structlog.get_logger()

# Ken Burns focal point presets (rule of thirds + center)
FOCAL_POINTS = [
    (0.33, 0.33),  # top-left third
    (0.50, 0.40),  # center-high
    (0.67, 0.33),  # top-right third
    (0.50, 0.50),  # center
    (0.33, 0.60),  # bottom-left third
    (0.67, 0.60),  # bottom-right third
]


def _download_stock_clip(query: str, output_path: str) -> str | None:
    """Download a stock clip from Pexels."""
    from packages.clients.pexels import search_and_download
    result = search_and_download(query, output_path)
    if not result:
        for fallback in ["people working office", "city street walking", "technology computer"]:
            result = search_and_download(fallback, output_path)
            if result:
                break
    return result


def _get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())


def _generate_whoosh(duration: float = 0.35, sample_rate: int = 44100) -> np.ndarray:
    """Generate a synthetic whoosh sound effect for transitions."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Frequency sweep from high to low
    freq = np.linspace(2000, 200, len(t))
    # Filtered noise with frequency sweep
    noise = np.random.randn(len(t)) * 0.3
    sweep = np.sin(2 * np.pi * freq * t / sample_rate) * 0.15
    signal = noise + sweep
    # Envelope: quick attack, smooth decay
    envelope = np.exp(-t / (duration * 0.3)) * np.minimum(t / 0.02, 1.0)
    signal = signal * envelope * 0.25  # Keep volume low
    return np.column_stack([signal, signal]).astype(np.float32)


def _generate_impact(duration: float = 0.2, sample_rate: int = 44100) -> np.ndarray:
    """Generate a subtle impact/hit sound for stat card reveals."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Low thump + high click
    thump = np.sin(2 * np.pi * 60 * t) * np.exp(-t / 0.05)
    click = np.sin(2 * np.pi * 800 * t) * np.exp(-t / 0.01) * 0.3
    signal = (thump + click) * 0.3
    return np.column_stack([signal, signal]).astype(np.float32)


def render_video(
    shots: list[dict],
    voiceover_path: str | None,
    srt_content: str | None,
    output_dir: str,
    script_content: str | None = None,
) -> dict:
    """Render the final video using MoviePy for single-pass compositing."""
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip,
        concatenate_videoclips, CompositeVideoClip,
        CompositeAudioClip, AudioClip,
        vfx,
    )

    log = logger.bind(service="rendering", action="render_video")
    log.info("starting video render (moviepy)")

    os.makedirs(output_dir, exist_ok=True)
    stock_dir = os.path.join(output_dir, "stock_clips")
    os.makedirs(stock_dir, exist_ok=True)

    # Get target duration
    target_duration = 0
    if voiceover_path and os.path.exists(voiceover_path):
        target_duration = _get_duration(voiceover_path)
        log.info("target duration", seconds=round(target_duration))

    # Step 1: Director creates scene plan
    if script_content and target_duration > 0:
        from apps.rendering_service.director import create_visual_plan
        scenes = create_visual_plan(script_content, target_duration, "Video")
        log.info("director plan", scenes=len(scenes))
    else:
        scenes = [{"type": "footage", "duration": 20, "search_query": "technology"} for _ in range(5)]

    # Step 2: Build MoviePy clips for each scene
    clips = []
    sfx_clips = []  # Sound effects to mix with voiceover
    current_time = 0.0  # Track timeline position for SFX placement

    for i, scene in enumerate(scenes):
        log.info("rendering scene", scene=i + 1, total=len(scenes), type=scene["type"])

        try:
            if scene["type"] == "footage":
                clip = _make_footage_clip(scene, i, stock_dir)
            elif scene["type"] == "stat_card":
                clip = _make_stat_card_clip(scene)
            elif scene["type"] == "title_card":
                clip = _make_title_card_clip(scene)
            else:
                continue

            if clip is None:
                continue

            # Varied transition duration (0.3-0.8s) instead of constant
            fade_duration = round(random.uniform(0.3, 0.8), 2)

            # Add crossfade with varied duration
            if clips:
                clip = clip.crossfadein(fade_duration)

                # Add whoosh SFX at transition point
                whoosh_data = _generate_whoosh(duration=fade_duration)
                whoosh_clip = AudioClip(
                    lambda t, d=whoosh_data, sr=44100: d[min(int(t * sr), len(d) - 1)],
                    duration=fade_duration, fps=44100,
                )
                sfx_clips.append(whoosh_clip.set_start(max(0, current_time - fade_duration / 2)))

            # Add impact SFX for stat cards
            if scene["type"] == "stat_card":
                impact_data = _generate_impact()
                impact_clip = AudioClip(
                    lambda t, d=impact_data, sr=44100: d[min(int(t * sr), len(d) - 1)],
                    duration=0.2, fps=44100,
                )
                sfx_clips.append(impact_clip.set_start(current_time + 0.3))

            current_time += clip.duration - (fade_duration if clips else 0)
            clips.append(clip)

        except Exception as e:
            log.warning("scene failed, skipping", scene=i, error=str(e))

    if not clips:
        raise RuntimeError("No clips rendered")

    log.info("all scenes built", count=len(clips))

    # Step 3: Add intro/outro
    intro_clip = _make_branding_clip("intro")
    outro_clip = _make_branding_clip("outro")

    if intro_clip:
        clips.insert(0, intro_clip)
        # Shift all SFX forward by intro duration
        intro_dur = intro_clip.duration
        sfx_clips = [s.set_start(s.start + intro_dur) for s in sfx_clips]

    if outro_clip:
        outro_fade = 0.5
        clips.append(outro_clip.crossfadein(outro_fade))

    # Step 4: Concatenate — use average fade for padding
    log.info("compositing video")
    avg_fade = 0.5
    final_video = concatenate_videoclips(clips, method="compose", padding=-avg_fade)

    # Step 5: Trim to voiceover duration
    if target_duration > 0 and final_video.duration > target_duration + 10:
        final_video = final_video.subclip(0, target_duration + 8)

    # Step 6: Add voiceover audio + SFX
    audio_tracks = []
    if voiceover_path and os.path.exists(voiceover_path):
        voice_audio = AudioFileClip(voiceover_path)
        audio_tracks.append(voice_audio)
        log.info("voice audio added")

    # Add SFX tracks
    if sfx_clips:
        audio_tracks.extend(sfx_clips)
        log.info("sfx added", count=len(sfx_clips))

    if audio_tracks:
        mixed_audio = CompositeAudioClip(audio_tracks)
        final_video = final_video.set_audio(mixed_audio)
        if voiceover_path and os.path.exists(voiceover_path):
            final_video = final_video.subclip(0, min(final_video.duration, voice_audio.duration + 8))

    # Step 7: Save SRT and generate ASS for burn-in
    srt_path = None
    ass_path = None
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)
        ass_path = _generate_ass_subtitles(srt_content, output_dir)

    # Step 8: Render final video (SINGLE PASS) with improved encoding
    raw_path = os.path.join(output_dir, "final_raw.mp4")
    final_path = os.path.join(output_dir, "final.mp4")
    log.info("rendering final video", duration=round(final_video.duration))

    # If we have subtitles to burn in, render raw first then add subs
    render_path = raw_path if ass_path else final_path

    final_video.write_videofile(
        render_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="slow",
        threads=4,
        logger=None,
        ffmpeg_params=[
            "-crf", "18",
            "-profile:v", "high",
            "-level", "4.1",
            "-movflags", "+faststart",
            "-bf", "2",
            "-g", "60",
        ],
    )

    # Step 9: Burn in styled subtitles if available
    if ass_path and os.path.exists(ass_path):
        log.info("burning in subtitles")
        _burn_subtitles(raw_path, ass_path, final_path)
        os.remove(raw_path)
    elif render_path != final_path:
        os.rename(render_path, final_path)

    # Cleanup
    final_video.close()
    for clip in clips:
        clip.close()

    file_size = os.path.getsize(final_path)
    result = {
        "status": "rendered",
        "path": os.path.abspath(final_path),
        "size_bytes": file_size,
        "clips_count": len(clips),
        "total_duration_seconds": round(final_video.duration if hasattr(final_video, 'duration') else 0),
    }

    log.info("render complete", size_mb=round(file_size / 1024 / 1024), clips=len(clips))
    return result


def _make_footage_clip(scene: dict, index: int, stock_dir: str):
    """Create a footage clip with varied Ken Burns zoom + color grading."""
    from moviepy.editor import VideoFileClip, vfx
    import cv2

    query = scene.get("search_query", "technology")
    duration = scene.get("duration", 20)
    stock_path = os.path.join(stock_dir, f"stock_{index:03d}.mp4")

    if not _download_stock_clip(query, stock_path):
        return None

    clip = VideoFileClip(stock_path)

    source_dur = clip.duration
    if source_dur < 3:
        clip.close()
        return None

    # Speed up slightly (1.3x) to avoid slo-mo look
    clip = clip.fx(vfx.speedx, 1.3)

    # Take what we need
    available = clip.duration
    use_duration = min(duration, available)
    if use_duration < available:
        clip = clip.subclip(0, use_duration)

    # Resize to 1080p
    clip = clip.resize(newsize=(1920, 1080))

    # Ken Burns: vary direction and focal point per clip
    clip_dur = clip.duration
    zoom_in = (index % 2 == 0)  # Alternate zoom in/out
    focal = FOCAL_POINTS[index % len(FOCAL_POINTS)]
    zoom_amount = random.uniform(0.06, 0.12)  # Vary zoom intensity

    def zoom_effect(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]

        progress = t / max(clip_dur, 1)
        if zoom_in:
            scale = 1.0 + zoom_amount * progress
        else:
            scale = (1.0 + zoom_amount) - zoom_amount * progress

        new_w = int(w / scale)
        new_h = int(h / scale)

        # Focal point determines crop position
        max_x = w - new_w
        max_y = h - new_h
        x = int(max_x * focal[0])
        y = int(max_y * focal[1])

        # Clamp
        x = max(0, min(x, w - new_w))
        y = max(0, min(y, h - new_h))

        cropped = frame[y:y + new_h, x:x + new_w]
        resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)
        return resized

    clip = clip.fl(zoom_effect)
    clip = clip.without_audio()

    # Color grading: slight desaturation + cool tint to match dark brand aesthetic
    def color_grade(get_frame, t):
        frame = get_frame(t).astype(np.float32)

        # Desaturate slightly (blend toward luminance)
        gray = 0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]
        saturation = 0.82  # 82% saturation
        for c in range(3):
            frame[:, :, c] = frame[:, :, c] * saturation + gray * (1 - saturation)

        # Cool blue tint: slightly boost blue, slightly reduce red
        frame[:, :, 0] = frame[:, :, 0] * 0.95   # red down
        frame[:, :, 2] = np.minimum(frame[:, :, 2] * 1.08, 255)  # blue up

        # Slight contrast boost
        frame = ((frame - 128) * 1.05 + 128)
        frame = np.clip(frame, 0, 255)

        return frame.astype(np.uint8)

    clip = clip.fl(color_grade)

    return clip


def _make_stat_card_clip(scene: dict):
    """Create a stat card as an ImageClip."""
    from moviepy.editor import ImageClip

    duration = scene.get("duration", 4)
    stat_text = scene.get("stat_text", "")
    subtitle = scene.get("subtitle", "")

    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR, SUBTITLE_COLOR
    from apps.rendering_service.fonts import get_font

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_stat = get_font(120)
    bbox = draw.textbbox((0, 0), stat_text, font=font_stat)
    stat_w = bbox[2] - bbox[0]
    stat_x = (WIDTH - stat_w) // 2
    stat_y = HEIGHT // 2 - 100

    # Softer shadow (larger offset, semi-transparent feel via darker shade)
    draw.text((stat_x + 4, stat_y + 4), stat_text, fill=(5, 5, 15), font=font_stat)
    draw.text((stat_x, stat_y), stat_text, fill=ACCENT_COLOR, font=font_stat)

    line_w = min(stat_w + 60, 500)
    line_x = (WIDTH - line_w) // 2
    draw.rectangle([(line_x, stat_y + 130), (line_x + line_w, stat_y + 134)], fill=ACCENT_COLOR)

    if subtitle:
        font_sub = get_font(36)
        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        sub_w = bbox_sub[2] - bbox_sub[0]
        draw.text(((WIDTH - sub_w) // 2, stat_y + 155), subtitle, fill=SUBTITLE_COLOR, font=font_sub)

    frame = np.array(img)
    clip = ImageClip(frame, duration=duration)
    return clip


def _make_title_card_clip(scene: dict):
    """Create a title card as an ImageClip."""
    from moviepy.editor import ImageClip
    import textwrap

    duration = scene.get("duration", 3)
    title_text = scene.get("title_text", "")

    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR
    from apps.rendering_service.fonts import get_font

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = get_font(64)
    wrapped = textwrap.fill(title_text, width=28)
    lines = wrapped.split("\n")

    line_height = 80
    total_h = len(lines) * line_height
    start_y = (HEIGHT - total_h) // 2 - 20

    max_w = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        text_w = bbox[2] - bbox[0]
        max_w = max(max_w, text_w)
        x = (WIDTH - text_w) // 2
        y = start_y + i * line_height
        draw.text((x + 3, y + 3), line, fill=(5, 5, 15), font=font_title)
        draw.text((x, y), line, fill=(255, 255, 255), font=font_title)

    line_w = min(max_w + 40, 600)
    line_x = (WIDTH - line_w) // 2
    draw.rectangle([(line_x, start_y + total_h + 15), (line_x + line_w, start_y + total_h + 18)], fill=ACCENT_COLOR)

    frame = np.array(img)
    clip = ImageClip(frame, duration=duration)
    return clip


def _make_branding_clip(clip_type: str):
    """Create intro or outro as ImageClip."""
    from moviepy.editor import ImageClip
    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR
    from apps.rendering_service.fonts import get_font

    channel_name = os.getenv("CHANNEL_NAME", "Signal Intel")

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    if clip_type == "intro":
        font = get_font(72)
        bbox = draw.textbbox((0, 0), channel_name, font=font)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = HEIGHT // 2 - 50
        draw.text((x + 3, y + 3), channel_name, fill=(5, 5, 15), font=font)
        draw.text((x, y), channel_name, fill=(255, 255, 255), font=font)
        line_w = min(text_w + 40, 600)
        draw.rectangle([((WIDTH - line_w) // 2, y + 85), ((WIDTH + line_w) // 2, y + 88)], fill=ACCENT_COLOR)
        duration = 3

    else:  # outro
        font_name = get_font(60)
        bbox = draw.textbbox((0, 0), channel_name, font=font_name)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = HEIGHT // 2 - 80
        draw.text((x + 3, y + 3), channel_name, fill=(5, 5, 15), font=font_name)
        draw.text((x, y), channel_name, fill=(255, 255, 255), font=font_name)

        font_cta = get_font(36)
        cta = "Subscribe for more"
        bbox_cta = draw.textbbox((0, 0), cta, font=font_cta)
        draw.text(((WIDTH - (bbox_cta[2] - bbox_cta[0])) // 2, y + 90), cta, fill=(200, 200, 200), font=font_cta)

        # Subscribe button
        btn_w, btn_h = 220, 45
        btn_x = (WIDTH - btn_w) // 2
        btn_y = y + 150
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=8, fill=(204, 0, 0))
        font_btn = get_font(22)
        bbox_btn = draw.textbbox((0, 0), "SUBSCRIBE", font=font_btn)
        draw.text(((WIDTH - (bbox_btn[2] - bbox_btn[0])) // 2, btn_y + 10), "SUBSCRIBE", fill=(255, 255, 255), font=font_btn)

        draw.rectangle([((WIDTH - 400) // 2, y + 75), ((WIDTH + 400) // 2, y + 78)], fill=ACCENT_COLOR)
        duration = 5

    frame = np.array(img)
    clip = ImageClip(frame, duration=duration)
    return clip


def _generate_ass_subtitles(srt_content: str, output_dir: str) -> str | None:
    """Convert SRT content to ASS format with professional styling."""
    from apps.rendering_service.fonts import FONT_PATH_STR

    # Determine font name from path
    font_name = "Inter"
    if "dejavu" in FONT_PATH_STR.lower():
        font_name = "DejaVu Sans"

    ass_content = f"""[Script Info]
Title: Video Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},26,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,2,0,2,40,40,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Parse SRT entries
    import re
    entries = re.split(r'\n\n+', srt_content.strip())
    for entry in entries:
        lines = entry.strip().split('\n')
        if len(lines) < 3:
            continue

        # Parse timestamp line
        time_match = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1]
        )
        if not time_match:
            continue

        g = time_match.groups()
        start = f"{g[0]}:{g[1]}:{g[2]}.{g[3][:2]}"
        end = f"{g[4]}:{g[5]}:{g[6]}.{g[7][:2]}"

        text = "\\N".join(lines[2:])
        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    ass_path = os.path.join(output_dir, "subtitles.ass")
    with open(ass_path, "w") as f:
        f.write(ass_content)
    return ass_path


def _burn_subtitles(input_path: str, ass_path: str, output_path: str):
    """Burn ASS subtitles into video using FFmpeg."""
    # Escape path for FFmpeg filter (colons and backslashes)
    ass_escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"ass={ass_escaped}",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-profile:v", "high",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        logger.warning("subtitle burn failed, using raw video", stderr=result.stderr[-300:])
        os.rename(input_path, output_path)
