"""YouTube Data API v3 client for discovering candidate videos."""

import os
import re
from datetime import datetime, timezone

import structlog
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

logger = structlog.get_logger()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def _get_client():
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY not set in environment")
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def _parse_duration(duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def search_videos(
    query: str,
    max_results: int = 10,
    published_after: datetime | None = None,
    order: str = "viewCount",
    video_duration: str = "medium",
) -> list[dict]:
    """Search YouTube for videos matching a query.

    Args:
        query: Search terms.
        max_results: Number of results (max 50). Each call costs 100 quota units.
        published_after: Only return videos published after this datetime.
        order: Sort order — "viewCount", "date", "relevance", "rating".
        video_duration: "short" (<4min), "medium" (4-20min), "long" (>20min), "any".

    Returns:
        List of dicts with video metadata.
    """
    client = _get_client()
    log = logger.bind(query=query, max_results=max_results, order=order)
    log.info("searching youtube")

    search_params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": min(max_results, 50),
        "order": order,
        "videoDuration": video_duration,
    }
    if published_after:
        search_params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")

    response = client.search().list(**search_params).execute()
    video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

    if not video_ids:
        log.info("no results found")
        return []

    log.info("search returned results", count=len(video_ids))
    return get_video_details(video_ids)


def get_video_details(video_ids: list[str]) -> list[dict]:
    """Fetch detailed metadata for a list of video IDs.

    Costs 1 quota unit per call (up to 50 IDs per call).
    """
    client = _get_client()

    videos_response = client.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(video_ids),
    ).execute()

    results = []
    for item in videos_response.get("items", []):
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})

        channel_id = snippet["channelId"]

        results.append({
            "video_id": item["id"],
            "title": snippet["title"],
            "channel_name": snippet["channelTitle"],
            "channel_id": channel_id,
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "published_at": snippet["publishedAt"],
            "duration_seconds": _parse_duration(content.get("duration", "PT0S")),
            "tags": snippet.get("tags", []),
            "description": snippet.get("description", ""),
        })

    return results


def get_channel_subscribers(channel_ids: list[str]) -> dict[str, int]:
    """Fetch subscriber counts for a list of channel IDs.

    Costs 1 quota unit per call (up to 50 IDs per call).
    """
    client = _get_client()

    response = client.channels().list(
        part="statistics",
        id=",".join(channel_ids[:50]),
    ).execute()

    result = {}
    for item in response.get("items", []):
        sub_count = int(item["statistics"].get("subscriberCount", 0))
        result[item["id"]] = sub_count

    return result
