"""Tests for the research service — scoring logic and discovery integration."""

from datetime import datetime, timedelta, timezone

from packages.schemas.channel import ChannelConfig
from packages.schemas.research import CandidateVideo
from apps.research_service.scoring import score_candidates


def _make_candidate(
    video_id: str = "vid1",
    title: str = "Test Video",
    views: int = 100_000,
    subs: int = 10_000,
    days_ago: int = 1,
    tags: list[str] | None = None,
) -> CandidateVideo:
    return CandidateVideo(
        video_id=video_id,
        title=title,
        channel_name="TestChannel",
        channel_subscribers=subs,
        views=views,
        published_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        duration_seconds=600,
        tags=tags or [],
    )


def _make_config(**overrides) -> ChannelConfig:
    defaults = {
        "channel_id": 1,
        "name": "TestChannel",
        "niche": "tech",
        "search_terms": ["AI", "technology", "breakthrough"],
    }
    defaults.update(overrides)
    return ChannelConfig(**defaults)


def test_scoring_returns_sorted_by_score():
    candidates = [
        _make_candidate(video_id="low", views=1000, subs=10_000),
        _make_candidate(video_id="high", views=1_000_000, subs=10_000),
    ]
    config = _make_config()
    scored = score_candidates(candidates, config)
    assert scored[0].video_id == "high"
    assert scored[0].breakout_score > scored[1].breakout_score


def test_scoring_views_ratio_impact():
    """A video with high views-to-subs ratio should score higher."""
    c1 = _make_candidate(video_id="viral", views=500_000, subs=1_000, days_ago=1)
    c2 = _make_candidate(video_id="normal", views=500_000, subs=500_000, days_ago=1)
    scored = score_candidates([c1, c2], _make_config())
    assert scored[0].video_id == "viral"


def test_scoring_recency_impact():
    """A newer video should score higher than an older one, all else equal."""
    c1 = _make_candidate(video_id="new", days_ago=1)
    c2 = _make_candidate(video_id="old", days_ago=6)
    scored = score_candidates([c1, c2], _make_config())
    assert scored[0].video_id == "new"


def test_scoring_relevance_impact():
    """A video with matching tags should score higher."""
    c1 = _make_candidate(video_id="relevant", tags=["AI", "technology", "future"])
    c2 = _make_candidate(video_id="irrelevant", tags=["cooking", "recipes", "food"])
    scored = score_candidates([c1, c2], _make_config())
    assert scored[0].video_id == "relevant"


def test_scoring_zero_subscribers():
    """Handles channels with 0 or unknown subscribers gracefully."""
    c = _make_candidate(subs=0, views=50_000)
    scored = score_candidates([c], _make_config())
    assert scored[0].breakout_score > 0


def test_scoring_empty_candidates():
    scored = score_candidates([], _make_config())
    assert scored == []


def test_scoring_all_scores_non_negative():
    candidates = [
        _make_candidate(video_id=f"v{i}", views=i * 1000, subs=100, days_ago=i)
        for i in range(1, 8)
    ]
    scored = score_candidates(candidates, _make_config())
    for c in scored:
        assert c.breakout_score >= 0
