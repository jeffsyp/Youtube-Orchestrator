"""Helpers for normalizing Hardcore Ranked user-facing copy."""

from __future__ import annotations

import copy
import re


def normalize_hardcore_ranked_viewer_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    patterns = [
        (r"(?i)\byou(?:[\s-]+suit)? guy\b", "you"),
        (r"(?i)\byou(?:[\s-]+suit)? jumper\b", "you"),
        (r"(?i)\byou(?:[\s-]+suit)? athlete\b", "you"),
        (r"(?i)\bthe frog(?:[\s-]+suit)? guy\b", "you"),
        (r"(?i)\bfrog(?:[\s-]+suit)? guy\b", "you"),
        (r"(?i)\bthe frog(?:[\s-]+suit)? jumper\b", "you"),
        (r"(?i)\bfrog(?:[\s-]+suit)? jumper\b", "you"),
        (r"(?i)\bthe frog(?:[\s-]+suit)? athlete\b", "you"),
        (r"(?i)\bfrog(?:[\s-]+suit)? athlete\b", "you"),
        (r"(?i)\bthe frog(?:[\s-]+suit)? mascot\b", "you"),
        (r"(?i)\bfrog(?:[\s-]+suit)? mascot\b", "you"),
        (r"(?i)\bthe frog(?:-suit)? guy\b", "you"),
        (r"(?i)\bfrog(?:-suit)? guy\b", "you"),
        (r"(?i)\bthe frog(?:-suit)? jumper\b", "you"),
        (r"(?i)\bfrog(?:-suit)? jumper\b", "you"),
        (r"(?i)\bthe frog(?:-suit)? athlete\b", "you"),
        (r"(?i)\bfrog(?:-suit)? athlete\b", "you"),
        (r"(?i)\bthe frog(?:-suit)? mascot\b", "you"),
        (r"(?i)\bfrog(?:-suit)? mascot\b", "you"),
        (r"(?i)\bthe frog(?:-suit)?\b", "you"),
        (r"(?i)\bfrog(?:-suit)?\b", "you"),
        (r"(?i)\bthe skeleton athlete\b", "you"),
        (r"(?i)\bskeleton athlete\b", "you"),
        (r"(?i)\bthe skeleton mascot\b", "you"),
        (r"(?i)\bskeleton mascot\b", "you"),
        (r"(?i)\bthe skeleton\b", "you"),
        (r"(?i)\bskeleton\b", "you"),
        (r"(?i)\bjumper\b", "you"),
    ]
    for pattern, replacement in patterns:
        cleaned = re.sub(pattern, replacement, cleaned)

    grammar_fixes = {
        r"(?i)\byou is\b": "you are",
        r"(?i)\byou was\b": "you were",
        r"(?i)\byou has\b": "you have",
        r"(?i)\byou does\b": "you do",
        r"(?i)\byou gets\b": "you get",
        r"(?i)\byou jumps\b": "you jump",
        r"(?i)\byou runs\b": "you run",
        r"(?i)\byou swims\b": "you swim",
        r"(?i)\byou survives\b": "you survive",
        r"(?i)\byou melts\b": "you melt",
        r"(?i)\byou explodes\b": "you explode",
        r"(?i)\byou breaks\b": "you break",
        r"(?i)\byou falls\b": "you fall",
        r"(?i)\byou sinks\b": "you sink",
        r"(?i)\byou flies\b": "you fly",
        r"(?i)\byou lands\b": "you land",
        r"(?i)\byou goes\b": "you go",
        r"(?i)\byou turns\b": "you turn",
        r"(?i)\byou walks\b": "you walk",
        r"(?i)\byou bounces\b": "you bounce",
    }
    for pattern, replacement in grammar_fixes.items():
        cleaned = re.sub(pattern, replacement, cleaned)

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def normalize_hardcore_ranked_concept(concept: dict, *, channel_id: int) -> dict:
    """Normalize Hardcore Ranked user-facing concept copy to second person."""
    normalized = copy.deepcopy(concept) if isinstance(concept, dict) else {}
    if channel_id != 26 or not isinstance(normalized, dict):
        return normalized

    for key in ("title", "brief", "structure", "key_facts", "caption"):
        if isinstance(normalized.get(key), str):
            normalized[key] = normalize_hardcore_ranked_viewer_text(normalized[key])

    if isinstance(normalized.get("narration"), list):
        normalized["narration"] = [
            normalize_hardcore_ranked_viewer_text(line) if isinstance(line, str) else line
            for line in normalized["narration"]
        ]

    return normalized
