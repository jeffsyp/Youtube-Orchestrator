"""Load local channel profile overrides from channels/profiles.json."""

from __future__ import annotations

import json
import os
from functools import lru_cache


PROFILE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "channels",
    "profiles.json",
)


@lru_cache(maxsize=1)
def load_channel_profiles() -> dict[int, dict]:
    if not os.path.exists(PROFILE_PATH):
        return {}
    try:
        with open(PROFILE_PATH) as f:
            raw = json.load(f)
        return {int(key): value for key, value in raw.items()}
    except Exception:
        return {}


def get_channel_profile(channel_id: int) -> dict:
    return load_channel_profiles().get(int(channel_id), {})


def _get_profile_string(channel_id: int, key: str, default: str | None = None) -> str | None:
    profile = get_channel_profile(channel_id)
    value = profile.get(key)
    if isinstance(value, str) and value:
        return value
    return default


def _get_profile_string_list(channel_id: int, key: str, default: list[str] | None = None) -> list[str]:
    profile = get_channel_profile(channel_id)
    value = profile.get(key)
    if isinstance(value, list):
        items = [item for item in value if isinstance(item, str) and item]
        if items:
            return items
    return list(default or [])


def _default_audio_policy_for_draft_mode(draft_mode: str) -> str:
    if draft_mode == "dialogue_short":
        return "native_dialogue"
    if draft_mode in {"no_narration", "satisfying"}:
        return "native_sfx"
    return "voiceover"


def _default_primary_formats_for_draft_mode(draft_mode: str) -> list[str]:
    if draft_mode in {"no_narration", "satisfying"}:
        return ["single_frame", "attack_result"]
    if draft_mode == "dialogue_short":
        return ["attack_result", "mini_story"]
    return ["mini_story", "full_story"]


def get_channel_builder_slug(channel_id: int) -> str | None:
    return _get_profile_string(channel_id, "builder")


def get_channel_video_provider(channel_id: int, *, default: str = "grok") -> str:
    return _get_profile_string(channel_id, "video_provider", default) or default


def get_channel_video_model(channel_id: int, *, default: str | None = None) -> str | None:
    return _get_profile_string(channel_id, "video_model", default)


def get_channel_video_resolution(channel_id: int, *, default: str = "720p") -> str:
    return _get_profile_string(channel_id, "video_resolution", default) or default


def get_channel_category(
    channel_id: int,
    *,
    fallback_map: dict[int, str] | None = None,
    default: str = "Entertainment",
) -> str:
    profile = get_channel_profile(channel_id)
    category = profile.get("category")
    if isinstance(category, str) and category:
        return category
    return (fallback_map or {}).get(int(channel_id), default)


def get_channel_art_style(
    channel_id: int,
    *,
    fallback_map: dict[int, str] | None = None,
    default: str,
) -> str:
    profile = get_channel_profile(channel_id)
    art_style = profile.get("art_style")
    if isinstance(art_style, str) and art_style:
        return art_style
    return (fallback_map or {}).get(int(channel_id), default)


def should_skip_image_review(channel_id: int, *, default: bool = False) -> bool:
    profile = get_channel_profile(channel_id)
    if "skip_image_review" in profile:
        return bool(profile.get("skip_image_review"))
    return default


def get_channel_draft_mode(channel_id: int, *, default: str | None = None) -> str:
    fallback = default if default is not None else "no_narration"
    return _get_profile_string(channel_id, "draft_mode", fallback) or fallback


def get_channel_provider_strategy(channel_id: int, *, default: str = "grok") -> str:
    fallback = get_channel_video_provider(channel_id, default=default)
    return _get_profile_string(channel_id, "provider_strategy", fallback) or fallback


def get_channel_audio_policy(channel_id: int, *, default: str = "voiceover") -> str:
    draft_mode = get_channel_draft_mode(channel_id)
    fallback = default or _default_audio_policy_for_draft_mode(draft_mode)
    if default == "voiceover":
        fallback = _default_audio_policy_for_draft_mode(draft_mode)
    return _get_profile_string(channel_id, "audio_policy", fallback) or fallback


def get_channel_intro_policy(channel_id: int, *, default: str = "cold_open") -> str:
    return _get_profile_string(channel_id, "intro_policy", default) or default


def get_channel_anchor_policy(channel_id: int, *, default: str = "none") -> str:
    return _get_profile_string(channel_id, "anchor_policy", default) or default


def get_channel_primary_formats(channel_id: int, *, default: list[str] | None = None) -> list[str]:
    fallback = default or _default_primary_formats_for_draft_mode(get_channel_draft_mode(channel_id))
    return _get_profile_string_list(channel_id, "primary_formats", fallback)


def get_channel_core_lane(channel_id: int, *, default: str | None = None) -> str:
    fallback = default if default is not None else ""
    return _get_profile_string(channel_id, "core_lane", fallback) or fallback


def get_channel_strategy(channel_id: int) -> dict[str, object]:
    return {
        "draft_mode": get_channel_draft_mode(channel_id),
        "provider_strategy": get_channel_provider_strategy(channel_id),
        "audio_policy": get_channel_audio_policy(channel_id),
        "intro_policy": get_channel_intro_policy(channel_id),
        "anchor_policy": get_channel_anchor_policy(channel_id),
        "primary_formats": get_channel_primary_formats(channel_id),
        "core_lane": get_channel_core_lane(channel_id),
    }
