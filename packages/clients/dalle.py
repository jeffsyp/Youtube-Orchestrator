"""DALL-E 3 client for generating scene images."""

import os

import requests
import structlog
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = structlog.get_logger()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def _get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=OPENAI_API_KEY)


def generate_image(
    prompt: str,
    output_path: str,
    size: str = "1792x1024",
    quality: str = "standard",
    style: str = "vivid",
) -> str:
    """Generate an image with DALL-E 3 and save it.

    Args:
        prompt: Description of the image to generate.
        output_path: Where to save the PNG.
        size: Image dimensions — "1792x1024" (landscape), "1024x1024", "1024x1792".
        quality: "standard" (~$0.04) or "hd" (~$0.08).
        style: "vivid" (hyper-real) or "natural" (more muted).

    Returns:
        Path to saved image.
    """
    client = _get_client()
    log = logger.bind(prompt=prompt[:80], size=size, quality=quality)
    log.info("generating dall-e image")

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
        style=style,
    )

    image_url = response.data[0].url
    revised_prompt = response.data[0].revised_prompt
    log.info("image generated", revised_prompt=revised_prompt[:80])

    # Download and save
    img_data = requests.get(image_url, timeout=30).content
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_data)

    log.info("image saved", path=output_path, size_bytes=len(img_data))
    return output_path
