"""Reddit client for sourcing viral sports clips from subreddits."""

import os

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

# Domains that typically host video content
VIDEO_DOMAINS = {
    "youtube.com", "youtu.be", "v.redd.it", "streamable.com",
    "gfycat.com", "clips.twitch.tv", "twitter.com", "x.com",
    "reddit.com",  # reddit-hosted video
}


def _get_client():
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set")

    import praw

    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent="whistle-room-bot/1.0",
    )


def _is_video_post(post) -> bool:
    """Check if a Reddit post likely contains video content."""
    if post.is_video:
        return True
    if hasattr(post, "domain") and any(d in post.domain for d in VIDEO_DOMAINS):
        return True
    if hasattr(post, "url") and any(d in post.url for d in VIDEO_DOMAINS):
        return True
    return False


def search_top_clips(
    subreddits: list[str],
    time_filter: str = "week",
    limit: int = 20,
) -> list[dict]:
    """Search subreddits for top video clips.

    Args:
        subreddits: List of subreddit names to search.
        time_filter: Time window — "hour", "day", "week", "month", "year", "all".
        limit: Max clips to return across all subreddits.

    Returns:
        List of dicts with title, url, score, subreddit, permalink.
    """
    log = logger.bind(subreddits=subreddits, time_filter=time_filter)
    reddit = _get_client()

    clips = []
    per_sub = max(limit // len(subreddits), 10)

    for sub_name in subreddits:
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.top(time_filter=time_filter, limit=per_sub * 3):
                if not _is_video_post(post):
                    continue

                # Get the actual video URL
                url = post.url
                if post.is_video and hasattr(post, "media") and post.media:
                    reddit_video = post.media.get("reddit_video", {})
                    url = reddit_video.get("fallback_url", post.url)

                clips.append({
                    "title": post.title,
                    "url": url,
                    "score": post.score,
                    "subreddit": sub_name,
                    "permalink": f"https://reddit.com{post.permalink}",
                    "source": "reddit",
                })

                if len(clips) >= limit:
                    break
        except Exception as e:
            log.warning("failed to search subreddit", subreddit=sub_name, error=str(e))
            continue

    # Sort by score descending
    clips.sort(key=lambda c: c["score"], reverse=True)
    clips = clips[:limit]

    log.info("found clips", count=len(clips))
    return clips
