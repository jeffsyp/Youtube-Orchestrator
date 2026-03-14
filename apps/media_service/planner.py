"""Media service — generates visual plans, voice plans, SRT subtitles, and voiceover audio."""

import json
import os
import re

import structlog
from dotenv import load_dotenv

from packages.clients.claude import generate
from packages.prompts.media import build_package_prompt, build_visual_plan_prompt, build_voice_plan_prompt
from packages.schemas.media import ShotItem, VisualPlan, VoicePlan
from packages.schemas.packaging import PackagingPlan

load_dotenv()
logger = structlog.get_logger()

USE_VOICE = bool(os.getenv("ELEVENLABS_API_KEY"))


def _parse_json(text: str) -> dict:
    """Extract JSON from a response that might have markdown fencing or be truncated."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to fix truncated JSON by closing open structures
        fixed = text.rstrip()
        # Count open braces/brackets
        open_brackets = fixed.count("[") - fixed.count("]")
        open_braces = fixed.count("{") - fixed.count("}")

        # If we're inside an unterminated string, close it
        if fixed.count('"') % 2 != 0:
            fixed += '"'

        # Close open structures
        fixed += "}" * open_braces
        fixed += "]" * open_brackets

        return json.loads(fixed)


def build_visual_plan(script_content: str, idea_title: str) -> VisualPlan:
    """Generate a visual/shot plan for a video."""
    log = logger.bind(service="media", action="visual_plan")
    log.info("generating visual plan")

    system, user = build_visual_plan_prompt(script_content, idea_title)
    response = generate(user, system=system, max_tokens=4096, temperature=0.6)
    data = _parse_json(response)

    plan = VisualPlan(
        shots=[ShotItem(**s) for s in data["shots"]],
        total_duration_seconds=data["total_duration_seconds"],
        style_notes=data["style_notes"],
    )
    log.info("visual plan generated", shots=len(plan.shots))
    return plan


def build_voice_plan(script_content: str, idea_title: str, tone: str) -> VoicePlan:
    """Generate a voice/narration plan for a video."""
    log = logger.bind(service="media", action="voice_plan")
    log.info("generating voice plan")

    system, user = build_voice_plan_prompt(script_content, idea_title, tone)
    response = generate(user, system=system, max_tokens=4096, temperature=0.5)
    data = _parse_json(response)

    plan = VoicePlan(**data)
    log.info("voice plan generated")
    return plan


def generate_srt(script_content: str, words_per_minute: int = 150) -> str:
    """Generate a basic SRT subtitle file from script content.

    Splits script into chunks and assigns timestamps based on word count.
    """
    log = logger.bind(service="media", action="generate_srt")

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', script_content.strip())
    words_per_second = words_per_minute / 60.0

    srt_entries = []
    current_time = 0.0
    entry_num = 1

    for sentence in sentences:
        if not sentence.strip():
            continue
        word_count = len(sentence.split())
        duration = word_count / words_per_second

        start = _format_srt_time(current_time)
        end = _format_srt_time(current_time + duration)

        # SRT entries should be max ~2 lines
        words = sentence.split()
        if len(words) > 12:
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            text = f"{line1}\n{line2}"
        else:
            text = sentence

        srt_entries.append(f"{entry_num}\n{start} --> {end}\n{text}\n")
        entry_num += 1
        current_time += duration

    log.info("srt generated", entries=len(srt_entries))
    return "\n".join(srt_entries)


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_package(
    idea_title: str,
    script_content: str,
    niche: str,
    srt_content: str,
) -> PackagingPlan:
    """Generate the final video package metadata."""
    log = logger.bind(service="media", action="build_package")
    log.info("generating package metadata")

    system, user = build_package_prompt(idea_title, script_content, niche)
    response = generate(user, system=system, max_tokens=2048, temperature=0.5)
    data = _parse_json(response)

    package = PackagingPlan(
        title=data["title"],
        description=data["description"],
        tags=data["tags"],
        category=data.get("category", "Education"),
        thumbnail_text=data.get("thumbnail_text", ""),
        srt_content=srt_content,
        asset_manifest=[
            "script_final.txt",
            "visual_plan.json",
            "voice_plan.json",
            "subtitles.srt",
            "thumbnail_brief.txt",
        ],
        status="ready",
    )
    log.info("package generated", title=package.title)
    return package


def generate_voiceover(
    script_content: str,
    output_path: str,
    voice: str = "Adam",
) -> dict:
    """Generate voiceover audio from a script using ElevenLabs.

    Args:
        script_content: The narration text.
        output_path: Where to save the MP3 file.
        voice: ElevenLabs voice name or ID.

    Returns:
        Dict with status, file path, and audio size.
    """
    log = logger.bind(service="media", action="voiceover")

    if not USE_VOICE:
        log.info("elevenlabs not configured, skipping voiceover")
        return {"status": "skipped", "reason": "ELEVENLABS_API_KEY not set"}

    from packages.clients.elevenlabs import generate_speech

    audio = generate_speech(text=script_content, voice=voice, output_path=output_path)

    result = {
        "status": "generated",
        "path": output_path,
        "size_bytes": len(audio),
        "voice": voice,
    }
    log.info("voiceover generated", **result)
    return result
