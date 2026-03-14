"""Generate visual slides for each shot in the visual plan.

Creates clean, modern slides with text overlays — the style used by most
faceless tech/explainer YouTube channels. Dark backgrounds with accent colors,
large readable text, minimal design.
"""

import hashlib
import os
import textwrap

import structlog
from PIL import Image, ImageDraw, ImageFont

logger = structlog.get_logger()

# Video dimensions (1080p)
WIDTH = 1920
HEIGHT = 1080

# Color palette — dark tech aesthetic
BACKGROUNDS = [
    (15, 15, 35),      # Deep navy
    (20, 10, 30),      # Dark purple
    (10, 25, 25),      # Dark teal
    (25, 15, 15),      # Dark red
    (15, 20, 30),      # Slate blue
    (20, 20, 20),      # Charcoal
]

ACCENT_COLORS = [
    (0, 200, 255),     # Cyan
    (255, 100, 100),   # Coral
    (100, 255, 150),   # Mint
    (255, 200, 50),    # Gold
    (180, 100, 255),   # Purple
    (255, 150, 50),    # Orange
]

TEXT_COLOR = (255, 255, 255)
SUBTITLE_COLOR = (200, 200, 200)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if system fonts aren't available."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_gradient_bg(draw: ImageDraw.Draw, bg_color: tuple[int, int, int]):
    """Draw a subtle radial gradient background."""
    for y in range(HEIGHT):
        for x_step in range(0, WIDTH, 4):
            # Subtle gradient from center
            dx = (x_step - WIDTH / 2) / WIDTH
            dy = (y - HEIGHT / 2) / HEIGHT
            dist = (dx * dx + dy * dy) ** 0.5
            factor = max(0.6, 1.0 - dist * 0.5)
            r = int(bg_color[0] * factor)
            g = int(bg_color[1] * factor)
            b = int(bg_color[2] * factor)
            draw.line([(x_step, y), (x_step + 3, y)], fill=(r, g, b))


def _draw_accent_bar(draw: ImageDraw.Draw, accent: tuple[int, int, int]):
    """Draw a thin accent bar at the bottom."""
    draw.rectangle([(0, HEIGHT - 6), (WIDTH, HEIGHT)], fill=accent)


def generate_slide(
    scene_number: int,
    description: str,
    text_overlay: str | None,
    visual_style: str,
    output_path: str,
) -> str:
    """Generate a single slide image for a shot.

    Args:
        scene_number: Shot number (used for color cycling).
        description: What the scene is about.
        text_overlay: Key text to show on screen (if any).
        visual_style: Style hint (used for layout decisions).
        output_path: Where to save the PNG.

    Returns:
        The output file path.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    # Pick colors based on scene number
    bg = BACKGROUNDS[scene_number % len(BACKGROUNDS)]
    accent = ACCENT_COLORS[scene_number % len(ACCENT_COLORS)]

    # Background
    _draw_gradient_bg(draw, bg)
    _draw_accent_bar(draw, accent)

    # Main text (text_overlay or key phrase from description)
    main_text = text_overlay or _extract_key_phrase(description)
    if main_text:
        _draw_main_text(draw, main_text, accent)

    # Subtitle description at bottom
    if description and not text_overlay:
        _draw_description(draw, description)

    # Scene indicator dot
    _draw_scene_indicator(draw, scene_number, accent)

    img.save(output_path, "PNG")
    return output_path


def _extract_key_phrase(description: str) -> str:
    """Extract the most important phrase from a shot description."""
    # Take the first sentence or first 6 words
    sentences = description.split(".")
    first = sentences[0].strip()
    words = first.split()
    if len(words) > 8:
        return " ".join(words[:8])
    return first


def _draw_main_text(draw: ImageDraw.Draw, text: str, accent: tuple[int, int, int]):
    """Draw the main large text in the center of the slide."""
    font_large = _get_font(72)

    # Wrap text to fit
    wrapped = textwrap.fill(text, width=22)
    lines = wrapped.split("\n")

    # Calculate total height
    line_height = 90
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2 - 30

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_large)
        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2
        y = start_y + i * line_height

        # Draw text shadow
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0), font=font_large)
        # Draw main text
        draw.text((x, y), line, fill=TEXT_COLOR, font=font_large)

    # Draw accent underline below text
    underline_y = start_y + total_height + 15
    underline_width = min(400, WIDTH // 3)
    underline_x = (WIDTH - underline_width) // 2
    draw.rectangle(
        [(underline_x, underline_y), (underline_x + underline_width, underline_y + 4)],
        fill=accent,
    )


def _draw_description(draw: ImageDraw.Draw, description: str):
    """Draw a smaller description near the bottom."""
    font_small = _get_font(28)
    wrapped = textwrap.fill(description, width=60)
    lines = wrapped.split("\n")[:3]  # Max 3 lines

    start_y = HEIGHT - 120
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_small)
        text_width = bbox[2] - bbox[0]
        x = (WIDTH - text_width) // 2
        y = start_y + i * 35
        draw.text((x, y), line, fill=SUBTITLE_COLOR, font=font_small)


def _draw_scene_indicator(draw: ImageDraw.Draw, scene_number: int, accent: tuple[int, int, int]):
    """Draw a small scene number indicator in the top-right."""
    font = _get_font(20)
    text = f"SCENE {scene_number}"
    draw.text((WIDTH - 150, 30), text, fill=accent, font=font)


def generate_dalle_slide(
    description: str,
    text_overlay: str | None,
    output_path: str,
    niche: str = "technology",
) -> str:
    """Generate a scene image using DALL-E 3.

    Builds a cinematic prompt from the shot description.
    """
    from packages.clients.dalle import generate_image

    # Build a cinematic prompt for DALL-E
    base = description.strip().rstrip(".")
    prompt = (
        f"Cinematic wide-angle shot for a YouTube tech explainer video: {base}. "
        f"Modern, clean aesthetic with dark background and subtle blue/cyan accent lighting. "
        f"Photorealistic, high production value, no text or watermarks."
    )

    return generate_image(prompt=prompt, output_path=output_path, size="1792x1024")


def generate_all_slides(shots: list[dict], output_dir: str) -> list[str]:
    """Generate slides for all shots using DALL-E 3.

    Args:
        shots: List of shot dicts from VisualPlan.
        output_dir: Directory to save slides.

    Returns:
        List of file paths to generated slides.
    """
    os.makedirs(output_dir, exist_ok=True)
    log = logger.bind(service="rendering", action="generate_slides")
    log.info("generating slides with dall-e", count=len(shots))

    paths = []
    for shot in shots:
        scene_num = shot.get("scene_number", len(paths) + 1)
        output_path = os.path.join(output_dir, f"slide_{scene_num:03d}.png")

        generate_dalle_slide(
            description=shot.get("description", ""),
            text_overlay=shot.get("text_overlay"),
            output_path=output_path,
        )
        paths.append(output_path)

    log.info("slides generated", count=len(paths))
    return paths
