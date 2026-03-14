"""Tests for the YouTube API client utilities."""

from packages.clients.youtube import _parse_duration


def test_parse_duration_full():
    assert _parse_duration("PT1H2M3S") == 3723


def test_parse_duration_minutes_seconds():
    assert _parse_duration("PT10M30S") == 630


def test_parse_duration_minutes_only():
    assert _parse_duration("PT5M") == 300


def test_parse_duration_seconds_only():
    assert _parse_duration("PT45S") == 45


def test_parse_duration_hours_only():
    assert _parse_duration("PT2H") == 7200


def test_parse_duration_zero():
    assert _parse_duration("PT0S") == 0


def test_parse_duration_invalid():
    assert _parse_duration("invalid") == 0
