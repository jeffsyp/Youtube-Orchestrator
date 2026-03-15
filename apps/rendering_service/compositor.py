"""Video compositor — assembles all scenes into a final video using MoviePy.

Single render pass: footage + cards + transitions + text overlays + audio.
No multi-pass re-encoding. Crossfades between scenes. Ken Burns on footage.
"""

import os
import subprocess

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()


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
    fade_duration = 0.5

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

            # Add crossfade
            if clips:  # Not the first clip
                clip = clip.crossfadein(fade_duration)

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
    if outro_clip:
        clips.append(outro_clip.crossfadein(fade_duration))

    # Step 4: Concatenate with crossfade method
    log.info("compositing video")
    final_video = concatenate_videoclips(clips, method="compose", padding=-fade_duration)

    # Step 5: Trim to voiceover duration
    if target_duration > 0 and final_video.duration > target_duration + 10:
        final_video = final_video.subclip(0, target_duration + 8)  # +8 for outro

    # Step 6: Add voiceover audio
    if voiceover_path and os.path.exists(voiceover_path):
        audio = AudioFileClip(voiceover_path)
        final_video = final_video.set_audio(audio)
        # Trim to audio duration
        final_video = final_video.subclip(0, min(final_video.duration, audio.duration + 8))
        log.info("audio added")

    # Step 7: Save SRT
    if srt_content:
        srt_path = os.path.join(output_dir, "subtitles.srt")
        with open(srt_path, "w") as f:
            f.write(srt_content)

    # Step 8: Render final video (SINGLE PASS)
    final_path = os.path.join(output_dir, "final.mp4")
    log.info("rendering final video", duration=round(final_video.duration))

    final_video.write_videofile(
        final_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        bitrate="5000k",
        preset="fast",
        threads=4,
        logger=None,  # Suppress moviepy's progress bar
    )

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
    """Create a footage clip with Ken Burns zoom effect."""
    from moviepy.editor import VideoFileClip, vfx

    query = scene.get("search_query", "technology")
    duration = scene.get("duration", 20)
    stock_path = os.path.join(stock_dir, f"stock_{index:03d}.mp4")

    if not _download_stock_clip(query, stock_path):
        return None

    clip = VideoFileClip(stock_path)

    # Use up to the requested duration from the source
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
    clip = clip.resize((1920, 1080))

    # Ken Burns: slow zoom from 100% to 108% over the clip duration
    def zoom_effect(get_frame, t):
        import numpy as np
        from PIL import Image

        frame = get_frame(t)
        h, w = frame.shape[:2]

        # Zoom from 1.0 to 1.08 over the clip
        progress = t / max(clip.duration, 1)
        scale = 1.0 + 0.08 * progress

        # Calculate crop region (zoom into center)
        new_w = int(w / scale)
        new_h = int(h / scale)
        x = (w - new_w) // 2
        y = (h - new_h) // 2

        cropped = frame[y:y + new_h, x:x + new_w]

        # Resize back to original dimensions
        img = Image.fromarray(cropped)
        img = img.resize((w, h), Image.LANCZOS)
        return np.array(img)

    clip = clip.fl(zoom_effect)
    clip = clip.without_audio()

    return clip


def _make_stat_card_clip(scene: dict):
    """Create a stat card as an ImageClip."""
    from moviepy.editor import ImageClip
    import numpy as np

    duration = scene.get("duration", 4)
    stat_text = scene.get("stat_text", "")
    subtitle = scene.get("subtitle", "")

    # Generate the card image with Pillow
    from apps.rendering_service.cards import generate_stat_card
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        temp_path = f.name

    # Generate just the frame (not a video)
    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import _get_font, WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR, SUBTITLE_COLOR

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_stat = _get_font(120)
    bbox = draw.textbbox((0, 0), stat_text, font=font_stat)
    stat_w = bbox[2] - bbox[0]
    stat_x = (WIDTH - stat_w) // 2
    stat_y = HEIGHT // 2 - 100
    draw.text((stat_x + 3, stat_y + 3), stat_text, fill=(0, 0, 0), font=font_stat)
    draw.text((stat_x, stat_y), stat_text, fill=ACCENT_COLOR, font=font_stat)

    line_w = min(stat_w + 60, 500)
    line_x = (WIDTH - line_w) // 2
    draw.rectangle([(line_x, stat_y + 130), (line_x + line_w, stat_y + 134)], fill=ACCENT_COLOR)

    if subtitle:
        font_sub = _get_font(36)
        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        sub_w = bbox_sub[2] - bbox_sub[0]
        draw.text(((WIDTH - sub_w) // 2, stat_y + 155), subtitle, fill=SUBTITLE_COLOR, font=font_sub)

    frame = np.array(img)
    clip = ImageClip(frame, duration=duration)
    return clip


def _make_title_card_clip(scene: dict):
    """Create a title card as an ImageClip."""
    from moviepy.editor import ImageClip
    import numpy as np
    import textwrap

    duration = scene.get("duration", 3)
    title_text = scene.get("title_text", "")

    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import _get_font, WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _get_font(64)
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
        draw.text((x + 2, y + 2), line, fill=(0, 0, 0), font=font_title)
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
    import numpy as np
    from PIL import Image, ImageDraw
    from apps.rendering_service.cards import _get_font, WIDTH, HEIGHT, BG_COLOR, ACCENT_COLOR

    channel_name = os.getenv("CHANNEL_NAME", "Signal Intel")

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    if clip_type == "intro":
        font = _get_font(72)
        bbox = draw.textbbox((0, 0), channel_name, font=font)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = HEIGHT // 2 - 50
        draw.text((x + 2, y + 2), channel_name, fill=(0, 0, 0), font=font)
        draw.text((x, y), channel_name, fill=(255, 255, 255), font=font)
        line_w = min(text_w + 40, 600)
        draw.rectangle([((WIDTH - line_w) // 2, y + 85), ((WIDTH + line_w) // 2, y + 88)], fill=ACCENT_COLOR)
        duration = 3

    else:  # outro
        font_name = _get_font(60)
        bbox = draw.textbbox((0, 0), channel_name, font=font_name)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = HEIGHT // 2 - 80
        draw.text((x + 2, y + 2), channel_name, fill=(0, 0, 0), font=font_name)
        draw.text((x, y), channel_name, fill=(255, 255, 255), font=font_name)

        font_cta = _get_font(36)
        cta = "Subscribe for more"
        bbox_cta = draw.textbbox((0, 0), cta, font=font_cta)
        draw.text(((WIDTH - (bbox_cta[2] - bbox_cta[0])) // 2, y + 90), cta, fill=(200, 200, 200), font=font_cta)

        # Subscribe button
        btn_w, btn_h = 220, 45
        btn_x = (WIDTH - btn_w) // 2
        btn_y = y + 150
        draw.rounded_rectangle([(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)], radius=8, fill=(204, 0, 0))
        font_btn = _get_font(22)
        bbox_btn = draw.textbbox((0, 0), "SUBSCRIBE", font=font_btn)
        draw.text(((WIDTH - (bbox_btn[2] - bbox_btn[0])) // 2, btn_y + 10), "SUBSCRIBE", fill=(255, 255, 255), font=font_btn)

        draw.rectangle([((WIDTH - 400) // 2, y + 75), ((WIDTH + 400) // 2, y + 78)], fill=ACCENT_COLOR)
        duration = 5

    frame = np.array(img)
    clip = ImageClip(frame, duration=duration)
    return clip
