#!/usr/bin/env python3
"""
Standalone test: overlay sound effects at segment cut points on a final video.

Usage:
    python scripts/test_sfx.py [--run RUN_DIR] [--output OUTPUT_PATH]

Defaults to the most recent run with a final.mp4 and segment files.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = PROJECT_ROOT / "assets" / "sfx"
OUTPUT_DIR = PROJECT_ROOT / "output"

# SFX config: which sound to play at each type of transition
SFX_WHOOSH = SFX_DIR / "whoosh_mixkit.mp3"    # 1.5s - normal transitions
SFX_IMPACT = SFX_DIR / "swoosh_mixkit.mp3"   # 0.2s - final/punchline transition
SFX_DING = SFX_DIR / "el_ding.mp3"           # 0.48s - optional accent

# Volume adjustments (dB relative to original)
WHOOSH_VOL_DB = 15
IMPACT_VOL_DB = 20
DING_VOL_DB = 10


def get_duration(filepath: str) -> float:
    """Get media duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath,
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def find_best_run() -> Path | None:
    """Find the most recent run directory that has both final.mp4 and segment files."""
    runs = sorted(OUTPUT_DIR.glob("run_*"), key=lambda p: int(p.name.split("_")[1]), reverse=True)
    for run_dir in runs:
        final = run_dir / "final.mp4"
        seg_dir = run_dir / "segments"
        if final.exists() and seg_dir.exists():
            segs = sorted(seg_dir.glob("seg_*.mp4"))
            if len(segs) >= 2:
                return run_dir
    return None


def compute_cut_points(segment_dir: Path) -> list[float]:
    """
    Given a directory of seg_0.mp4, seg_1.mp4, ..., return the timestamps
    (in the final video) where each segment ends / next begins.
    """
    segs = sorted(segment_dir.glob("seg_*.mp4"), key=lambda p: int(p.stem.split("_")[1]))
    cut_points = []
    cumulative = 0.0
    for i, seg in enumerate(segs):
        dur = get_duration(str(seg))
        cumulative += dur
        if i < len(segs) - 1:  # don't add a cut after the last segment
            cut_points.append(cumulative)
        print(f"  {seg.name}: {dur:.3f}s  (cumulative: {cumulative:.3f}s)")
    return cut_points


def build_ffmpeg_cmd(
    input_video: str,
    cut_points: list[float],
    output_path: str,
) -> list[str]:
    """
    Build an FFmpeg command that overlays SFX at each cut point.

    Strategy:
    - Use amix/amerge with adelay to position each SFX at the right timestamp
    - The last transition gets an impact sound; others get whoosh
    - All SFX are mixed with the original audio track
    """
    if not cut_points:
        raise ValueError("No cut points found - need at least 2 segments")

    inputs = ["-i", input_video]
    filter_parts = []
    sfx_labels = []

    for i, cp in enumerate(cut_points):
        is_last = (i == len(cut_points) - 1)
        sfx_file = str(SFX_IMPACT) if is_last else str(SFX_WHOOSH)
        vol_db = IMPACT_VOL_DB if is_last else WHOOSH_VOL_DB

        inputs.extend(["-i", sfx_file])
        input_idx = i + 1  # 0 is the main video

        # Position SFX slightly before the cut point for anticipation
        offset_ms = max(0, int((cp - 0.15) * 1000))

        # Apply volume adjustment and delay
        filter_parts.append(
            f"[{input_idx}:a]volume={vol_db}dB,adelay={offset_ms}|{offset_ms}[sfx{i}]"
        )
        sfx_labels.append(f"[sfx{i}]")

    # Mix SFX together first, then overlay on original audio at full volume
    if len(sfx_labels) == 1:
        sfx_mix = sfx_labels[0]
        # Rename single SFX stream
        filter_parts.append(f"{sfx_mix}acopy[sfxmix]")
        sfx_mix = "[sfxmix]"
    else:
        all_sfx = "".join(sfx_labels)
        filter_parts.append(
            f"{all_sfx}amix=inputs={len(sfx_labels)}:duration=longest:normalize=0[sfxmix]"
        )
        sfx_mix = "[sfxmix]"
    # Overlay: original audio at full volume + SFX mixed on top
    filter_parts.append(
        f"[0:a]{sfx_mix}amerge=inputs=2,pan=stereo|c0<c0+c2|c1<c1+c3[aout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",      # no re-encode of video
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    return cmd


def main():
    parser = argparse.ArgumentParser(description="Test SFX overlay on a final video")
    parser.add_argument("--run", type=str, help="Run directory path (e.g. output/run_216)")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR / "test_sfx_output.mp4"))
    args = parser.parse_args()

    # Find the run directory
    if args.run:
        run_dir = Path(args.run)
        if not run_dir.is_absolute():
            run_dir = PROJECT_ROOT / run_dir
    else:
        run_dir = find_best_run()
        if run_dir is None:
            print("ERROR: No suitable run found with final.mp4 and segments/")
            sys.exit(1)

    final_video = run_dir / "final.mp4"
    segment_dir = run_dir / "segments"

    print(f"Run directory: {run_dir}")
    print(f"Final video:   {final_video} ({get_duration(str(final_video)):.3f}s)")
    print(f"Segment dir:   {segment_dir}")
    print()

    # Verify SFX files exist
    for sfx in [SFX_WHOOSH, SFX_IMPACT]:
        if not sfx.exists():
            print(f"ERROR: SFX file missing: {sfx}")
            sys.exit(1)

    # Compute cut points from segment durations
    print("Segments and cut points:")
    cut_points = compute_cut_points(segment_dir)
    print(f"\nCut points (transitions): {[f'{cp:.3f}s' for cp in cut_points]}")
    print(f"  - Whoosh at: {[f'{cp:.3f}s' for cp in cut_points[:-1]]}")
    print(f"  - Impact at: {cut_points[-1]:.3f}s (punchline transition)")
    print()

    # Build and run FFmpeg command
    output_path = args.output
    cmd = build_ffmpeg_cmd(str(final_video), cut_points, output_path)

    print("FFmpeg command:")
    print(" ".join(cmd[:6]) + " ...")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFmpeg STDERR:")
        print(result.stderr)
        sys.exit(1)

    out_dur = get_duration(output_path)
    print(f"Output: {output_path}")
    print(f"Duration: {out_dur:.3f}s")
    print("Done!")


if __name__ == "__main__":
    main()
