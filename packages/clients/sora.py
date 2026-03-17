"""OpenAI Sora 2 API client for AI video generation."""

import asyncio
import os
import time

import structlog
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = structlog.get_logger()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Sora pricing: ~$0.10/sec at 720p
DEFAULT_SECONDS = "8"  # Must be "4", "8", or "12"
DEFAULT_SIZE = "720x1280"  # Vertical for Shorts
POLL_INTERVAL = 5  # seconds between status checks


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=OPENAI_API_KEY)


def generate_video(
    prompt: str,
    output_path: str,
    duration: int = 8,
    size: str = DEFAULT_SIZE,
    timeout: int = 1200,
    image_url: str | None = None,
) -> dict:
    """Generate a video with Sora 2 and save it.

    Uses manual polling with sleep instead of create_and_poll to avoid
    blocking the async event loop for minutes at a time.
    """
    client = _get_client()
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_image=bool(image_url))
    log.info("generating sora video")

    seconds_str = str(duration)

    # Build kwargs for create (not create_and_poll)
    kwargs = {
        "model": "sora-2",
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
    }
    if image_url:
        kwargs["image"] = image_url

    # Submit the generation request
    video = client.videos.create(**kwargs)
    video_id = video.id
    log.info("sora job submitted", video_id=video_id)

    # Poll for completion — use time.sleep to release the thread
    # (Temporal runs sync activities on thread pool, so time.sleep is fine
    # and doesn't block the async event loop like create_and_poll does)
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise RuntimeError(f"Sora generation timed out after {timeout}s")

        video = client.videos.retrieve(video_id)

        if video.status == "completed":
            break
        elif video.status == "failed":
            error = getattr(video, "error", "unknown error")
            raise RuntimeError(f"Sora generation failed: {error}")

        # Sleep briefly then poll again
        time.sleep(POLL_INTERVAL)

    log.info("sora generation complete", video_id=video_id)

    # Download the video
    content = client.videos.download_content(video_id)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(content.read())

    file_size = os.path.getsize(output_path)
    log.info("sora video saved", path=output_path, size_bytes=file_size)

    return {
        "path": output_path,
        "video_id": video_id,
        "duration": duration,
        "size": size,
        "file_size_bytes": file_size,
        "prompt": prompt[:200],
    }
