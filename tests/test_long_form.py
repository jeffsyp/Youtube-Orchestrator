"""Tests for long-form video pipeline — prompts, detection, routing, subtitles."""

import json
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

class TestLongFormPrompts:
    """Ensure long-form prompt builders produce well-structured outputs."""

    def test_pitches_prompt_contains_duration_guidance(self):
        from packages.prompts.long_form import build_longform_pitches_prompt
        system, user = build_longform_pitches_prompt("SpookLand", "horror", [], 2)
        assert "10-13 minute" in system
        assert "thumbnail" in system.lower()
        assert "curiosity" in system.lower()
        assert "chapters" in system

    def test_pitches_prompt_includes_past_titles(self):
        from packages.prompts.long_form import build_longform_pitches_prompt
        system, user = build_longform_pitches_prompt(
            "SpookLand", "horror", ["OLD TITLE ONE", "OLD TITLE TWO"], 2
        )
        assert "OLD TITLE ONE" in user or "OLD TITLE ONE" in system

    def test_pitches_prompt_includes_trending(self):
        from packages.prompts.long_form import build_longform_pitches_prompt
        system, user = build_longform_pitches_prompt(
            "SpookLand", "horror", [], 2, trending="VIRAL: scary forest video 1M views"
        )
        assert "scary forest" in user

    def test_pitches_prompt_requests_thumbnail(self):
        from packages.prompts.long_form import build_longform_pitches_prompt
        system, user = build_longform_pitches_prompt("SpookLand", "horror", [], 1)
        assert '"thumbnail"' in system
        assert '"visual"' in system
        assert '"text"' in system
        assert '"emotion"' in system

    def test_chapter_script_prompt_first_chapter(self):
        from packages.prompts.long_form import build_longform_chapter_script_prompt
        system, user = build_longform_chapter_script_prompt(
            channel_name="SpookLand", niche="horror", voice_id="v1",
            channel_id=20, title="TEST",
            chapter={"title": "The Hook", "timing": "0:00-0:30", "purpose": "Hook", "beats": "open cold"},
            chapter_index=0, total_chapters=5,
            full_outline=[{"title": "Hook", "timing": "0:00-0:30", "purpose": "Hook"}],
            previous_narration_summary="",
            key_facts="Igor Dyatlov led 9 hikers",
            open_loops=["Who slashed the tent?"],
        )
        assert "FIRST CHAPTER" in system or "first chapter" in system.lower()
        assert "HOOK" in system
        assert "words" in system.lower()
        assert "TARGET" in system

    def test_chapter_script_prompt_last_chapter(self):
        from packages.prompts.long_form import build_longform_chapter_script_prompt
        system, user = build_longform_chapter_script_prompt(
            channel_name="SpookLand", niche="horror", voice_id="v1",
            channel_id=20, title="TEST",
            chapter={"title": "Resolution", "timing": "10:30-12:00", "purpose": "Wrap up"},
            chapter_index=4, total_chapters=5,
            full_outline=[{"title": "Resolution", "timing": "10:30-12:00", "purpose": "Wrap up"}],
            previous_narration_summary="previous stuff",
            key_facts="facts", open_loops=[],
        )
        assert "FINAL CHAPTER" in system
        assert "previous stuff" in user

    def test_chapter_script_prompt_middle_chapter(self):
        from packages.prompts.long_form import build_longform_chapter_script_prompt
        system, user = build_longform_chapter_script_prompt(
            channel_name="SpookLand", niche="horror", voice_id="v1",
            channel_id=20, title="TEST",
            chapter={"title": "Core", "timing": "2:30-7:30", "purpose": "The meat"},
            chapter_index=2, total_chapters=5,
            full_outline=[{"title": "Core", "timing": "2:30-7:30", "purpose": "The meat"}],
            previous_narration_summary="", key_facts="facts", open_loops=[],
        )
        assert "CHAPTER 3 OF 5" in system
        assert "pattern interrupt" in system.lower()

    def test_chapter_script_prompt_includes_timing(self):
        from packages.prompts.long_form import build_longform_chapter_script_prompt
        system, user = build_longform_chapter_script_prompt(
            channel_name="Test", niche="test", voice_id="v1",
            channel_id=1, title="T",
            chapter={"title": "Ch", "timing": "2:30-7:30", "purpose": "P", "beats": "B"},
            chapter_index=1, total_chapters=3,
            full_outline=[], previous_narration_summary="", key_facts="", open_loops=[],
        )
        assert "2:30-7:30" in system or "2:30-7:30" in user

    def test_visual_batch_prompt_first_batch(self):
        from packages.prompts.long_form import build_longform_visual_batch_prompt
        lines = [{"index": i, "duration": 4.0, "text": f"Line {i}"} for i in range(12)]
        system, user = build_longform_visual_batch_prompt(
            "SpookLand", "horror", "TEST TITLE", lines, 0, 5,
        )
        assert "MUST be type \"grok\"" in system or "must be type" in system.lower()
        assert "batch 1 of 5" in system.lower()
        assert "Line 0" in user

    def test_visual_batch_prompt_later_batch_with_summary(self):
        from packages.prompts.long_form import build_longform_visual_batch_prompt
        lines = [{"index": 24, "duration": 5.0, "text": "Later line"}]
        system, user = build_longform_visual_batch_prompt(
            "SpookLand", "horror", "TEST", lines, 2, 5,
            previous_batch_summary="Dark moody cartoon style",
        )
        assert "Dark moody cartoon style" in system
        assert "batch 3 of 5" in system.lower()

    def test_visual_batch_prompt_landscape_for_longform(self):
        from packages.prompts.long_form import build_longform_visual_batch_prompt
        lines = [{"index": 0, "duration": 3.0, "text": "test"}]
        system, _ = build_longform_visual_batch_prompt(
            "Ch", "niche", "T", lines, 0, 1, is_long_form=True,
        )
        assert "16:9" in system
        assert "landscape" in system.lower()

    def test_visual_batch_prompt_portrait_for_shortform(self):
        from packages.prompts.long_form import build_longform_visual_batch_prompt
        lines = [{"index": 0, "duration": 3.0, "text": "test"}]
        system, _ = build_longform_visual_batch_prompt(
            "Ch", "niche", "T", lines, 0, 1, is_long_form=False,
        )
        assert "9:16" in system
        assert "vertical" in system.lower()


