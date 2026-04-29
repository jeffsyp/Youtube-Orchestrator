#!/usr/bin/env python3
"""Build the refactored Hardcore Ranked short from actual-planet scenes."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any

from dotenv import load_dotenv

from apps.orchestrator.channel_builders.shared import (
    add_subtitles,
    build_intro_teasers,
    build_numpy_audio,
    build_silent_segments,
    combine_video_audio,
    concat_silent_video,
    generate_narration_with_timestamps,
    get_clip_duration,
)
from packages.clients.veo import generate_video_async


ROOT = "/Users/jeffsyp/Projects/Youtube-Orchestrator"
BASE_DIR = os.path.join(ROOT, "output", "manual_lab", "hardcore_ranked_planets", "refactor_v2")
OUT_DIR = os.path.join(BASE_DIR, "render_v2")
CONCEPT_PATH = os.path.join(BASE_DIR, "concept_v2.json")
RAW_IMAGE_DIR = os.path.join(BASE_DIR, "images", "raw")
MUSIC_PATH = os.path.join(ROOT, "assets", "music", "dark", "rising.mp3")
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _ensure_dirs() -> dict[str, str]:
    dirs = {
        "narr": os.path.join(OUT_DIR, "narration"),
        "clips": os.path.join(OUT_DIR, "clips"),
        "segments": os.path.join(OUT_DIR, "segments"),
        "review": os.path.join(OUT_DIR, "review"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def _load_concept() -> dict[str, Any]:
    with open(CONCEPT_PATH) as f:
        return json.load(f)


def _log_step(step: str) -> None:
    print(f"[render_v2] {step}", flush=True)


def _scene_image_path(slug: str) -> str:
    return os.path.join(RAW_IMAGE_DIR, f"{slug}.png")


def _drawtext(text: str, x: int, y: int, size: int, color: str) -> str:
    clean = text.upper().replace(":", r"\:")
    return (
        f"drawtext=fontfile='{FONT_PATH}':text='{clean}':x={x}:y={y}:"
        f"fontsize={size}:fontcolor={color}"
    )


def _overlay_label(clip_path: str, planet: str, jump_label: str, fact_label: str) -> None:
    tmp_path = clip_path.replace(".mp4", "_labeled.mp4")
    draw = ",".join(
        [
            "drawbox=x=36:y=36:w=560:h=206:color=black@0.45:t=fill",
            _drawtext(planet, 58, 54, 56, "white"),
            _drawtext(jump_label, 58, 114, 80, "#ffde59"),
            _drawtext(fact_label, 58, 184, 36, "#d0d8e8"),
        ]
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            clip_path,
            "-vf",
            draw,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            tmp_path,
        ],
        capture_output=True,
        check=True,
        timeout=300,
    )
    os.replace(tmp_path, clip_path)


def _hook_prompt() -> str:
    return (
        "Same exact side-view Earth test shot. The frog-suit jumper does one quick anticipatory dip, "
        "lightly bounces on the balls of his feet, then pops into a small practice hop next to the striped mast. "
        "The silver lander stays fixed in the background. Keep it natural, readable, and energetic. "
        "No camera movement, no scene cuts, no extra characters."
    )


def _scene_prompt(scene: dict[str, Any]) -> str:
    jump_label = scene["jump_label"]
    if jump_label == "8 in":
        action = (
            "The frog-suit jumper strains into a jump but barely gets off the ground, only lifting a few inches before dropping back quickly."
        )
    elif jump_label.startswith("4 ft"):
        action = (
            "The frog-suit jumper launches sharply upward, rises far above the normal mark beside the mast, hangs in the air for a beat, then starts drifting down."
        )
    elif jump_label.startswith("1 ft 11"):
        action = (
            "The frog-suit jumper springs upward with a buoyant jump, reaches a clearly above-normal apex, hangs for a moment, then begins a gentle descent."
        )
    elif jump_label.startswith("1 ft 8"):
        action = (
            "The frog-suit jumper performs a clean normal vertical jump, reaches a familiar athletic apex beside the mast, then returns naturally."
        )
    else:
        action = (
            "The frog-suit jumper pushes off hard, reaches a slightly lower-than-normal apex, then drops back down sooner with heavier body language."
        )
    return (
        f"{action} Keep the same side-view composition, the same striped mast, and the same silver lander for scale. "
        f"The {scene['planet']} environment must stay stable and readable behind the action. "
        "No camera movement, no text, no extra characters."
    )


async def _generate_narration(concept: dict[str, Any], dirs: dict[str, str]) -> None:
    _log_step("generating narration")
    await generate_narration_with_timestamps(
        concept["narration"],
        dirs["narr"],
        OUT_DIR,
        VOICE_ID,
        lambda step: asyncio.sleep(0),
    )


async def _animate_scenes(concept: dict[str, Any], dirs: dict[str, str]) -> None:
    hook_clip = os.path.join(dirs["clips"], "clip_00.mp4")
    if not os.path.exists(hook_clip):
        _log_step("animating hook")
        result = await generate_video_async(
            prompt=_hook_prompt(),
            output_path=hook_clip,
            model="veo-3.1-lite-generate-001",
            duration_seconds=4,
            aspect_ratio="9:16",
            resolution="720p",
            image_path=_scene_image_path("earth"),
        )
        print(result["path"], flush=True)
        _overlay_label(hook_clip, "Earth", "1 ft 8 in", "1G BASELINE")

    for idx, scene in enumerate(concept["scenes"], start=1):
        clip_path = os.path.join(dirs["clips"], f"clip_{idx:02d}.mp4")
        if os.path.exists(clip_path):
            continue
        _log_step(f"animating {scene['planet']}")
        narr_path = os.path.join(dirs["narr"], f"line_{idx:02d}.mp3")
        requested = get_clip_duration(narr_path)
        duration = 4 if requested <= 4 else 6 if requested <= 6 else 8
        result = await generate_video_async(
            prompt=_scene_prompt(scene),
            output_path=clip_path,
            model="veo-3.1-lite-generate-001",
            duration_seconds=duration,
            aspect_ratio="9:16",
            resolution="720p",
            image_path=_scene_image_path(scene["slug"]),
        )
        print(result["path"], flush=True)
        _overlay_label(clip_path, scene["planet"], scene["jump_label"], scene["fact_label"])


def _build_video(concept: dict[str, Any], dirs: dict[str, str]) -> str:
    _log_step("building video")
    n_lines = len(concept["narration"])
    seg_durations = build_silent_segments(n_lines, dirs["clips"], dirs["narr"], dirs["segments"])
    actual_teaser_dur = build_intro_teasers(n_lines, dirs["narr"], dirs["clips"], dirs["segments"])
    teasers_path = os.path.join(dirs["segments"], "teasers.mp4")
    all_video_path, total_dur = concat_silent_video(teasers_path, dirs["segments"], n_lines, OUT_DIR)
    audio_path, seg_starts = build_numpy_audio(
        n_lines,
        dirs["narr"],
        MUSIC_PATH,
        actual_teaser_dur,
        seg_durations,
        total_dur,
        OUT_DIR,
    )
    combined = combine_video_audio(all_video_path, audio_path, OUT_DIR)
    with open(os.path.join(OUT_DIR, "word_timestamps.json")) as f:
        word_data = json.load(f)
    return add_subtitles(combined, word_data, seg_starts, OUT_DIR)


def _build_review_sheet(final_path: str, review_dir: str) -> str:
    sheet_path = os.path.join(review_dir, "final_sheet.jpg")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            final_path,
            "-vf",
            "fps=1,scale=320:-1,tile=3x3",
            "-frames:v",
            "1",
            sheet_path,
        ],
        capture_output=True,
        check=True,
        timeout=300,
    )
    return sheet_path


async def main() -> None:
    load_dotenv(os.path.join(ROOT, ".env"), override=True)
    concept = _load_concept()
    dirs = _ensure_dirs()
    await _generate_narration(concept, dirs)
    await _animate_scenes(concept, dirs)
    final_path = _build_video(concept, dirs)
    sheet_path = _build_review_sheet(final_path, dirs["review"])
    _log_step(f"done -> {final_path}")
    _log_step(f"sheet -> {sheet_path}")


if __name__ == "__main__":
    asyncio.run(main())
