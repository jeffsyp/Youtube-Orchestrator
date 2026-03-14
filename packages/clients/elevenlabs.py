"""ElevenLabs API client for text-to-speech voice generation."""

import os

import structlog
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

logger = structlog.get_logger()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Good default voices for YouTube narration
DEFAULT_VOICE = "Adam"  # Clear, professional male voice


def _get_client() -> ElevenLabs:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set in environment")
    return ElevenLabs(api_key=ELEVENLABS_API_KEY)


def list_voices() -> list[dict]:
    """List available voices."""
    client = _get_client()
    response = client.voices.get_all()
    return [
        {"voice_id": v.voice_id, "name": v.name, "category": v.category}
        for v in response.voices
    ]


def generate_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    model: str = "eleven_multilingual_v2",
    output_path: str | None = None,
) -> bytes:
    """Generate speech audio from text.

    Args:
        text: The text to convert to speech.
        voice: Voice name or ID.
        model: ElevenLabs model to use.
        output_path: If provided, saves the audio to this file path.

    Returns:
        Raw audio bytes (MP3 format).
    """
    client = _get_client()
    log = logger.bind(voice=voice, model=model, text_length=len(text))
    log.info("generating speech")

    response = client.text_to_speech.convert(
        text=text,
        voice_id=_resolve_voice_id(client, voice),
        model_id=model,
    )

    # Collect all chunks into bytes
    audio_bytes = b"".join(response)

    log.info("speech generated", audio_size=len(audio_bytes))

    if output_path:
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        log.info("audio saved", path=output_path)

    return audio_bytes


def _resolve_voice_id(client: ElevenLabs, voice: str) -> str:
    """Resolve a voice name to its ID. If already an ID, return as-is."""
    # If it looks like a voice ID (long alphanumeric), use directly
    if len(voice) > 15:
        return voice

    # Otherwise look up by name (partial match — "Adam" matches "Adam - Dominant, Firm")
    response = client.voices.get_all()
    voice_lower = voice.lower()
    for v in response.voices:
        if v.name.lower() == voice_lower or v.name.lower().startswith(voice_lower + " "):
            return v.voice_id

    raise ValueError(f"Voice '{voice}' not found. Available: {[v.name for v in response.voices]}")
