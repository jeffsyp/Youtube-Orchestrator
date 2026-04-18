from __future__ import annotations

from collections.abc import Mapping

VALID_FORMAT_STRATEGIES = (
    "single_frame",
    "attack_result",
    "mini_story",
    "full_story",
)


FORMAT_STRATEGY_DESCRIPTIONS = {
    "single_frame": "one instantly legible thesis image plus an optional tiny aftermath",
    "attack_result": "a simple setup beat followed by a consequence beat",
    "mini_story": "a short connected escalation with only a few clean beats",
    "full_story": "a step-by-step sequence only because the premise genuinely needs it",
}


FORMAT_STRATEGY_SPECS = {
    "single_frame": {
        "min_lines": 1,
        "max_lines": 2,
        "max_duration": 12.0,
        "min_action_lines": 1,
    },
    "attack_result": {
        "min_lines": 2,
        "max_lines": 4,
        "max_duration": 18.0,
        "min_action_lines": 2,
    },
    "mini_story": {
        "min_lines": 3,
        "max_lines": 5,
        "max_duration": 24.0,
        "min_action_lines": 3,
    },
    "full_story": {
        "min_lines": 5,
        "max_lines": 7,
        "max_duration": 29.0,
        "min_action_lines": 4,
    },
}


def normalize_format_strategy(value: str | None, default: str = "mini_story") -> str:
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in VALID_FORMAT_STRATEGIES:
            return normalized
    return default


def get_format_strategy_spec(strategy: str | None) -> dict[str, float | int]:
    normalized = normalize_format_strategy(strategy)
    return dict(FORMAT_STRATEGY_SPECS[normalized])


def infer_format_strategy(concept: Mapping | None, *, form_type: str = "short") -> str:
    if not isinstance(concept, Mapping):
        concept = {}

    explicit = normalize_format_strategy(concept.get("format_strategy")) if concept.get("format_strategy") else None
    if explicit:
        return explicit

    normalized_form = (form_type or concept.get("form_type") or "short").lower()
    if concept.get("long_form") or normalized_form in {"mid", "midform", "long", "long_form"}:
        return "full_story"

    scenes = concept.get("scenes")
    narration = concept.get("narration")
    beats = concept.get("beats")

    scene_count = len(scenes) if isinstance(scenes, list) else 0
    line_count = len(narration) if isinstance(narration, list) else 0
    beat_count = len(beats) if isinstance(beats, list) else 0

    primary_count = max(scene_count, line_count, beat_count)
    if primary_count <= 1:
        return "single_frame"
    if primary_count <= 3:
        return "attack_result"
    if primary_count <= 5:
        return "mini_story"
    return "full_story"


def apply_format_strategy_defaults(concept: Mapping | None, *, form_type: str = "short") -> dict:
    normalized = dict(concept or {})
    normalized["format_strategy"] = infer_format_strategy(normalized, form_type=form_type)
    return normalized
