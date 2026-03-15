"""Programmatic YouTube thumbnail generation.

Creates consistent branded thumbnails with:
- Gradient background in brand colors
- Bold title text (3-5 words max)
- Accent elements (underline, corner marks)
- 1280x720 resolution (YouTube standard)
"""

import os
import textwrap

import structlog
from PIL import Image, ImageDraw

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
