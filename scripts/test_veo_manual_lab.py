#!/usr/bin/env python3
"""Manual Veo test harness for image/video-driven Veo lab experiments."""

from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv

from packages.clients.veo import generate_video_async

load_dotenv(override=True)


ROOT = "/Users/jeffsyp/Projects/Youtube-Orchestrator"
LAB_DIR = os.path.join(ROOT, "output", "manual_lab", "zoro_vs_killua")
DEFAULT_START = os.path.join(LAB_DIR, "simple_clipA_zoro_onigiri.png")
DEFAULT_END = os.path.join(LAB_DIR, "simple_clipB_killua_down.png")
DEFAULT_OUT = os.path.join(LAB_DIR, "review", "veo_zoro_onigiri_to_killua_down.mp4")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--prompt",
        default=(
            "Anime duel in a ruined stone arena. Start from Zoro from One Piece launching Onigiri. "
            "End with Killua from Hunter x Hunter down on the ground as if the slash just finished him. "
            "One clean causal action beat. Keep both character designs accurate. Strong dust burst, slash force, "
            "and clear aftermath. No text, no camera language."
        ),
    )
    p.add_argument("--start-image", default=DEFAULT_START)
    p.add_argument("--source-video", default="")
    p.add_argument("--end-image", default=DEFAULT_END)
    p.add_argument("--output", default=DEFAULT_OUT)
    p.add_argument("--model", default="veo-3.1-generate-001")
    p.add_argument("--duration", type=int, default=4)
    p.add_argument("--aspect-ratio", default="9:16")
    p.add_argument("--resolution", default="720p")
    p.add_argument(
        "--negative-prompt",
        default=(
            "no extra characters, no text overlays, no split screens, no duplicated limbs, "
            "no blurry smears, no comedic chibi proportions, no photorealism"
        ),
    )
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--generate-audio", action="store_true")
    return p


async def main() -> None:
    args = build_parser().parse_args()
    start_image = args.start_image or None
    source_video = args.source_video or None
    end_image = args.end_image or None
    result = await generate_video_async(
        prompt=args.prompt,
        output_path=args.output,
        model=args.model,
        duration_seconds=args.duration,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        image_path=start_image,
        video_path=source_video,
        last_frame_path=end_image,
        negative_prompt=args.negative_prompt,
        seed=args.seed,
        generate_audio=args.generate_audio,
    )
    print(result["path"])


if __name__ == "__main__":
    asyncio.run(main())
