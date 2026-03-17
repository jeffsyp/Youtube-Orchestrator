"""ElevenLabs API client for text-to-speech voice generation."""

import os

import structlog
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

logger = structlog.get_logger()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Good default voices for YouTube narration
DEFAULT_VOICE = "Liam"  # Energetic, Social Media Creator


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

    Automatically chunks long text to stay within API limits.

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

    voice_id = _resolve_voice_id(client, voice)

    # Chunk text at sentence boundaries to stay under 5000 chars per request
    MAX_CHUNK = 4500
    if len(text) <= MAX_CHUNK:
        chunks = [text]
    else:
        chunks = _split_text(text, MAX_CHUNK)
        log.info("text chunked for api limits", chunks=len(chunks))

    all_audio = b""
    for i, chunk in enumerate(chunks):
        log.info("generating chunk", chunk=i + 1, total=len(chunks), chars=len(chunk))
        response = client.text_to_speech.convert(
            text=chunk,
            voice_id=voice_id,
            model_id=model,
        )
        all_audio += b"".join(response)

    log.info("speech generated", audio_size=len(all_audio))

    if output_path:
        with open(output_path, "wb") as f:
            f.write(all_audio)
        log.info("audio saved", path=output_path)

    return all_audio


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = current + " " + sentence if current else sentence
    if current:
        chunks.append(current.strip())
    return chunks


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
