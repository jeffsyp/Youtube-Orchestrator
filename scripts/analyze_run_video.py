#!/usr/bin/env python3
"""Build a scene-by-scene audit bundle for a rendered run.

This is a local operator tool for strict Shorts review. It does not try to
"judge" the video automatically. Instead, it generates the exact artifacts
we want for human/assistant review:

- full-video dense frame sheets
- per-line scene sheets aligned to narration timing
- clip triptychs (start / mid / end)
- a JSON + Markdown timeline that maps narration lines to sub-actions/clips

Usage:
    python3 scripts/analyze_run_video.py 1471
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageOps
except Exception:  # pragma: no cover - best effort local tool
    Image = None
    ImageDraw = None
    ImageOps = None


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _duration(path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    return float(result.stdout.strip())


def _format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _load_json(path: Path):
    return json.loads(path.read_text())


def _extract_frame(video_path: Path, timestamp: float, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(timestamp, 0.0):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


def _sample_times(start: float, end: float, count: int) -> list[float]:
    if count <= 1 or end <= start:
        return [start]
    if end - start < 0.25:
        return [start + (end - start) / 2.0]
    margin = min(0.08, (end - start) / 10.0)
    usable_start = start + margin
    usable_end = max(usable_start, end - margin)
    if math.isclose(usable_start, usable_end):
        return [usable_start]
    return [
        usable_start + (usable_end - usable_start) * idx / (count - 1)
        for idx in range(count)
    ]


def _render_sheet(
    image_specs: list[tuple[Path, str]],
    output_path: Path,
    cols: int,
    thumb_size: tuple[int, int] = (270, 480),
) -> None:
    if Image is None or ImageDraw is None or ImageOps is None:
        return

    rows = math.ceil(len(image_specs) / cols)
    cell_w, cell_h = thumb_size
    caption_h = 50
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + caption_h)), "white")

    for idx, (image_path, caption) in enumerate(image_specs):
        row = idx // cols
        col = idx % cols
        base_x = col * cell_w
        base_y = row * (cell_h + caption_h)

        cell = Image.new("RGB", (cell_w, cell_h + caption_h), "#f2f2f2")
        img = Image.open(image_path).convert("RGB")
        img = ImageOps.contain(img, (cell_w - 12, cell_h - 12))
        cell.paste(img, ((cell_w - img.width) // 2, 6))
        draw = ImageDraw.Draw(cell)
        draw.text((10, cell_h + 12), caption, fill="black")
        sheet.paste(cell, (base_x, base_y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def _build_line_timeline(run_dir: Path, narration_lines: list[str]) -> tuple[list[dict], dict[int, list[dict]]]:
    word_path = run_dir / "word_timestamps.json"
    narr_dir = run_dir / "narration"
    seg_dir = run_dir / "segments"

    word_data = _load_json(word_path) if word_path.exists() else []
    words_by_line: dict[int, list[dict]] = defaultdict(list)
    for word in word_data:
        words_by_line[int(word["line"])].append(word)

    teaser_path = seg_dir / "teasers.mp4"
    if teaser_path.exists():
        teaser_duration = _duration(teaser_path)
    else:
        teaser_duration = _duration(narr_dir / "line_00.mp3")

    segment_durations: list[float] = []
    for idx in range(len(narration_lines)):
        seg_path = seg_dir / f"seg_{idx:02d}.mp4"
        if seg_path.exists():
            segment_durations.append(_duration(seg_path))
            continue

        fallback = _duration(narr_dir / f"line_{idx:02d}.mp3") if (narr_dir / f"line_{idx:02d}.mp3").exists() else 3.0
        if idx == len(narration_lines) - 1:
            fallback += 0.6
        segment_durations.append(fallback)

    seg_starts = [0.0]
    current = teaser_duration
    for idx in range(1, len(narration_lines)):
        seg_starts.append(current)
        overlap = 0.4 if idx < len(narration_lines) - 1 else 0.0
        current += max(segment_durations[idx] - overlap, 0.0)

    line_timeline: list[dict] = []
    for idx, line in enumerate(narration_lines):
        local_words = words_by_line.get(idx, [])
        if local_words:
            local_start = min(float(word["start"]) for word in local_words)
            local_end = max(float(word["end"]) for word in local_words)
        else:
            local_start = 0.0
            local_end = _duration(narr_dir / f"line_{idx:02d}.mp3") if (narr_dir / f"line_{idx:02d}.mp3").exists() else 0.0

        abs_start = seg_starts[idx] + local_start
        abs_end = seg_starts[idx] + local_end
        line_timeline.append(
            {
                "line": idx,
                "text": line,
                "local_start": round(local_start, 3),
                "local_end": round(local_end, 3),
                "start": round(abs_start, 3),
                "end": round(abs_end, 3),
                "duration": round(max(abs_end - abs_start, 0.0), 3),
                "segment_start": round(seg_starts[idx], 3),
                "segment_duration": round(segment_durations[idx], 3),
            }
        )

    return line_timeline, words_by_line


def _build_sub_action_map(run_dir: Path) -> dict[int, list[dict]]:
    plan_path = run_dir / "images" / "plan.json"
    sub_actions_by_line: dict[int, list[dict]] = defaultdict(list)
    if not plan_path.exists():
        return sub_actions_by_line

    plan = _load_json(plan_path)
    for idx, sub_action in enumerate(plan):
        line_idx = int(sub_action.get("line", 0))
        clip_name = f"sub_{idx:03d}.mp4"
        sub_actions_by_line[line_idx].append(
            {
                "sub_action": idx,
                "clip_name": clip_name,
                "new_scene": bool(sub_action.get("new_scene", True)),
                "duration": sub_action.get("duration"),
                "chain_rule": sub_action.get("chain_rule"),
                "image_prompt": sub_action.get("image_prompt"),
                "animation_prompt": sub_action.get("animation_prompt"),
            }
        )
    return sub_actions_by_line


def _extract_dense_frames(video_path: Path, audit_dir: Path, fps: int, frames_per_sheet: int) -> list[Path]:
    dense_dir = audit_dir / "dense_frames"
    if dense_dir.exists():
        shutil.rmtree(dense_dir)
    dense_dir.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps},scale=270:-1",
            str(dense_dir / "frame_%03d.jpg"),
        ]
    )
    frames = sorted(dense_dir.glob("frame_*.jpg"))
    if Image is None:
        return frames

    for chunk_start in range(0, len(frames), frames_per_sheet):
        chunk = frames[chunk_start:chunk_start + frames_per_sheet]
        specs = []
        for local_idx, frame_path in enumerate(chunk):
            absolute_idx = chunk_start + local_idx
            timestamp = absolute_idx / float(fps)
            specs.append((frame_path, f"{frame_path.stem}  {_format_time(timestamp)}"))
        _render_sheet(
            specs,
            audit_dir / f"dense_sheet_{chunk_start // frames_per_sheet + 1:02d}.jpg",
            cols=4,
        )
    return frames


def _extract_line_sheets(
    video_path: Path,
    audit_dir: Path,
    line_timeline: list[dict],
    frames_per_line: int,
) -> list[dict]:
    line_dir = audit_dir / "lines"
    if line_dir.exists():
        shutil.rmtree(line_dir)
    line_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[dict] = []
    for line_info in line_timeline:
        line_idx = line_info["line"]
        times = _sample_times(line_info["start"], line_info["end"], frames_per_line)
        specs = []
        extracted = []
        for frame_idx, timestamp in enumerate(times):
            frame_path = line_dir / f"line_{line_idx:02d}_{frame_idx:02d}.jpg"
            _extract_frame(video_path, timestamp, frame_path)
            specs.append((frame_path, _format_time(timestamp)))
            extracted.append(str(frame_path))

        sheet_path = line_dir / f"line_{line_idx:02d}_sheet.jpg"
        if Image is not None:
            _render_sheet(specs, sheet_path, cols=min(3, len(specs)))

        outputs.append(
            {
                "line": line_idx,
                "sheet_path": str(sheet_path),
                "frame_paths": extracted,
            }
        )
    return outputs


def _extract_clip_triptychs(run_dir: Path, audit_dir: Path) -> str | None:
    clips_dir = run_dir / "clips"
    triptych_dir = audit_dir / "clip_triptychs"
    if triptych_dir.exists():
        shutil.rmtree(triptych_dir)
    triptych_dir.mkdir(parents=True, exist_ok=True)

    specs = []
    for clip_path in sorted(clips_dir.glob("sub_*.mp4")):
        clip_duration = _duration(clip_path)
        key_times = [0.1, clip_duration / 2.0, max(clip_duration - 0.12, 0.1)]
        panel_paths = []
        for idx, timestamp in enumerate(key_times):
            frame_path = triptych_dir / f"{clip_path.stem}_{idx}.jpg"
            _extract_frame(clip_path, timestamp, frame_path)
            panel_paths.append(frame_path)

        if Image is None:
            continue

        row_sheet = triptych_dir / f"{clip_path.stem}_triptych.jpg"
        row_specs = list(zip(panel_paths, ["start", "mid", "end"]))
        _render_sheet(row_specs, row_sheet, cols=3, thumb_size=(190, 350))
        specs.append((row_sheet, clip_path.stem))

    if Image is None or not specs:
        return None

    output_path = audit_dir / "clip_triptych_sheet.jpg"
    _render_sheet(specs, output_path, cols=1, thumb_size=(600, 390))
    return str(output_path)


def _write_markdown(
    audit_dir: Path,
    run_id: int,
    title: str,
    final_duration: float,
    line_timeline: list[dict],
    sub_actions_by_line: dict[int, list[dict]],
    line_sheet_info: list[dict],
    clip_triptych_sheet: str | None,
) -> Path:
    sheet_lookup = {entry["line"]: entry for entry in line_sheet_info}
    lines = [
        f"# Run {run_id} Scene Audit",
        "",
        f"- Title: {title}",
        f"- Final duration: {_format_time(final_duration)}",
        f"- Clip triptychs: {clip_triptych_sheet or 'not generated'}",
        "",
    ]

    for line_info in line_timeline:
        line_idx = line_info["line"]
        lines.append(f"## Line {line_idx}")
        lines.append(f"- Time: {_format_time(line_info['start'])} -> {_format_time(line_info['end'])}")
        lines.append(f"- Narration: {line_info['text']}")
        lines.append(f"- Line sheet: {sheet_lookup[line_idx]['sheet_path']}")
        actions = sub_actions_by_line.get(line_idx, [])
        if actions:
            clip_names = ", ".join(action["clip_name"] for action in actions)
            lines.append(f"- Planned clips: {clip_names}")
            for action in actions:
                lines.append(
                    f"- Sub-action {action['sub_action']}: image=`{action.get('image_prompt', '')}` | animation=`{action.get('animation_prompt', '')}`"
                )
        else:
            lines.append("- Planned clips: none found")
        lines.append("")

    output_path = audit_dir / "scene_audit.md"
    output_path.write_text("\n".join(lines))
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a scene-by-scene audit bundle for a rendered run.")
    parser.add_argument("run_id", type=int, help="Run id, e.g. 1471")
    parser.add_argument("--fps", type=int, default=4, help="Dense full-video sampling rate")
    parser.add_argument("--frames-per-line", type=int, default=6, help="Frames to sample per narration line")
    parser.add_argument("--frames-per-dense-sheet", type=int, default=24, help="Frames per dense sheet")
    args = parser.parse_args()

    run_dir = OUTPUT_DIR / f"run_{args.run_id}"
    video_path = run_dir / "final.mp4"
    concept_path = run_dir / "concept_snapshot.json"
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}", file=sys.stderr)
        return 1
    if not video_path.exists():
        print(f"Final video not found: {video_path}", file=sys.stderr)
        return 1
    if not concept_path.exists():
        print(f"Concept snapshot not found: {concept_path}", file=sys.stderr)
        return 1

    concept = _load_json(concept_path)
    narration_lines = concept.get("narration", [])
    title = concept.get("title", f"Run {args.run_id}")
    audit_dir = run_dir / "review_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    line_timeline, _ = _build_line_timeline(run_dir, narration_lines)
    sub_actions_by_line = _build_sub_action_map(run_dir)
    _extract_dense_frames(video_path, audit_dir, args.fps, args.frames_per_dense_sheet)
    line_sheet_info = _extract_line_sheets(video_path, audit_dir, line_timeline, args.frames_per_line)
    clip_triptych_sheet = _extract_clip_triptychs(run_dir, audit_dir)

    audit_payload = {
        "run_id": args.run_id,
        "title": title,
        "final_video": str(video_path),
        "final_duration": round(_duration(video_path), 3),
        "line_timeline": line_timeline,
        "sub_actions_by_line": sub_actions_by_line,
        "line_sheet_info": line_sheet_info,
        "clip_triptych_sheet": clip_triptych_sheet,
    }
    json_path = audit_dir / "scene_audit.json"
    json_path.write_text(json.dumps(audit_payload, indent=2))

    md_path = _write_markdown(
        audit_dir,
        args.run_id,
        title,
        _duration(video_path),
        line_timeline,
        sub_actions_by_line,
        line_sheet_info,
        clip_triptych_sheet,
    )

    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
