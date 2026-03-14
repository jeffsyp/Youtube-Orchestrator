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

    # Download and save, compress if needed for YouTube thumbnail (2MB limit)
    img_data = requests.get(image_url, timeout=30).content
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if len(img_data) > 2_000_000 or output_path.endswith(".jpg"):
        # Compress with Pillow
        from PIL import Image as PILImage
        import io
        img = PILImage.open(io.BytesIO(img_data))
        img = img.convert("RGB")
        # Save as JPEG with quality reduction until under 2MB
        quality = 90
        while quality > 30:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            if buf.tell() < 2_000_000:
                break
            quality -= 10
        with open(output_path, "wb") as f:
            f.write(buf.getvalue())
        log.info("image saved (compressed)", path=output_path, size_bytes=buf.tell(), quality=quality)
    else:
        with open(output_path, "wb") as f:
            f.write(img_data)
        log.info("image saved", path=output_path, size_bytes=len(img_data))

    return output_path
