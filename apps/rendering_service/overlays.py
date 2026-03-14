"""Text overlay rendering — applies professional text cues to video using FFmpeg.

Styles:
- section_title: Large bold text, centered, with background bar
- key_fact: Medium text, lower-left, with subtle background
- emphasis: Large text, centered, brief flash

All text uses fade-in/fade-out for smooth appearance.
"""

import json
import os

import structlog

from packages.clients.claude import generate
from packages.prompts.overlays import generate_overlay_cues_prompt

logger = structlog.get_logger()

# Font paths (in order of preference)
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _get_font_path() -> str:
    for path in FONT_PATHS:
        if os.path.exists(path):
            return path
    return ""


def generate_cues(script_content: str, duration_seconds: float) -> list[dict]:
    """Use Claude to generate timed text overlay cues from a script."""
    log = logger.bind(service="overlays", action="generate_cues")
    log.info("generating text overlay cues", duration=round(duration_seconds))

    system, user = generate_overlay_cues_prompt(script_content, duration_seconds)
    response = generate(user, system=system, max_tokens=2048, temperature=0.4)

    # Parse JSON
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end])

    try:
        cues = json.loads(text)
    except json.JSONDecodeError:
        # Try fixing truncated JSON
        fixed = text.rstrip()
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        cues = json.loads(fixed)

    # Validate and clean cues
    valid_cues = []
    for cue in cues:
        if all(k in cue for k in ("start_seconds", "duration", "text", "style")):
            cue["start_seconds"] = max(0, float(cue["start_seconds"]))
            cue["duration"] = max(1, min(5, float(cue["duration"])))
            cue["text"] = cue["text"][:40]  # Cap length
            if cue["style"] not in ("section_title", "key_fact", "emphasis"):
                cue["style"] = "key_fact"
            valid_cues.append(cue)

    # Sort by start time and remove overlaps
    valid_cues.sort(key=lambda c: c["start_seconds"])
    non_overlapping = []
    for cue in valid_cues:
        if non_overlapping:
            prev_end = non_overlapping[-1]["start_seconds"] + non_overlapping[-1]["duration"]
            if cue["start_seconds"] < prev_end + 1:  # 1 second gap minimum
                continue
        non_overlapping.append(cue)

    log.info("cues generated", total=len(cues), valid=len(non_overlapping))
    return non_overlapping


def build_drawtext_filter(cues: list[dict]) -> str:
    """Build an FFmpeg filter chain for all text overlays.

    Each cue gets a drawtext filter with:
    - Fade-in over 0.3 seconds
    - Hold for the specified duration
    - Fade-out over 0.3 seconds
    - Style-specific positioning, size, and background
    """
    font = _get_font_path()
    if not font:
        return ""

    # Escape font path for FFmpeg
    font_esc = font.replace(":", "\\:")

    filters = []
    fade_in = 0.3
    fade_out = 0.3

    for cue in cues:
        start = cue["start_seconds"]
        dur = cue["duration"]
        text = cue["text"].replace("'", "'").replace(":", "\\:").replace("%", "%%")
        style = cue["style"]
        end = start + dur

        # Alpha expression: fade in, hold, fade out
        alpha = (
            f"if(lt(t,{start}),0,"
            f"if(lt(t,{start + fade_in}),(t-{start})/{fade_in},"
            f"if(lt(t,{end - fade_out}),1,"
            f"if(lt(t,{end}),({end}-t)/{fade_out},"
            f"0))))"
        )

        if style == "section_title":
            # Large centered text with dark background bar
            filters.append(
                f"drawbox=x=0:y=(h/2-40):w=iw:h=80"
                f":color=black@0.6:t=fill"
                f":enable='between(t,{start},{end})'"
            )
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize=48"
                f":fontcolor=white"
                f":x=(w-text_w)/2"
                f":y=(h/2-20)"
                f":alpha='{alpha}'"
                f":shadowcolor=black@0.8:shadowx=2:shadowy=2"
            )

        elif style == "key_fact":
            # Medium text, lower-left with subtle background pill
            filters.append(
                f"drawbox=x=40:y=(h-120):w=(text_w+40):h=50"
                f":color=black@0.5:t=fill"
                f":enable='between(t,{start},{end})'"
                # Use a fixed width estimate since text_w isn't available in drawbox
            )
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize=32"
                f":fontcolor=white"
                f":x=60"
                f":y=(h-112)"
                f":alpha='{alpha}'"
                f":shadowcolor=black@0.8:shadowx=1:shadowy=1"
            )

        elif style == "emphasis":
            # Large centered text, no background, dramatic
            filters.append(
                f"drawtext=fontfile='{font_esc}'"
                f":text='{text}'"
                f":fontsize=56"
                f":fontcolor=white"
                f":x=(w-text_w)/2"
                f":y=(h/2-25)"
                f":alpha='{alpha}'"
                f":shadowcolor=black@0.9:shadowx=3:shadowy=3"
                f":borderw=2:bordercolor=black@0.5"
            )

    return ",".join(filters) if filters else ""


def apply_overlays(input_path: str, output_path: str, cues: list[dict]) -> str:
    """Apply text overlays to a video file.

    Args:
        input_path: Source video.
        output_path: Where to save the result.
        cues: List of text cue dicts.

    Returns:
        Path to the output video.
    """
    import subprocess

    log = logger.bind(service="overlays", action="apply")

    if not cues:
        log.info("no cues to apply, copying video")
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
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        log.error("overlay rendering failed", stderr=result.stderr[-300:])
        raise RuntimeError(f"FFmpeg overlay failed: {result.stderr[-200:]}")

    log.info("overlays applied", output=output_path)
    return output_path
