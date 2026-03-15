"""Generate stat cards and title cards as video clips.

Stat cards: Big bold number/stat centered on dark background with subtitle
Title cards: Section heading centered with accent line

Both are rendered as short video clips (2-4 seconds) with fade in/out.
"""

import os
import subprocess

import structlog
from PIL import Image, ImageDraw, ImageFont

logger = structlog.get_logger()

WIDTH = 1920
HEIGHT = 1080
BG_COLOR = (12, 12, 20)
ACCENT_COLOR = (0, 180, 255)
TEXT_COLOR = (255, 255, 255)
SUBTITLE_COLOR = (180, 180, 190)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    from apps.rendering_service.fonts import get_font
    return get_font(size)


def _image_to_clip(image_path: str, output_path: str, duration: float) -> str:
    """Convert a static image to a video clip with fade in/out."""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-t", str(duration),
        "-vf", f"fade=in:st=0:d=0.4,fade=out:st={max(0, duration - 0.4)}:d=0.4,fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart",
        "-video_track_timescale", "30000",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return output_path


def generate_stat_card(stat_text: str, subtitle: str, output_path: str, duration: float = 4.0) -> str:
    """Generate a stat card video clip.

    Big bold stat/number centered with subtitle below.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Big stat text
    font_stat = _get_font(120)
    bbox = draw.textbbox((0, 0), stat_text, font=font_stat)
    stat_w = bbox[2] - bbox[0]
    stat_x = (WIDTH - stat_w) // 2
    stat_y = HEIGHT // 2 - 100

    # Shadow
    draw.text((stat_x + 3, stat_y + 3), stat_text, fill=(0, 0, 0), font=font_stat)
    draw.text((stat_x, stat_y), stat_text, fill=ACCENT_COLOR, font=font_stat)

    # Accent line
    line_w = min(stat_w + 60, 500)
    line_x = (WIDTH - line_w) // 2
    draw.rectangle([(line_x, stat_y + 130), (line_x + line_w, stat_y + 134)], fill=ACCENT_COLOR)

    # Subtitle
    if subtitle:
        font_sub = _get_font(36)
        bbox_sub = draw.textbbox((0, 0), subtitle, font=font_sub)
        sub_w = bbox_sub[2] - bbox_sub[0]
        sub_x = (WIDTH - sub_w) // 2
        draw.text((sub_x, stat_y + 155), subtitle, fill=SUBTITLE_COLOR, font=font_sub)

    frame_path = output_path + ".frame.png"
    img.save(frame_path, "PNG")
    _image_to_clip(frame_path, output_path, duration)
    os.remove(frame_path)

    return output_path


def generate_title_card(title_text: str, output_path: str, duration: float = 3.0) -> str:
    """Generate a title card video clip.

    Section heading centered with accent line below.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title text
    font_title = _get_font(64)

    # Word wrap if too long
    import textwrap
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
        draw.text((x, y), line, fill=TEXT_COLOR, font=font_title)

    # Accent line
    line_w = min(max_w + 40, 600)
    line_x = (WIDTH - line_w) // 2
    line_y = start_y + total_h + 15
    draw.rectangle([(line_x, line_y), (line_x + line_w, line_y + 3)], fill=ACCENT_COLOR)

    frame_path = output_path + ".frame.png"
    img.save(frame_path, "PNG")
    _image_to_clip(frame_path, output_path, duration)
    os.remove(frame_path)

    return output_path
