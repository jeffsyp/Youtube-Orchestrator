"""OpenAI Sora 2 API client for AI video generation."""

import os

import structlog
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = structlog.get_logger()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Sora pricing: ~$0.10/sec at 720p
DEFAULT_SECONDS = "8"  # Must be "4", "8", or "12"
DEFAULT_SIZE = "720x1280"  # Vertical for Shorts


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

    Args:
        prompt: Detailed description of the video to generate.
        output_path: Where to save the MP4.
        duration: Video duration in seconds (4, 8, or 12).
        size: Video dimensions — "720x1280" (vertical), "1280x720" (landscape).
        timeout: Max seconds to wait for generation (default 1200).
        image_url: Optional reference image URL for image-to-video generation.
            The image acts as the first frame.

    Returns:
        Dict with path, duration, size, and generation metadata.
    """
    client = _get_client()
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_image=bool(image_url))
    log.info("generating sora video")

    # Sora API uses string literals for seconds
    seconds_str = str(duration)

    # Build kwargs
    kwargs = {
        "model": "sora-2-pro",
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
        "timeout": timeout,
    }
    if image_url:
        kwargs["image"] = image_url

    # create_and_poll handles polling automatically
    video = client.videos.create_and_poll(**kwargs)

    if video.status == "failed":
        error = getattr(video, "error", "unknown error")
        raise RuntimeError(f"Sora generation failed: {error}")

    video_id = video.id
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
