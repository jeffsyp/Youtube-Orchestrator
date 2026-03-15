"""Text overlay rendering — applies professional text cues to video using FFmpeg.

Styles:
- section_title: Large bold text, centered, with box background
- key_fact: Medium text, lower-left, with box background
- emphasis: Large text, centered, brief flash
"""

import json
import os
import subprocess

import structlog

from packages.clients.claude import generate
from packages.prompts.overlays import generate_overlay_cues_prompt

logger = structlog.get_logger()

def _get_font_path() -> str:
    from apps.rendering_service.fonts import FONT_PATH_STR
    return FONT_PATH_STR


def generate_cues(script_content: str, duration_seconds: float) -> list[dict]:
    """Use Claude to generate timed text overlay cues from a script."""
    log = logger.bind(service="overlays", action="generate_cues")
    log.info("generating text overlay cues", duration=round(duration_seconds))

    system, user = generate_overlay_cues_prompt(script_content, duration_seconds)
    response = generate(user, system=system, max_tokens=2048, temperature=0.4)

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        cues = json.loads(text)
    except json.JSONDecodeError:
        fixed = text.rstrip()
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        cues = json.loads(fixed)

    valid_cues = []
    for cue in cues:
        if all(k in cue for k in ("start_seconds", "duration", "text", "style")):
            cue["start_seconds"] = max(0, float(cue["start_seconds"]))
            cue["duration"] = max(1, min(5, float(cue["duration"])))
            cue["text"] = str(cue["text"])[:40]
            if cue["style"] not in ("section_title", "key_fact", "emphasis"):
                cue["style"] = "key_fact"
            valid_cues.append(cue)

    valid_cues.sort(key=lambda c: c["start_seconds"])
    non_overlapping = []
    for cue in valid_cues:
        if non_overlapping:
            prev_end = non_overlapping[-1]["start_seconds"] + non_overlapping[-1]["duration"]
            if cue["start_seconds"] < prev_end + 1:
                continue
        non_overlapping.append(cue)

    log.info("cues generated", total=len(cues), valid=len(non_overlapping))
    return non_overlapping


def _escape_text(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\u2019")  # Replace apostrophe with unicode right quote
        .replace(":", "\\:")
        .replace("%", "%%")
        .replace('"', '\\"')
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(";", "\\;")
    )


def build_drawtext_filter(cues: list[dict]) -> str:
    """Build FFmpeg drawtext filter chain for all text overlays."""
    font = _get_font_path()
    if not font:
        return ""

    font_esc = font.replace(":", "\\:")
    filters = []

    for cue in cues:
        start = cue["start_seconds"]
        dur = cue["duration"]
        text = _escape_text(cue["text"])
        style = cue["style"]
        end = start + dur
        fade_in = 0.4
        fade_out = 0.4

        enable = f"between(t\\,{start}\\,{end})"

        # Alpha envelope: fade in over fade_in seconds, hold, fade out over fade_out seconds
        alpha = (
            f"if(lt(t\\,{start + fade_in})\\,"
            f"(t-{start})/{fade_in}\\,"
            f"if(gt(t\\,{end - fade_out})\\,"
            f"({end}-t)/{fade_out}\\,"
            f"1))"
        )

        if style == "section_title":
            # Slide up from +20px while fading in
            slide_y = (
                f"if(lt(t\\,{start + fade_in})\\,"
                f"(h/2-24)+20*(1-(t-{start})/{fade_in})\\,"
                f"(h/2-24))"
            )
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize=48"
                f":fontcolor=white@{{{alpha}}}"
                f":x=(w-text_w)/2"
                f":y={slide_y}"
                f":box=1:boxcolor=black@0.6:boxborderw=15"
                f":shadowcolor=black@0.8:shadowx=3:shadowy=3"
                f":enable='{enable}'"
            )

        elif style == "key_fact":
            # Slide in from left while fading in
            slide_x = (
                f"if(lt(t\\,{start + fade_in})\\,"
                f"60-40*(1-(t-{start})/{fade_in})\\,"
                f"60)"
            )
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize=32"
                f":fontcolor=white@{{{alpha}}}"
                f":x={slide_x}"
                f":y=h-100"
                f":box=1:boxcolor=black@0.5:boxborderw=10"
                f":shadowcolor=black@0.8:shadowx=2:shadowy=2"
                f":enable='{enable}'"
            )

        elif style == "emphasis":
            # Scale-in effect via font size change + fade
            scale_size = (
                f"if(lt(t\\,{start + fade_in})\\,"
                f"48+8*(t-{start})/{fade_in}\\,"
                f"56)"
            )
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize={scale_size}"
                f":fontcolor=white@{{{alpha}}}"
                f":x=(w-text_w)/2"
                f":y=(h/2-28)"
                f":box=1:boxcolor=black@0.7:boxborderw=12"
                f":shadowcolor=black@0.9:shadowx=3:shadowy=3"
                f":enable='{enable}'"
            )

    return ",".join(filters) if filters else ""


def apply_overlays(input_path: str, output_path: str, cues: list[dict]) -> str:
    """Apply text overlays to a video file."""
    log = logger.bind(service="overlays", action="apply")

    if not cues:
        log.info("no cues to apply")
        os.rename(input_path, output_path)
        return output_path

    filter_str = build_drawtext_filter(cues)
    if not filter_str:
        log.warning("no font found, skipping overlays")
        os.rename(input_path, output_path)
        return output_path

    log.info("applying text overlays", cues=len(cues))

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_str,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

    if result.returncode != 0:
        log.error("overlay rendering failed", stderr=result.stderr[-300:])
        # Fall back to no overlays
        log.warning("falling back to video without overlays")
        os.rename(input_path, output_path)
        return output_path

    log.info("overlays applied", output=output_path)
    return output_path
