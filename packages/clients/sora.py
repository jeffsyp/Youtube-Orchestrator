"""OpenAI Sora 2 API client for AI video generation."""

import asyncio
import base64
import os
import subprocess
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


def _extract_last_frame(video_path: str) -> str | None:
    """Extract a late frame from a video and return as base64 data URL for Sora input_reference.

    Uses the thumbnail filter which reliably picks a representative late frame,
    then scales to 720x1280 (Sora's expected dimensions). JPEG for smaller payload.
    """
    frame_path = video_path.replace(".mp4", "_lastframe.jpg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", "thumbnail,scale=720:1280",
         "-vframes", "1", "-update", "1", "-q:v", "10", frame_path],
        capture_output=True,
    )
    if result.returncode != 0 or not os.path.exists(frame_path):
        logger.warning("last frame extraction failed", video=video_path,
                        returncode=result.returncode)
        return None
    with open(frame_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    os.remove(frame_path)
    return f"data:image/jpeg;base64,{b64}"


async def generate_video_async(
    prompt: str,
    output_path: str,
    duration: int = 8,
    size: str = DEFAULT_SIZE,
    timeout: int = 1200,
    image_url: str | None = None,
    reference_image_url: str | None = None,
    model: str = "sora-2",
) -> dict:
    """Generate a video with Sora 2 or Sora 2 Pro — async version.

    Args:
        prompt: Text prompt for video generation.
        output_path: Where to save the generated video.
        duration: Video duration in seconds. sora-2: 4/8/12. sora-2-pro: 4/8/12/16/20.
        model: "sora-2" or "sora-2-pro".
        size: Video dimensions (e.g., "720x1280").
        timeout: Max seconds to wait for generation.
        image_url: Deprecated — use reference_image_url instead.
        reference_image_url: Image URL or base64 data URL to use as style/scene reference.
    """
    client = _get_client()
    ref_url = reference_image_url or image_url
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_reference=bool(ref_url))
    log.info("generating sora video", model=model)

    seconds_str = str(duration)

    kwargs = {
        "model": model,
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
    }
    extra_body = {}
    if ref_url:
        extra_body["input_reference"] = {"image_url": ref_url}
    if extra_body:
        kwargs["extra_body"] = extra_body

    # Submit with retry for transient errors (500, 429, network)
    # Do NOT retry on billing/auth/policy errors — fail immediately
    _no_retry = ["billing", "unauthorized", "authentication", "invalid_api_key",
                  "content policy", "moderation", "safety"]
    max_submit_retries = 3
    video = None
    for attempt in range(1, max_submit_retries + 1):
        try:
            video = client.videos.create(**kwargs)
            break
        except Exception as e:
            err_str = str(e).lower()
            if any(p in err_str for p in _no_retry):
                raise RuntimeError(f"Sora error (not retryable): {e}") from e
            log.warning("sora submit failed", attempt=attempt, max=max_submit_retries,
                        error=str(e), error_type=type(e).__name__)
            if attempt == max_submit_retries:
                raise RuntimeError(f"Sora submit failed after {max_submit_retries} attempts: {e}") from e
            await asyncio.sleep(10 * attempt)

    video_id = video.id
    log.info("sora job submitted", video_id=video_id)

    # Poll with asyncio.sleep — releases event loop between polls
    start_time = time.time()
    last_status = None
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise RuntimeError(f"Sora generation timed out after {timeout}s (video_id={video_id}, last_status={last_status})")

        try:
            video = client.videos.retrieve(video_id)
        except Exception as e:
            log.warning("sora poll error, retrying", video_id=video_id, error=str(e),
                        error_type=type(e).__name__, elapsed=int(elapsed))
            await asyncio.sleep(POLL_INTERVAL * 2)
            continue

        if video.status != last_status:
            log.info("sora status change", video_id=video_id, status=video.status,
                     elapsed=int(elapsed))
            last_status = video.status

        if video.status == "completed":
            break
        elif video.status == "failed":
            error = getattr(video, "error", "unknown error")
            raise RuntimeError(f"Sora generation failed: {error} (video_id={video_id})")

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


