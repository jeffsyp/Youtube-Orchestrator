#!/usr/bin/env python3
"""Build a manual Hardcore Ranked short: jump height on extreme planets."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from apps.orchestrator.channel_builders.shared import (
    add_subtitles,
    build_intro_teasers,
    build_numpy_audio,
    build_silent_segments,
    combine_video_audio,
    concat_silent_video,
    generate_narration_with_timestamps,
    get_clip_duration,
    get_duration,
)
from packages.clients.grok import generate_image_dalle_async
from packages.clients.veo import generate_video_async


ROOT = "/Users/jeffsyp/Projects/Youtube-Orchestrator"
OUT_DIR = os.path.join(ROOT, "output", "manual_lab", "hardcore_ranked_planets", "render_v1")
CONCEPT_PATH = os.path.join(ROOT, "output", "manual_lab", "hardcore_ranked_planets", "concept.json")
FROG_REF = os.path.join(ROOT, "assets", "character_cache", "hardcore_ranked_frog_v3.png")
MUSIC_PATH = os.path.join(ROOT, "assets", "music", "dark", "rising.mp3")
VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

BASE_SCENE_PROMPT = (
    "Photorealistic sci-fi gravity test chamber. Strict side-view camera, perfectly level, like a science ad. "
    "A human-sized person wearing the exact same green frog-themed astronaut suit from the reference image stands on "
    "a glowing launch pad beside a tall vertical measuring ruler with clear tick marks. He is crouched and ready to jump. "
    "A huge observation window fills the back wall, showing deep space and a neutral planet-selection backdrop. "
    "Same chamber lighting, same platform, same ruler, same camera angle must be reusable for every scene. "
    "Photorealistic. NO text anywhere."
)

HOOK_PROMPT = (
    "Keep the exact same gravity chamber, same launch pad, same ruler, same side-view angle. "
    "The frog-suit test subject crouches lower, pumps his arms once, and prepares to explode upward for a jump test. "
    "Indicator lights pulse softly around the pad while the observation window glows with deep space. "
    "Energetic anticipation, no text, no camera movement."
)


def _ensure_dirs() -> dict[str, str]:
    dirs = {
        "narr": os.path.join(OUT_DIR, "narration"),
        "images": os.path.join(OUT_DIR, "images"),
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
    print(f"[build] {step}", flush=True)


def _overlay_label(clip_path: str, planet: str, jump_label: str) -> None:
    tmp_path = clip_path.replace(".mp4", "_labeled.mp4")
    planet_txt = planet.upper().replace(":", r"\:")
    label_txt = jump_label.upper().replace(":", r"\:")
    draw = (
        f"drawbox=x=40:y=40:w=500:h=210:color=black@0.45:t=fill,"
        f"drawtext=fontfile='{FONT_PATH}':text='{planet_txt}':x=66:y=62:fontsize=60:fontcolor=white,"
        f"drawtext=fontfile='{FONT_PATH}':text='{label_txt}':x=66:y=126:fontsize=84:fontcolor=white"
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


def _planet_scene_prompt(planet: str, jump_label: str) -> str:
    if jump_label == "8 in":
        body = (
            "The subject is barely airborne, only a few inches off the launch pad, knees still bent, looking crushed by gravity."
        )
    elif jump_label.startswith("4 ft"):
        body = (
            "The subject is soaring high beside the ruler, floating near the upper section with a long airy hang time and legs tucked."
        )
    elif jump_label.startswith("1 ft 11"):
        body = (
            "The subject is clearly above a normal jump, near the upper-middle section of the ruler, looking springy and weightless."
        )
    elif jump_label.startswith("1 ft 8"):
        body = (
            "The subject is at a normal athletic jump apex around the middle of the ruler, balanced and familiar."
        )
    else:
        body = (
            "The subject reaches only a modest apex below the normal mark, looking heavier and dropping faster."
        )
    return (
        "Keep EVERYTHING identical to the input image: same gravity chamber, same side-view camera, same launch pad, "
        "same vertical ruler, same lighting, same frog astronaut suit, same character proportions. "
        f"Change only two things. First, the huge observation window now clearly shows {planet} in space. "
        f"Second, {body} The ruler must make the height visually obvious. Photorealistic. NO text anywhere."
    )


def _planet_animation_prompt(planet: str, jump_label: str) -> str:
    if jump_label == "8 in":
        motion = (
            "The frog-suit test subject tries to jump but barely lifts off the launch pad, rises only a tiny amount, then slams back down quickly with heavy body language."
        )
    elif jump_label.startswith("4 ft"):
        motion = (
            "The frog-suit test subject launches sharply upward, keeps floating for an extra beat near the top of the ruler, then drifts back down in obvious low gravity."
        )
    elif jump_label.startswith("1 ft 11"):
        motion = (
            "The frog-suit test subject springs upward with a light bounce, reaches a noticeably high apex, hangs for a moment, then returns to the pad smoothly."
        )
    elif jump_label.startswith("1 ft 8"):
        motion = (
            "The frog-suit test subject performs a clean normal vertical jump, hits a familiar athletic apex, then lands naturally back on the pad."
        )
    else:
        motion = (
            "The frog-suit test subject jumps with effort, reaches a lower-than-normal apex, then drops back down faster as gravity pulls harder."
        )
    return (
        f"{motion} Keep the same strict side-view chamber shot the entire time. "
        f"{planet} stays visible through the observation window. The ruler stays fixed and readable. "
        "No camera movement, no scene cuts, no extra characters."
    )


async def _generate_base_scene(client: AsyncOpenAI, dirs: dict[str, str]) -> str:
    base_scene = os.path.join(dirs["images"], "base_scene.png")
    if os.path.exists(base_scene):
        return base_scene
    _log_step("generating base chamber")
    with open(FROG_REF, "rb") as ref_file:
        resp = await client.images.edit(
            model="gpt-image-1.5",
            image=ref_file,
            prompt=f"Place this exact frog-suit character into the scene. {BASE_SCENE_PROMPT}",
            size="1024x1536",
            quality="medium",
            input_fidelity="high",
        )
    if not resp.data or not resp.data[0].b64_json:
        raise RuntimeError("Base scene generation returned no image data.")
    with open(base_scene, "wb") as f:
        f.write(base64.b64decode(resp.data[0].b64_json))
    return base_scene


async def _generate_planet_images(client: AsyncOpenAI, concept: dict[str, Any], dirs: dict[str, str]) -> None:
    base_scene = await _generate_base_scene(client, dirs)
    hook_scene = os.path.join(dirs["images"], "scene_00.png")
    if not os.path.exists(hook_scene):
        shutil.copy2(base_scene, hook_scene)

    for idx, spec in enumerate(concept["planet_heights"], start=1):
        out_path = os.path.join(dirs["images"], f"scene_{idx:02d}.png")
        if os.path.exists(out_path):
            continue
        _log_step(f"generating image {idx}/{len(concept['planet_heights'])}")
        prompt = _planet_scene_prompt(spec["planet"], spec["jump_label"])
        try:
            with open(base_scene, "rb") as base_file:
                resp = await client.images.edit(
                    model="gpt-image-1.5",
                    image=base_file,
                    prompt=prompt,
                    size="1024x1536",
                    quality="medium",
                    input_fidelity="high",
                )
            if not resp.data or not resp.data[0].b64_json:
                raise RuntimeError("No image data in planet scene edit response.")
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(resp.data[0].b64_json))
        except Exception:
            fallback_prompt = (
                f"{BASE_SCENE_PROMPT} Through the observation window you can clearly see {spec['planet']}. "
                f"The frog-suit test subject is shown at a jump height of {spec['jump_label']} beside the ruler. "
                "Same side view, same chamber, same launch pad. Photorealistic. NO text anywhere."
            )
            await generate_image_dalle_async(fallback_prompt, out_path, size="1024x1536", quality="medium")


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
        hook_duration = 4
        result = await generate_video_async(
            prompt=HOOK_PROMPT,
            output_path=hook_clip,
            model="veo-3.1-lite-generate-001",
            duration_seconds=hook_duration,
            aspect_ratio="9:16",
            resolution="720p",
            image_path=os.path.join(dirs["images"], "scene_00.png"),
        )
        print(result["path"], flush=True)

    for idx, spec in enumerate(concept["planet_heights"], start=1):
        clip_path = os.path.join(dirs["clips"], f"clip_{idx:02d}.mp4")
        if os.path.exists(clip_path):
            continue
        _log_step(f"animating {spec['planet']}")
        narr_path = os.path.join(dirs["narr"], f"line_{idx:02d}.mp3")
        requested = get_clip_duration(narr_path)
        duration = 4 if requested <= 4 else 6 if requested <= 6 else 8
        result = await generate_video_async(
            prompt=_planet_animation_prompt(spec["planet"], spec["jump_label"]),
            output_path=clip_path,
            model="veo-3.1-lite-generate-001",
            duration_seconds=duration,
            aspect_ratio="9:16",
            resolution="720p",
            image_path=os.path.join(dirs["images"], f"scene_{idx:02d}.png"),
        )
        print(result["path"], flush=True)
        _overlay_label(clip_path, spec["planet"], spec["jump_label"])


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
    final_path = add_subtitles(combined, word_data, seg_starts, OUT_DIR)
    return final_path


async def main() -> None:
    load_dotenv(os.path.join(ROOT, ".env"), override=True)
    concept = _load_concept()
    dirs = _ensure_dirs()
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120.0)
    await _generate_narration(concept, dirs)
    await _generate_planet_images(client, concept, dirs)
    await _animate_scenes(concept, dirs)
    final_path = _build_video(concept, dirs)
    _log_step(f"done -> {final_path}")


if __name__ == "__main__":
    asyncio.run(main())
