"""Intro and outro generation for channel branding.

Creates:
- 3-second intro: channel name with animated reveal
- 5-second outro: subscribe CTA with channel name
"""

import os
import subprocess

import structlog
from PIL import Image, ImageDraw, ImageFont

logger = structlog.get_logger()

WIDTH = 1920
HEIGHT = 1080


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    from apps.rendering_service.fonts import get_font
    return get_font(size)


def _run_ffmpeg(args: list[str], description: str = ""):
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed ({description}): {result.stderr[-200:]}")
    return result


def generate_intro(channel_name: str, output_path: str, duration: float = 3.0) -> str:
    """Generate a 3-second intro clip with channel name reveal.

    Dark background with the channel name fading in and a subtle
    accent line animating underneath.
    """
    log = logger.bind(service="branding", action="intro")
    log.info("generating intro", channel=channel_name)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Create the intro frame
    frame_path = output_path + ".frame.png"
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 12, 20))
    draw = ImageDraw.Draw(img)

    # Channel name — large, centered
    font_large = _get_font(72)
    bbox = draw.textbbox((0, 0), channel_name, font=font_large)
    text_w = bbox[2] - bbox[0]
    x = (WIDTH - text_w) // 2
    y = HEIGHT // 2 - 50

    # Text shadow
    draw.text((x + 2, y + 2), channel_name, fill=(0, 0, 0), font=font_large)
    draw.text((x, y), channel_name, fill=(255, 255, 255), font=font_large)

    # Accent line under text
    line_w = min(text_w + 40, 600)
    line_x = (WIDTH - line_w) // 2
    line_y = y + 85
    draw.rectangle([(line_x, line_y), (line_x + line_w, line_y + 3)], fill=(0, 180, 255))

    img.save(frame_path, "PNG")

    # Convert to video with fade-in effect
    fps = 30
    _run_ffmpeg(
        [
            "-loop", "1",
            "-i", frame_path,
            "-t", str(duration),
            "-vf", (
                f"fade=in:st=0:d=0.8,fade=out:st={duration - 0.5}:d=0.5,"
                f"fps={fps}"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path,
        ],
        description="intro clip",
    )

    os.remove(frame_path)
    log.info("intro generated", path=output_path)
    return output_path


def generate_outro(channel_name: str, output_path: str, duration: float = 5.0) -> str:
    """Generate a 5-second outro clip with subscribe CTA.

    Dark background with channel name and "Subscribe for more" text.
    """
    log = logger.bind(service="branding", action="outro")
    log.info("generating outro", channel=channel_name)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    frame_path = output_path + ".frame.png"
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 12, 20))
    draw = ImageDraw.Draw(img)

    # Channel name
    font_name = _get_font(60)
    bbox = draw.textbbox((0, 0), channel_name, font=font_name)
    text_w = bbox[2] - bbox[0]
    x = (WIDTH - text_w) // 2
    y = HEIGHT // 2 - 80
    draw.text((x + 2, y + 2), channel_name, fill=(0, 0, 0), font=font_name)
    draw.text((x, y), channel_name, fill=(255, 255, 255), font=font_name)

    # Subscribe CTA
    font_cta = _get_font(36)
    cta = "Subscribe for more"
    bbox_cta = draw.textbbox((0, 0), cta, font=font_cta)
    cta_w = bbox_cta[2] - bbox_cta[0]
    cta_x = (WIDTH - cta_w) // 2
    cta_y = y + 90
    draw.text((cta_x, cta_y), cta, fill=(200, 200, 200), font=font_cta)

    # Subscribe button shape
    btn_w = 220
    btn_h = 45
    btn_x = (WIDTH - btn_w) // 2
    btn_y = cta_y + 60
    draw.rounded_rectangle(
        [(btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h)],
        radius=8,
        fill=(204, 0, 0),
    )
    font_btn = _get_font(22)
    btn_text = "SUBSCRIBE"
    bbox_btn = draw.textbbox((0, 0), btn_text, font=font_btn)
    btn_text_w = bbox_btn[2] - bbox_btn[0]
    draw.text(
        ((WIDTH - btn_text_w) // 2, btn_y + 10),
        btn_text,
        fill=(255, 255, 255),
        font=font_btn,
    )

    # Accent line
    line_w = 400
    line_x = (WIDTH - line_w) // 2
    draw.rectangle([(line_x, y + 75), (line_x + line_w, y + 78)], fill=(0, 180, 255))

    img.save(frame_path, "PNG")

    fps = 30
    _run_ffmpeg(
        [
            "-loop", "1",
            "-i", frame_path,
            "-t", str(duration),
            "-vf", (
                f"fade=in:st=0:d=0.8,fade=out:st={duration - 0.8}:d=0.8,"
                f"fps={fps}"
            ),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path,
        ],
        description="outro clip",
    )

    os.remove(frame_path)
    log.info("outro generated", path=output_path)
    return output_path