async def extend_video_async(
    video_id: str,
    prompt: str,
    output_path: str,
    duration: int = 24,
    model: str = "sora-2-pro",
    timeout: int = 2400,
) -> dict:
    """Extend an existing Sora video using the full clip as context.

    Args:
        video_id: ID of the video to extend.
        prompt: What should happen next.
        output_path: Where to save the stitched result.
        duration: Total stitched duration (original + extension).
        model: Sora model.
        timeout: Max wait seconds.
    """
    client = _get_client()
    log = logger.bind(video_id=video_id, prompt=prompt[:100], duration=duration, model=model)
    log.info("extending sora video")

    _no_retry = ["billing", "moderation", "content policy", "unauthorized", "safety"]

    import requests as req

    max_retries = 3
    ext = None
    for attempt in range(1, max_retries + 1):
        try:
            # Use raw API — SDK has a bug with video reference format
            r = req.post(
                "https://api.openai.com/v1/videos/extensions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "prompt": prompt,
                    "seconds": str(duration),
                    "video": {"id": video_id},
                },
            )
            if r.status_code != 200:
                raise RuntimeError(f"Sora extend HTTP {r.status_code}: {r.text[:200]}")
            ext_data = r.json()

            class _FakeExt:
                def __init__(self, d):
                    self.id = d.get("id")
                    self.status = d.get("status", "in_progress")
            ext = _FakeExt(ext_data)
            break
        except Exception as e:
            if any(p in str(e).lower() for p in _no_retry):
                raise RuntimeError(f"Sora extend error (not retryable): {e}") from e
            log.warning("sora extend failed", attempt=attempt, error=str(e)[:200])
            if attempt == max_retries:
                raise RuntimeError(f"Sora extend failed after {max_retries} attempts: {e}") from e
            await asyncio.sleep(10 * attempt)

    ext_id = ext.id
    log.info("sora extension submitted", ext_id=ext_id)

    start_time = time.time()
    last_status = None
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise RuntimeError(f"Sora extension timed out after {timeout}s")

        try:
            ext = client.videos.retrieve(ext_id)
        except Exception as e:
            log.warning("sora extend poll error", error=str(e)[:100])
            await asyncio.sleep(POLL_INTERVAL * 2)
            continue

        if ext.status != last_status:
            log.info("sora extend status", status=ext.status, elapsed=int(elapsed))
            last_status = ext.status

        if ext.status == "completed":
            break
        elif ext.status == "failed":
            error = getattr(ext, "error", "unknown")
            raise RuntimeError(f"Sora extension failed: {error}")

        await asyncio.sleep(POLL_INTERVAL)

    log.info("sora extension complete", ext_id=ext_id)

    content = client.videos.download_content(ext_id)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(content.read())

    file_size = os.path.getsize(output_path)
    log.info("sora extended video saved", path=output_path, size_bytes=file_size)

    return {
        "path": output_path,
        "video_id": ext_id,
        "source_video_id": video_id,
        "duration": duration,
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
    reference_image_url: str | None = None,
) -> dict:
    """Sync wrapper with retry and polling."""
    client = _get_client()
    ref_url = reference_image_url or image_url
    log = logger.bind(prompt=prompt[:100], duration=duration, size=size,
                      has_reference=bool(ref_url))
    log.info("generating sora video")

    seconds_str = str(duration)
    kwargs = {
        "model": "sora-2",
        "prompt": prompt,
        "seconds": seconds_str,
        "size": size,
    }
    extra_body = {}
    if ref_url:
        extra_body["input_reference"] = {"image_url": ref_url}
    if extra_body:
        kwargs["extra_body"] = extra_body

    # Submit with retry for transient errors
    max_submit_retries = 3
    video = None
    for attempt in range(1, max_submit_retries + 1):
        try:
            video = client.videos.create(**kwargs)
            break
        except Exception as e:
            log.warning("sora submit failed", attempt=attempt, max=max_submit_retries,
                        error=str(e), error_type=type(e).__name__)
            if attempt == max_submit_retries:
                raise RuntimeError(f"Sora submit failed after {max_submit_retries} attempts: {e}") from e
            time.sleep(10 * attempt)

    video_id = video.id
    log.info("sora job submitted", video_id=video_id)

    start_time = time.time()
    last_status = None
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise RuntimeError(f"Sora generation timed out after {timeout}s (video_id={video_id}, last_status={last_status})")

        try:
            video = client.videos.retrieve(video_id)
        except Exception as e:
            log.warning("sora poll error, retrying", video_id=video_id, error=str(e),
                        error_type=type(e).__name__, elapsed=int(elapsed))
            time.sleep(POLL_INTERVAL * 2)
            continue

        if video.status != last_status:
            log.info("sora status change", video_id=video_id, status=video.status,
                     elapsed=int(elapsed))
            last_status = video.status

        if video.status == "completed":
            break
        elif video.status == "failed":
            error = getattr(video, "error", "unknown error")
            raise RuntimeError(f"Sora generation failed: {error} (video_id={video_id})")

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
