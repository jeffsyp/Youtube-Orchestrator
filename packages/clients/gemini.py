"""Google Gemini API client for video analysis."""

import os

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL = "gemini-3-pro-preview"


def _get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set in environment")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def review_video(video_path: str, prompt: str, model: str | None = None, max_retries: int = 3) -> str:
    """Send a video file to Gemini for analysis.

    Args:
        video_path: Path to the MP4 file.
        prompt: Analysis prompt.
        model: Model to use (defaults to gemini-2.5-flash).
        max_retries: Max retries on rate limit errors.

    Returns:
        Gemini's text response.
    """
    import time
    from google.genai import types

    client = _get_client()
    model = model or MODEL
    log = logger.bind(model=model, video=video_path)

    file_size = os.path.getsize(video_path)
    log.info("sending video to gemini", size_mb=round(file_size / 1024 / 1024, 1))

    video_bytes = open(video_path, "rb").read()

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=types.Content(
                    parts=[
                        types.Part(
                            inline_data=types.Blob(data=video_bytes, mime_type="video/mp4")
                        ),
                        types.Part(text=prompt),
                    ]
                ),
            )

            text = response.text
            log.info("gemini response received", response_length=len(text))
            return text
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                # Pro overloaded — fall back to Flash immediately
                fallback = "gemini-2.5-flash"
                log.warning("gemini pro unavailable, falling back to flash", attempt=attempt + 1)
                try:
                    response = client.models.generate_content(
                        model=fallback,
                        contents=types.Content(
                            parts=[
                                types.Part(inline_data=types.Blob(data=video_bytes, mime_type="video/mp4")),
                                types.Part(text=prompt),
                            ]
                        ),
                    )
                    text = response.text
                    log.info("gemini flash response received", response_length=len(text), fallback=True)
                    return text
                except Exception as flash_err:
                    log.warning("flash fallback also failed", error=str(flash_err)[:100])
                    time.sleep(15)
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 45 * (attempt + 1)
                log.warning("gemini rate limited, retrying", attempt=attempt + 1, wait=wait)
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"Gemini rate limited after {max_retries} retries")
