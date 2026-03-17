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

DEFAULT_SECONDS = "8"
DEFAULT_SIZE = "720x1280"
POLL_INTERVAL = 5


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=OPENAI_API_KEY)


async def generate_video_async(
    prompt: str,
    output_path: str,
    duration: int = 8,
    size: str = DEFAULT_SIZE,
    timeout: int = 1200,
    image_url: str | None = None,
) -> dict:
    """Generate a video with Sora 2 — async version that doesn't block the event loop.

    Uses asyncio.sleep for polling so other activities can run concurrently.
    """
    client = _get_client()
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_image=bool(image_url))
    log.info("generating sora video")

    seconds_str = str(duration)

    kwargs = {
        "model": "sora-2-pro",
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
    }
    if image_url:
        kwargs["image"] = image_url

    # Submit (sync call, fast)
    video = client.videos.create(**kwargs)
    video_id = video.id
    log.info("sora job submitted", video_id=video_id)

    # Poll with asyncio.sleep — releases event loop between polls
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

        await asyncio.sleep(POLL_INTERVAL)

    log.info("sora generation complete", video_id=video_id)

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


def generate_video(
    prompt: str,
    output_path: str,
    duration: int = 8,
    size: str = DEFAULT_SIZE,
    timeout: int = 1200,
    image_url: str | None = None,
) -> dict:
    """Sync wrapper — tries async first, falls back to sync polling.

    Temporal activities run in an async context, so we try to use
    asyncio.sleep for non-blocking polling. If there's no event loop,
    falls back to time.sleep.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context — but we can't await from a sync function.
        # Use the sync fallback with time.sleep.
    except RuntimeError:
        pass

    # Sync fallback
    client = _get_client()
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_image=bool(image_url))
    log.info("generating sora video")

    seconds_str = str(duration)
    kwargs = {
        "model": "sora-2-pro",
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
    }
    if image_url:
        kwargs["image"] = image_url

    video = client.videos.create(**kwargs)
    video_id = video.id
    log.info("sora job submitted", video_id=video_id)

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

        time.sleep(POLL_INTERVAL)

    log.info("sora generation complete", video_id=video_id)

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
