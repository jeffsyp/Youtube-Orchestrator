"""Anthropic Claude API client for all AI reasoning tasks."""

import os

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Use sonnet for main tasks, haiku for cheaper tasks (scoring, extraction)
MODEL_MAIN = "claude-opus-4-6"
MODEL_CHEAP = "claude-haiku-4-5-20251001"


def _get_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def generate(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Send a prompt to Claude and return the text response.

    Args:
        prompt: The user message.
        system: Optional system prompt.
        model: Model to use (defaults to MODEL_MAIN).
        max_tokens: Max response tokens.
        temperature: Sampling temperature.

    Returns:
        The assistant's text response.
    """
    client = _get_client()
    model = model or MODEL_MAIN
    log = logger.bind(model=model, max_tokens=max_tokens)
    log.info("calling claude api")

    messages = [{"role": "user", "content": prompt}]
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = response.content[0].text

    log.info(
        "claude response received",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return text


def generate_cheap(prompt: str, system: str = "", max_tokens: int = 2048) -> str:
    """Use the cheaper/faster model for simple tasks."""
    return generate(prompt, system=system, model=MODEL_CHEAP, max_tokens=max_tokens)


def generate_with_images(
    prompt: str,
    image_paths: list[str],
    system: str = "",
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.5,
) -> str:
    """Send a prompt with images to Claude vision and return the text response.

    Args:
        prompt: The user text message.
        image_paths: List of paths to image files (JPEG, PNG, GIF, WebP).
        system: Optional system prompt.
        model: Model to use (defaults to MODEL_MAIN).
        max_tokens: Max response tokens.
        temperature: Sampling temperature.

    Returns:
        The assistant's text response.
    """
    import base64
    import mimetypes

    client = _get_client()
    model = model or MODEL_MAIN
    log = logger.bind(model=model, max_tokens=max_tokens, images=len(image_paths))
    log.info("calling claude vision api")

    # Build content blocks: images first, then text
    content = []
    for path in image_paths:
        if not os.path.exists(path):
            log.warning("image not found, skipping", path=path)
            continue

        mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
        with open(path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": image_data,
            },
        })

    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": temperature,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = response.content[0].text

    log.info(
        "claude vision response received",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    return text
