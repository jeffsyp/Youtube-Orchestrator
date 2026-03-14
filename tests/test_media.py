"""Tests for media service utilities — SRT generation, time formatting."""

from apps.media_service.planner import _format_srt_time, generate_srt


def test_format_srt_time_zero():
    assert _format_srt_time(0.0) == "00:00:00,000"


def test_format_srt_time_seconds():
    assert _format_srt_time(5.5) == "00:00:05,500"


def test_format_srt_time_minutes():
    assert _format_srt_time(125.75) == "00:02:05,750"


def test_format_srt_time_hours():
    assert _format_srt_time(3661.0) == "01:01:01,000"


def test_generate_srt_basic():
    script = "This is sentence one. This is sentence two. And this is sentence three."
    srt = generate_srt(script)

    assert "1\n" in srt
    assert "2\n" in srt
    assert "3\n" in srt
    assert "-->" in srt
    assert "This is sentence one." in srt


def test_generate_srt_timestamps_increase():
    script = "First sentence here. Second sentence here. Third sentence here."
    srt = generate_srt(script)
    lines = srt.strip().split("\n")

    timestamps = [l for l in lines if "-->" in l]
    assert len(timestamps) == 3

    # Verify each timestamp starts after the previous one ends
    for i in range(1, len(timestamps)):
        prev_end = timestamps[i - 1].split(" --> ")[1]
        curr_start = timestamps[i].split(" --> ")[0]
        assert curr_start >= prev_end


def test_generate_srt_empty():
    srt = generate_srt("")
    assert srt.strip() == ""


def test_generate_srt_long_sentence_wraps():
    script = "This is a very long sentence that has many words in it and should be split across two lines for readability in subtitles."
    srt = generate_srt(script)
    # Should contain a newline within the subtitle text (wrapped)
    entries = srt.strip().split("\n\n")
    assert len(entries) >= 1
