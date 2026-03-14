"""Pexels API client for downloading free stock video clips."""

import os

import requests
import structlog
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
BASE_URL = "https://api.pexels.com/videos"


def _headers() -> dict:
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY not set in environment")
    return {"Authorization": PEXELS_API_KEY}


def search_videos(query: str, per_page: int = 5, min_duration: int = 3, orientation: str = "landscape") -> list[dict]:
    """Search Pexels for stock video clips.

    Args:
        query: Search terms (e.g., "data center", "circuit board").
        per_page: Number of results.
        min_duration: Minimum clip duration in seconds.
        orientation: "landscape", "portrait", or "square".

    Returns:
        List of video dicts with id, url, duration, and download links.
    """
    log = logger.bind(query=query)
    log.info("searching pexels videos")

    response = requests.get(
        f"{BASE_URL}/search",
        headers=_headers(),
        params={
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
            "size": "medium",
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for video in data.get("videos", []):
        if video.get("duration", 0) < min_duration:
            continue

        # Find the best HD file (prefer 1920x1080)
        best_file = None
        for vf in video.get("video_files", []):
            if vf.get("width", 0) >= 1280:
                if best_file is None or abs(vf.get("height", 0) - 1080) < abs(best_file.get("height", 0) - 1080):
                    best_file = vf

        # Fallback to any file
        if not best_file and video.get("video_files"):
            best_file = video["video_files"][0]

        if best_file:
            results.append({
                "id": video["id"],
                "duration": video["duration"],
                "width": best_file.get("width", 0),
                "height": best_file.get("height", 0),
                "download_url": best_file["link"],
            })

    log.info("pexels results", count=len(results))
    return results


def download_video(url: str, output_path: str) -> str:
    """Download a video file from Pexels.

    Args:
        url: Direct download URL.
        output_path: Where to save the file.

    Returns:
        Path to saved file.
    """
    log = logger.bind(output=output_path)
    log.info("downloading stock video")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    response = requests.get(url, timeout=60, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size = os.path.getsize(output_path)
    log.info("video downloaded", size_bytes=size)
    return output_path


def search_and_download(query: str, output_path: str) -> str | None:
    """Search for a stock video and download the best match.

    Returns the file path, or None if nothing found.
    """
    results = search_videos(query, per_page=3)
    if not results:
        # Try simpler query (first 2 words)
        simple = " ".join(query.split()[:2])
        results = search_videos(simple, per_page=3)

    if not results:
        return None

    return download_video(results[0]["download_url"], output_path)
