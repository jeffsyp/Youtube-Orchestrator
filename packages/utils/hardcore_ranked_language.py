"""Helpers for normalizing Hardcore Ranked user-facing copy and draft quality."""

from __future__ import annotations

import copy
import re


_HARDCORE_MEASUREMENT_FAMILY_RE = re.compile(
    r"\b(liquid|fluid|gel|slurry|mercury|honey|water|nitrogen|oil|acid|metal|material|armor|bullet|projectile|penetration|cavitation)\b",
    re.IGNORECASE,
)
_HARDCORE_SMALL_UNIT_RE = re.compile(
    r"\b("
    r"inches?|feet|foot|ft|centimeters?|millimeters?|cm|mm|seconds?|milliseconds?|ms"
    r")\b",
    re.IGNORECASE,
)
_HARDCORE_PRECISION_SHELL_RE = re.compile(
    r"\b("
    r"how many|how much|how long|how fast|how far|stop(?:s|ping)?|slow(?:s|ing)?|halt(?:s|ing)?|penetrat(?:e|es|ion)"
    r")\b",
    re.IGNORECASE,
)
_HARDCORE_VISUAL_OUTCOME_RE = re.compile(
    r"\b("
    r"survive(?:s|d)?|last(?:s|ed|ing)?|melts?|burn(?:s|ed|ing)?|crush(?:es|ed|ing)?|"
    r"explode(?:s|d|ing)?|launch(?:es|ed|ing)?|escape(?:s|d|ing)?|reach(?:es|ed|ing)?|"
    r"break(?:s|ing)?|shatter(?:s|ed|ing)?|snap(?:s|ped|ping)?|sink(?:s|ing)?|"
    r"capsize(?:s|d|ing)?|freeze(?:s|d|ing)?|collapse(?:s|d|ing)?|exits?|"
    r"burn through|melt through|tear(?:s|ing)? through"
    r")\b",
    re.IGNORECASE,
)
_HARDCORE_BALLISTIC_PRECISION_RE = re.compile(
    r"\bbullet\b.*\b(liquid|fluid|gel|slurry|mercury|honey|water|nitrogen|cavitation|penetration)\b|"
    r"\b(liquid|fluid|gel|slurry|mercury|honey|water|nitrogen|cavitation|penetration)\b.*\bbullet\b",
    re.IGNORECASE,
)


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


def hardcore_ranked_pitch_rejection_reason(pitch: dict | None, *, channel_id: int) -> str | None:
    """Return a human-readable rejection reason for weak Hardcore Ranked pitches."""
    if channel_id != 26 or not isinstance(pitch, dict):
        return None

    title = str(pitch.get("title") or "")
    brief = str(pitch.get("brief") or "")
    structure = str(pitch.get("structure") or "")
    key_facts = str(pitch.get("key_facts") or "")
    text_blob = " ".join(part for part in [title, brief, structure, key_facts] if part).strip()
    lowered = text_blob.lower()

    if _HARDCORE_BALLISTIC_PRECISION_RE.search(text_blob):
        return (
            "ballistic/liquid rankings depend on tiny penetration-distance differences that are hard "
            "to read instantly in a Shorts test rig"
        )

    small_unit_mentions = len(_HARDCORE_SMALL_UNIT_RE.findall(text_blob))
    has_measurement_family = bool(_HARDCORE_MEASUREMENT_FAMILY_RE.search(text_blob))
    has_precision_shell = bool(_HARDCORE_PRECISION_SHELL_RE.search(text_blob))
    has_visual_outcome = bool(_HARDCORE_VISUAL_OUTCOME_RE.search(text_blob))

    if (
        small_unit_mentions >= 2
        and has_measurement_family
        and has_precision_shell
        and not has_visual_outcome
    ):
        return (
            "the payoff depends on subtle unit-by-unit measurement differences instead of an instantly "
            "legible visual outcome"
        )

    if (
        "same test rig" in lowered or "same bullet" in lowered or "same gun" in lowered
    ) and small_unit_mentions >= 2 and has_measurement_family:
        return (
            "the repeated rig would force viewers to compare tiny internal differences instead of obvious "
            "success or failure states"
        )

    return None
