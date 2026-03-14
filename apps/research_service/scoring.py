"""Score candidate videos for breakout potential."""

from datetime import datetime, timezone

import structlog

from packages.schemas.channel import ChannelConfig
from packages.schemas.research import CandidateVideo

logger = structlog.get_logger()


def score_candidates(
    candidates: list[CandidateVideo],
    config: ChannelConfig,
) -> list[CandidateVideo]:
    """Score each candidate on breakout potential and return sorted by score (descending).

    Scoring formula (weights from channel config):
        - views_ratio: views / channel_subscribers (capped at 100)
        - recency: days since published (newer = higher, max 7 days back)
        - topic_relevance: keyword overlap between video tags and channel search terms

    Each component is normalized to 0-100, then weighted.
    """
    weights = config.scoring_weights
    w_ratio = weights.get("views_ratio", 0.4)
    w_recency = weights.get("recency", 0.3)
    w_relevance = weights.get("topic_relevance", 0.3)

    search_terms_lower = {term.lower() for term in config.search_terms}
    # Also split multi-word terms into individual words for matching
    search_words = set()
    for term in search_terms_lower:
        search_words.update(term.split())

    now = datetime.now(timezone.utc)
    scored = []

    for c in candidates:
        # Views ratio score: views per subscriber, capped at 100x
        if c.channel_subscribers > 0:
            ratio = min(c.views / c.channel_subscribers, 100.0)
        else:
            ratio = min(c.views / 1000.0, 100.0)  # Unknown subs, use views/1000
        ratio_score = ratio  # Already 0-100 range

        # Recency score: 0-100, where today=100, 7 days ago=0
        days_old = (now - c.published_at).total_seconds() / 86400
        recency_score = max(0.0, min(100.0, 100.0 - (days_old * (100.0 / 7.0))))

        # Topic relevance score: keyword overlap
        video_words = {tag.lower() for tag in c.tags}
        video_words.update(word.lower() for word in c.title.split())
        if search_words:
            overlap = len(video_words & search_words)
            relevance_score = min(100.0, overlap * 25.0)  # 4+ matches = 100
        else:
            relevance_score = 50.0  # Neutral if no search terms

        final_score = round(
            ratio_score * w_ratio + recency_score * w_recency + relevance_score * w_relevance,
            1,
        )

        scored.append(c.model_copy(update={"breakout_score": final_score}))

    scored.sort(key=lambda c: c.breakout_score, reverse=True)

    log = logger.bind(channel=config.name)
    log.info(
        "scoring complete",
        count=len(scored),
        top_score=scored[0].breakout_score if scored else 0,
        top_title=scored[0].title if scored else "",
    )
    return scored