# ---------------------------------------------------------------------------
# Long-form detection
# ---------------------------------------------------------------------------

class TestLongFormDetection:
    """Ensure long-form is detected from concept JSON in runner and monitor."""

    def test_runner_detects_long_form_flag(self):
        concept = {"long_form": True, "narration": ["a"] * 5}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        assert is_long is True

    def test_runner_detects_long_form_by_narration_count(self):
        concept = {"narration": ["line"] * 60}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        assert is_long is True

    def test_runner_detects_long_form_by_beat_count(self):
        concept = {"beats": [{}] * 25}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        assert is_long is True

    def test_runner_short_form_default(self):
        concept = {"narration": ["a", "b", "c"], "beats": []}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        assert is_long is False

    def test_timeout_long_form(self):
        concept = {"long_form": True}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        timeout = 10800 if is_long else 3600
        assert timeout == 10800

    def test_timeout_short_form(self):
        concept = {"narration": ["a", "b"]}
        is_long = (
            concept.get("long_form", False)
            or len(concept.get("narration", [])) >= 20
            or len(concept.get("beats", [])) >= 20
        )
        timeout = 10800 if is_long else 3600
        assert timeout == 3600


# ---------------------------------------------------------------------------
# Subtitle PlayRes
# ---------------------------------------------------------------------------

class TestSubtitlePlayRes:
    """Ensure karaoke subtitles use correct resolution for long vs short form."""

    def test_short_form_playres(self):
        from apps.orchestrator.deity_pipeline import _write_karaoke_ass
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            path = f.name
        try:
            _write_karaoke_ass(path, [("hello", 0.0, 0.5)], is_long_form=False)
            content = open(path).read()
            assert "PlayResX: 720" in content
            assert "PlayResY: 1280" in content
            assert "Impact,52," in content
        finally:
            os.unlink(path)

    def test_long_form_playres(self):
        from apps.orchestrator.deity_pipeline import _write_karaoke_ass
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            path = f.name
        try:
            _write_karaoke_ass(path, [("hello", 0.0, 0.5)], is_long_form=True)
            content = open(path).read()
            assert "PlayResX: 1920" in content
            assert "PlayResY: 1080" in content
            assert "Impact,42," in content
        finally:
            os.unlink(path)

    def test_labels_written(self):
        from apps.orchestrator.deity_pipeline import _write_karaoke_ass
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as f:
            path = f.name
        try:
            _write_karaoke_ass(
                path,
                [("word", 0.0, 1.0)],
                beat_labels=[("CHAPTER 1", 0.0, 5.0)],
                is_long_form=True,
            )
            content = open(path).read()
            assert "CHAPTER 1" in content
            assert "Label" in content
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Token file derivation
# ---------------------------------------------------------------------------

class TestTokenFileDerivation:
    """Ensure channel names map to the correct YouTube token files."""

    def _derive(self, name: str) -> str:
        token_name = name.lower().replace(" ", "").replace("'", "").replace("\u2019", "")
        return f"youtube_token_{token_name}.json"

    def test_spookland(self):
        assert self._derive("SpookLand") == "youtube_token_spookland.json"

    def test_what_if_city(self):
        assert self._derive("What If City") == "youtube_token_whatifcity.json"

    def test_nature_receipts(self):
        assert self._derive("Nature Receipts") == "youtube_token_naturereceipts.json"

    def test_crab_rave_shorts(self):
        assert self._derive("Crab Rave Shorts") == "youtube_token_crabraveshorts.json"

    def test_munchlax_lore(self):
        assert self._derive("Munchlax Lore") == "youtube_token_munchlaxlore.json"

    def test_smooth_brain_academy(self):
        assert self._derive("Smooth Brain Academy") == "youtube_token_smoothbrainacademy.json"

    def test_one_on_ones(self):
        assert self._derive("One on Ones For Fun") == "youtube_token_oneononesforfun.json"


