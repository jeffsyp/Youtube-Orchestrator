from __future__ import annotations

from collections.abc import Mapping
import re

_STYLE_PREFIX_RE = re.compile(r"^(?P<style>\s*Simple crude cartoon\s*[—-][^.]*\.)\s*", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

_CRABRAVE_GAME_RULES = (
    {
        "terms": ("minecraft",),
        "keywords": ("minecraft", "blocky", "pixelated", "voxel", "cube", "diamond block"),
        "anchor": (
            "Keep Minecraft-inspired voxel design language in EVERY scene: square heads, "
            "rectangular limbs, chunky cube tools, pixelated stone textures, diamond blocks, "
            "and ladder/plank props built from hard-edged blocks. Never drift into rounded "
            "generic human anatomy."
        ),
    },
    {
        "terms": ("roblox",),
        "keywords": ("roblox", "blocky", "plastic", "stud", "toy-brick"),
        "anchor": (
            "Keep Roblox-inspired toy-brick design language in EVERY scene: blocky torsos, "
            "simple limbs, chunky accessories, and stiff modular proportions with plastic-like "
            "surfaces. Never drift into rounded generic human anatomy."
        ),
    },
    {
        "terms": ("halo", "master chief", "spartan"),
        "keywords": ("halo", "master chief", "spartan", "visor", "armor", "unsc"),
        "anchor": (
            "Keep Halo-inspired military sci-fi design language in EVERY scene: bulky angular "
            "power armor, gold visors, hard-edged UNSC props, and metallic battlefield shapes. "
            "Never drift into generic hoodie-cartoon anatomy."
        ),
    },
    {
        "terms": ("fortnite", "battle bus", "llama"),
        "keywords": ("fortnite", "battle bus", "llama", "cartoony battle royale", "pickaxe"),
        "anchor": (
            "Keep Fortnite-inspired design language in EVERY scene: bright stylized game-world "
            "materials, chunky pickaxes, exaggerated outfits, and recognizable battle-royale "
            "prop shapes. Never drift into bland generic cartoon anatomy."
        ),
    },
    {
        "terms": ("mario", "luigi", "bowser", "toad", "goomba"),
        "keywords": ("mario", "luigi", "bowser", "toad", "goomba", "question block", "pipe"),
        "anchor": (
            "Keep Mario-inspired platformer design language in EVERY scene: rounded mascot "
            "silhouettes, bright toy-like props, question blocks, green pipes, and instantly "
            "readable Nintendo-like level geometry."
        ),
    },
    {
        "terms": ("among us", "crewmate", "impostor"),
        "keywords": ("among us", "crewmate", "impostor", "visor", "spacesuit"),
        "anchor": (
            "Keep Among Us-inspired design language in EVERY scene: bean-shaped spacesuits, "
            "single glass visors, simple ship interiors, and clean hard-color silhouettes."
        ),
    },
)


def _normalize_space(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text or "").strip()


def _match_rule(search_space: str) -> tuple[str, tuple[str, ...]] | None:
    haystack = (search_space or "").lower()
    for rule in _CRABRAVE_GAME_RULES:
        if any(term in haystack for term in rule["terms"]):
            return rule["anchor"], tuple(rule["keywords"])
    return None


def _fallback_anchor(first_prompt: str) -> tuple[str, tuple[str, ...]] | None:
    lowered = (first_prompt or "").lower()
    if any(term in lowered for term in ("blocky", "pixelated", "voxel", "cube", "square-headed")):
        return (
            "Keep the same hard-edged game design language in EVERY scene: blocky silhouettes, "
            "chunky props, and world textures that still read as the same game. Never drift into "
            "rounded generic cartoon anatomy.",
            ("blocky", "pixelated", "voxel", "cube", "square"),
        )
    return (
        "Keep the game's signature character silhouettes, props, and environment design cues "
        "visible in EVERY scene so the world is instantly recognizable, not generic cartoon filler.",
        ("signature", "recognizable", "game"),
    )


def _insert_anchor(prompt: str, anchor: str) -> str:
    text = (prompt or "").strip()
    if not text:
        return text

    match = _STYLE_PREFIX_RE.match(text)
    if match:
        style = match.group("style").strip()
        rest = text[match.end():].strip()
        return _normalize_space(f"{style} {anchor} {rest}")
    return _normalize_space(f"{anchor} {text}")


def normalize_game_meme_concept(concept: Mapping | None, *, channel_id: int) -> dict:
    normalized = dict(concept or {})
    if channel_id != 16:
        return normalized

    scenes = normalized.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return normalized

    first_prompt = ""
    if isinstance(scenes[0], Mapping):
        first_prompt = str(scenes[0].get("image_prompt") or "")
    search_space = " ".join(
        [
            str(normalized.get("title") or ""),
            str(normalized.get("brief") or ""),
            first_prompt,
        ]
    )
    anchor_info = _match_rule(search_space) or _fallback_anchor(first_prompt)
    if not anchor_info:
        return normalized

    anchor, keywords = anchor_info
    updated_scenes = []
    for scene in scenes:
        if not isinstance(scene, Mapping):
            updated_scenes.append(scene)
            continue
        scene_dict = dict(scene)
        image_prompt = str(scene_dict.get("image_prompt") or "").strip()
        if image_prompt and anchor.lower() not in image_prompt.lower():
            lowered = image_prompt.lower()
            if not any(keyword in lowered for keyword in keywords):
                scene_dict["image_prompt"] = _insert_anchor(image_prompt, anchor)
            else:
                scene_dict["image_prompt"] = _insert_anchor(image_prompt, anchor)
        updated_scenes.append(scene_dict)

    normalized["scenes"] = updated_scenes
    return normalized
