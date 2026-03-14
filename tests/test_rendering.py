"""Tests for the rendering service — Pillow slide generation (used as fallback reference)."""

import os
import tempfile

from apps.rendering_service.image_gen import generate_slide


def test_generate_slide_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_slide.png")
        result = generate_slide(
            scene_number=1,
            description="A test slide with some description",
            text_overlay="TEST TEXT",
            visual_style="motion graphics",
            output_path=path,
        )
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0


def test_generate_slide_no_overlay():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_slide.png")
        result = generate_slide(
            scene_number=2,
            description="Description only, no text overlay",
            text_overlay=None,
            visual_style="b-roll",
            output_path=path,
        )
        assert os.path.exists(result)
