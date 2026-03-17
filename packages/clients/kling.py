"""Kling 3.0 API client for AI video generation."""

import os
import time

import jwt
import requests
import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY")
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY")

API_BASE = "https://api.klingai.com"
POLL_INTERVAL = 10


def _generate_token() -> str:
    if not KLING_ACCESS_KEY or not KLING_SECRET_KEY:
        raise RuntimeError("KLING_ACCESS_KEY and KLING_SECRET_KEY must be set")
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": KLING_ACCESS_KEY,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5,
    }
    return jwt.encode(payload, KLING_SECRET_KEY, algorithm="HS256", headers=headers)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_generate_token()}",
        "Content-Type": "application/json",
    }


def generate_video(
    prompt: str,
    output_path: str,
    duration: int = 10,
    aspect_ratio: str = "9:16",
    mode: str = "std",
    model: str = "kling-v3",
    timeout: int = 600,
    negative_prompt: str = "blurry, low quality, distorted, text, watermark",
) -> dict:
    """Generate a video with Kling and save it.

    Args:
        prompt: Description of the video.
        output_path: Where to save the MP4.
        duration: 5 or 10 seconds.
        aspect_ratio: "9:16" (vertical), "16:9" (landscape), "1:1" (square).
        mode: "std" (standard) or "pro" (higher quality).
        model: Model version.
        timeout: Max seconds to wait.
        negative_prompt: What to avoid.

    Returns:
        Dict with path, duration, and metadata.
    """
    log = logger.bind(prompt=prompt[:100], duration=duration, model=model, mode=mode)
    log.info("generating kling video")

    # Submit generation request
    resp = requests.post(
        f"{API_BASE}/v1/videos/text2video",
        headers=_headers(),
        json={
            "model_name": model,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "duration": str(duration),
            "aspect_ratio": aspect_ratio,
            "mode": mode,
            "cfg_scale": 0.5,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"Kling submit failed: {data.get('message', data)}")

    task_id = data["data"]["task_id"]
    log.info("kling job submitted", task_id=task_id)

    # Poll for completion
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise RuntimeError(f"Kling generation timed out after {timeout}s")

        status_resp = requests.get(
            f"{API_BASE}/v1/videos/text2video/{task_id}",
            headers=_headers(),
            timeout=30,
        )
        status_resp.raise_for_status()
        task = status_resp.json()["data"]

        if task["task_status"] == "succeed":
            video_url = task["task_result"]["videos"][0]["url"]
            break
        elif task["task_status"] == "failed":
            msg = task.get("task_status_msg", "unknown error")
            raise RuntimeError(f"Kling generation failed: {msg}")

        time.sleep(POLL_INTERVAL)

    log.info("kling generation complete", task_id=task_id)

    # Download video
    video_data = requests.get(video_url, timeout=120)
    video_data.raise_for_status()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(video_data.content)

    file_size = os.path.getsize(output_path)
    log.info("kling video saved", path=output_path, size_bytes=file_size)

    return {
        "path": output_path,
        "task_id": task_id,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "file_size_bytes": file_size,
        "prompt": prompt[:200],
        "source": "kling",
    }
