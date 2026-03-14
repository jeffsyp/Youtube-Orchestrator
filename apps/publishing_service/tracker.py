"""Performance tracking — fetches video metrics from YouTube after publishing.

Phase 5+: Captures views, CTR, and retention data for published videos.
Feeds back into the scoring model (Phase 6).
"""

import structlog

from packages.clients.youtube import get_video_details

logger = structlog.get_logger()


def get_video_performance(video_id: str) -> dict:
    """Fetch current performance metrics for a published video.

    Returns dict with views, likes, comments, and engagement rate.
    """
    log = logger.bind(video_id=video_id)
    log.info("fetching video performance")

    details = get_video_details([video_id])
    if not details:
        log.warning("video not found")
        return {"video_id": video_id, "error": "not found"}

    video = details[0]
    views = video["views"]
    likes = video["likes"]
    comments = video["comment_count"]

    engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0.0

    metrics = {
        "video_id": video_id,
        "views": views,
        "likes": likes,
        "comments": comments,
        "engagement_rate": round(engagement_rate, 2),
    }

    log.info("performance fetched", **metrics)
    return metrics