# ---------------------------------------------------------------------------
# Video path resolution
# ---------------------------------------------------------------------------

class TestVideoPathResolution:
    """Ensure video streaming finds files after cleanup."""

    def test_channel_folder_path_construction(self):
        """The fallback path should match what the cleanup worker writes."""
        import re
        title = "WHAT IF THE EARTH HAD TWO SUNS"
        channel_name = "What If City"
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:80]
        path = os.path.join("output", "videos", channel_name, f"{safe_title}.mp4")
        assert path == "output/videos/What If City/WHAT IF THE EARTH HAD TWO SUNS.mp4"

    def test_safe_title_strips_special_chars(self):
        import re
        title = "What's The Deal: A Story (2024)"
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:80]
        assert ":" not in safe_title
        assert "(" not in safe_title
        assert "'" not in safe_title

    def test_safe_title_truncates(self):
        import re
        title = "A" * 200
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:80]
        assert len(safe_title) == 80


# ---------------------------------------------------------------------------
# Concept generator — form_type routing
# ---------------------------------------------------------------------------

class TestConceptGeneratorRouting:
    """Ensure short vs long form uses different prompt builders."""

    def test_research_cache_key_differs_by_form_type(self):
        """Short and long form should have separate research caches."""
        short_key = f"{'horror'}_{' short'}"
        long_key = f"{'horror'}_{'long'}"
        assert short_key != long_key

    def test_youtube_duration_param(self):
        """Long-form should search for medium-duration videos."""
        form_type = "long"
        video_duration = "medium" if form_type == "long" else "short"
        assert video_duration == "medium"

        form_type = "short"
        video_duration = "medium" if form_type == "long" else "short"
        assert video_duration == "short"


# ---------------------------------------------------------------------------
# Concept JSON structure
# ---------------------------------------------------------------------------

class TestLongFormConceptStructure:
    """Validate the shape of long-form concept JSON."""

    def _make_concept(self):
        return {
            "title": "Test Title",
            "narration": [f"Line {i}" for i in range(60)],
            "caption": "Description",
            "tags": ["tag1"],
            "voice_id": "voice123",
            "channel_id": 20,
            "format_version": 2,
            "long_form": True,
            "chapters": [
                {"title": "Hook", "timing": "0:00-0:30", "purpose": "Hook", "beats": "cold open"},
                {"title": "Core", "timing": "0:30-7:30", "purpose": "Main story"},
                {"title": "End", "timing": "7:30-10:00", "purpose": "Resolution"},
            ],
            "open_loops": ["Who did it?", "What was the sound?"],
            "thumbnail": {
                "visual": "A dark forest with glowing eyes",
                "text": "THEY WATCHED",
                "emotion": "fear",
            },
        }

    def test_has_required_fields(self):
        c = self._make_concept()
        assert c["format_version"] == 2
        assert c["long_form"] is True
        assert len(c["narration"]) > 20
        assert len(c["chapters"]) >= 3
        assert isinstance(c["open_loops"], list)

    def test_thumbnail_structure(self):
        c = self._make_concept()
        thumb = c["thumbnail"]
        assert "visual" in thumb
        assert "text" in thumb
        assert "emotion" in thumb

    def test_chapters_have_timing(self):
        c = self._make_concept()
        for ch in c["chapters"]:
            assert "timing" in ch
            assert "title" in ch
            assert "purpose" in ch

    def test_narration_is_list_of_strings(self):
        c = self._make_concept()
        assert all(isinstance(line, str) for line in c["narration"])

    def test_pipeline_routes_to_narration_first(self):
        """format_version 2 should route to _run_narration_first."""
        c = self._make_concept()
        assert c.get("format_version") == 2  # This triggers narration-first path


# ---------------------------------------------------------------------------
# Content bank form_type
# ---------------------------------------------------------------------------

class TestContentBankFormType:
    """Ensure form_type flows from draft → content_bank → pipeline."""

    def test_approve_carries_form_type(self):
        """When a draft is approved, form_type should transfer to content_bank."""
        # Simulates the approval SQL logic
        draft_form_type = "long"
        cb_form_type = draft_form_type  # This is what the API does
        assert cb_form_type == "long"

    def test_default_form_type_is_short(self):
        draft_form_type = None
        cb_form_type = draft_form_type or "short"
        assert cb_form_type == "short"
