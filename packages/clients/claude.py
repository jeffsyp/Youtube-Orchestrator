"""Anthropic Claude API client for all AI reasoning tasks."""

import os

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Use sonnet for main tasks, haiku for cheaper tasks (scoring, extraction)
MODEL_MAIN = "claude-sonnet-4-6"
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
