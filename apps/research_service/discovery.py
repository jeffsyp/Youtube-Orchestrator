"""Discover candidate viral videos from YouTube for a given channel config."""

from datetime import datetime, timedelta, timezone

import structlog

from packages.clients.youtube import get_channel_subscribers, search_videos
from packages.schemas.channel import ChannelConfig
from packages.schemas.research import CandidateVideo

logger = structlog.get_logger()


def discover_candidates(
    config: ChannelConfig,
    days_back: int = 7,
    max_per_term: int = 10,
) -> list[CandidateVideo]:
    """Search YouTube for viral videos matching the channel's niche.

    Runs one search per search term in the channel config. Deduplicates by video_id.
    Enriches with subscriber counts to enable breakout scoring.

    Quota cost: ~(len(search_terms) * 100 + 2) units.
    """
    log = logger.bind(channel=config.name, niche=config.niche)
    log.info("starting discovery", search_terms=config.search_terms, days_back=days_back)

    published_after = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen_ids: set[str] = set()
    raw_videos: list[dict] = []

    for term in config.search_terms:
        results = search_videos(
            query=term,
            max_results=max_per_term,
            published_after=published_after,
            order="viewCount",
            video_duration="medium",
        )
        for video in results:
            if video["video_id"] not in seen_ids:
                seen_ids.add(video["video_id"])
                raw_videos.append(video)

    if not raw_videos:
        log.warning("no candidates found")
        return []

    log.info("raw videos collected", count=len(raw_videos))

    # Fetch subscriber counts for all unique channels
    channel_ids = list({v["channel_id"] for v in raw_videos})
    subs_map = {}
    # Batch in groups of 50
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        subs_map.update(get_channel_subscribers(batch))

    # Build CandidateVideo objects
    candidates = []
    for v in raw_videos:
        sub_count = subs_map.get(v["channel_id"], 0)
        published = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))

        candidates.append(CandidateVideo(
            video_id=v["video_id"],
            title=v["title"],
            channel_name=v["channel_name"],
            channel_subscribers=sub_count,
            views=v["views"],
            published_at=published,
            duration_seconds=v["duration_seconds"],
            tags=v["tags"][:20],  # Cap tags to avoid bloat
            breakout_score=0.0,
        ))

    log.info("candidates built", count=len(candidates))
    return candidates
