from __future__ import annotations

from collections.abc import Mapping
import re

_STYLE_PREFIX_RE = re.compile(r"^(?P<style>\s*Simple crude cartoon\s*[—-][^.]*\.)\s*", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_LEAGUE_KILL_TROPHY_RE = re.compile(
    r"holding a (?:glowing\s+)?(?:doodled\s+)?kill notification trophy",
    re.IGNORECASE,
)
_LEAGUE_GENERIC_TROPHY_RE = re.compile(r"\btrophy\b", re.IGNORECASE)
_LEAGUE_STEAL_AND_RECALL_RE = re.compile(
    r"(?:steal|stole|takes? the kill|kill steal|took the kill).*(?:recall|recalled)|"
    r"(?:recall|recalled).*(?:steal|stole|takes? the kill|kill steal)",
    re.IGNORECASE,
)

_CRABRAVE_GAME_RULES = (
    {
        "name": "league",
        "terms": (
            "league of legends",
            "summoner's rift",
            "baron nashor",
            "rift herald",
            "dragon pit",
            "blue buff",
            "red buff",
            "lane gank",
            "league jungler",
            "mid lane",
            "bot lane",
            "top lane",
            "yasuo",
            "lee sin",
            "ahri",
            "teemo",
            "amumu",
            "master yi",
            "jinx",
            "thresh",
            "lux",
            "ezreal",
            "darius",
            "garen",
        ),
        "keywords": (
            "league of legends",
            "league",
            "summoner's rift",
            "moba",
            "lane",
            "turret",
            "jungle",
            "minimap",
            "health bar",
            "ahri",
            "lee sin",
            "yasuo",
            "teemo",
            "amumu",
        ),
        "anchor": (
            "Keep League of Legends-inspired MOBA design language in EVERY scene: "
            "Summoner's Rift cracked stone lane paths, brush edges, river or jungle "
            "entrances, chunky defense turret bases, doodled minimap and health-bar "
            "cues, and champion silhouettes that read like real League archetypes. "
            "Never drift into generic fantasy forests, campfires, palm trees, random "
            "castle ruins, or treasure-prop filler."
        ),
    },
    {
        "name": "minecraft",
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
        "name": "roblox",
        "terms": ("roblox",),
        "keywords": ("roblox", "blocky", "plastic", "stud", "toy-brick"),
        "anchor": (
            "Keep Roblox-inspired toy-brick design language in EVERY scene: blocky torsos, "
            "simple limbs, chunky accessories, and stiff modular proportions with plastic-like "
            "surfaces. Never drift into rounded generic human anatomy."
        ),
    },
    {
        "name": "halo",
        "terms": ("halo", "master chief", "spartan"),
        "keywords": ("halo", "master chief", "spartan", "visor", "armor", "unsc"),
        "anchor": (
            "Keep Halo-inspired military sci-fi design language in EVERY scene: bulky angular "
            "power armor, gold visors, hard-edged UNSC props, and metallic battlefield shapes. "
            "Never drift into generic hoodie-cartoon anatomy."
        ),
    },
    {
        "name": "fortnite",
        "terms": ("fortnite", "battle bus", "llama"),
        "keywords": ("fortnite", "battle bus", "llama", "cartoony battle royale", "pickaxe"),
        "anchor": (
            "Keep Fortnite-inspired design language in EVERY scene: bright stylized game-world "
            "materials, chunky pickaxes, exaggerated outfits, and recognizable battle-royale "
            "prop shapes. Never drift into bland generic cartoon anatomy."
        ),
    },
    {
        "name": "mario",
        "terms": ("mario", "luigi", "bowser", "toad", "goomba"),
        "keywords": ("mario", "luigi", "bowser", "toad", "goomba", "question block", "pipe"),
        "anchor": (
            "Keep Mario-inspired platformer design language in EVERY scene: rounded mascot "
            "silhouettes, bright toy-like props, question blocks, green pipes, and instantly "
            "readable Nintendo-like level geometry."
        ),
    },
    {
        "name": "among_us",
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


def _match_rule(search_space: str) -> Mapping[str, object] | None:
    haystack = (search_space or "").lower()
    for rule in _CRABRAVE_GAME_RULES:
        if any(term in haystack for term in rule["terms"]):
            return rule
    return None


def _fallback_rule(first_prompt: str) -> Mapping[str, object] | None:
    lowered = (first_prompt or "").lower()
    if any(term in lowered for term in ("blocky", "pixelated", "voxel", "cube", "square-headed")):
        return {
            "name": "fallback_blocky",
            "anchor": (
                "Keep the same hard-edged game design language in EVERY scene: blocky silhouettes, "
                "chunky props, and world textures that still read as the same game. Never drift into "
                "rounded generic cartoon anatomy."
            ),
            "keywords": ("blocky", "pixelated", "voxel", "cube", "square"),
        }
    return {
        "name": "fallback_generic",
        "anchor": (
            "Keep the game's signature character silhouettes, props, and environment design cues "
            "visible in EVERY scene so the world is instantly recognizable, not generic cartoon filler."
        ),
        "keywords": ("signature", "recognizable", "game"),
    }


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


def _build_league_scene_hint(scene: Mapping[str, object]) -> str:
    scene_blob = " ".join(
        str(scene.get(key) or "")
        for key in ("image_prompt", "video_prompt")
    ).lower()

    hints = [
        (
            "Show Summoner's Rift geometry in frame: cracked lane stones, river brush or a "
            "jungle entrance, a doodled minimap corner, and chunky health-bar HUD cues."
        ),
        (
            "Use a specific League silhouette like Ahri tails, Lee Sin's red headband, Yasuo's "
            "topknot, Amumu's bandages, or Teemo's scout cap instead of a generic fantasy adventurer."
        ),
    ]

    if any(term in scene_blob for term in ("gank", "smite", "blue buff", "red buff", "camp", "brush ambush")):
        hints.append(
            "For gank beats, put the champion at a lane-to-jungle choke or brush ambush with camp "
            "stones or river brush visible."
        )

    if any(term in scene_blob for term in ("turret", "tower", "lane", "mid", "top", "bot")):
        hints.append(
            "Keep a stone defense turret base or lane edge in frame so the viewer instantly reads the lane."
        )

    if "recall" in scene_blob:
        hints.append("Show the blue recall ring on the lane near an allied turret base.")

    if any(term in scene_blob for term in ("kill", "stole", "steal", "shutdown", "execute")):
        hints.append(
            "Use doodled kill-feed icons, ping bursts, or gold pop cues instead of trophies or random loot props."
        )

    return " ".join(hints)


def _rewrite_league_prompt_surface(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        return text

    rewritten = _LEAGUE_KILL_TROPHY_RE.sub(
        "with glowing doodled kill-feed icons and gold pop bursts beside him",
        text,
    )
    rewritten = _LEAGUE_GENERIC_TROPHY_RE.sub("kill-feed icon", rewritten)
    return _normalize_space(rewritten)


def _augment_art_style(art_style: str, rule_name: str) -> str:
    text = (art_style or "").strip()
    if not text or rule_name != "league":
        return text

    addon = (
        "League of Legends scenes must still show Summoner's Rift lane, turret, brush, jungle, "
        "minimap, and health-bar cues in the same crude doodle style."
    )
    if addon.lower() in text.lower():
        return text
    return _normalize_space(f"{text} {addon}")


def _looks_like_league_jungle_steal_and_recall(concept: Mapping[str, object]) -> bool:
    title = str(concept.get("title") or "")
    brief = str(concept.get("brief") or "")
    search_space = f"{title} {brief}".lower()
    if "league" not in search_space and "jungler" not in search_space:
        return False
    if not any(term in search_space for term in ("jungler", "gank", "lane")):
        return False
    return bool(_LEAGUE_STEAL_AND_RECALL_RE.search(search_space))


def _build_scene_prompt(style: str, description: str) -> str:
    return _normalize_space(
        f"{style} {description} One speaking character in the foreground. "
        "Background characters allowed as silent silhouettes. NO text anywhere."
    )


def _rewrite_league_jungle_steal_and_recall(concept: Mapping[str, object]) -> dict:
    rewritten = dict(concept)
    style = str(rewritten.get("art_style") or "").strip()
    if not style:
        style = "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic."

    rewritten["format_strategy"] = "mini_story"
    rewritten["scenes"] = [
        {
            "duration": 3,
            "image_prompt": _build_scene_prompt(
                style,
                "Summoner's Rift mid lane from a medium gameplay angle: panicked mid laner in the foreground spam-pinging "
                "toward river brush, cracked stone lane path and allied turret base in frame, low enemy champion barely "
                "alive in the background with an almost-empty health bar and a doodled minimap corner visible.",
            ),
            "video_prompt": (
                "Mid laner spam-pings toward river brush and blurts jung, come mid, he's one, hurry. "
                "Ping spam, spell crackle, minion chatter."
            ),
        },
        {
            "duration": 3,
            "image_prompt": _build_scene_prompt(
                style,
                "Summoner's Rift mid lane at the river choke: jungler exploding out of river brush in the foreground as the "
                "low enemy pops into a kill-feed burst, gold pop icons and damage sparks visible, mid laner reaching in from "
                "the background like the last hit got stolen.",
            ),
            "video_prompt": (
                "Jungler dashes out of brush, snipes the last hit, and laughs easy, easy, I got him. "
                "Dash thump, kill ping, gold pop."
            ),
        },
        {
            "duration": 4,
            "image_prompt": _build_scene_prompt(
                style,
                "Summoner's Rift mid lane under the allied turret: furious mid laner in the foreground pointing at a blue "
                "recall ring while the jungler is already channeling recall in the background with fresh gold pop icons still "
                "floating nearby, lane stones, turret base, and health-bar HUD cues still visible.",
            ),
            "video_prompt": (
                "Mid laner points at the recall ring and blurts wait, you took it and recalled? "
                "Recall hum, awkward silence."
            ),
        },
    ]
    return rewritten


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
    rule = _match_rule(search_space) or _fallback_rule(first_prompt)
    if not rule:
        return normalized

    anchor = str(rule["anchor"])
    keywords = tuple(rule["keywords"])
    rule_name = str(rule.get("name") or "")

    if rule_name == "league" and _looks_like_league_jungle_steal_and_recall(normalized):
        normalized = _rewrite_league_jungle_steal_and_recall(normalized)
        scenes = normalized.get("scenes") if isinstance(normalized.get("scenes"), list) else scenes

    art_style = str(normalized.get("art_style") or "").strip()
    if art_style:
        normalized["art_style"] = _augment_art_style(art_style, rule_name)

    updated_scenes = []
    for scene in scenes:
        if not isinstance(scene, Mapping):
            updated_scenes.append(scene)
            continue
        scene_dict = dict(scene)
        image_prompt = str(scene_dict.get("image_prompt") or "").strip()
        if image_prompt:
            if rule_name == "league":
                image_prompt = _rewrite_league_prompt_surface(image_prompt)
            lowered = image_prompt.lower()
            scene_anchor = anchor
            if rule_name == "league":
                scene_anchor = _normalize_space(f"{scene_anchor} {_build_league_scene_hint(scene_dict)}")
            if scene_anchor.lower() not in lowered:
                if not any(keyword in lowered for keyword in keywords):
                    scene_dict["image_prompt"] = _insert_anchor(image_prompt, scene_anchor)
                else:
                    scene_dict["image_prompt"] = _insert_anchor(image_prompt, scene_anchor)
            elif image_prompt != str(scene_dict.get("image_prompt") or "").strip():
                scene_dict["image_prompt"] = image_prompt
        updated_scenes.append(scene_dict)

    normalized["scenes"] = updated_scenes
    return normalized
