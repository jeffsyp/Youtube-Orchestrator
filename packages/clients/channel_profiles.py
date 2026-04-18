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


def get_channel_builder_slug(channel_id: int) -> str | None:
    profile = get_channel_profile(channel_id)
    builder = profile.get("builder")
    return builder if isinstance(builder, str) and builder else None


def get_channel_video_provider(channel_id: int, *, default: str = "grok") -> str:
    profile = get_channel_profile(channel_id)
    provider = profile.get("video_provider")
    return provider if isinstance(provider, str) and provider else default


def get_channel_video_model(channel_id: int, *, default: str | None = None) -> str | None:
    profile = get_channel_profile(channel_id)
    model = profile.get("video_model")
    return model if isinstance(model, str) and model else default


def get_channel_video_resolution(channel_id: int, *, default: str = "720p") -> str:
    profile = get_channel_profile(channel_id)
    resolution = profile.get("video_resolution")
    return resolution if isinstance(resolution, str) and resolution else default


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
