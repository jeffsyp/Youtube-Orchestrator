"""Shared font loading for all rendering modules.

Prefers Inter (bundled in assets/fonts/) over system fallbacks.
"""

import os

from PIL import ImageFont

# Project root → assets/fonts/
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts")

FONT_PATHS = [
    os.path.join(_ASSETS_DIR, "Inter-Bold.ttf"),
    os.path.join(_ASSETS_DIR, "Inter-ExtraBold.ttf"),
    os.path.join(_ASSETS_DIR, "Inter-SemiBold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

# For FFmpeg drawtext filters
FONT_PATH_STR: str = ""
for _p in FONT_PATHS:
    if os.path.exists(_p):
        FONT_PATH_STR = _p
        break


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get the best available font at the given size."""
    for path in FONT_PATHS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
