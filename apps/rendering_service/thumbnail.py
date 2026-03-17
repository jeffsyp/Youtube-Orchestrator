"""Programmatic YouTube thumbnail generation.

Creates consistent branded thumbnails with:
- Gradient background in brand colors
- Bold title text (3-5 words max)
- Accent elements (underline, corner marks)
- 1280x720 resolution (YouTube standard)

Also provides Shorts thumbnail generation:
- Extracts a visually interesting frame from rendered video
- Adds subtle title text overlay
- Outputs 1280x720 PNG
"""

import os
import subprocess
import textwrap

import structlog
from PIL import Image, ImageDraw, ImageFilter

from apps.rendering_service.fonts import get_font

logger = structlog.get_logger()

WIDTH = 1280
HEIGHT = 720

# Brand palette
BG_COLORS = [
    ((8, 8, 30), (25, 15, 50)),      # Dark navy → deep purple
    ((10, 20, 35), (5, 10, 25)),      # Dark blue → deeper blue
    ((15, 8, 25), (30, 10, 40)),      # Dark purple → medium purple
    ((5, 15, 20), (10, 30, 35)),      # Dark teal → medium teal
]

ACCENT_COLOR = (0, 180, 255)  # Cyan


def generate_thumbnail(
    title: str,
    output_path: str,
    accent_color: tuple[int, int, int] = ACCENT_COLOR,
    bg_index: int = 0,
) -> str:
    """Generate a branded YouTube thumbnail.

    Args:
        title: Short title text (3-5 words ideal).
        output_path: Where to save the PNG.
        accent_color: Accent color for decorative elements.
        bg_index: Background gradient index (0-3).

    Returns:
        The output file path.
    """
    log = logger.bind(service="thumbnail")
    log.info("generating thumbnail", title=title)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    bg_start, bg_end = BG_COLORS[bg_index % len(BG_COLORS)]

    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    # Draw gradient background
    for y in range(HEIGHT):
        progress = y / HEIGHT
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * progress)
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * progress)
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * progress)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Corner accent marks (top-left and bottom-right)
    mark_len = 60
    mark_w = 4
    # Top-left
    draw.rectangle([(40, 40), (40 + mark_len, 40 + mark_w)], fill=accent_color)
    draw.rectangle([(40, 40), (40 + mark_w, 40 + mark_len)], fill=accent_color)
    # Bottom-right
    draw.rectangle([(WIDTH - 40 - mark_len, HEIGHT - 40 - mark_w), (WIDTH - 40, HEIGHT - 40)], fill=accent_color)
    draw.rectangle([(WIDTH - 40 - mark_w, HEIGHT - 40 - mark_len), (WIDTH - 40, HEIGHT - 40)], fill=accent_color)

    # Title text — bold, large, wrapped
    # Shorten to max 5 words for thumbnail
    words = title.split()
    if len(words) > 6:
        title = " ".join(words[:6])

    font_size = 72
    if len(title) > 25:
        font_size = 60
    if len(title) > 40:
        font_size = 48

    font = get_font(font_size)
    wrapped = textwrap.fill(title.upper(), width=16)
    lines = wrapped.split("\n")

    line_height = int(font_size * 1.25)
    total_h = len(lines) * line_height
    start_y = (HEIGHT - total_h) // 2

    max_w = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        max_w = max(max_w, text_w)
        x = (WIDTH - text_w) // 2
        y = start_y + i * line_height

        # Black outline (4 directions for thickness)
        for dx, dy in [(-3, -3), (-3, 3), (3, -3), (3, 3), (-3, 0), (3, 0), (0, -3), (0, 3)]:
            draw.text((x + dx, y + dy), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(255, 255, 255), font=font)

    # Accent underline below text
    underline_w = min(max_w + 40, WIDTH - 120)
    underline_x = (WIDTH - underline_w) // 2
    underline_y = start_y + total_h + 15
    draw.rectangle(
        [(underline_x, underline_y), (underline_x + underline_w, underline_y + 5)],
        fill=accent_color,
    )

    img.save(output_path, "PNG", quality=95)
    log.info("thumbnail generated", path=output_path, size=f"{WIDTH}x{HEIGHT}")
    return output_path


def generate_shorts_thumbnail(
    video_path: str,
    title: str,
    output_path: str,
) -> str:
    """Generate a thumbnail for YouTube Shorts from a rendered video.

    Extracts a frame from 2/3 through the video (typically the most visually
    interesting part), scales it to 1280x720, and adds a subtle title overlay.

    Args:
        video_path: Path to the rendered Short MP4.
        title: Video title for the text overlay.
        output_path: Where to save the PNG thumbnail.

    Returns:
        The output file path.
    """
    log = logger.bind(service="thumbnail", variant="shorts")
    log.info("generating shorts thumbnail", title=title, video=video_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Get video duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    duration = float(probe.stdout.strip())

    # Extract frame at 2/3 through the video
    timestamp = duration * 2 / 3
    frame_path = output_path + ".frame.png"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        frame_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Frame extraction failed: {result.stderr[-300:]}")

    # Open extracted frame and resize to thumbnail dimensions (1280x720)
    img = Image.open(frame_path)
    img = img.convert("RGB")

    # Scale to cover 1280x720, then center-crop
    src_w, src_h = img.size
    scale = max(WIDTH / src_w, HEIGHT / src_h)
    scaled_w = int(src_w * scale)
    scaled_h = int(src_h * scale)
    img = img.resize((scaled_w, scaled_h), Image.LANCZOS)

    # Center crop to exact 1280x720
    left = (scaled_w - WIDTH) // 2
    top = (scaled_h - HEIGHT) // 2
    img = img.crop((left, top, left + WIDTH, top + HEIGHT))

    # Add subtle text overlay with the title
    draw = ImageDraw.Draw(img)

    # Shorten title if needed
    words = title.split()
    if len(words) > 8:
        title = " ".join(words[:8])

    font_size = 56
    if len(title) > 30:
        font_size = 44
    if len(title) > 50:
        font_size = 36

    font = get_font(font_size)
    wrapped = textwrap.fill(title.upper(), width=22)
    lines = wrapped.split("\n")

    line_height = int(font_size * 1.3)
    total_h = len(lines) * line_height
    # Position text in lower third
    start_y = HEIGHT - total_h - 50

    # Semi-transparent dark gradient bar behind text for readability
    gradient_top = start_y - 30
    for y in range(max(0, gradient_top), HEIGHT):
        progress = (y - gradient_top) / (HEIGHT - gradient_top)
        alpha = int(160 * progress)
        draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha) if img.mode == "RGBA" else (
            max(0, int(255 * (1 - progress * 0.65))),) * 3)

    # Re-overlay gradient as a separate RGBA layer for proper blending
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(max(0, gradient_top), HEIGHT):
        progress = (y - gradient_top) / max(1, HEIGHT - gradient_top)
        alpha = int(170 * progress)
        overlay_draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = start_y + i * line_height

        # Black outline for contrast
        for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((x + dx, y + dy), line, fill=(0, 0, 0, 255), font=font)
        draw.text((x, y), line, fill=(255, 255, 255, 255), font=font)

    img = img.convert("RGB")
    img.save(output_path, "PNG", quality=95)

    # Cleanup temp frame
    if os.path.exists(frame_path):
        os.remove(frame_path)

    log.info("shorts thumbnail generated", path=output_path, size=f"{WIDTH}x{HEIGHT}")
    return output_path
