"""Tests for prompt generation — ensures prompts are well-formed."""

from packages.prompts.research import extract_templates_prompt, generate_ideas_prompt
from packages.prompts.writing import (
    build_outline_prompt,
    critique_script_prompt,
    revise_script_prompt,
    write_script_prompt,
)
from packages.prompts.media import (
    build_package_prompt,
    build_visual_plan_prompt,
    build_voice_plan_prompt,
)


def test_extract_templates_prompt():
    system, user = extract_templates_prompt("- video1\n- video2", "tech")
    assert "tech" in user
    assert "video1" in user
    assert "pattern_name" in user
    assert len(system) > 0


def test_generate_ideas_prompt():
    system, user = generate_ideas_prompt("templates", "candidates", "tech", "casual")
    assert "tech" in user
    assert "casual" in system
    assert "score" in user


def test_build_outline_prompt():
    idea = {"title": "Test", "hook": "Hook", "angle": "Angle", "target_length_seconds": 480}
    system, user = build_outline_prompt(idea, "tech")
    assert "Test" in user
    assert "480" in user


def test_write_script_prompt():
    outline = {
        "idea_title": "Test",
        "sections": ["Hook", "Body", "CTA"],
        "estimated_duration_seconds": 480,
        "key_points": ["point1"],
    }
    system, user = write_script_prompt(outline, "tech", "casual")
    assert "Test" in user
    assert "casual" in system
    assert "Hook" in user


def test_critique_script_prompt():
    system, user = critique_script_prompt("Script content here", "Test Title")
    assert "Test Title" in user
    assert "Script content here" in user
    assert "WEAKNESSES" in user


def test_revise_script_prompt():
    system, user = revise_script_prompt("Script", "Critique notes", "Title", "casual")
    assert "Script" in user
    assert "Critique notes" in user
    assert "casual" in system


def test_visual_plan_prompt():
    system, user = build_visual_plan_prompt("Script content", "Title")
    assert "Title" in user
    assert "scene_number" in user


def test_voice_plan_prompt():
    system, user = build_voice_plan_prompt("Script", "Title", "casual")
    assert "casual" in user
    assert "emphasis_points" in user


def test_package_prompt():
    system, user = build_package_prompt("Title", "Script", "tech")
    assert "Title" in user
    assert "tech" in user
    assert "tags" in user
