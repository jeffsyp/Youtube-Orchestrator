"""Auto-generate concept drafts per channel using Claude."""

import asyncio
from collections import Counter
import json
import os
import re

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
from packages.clients.db import get_engine
from packages.utils.hardcore_ranked_language import normalize_hardcore_ranked_concept, normalize_hardcore_ranked_viewer_text

load_dotenv(override=True)
logger = structlog.get_logger()


def _strip_code_block(text: str) -> str:
    """Strip markdown code block fencing from LLM responses."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_nightnight_characters(text: str) -> list[str]:
    """Return known anime character names mentioned in text, in reading order."""
    matches = []
    lowered = text.lower()
    for name, pattern in _NIGHTNIGHT_CHARACTER_PATTERNS:
        for match in pattern.finditer(lowered):
            matches.append((match.start(), name))

    matches.sort(key=lambda item: item[0])
    ordered = []
    seen = set()
    for _, name in matches:
        if name in seen:
            continue
        seen.add(name)
        ordered.append(name)
    return ordered


def _diversify_nightnight_concepts(concepts: list[dict], past_titles: list[str], remaining: int) -> list[dict]:
    """Prefer fresher NightNight concepts instead of repeating the same anchors."""
    if remaining <= 0 or len(concepts) <= remaining:
        return concepts[:remaining]

    recent_titles = past_titles[-60:]
    historical_char_counts = Counter()
    historical_franchise_counts = Counter()
    for title in recent_titles:
        characters = _extract_nightnight_characters(title)
        if not characters:
            continue
        historical_char_counts.update(characters)
        historical_franchise_counts.update(
            {NIGHTNIGHT_CHARACTER_FRANCHISE[character] for character in characters}
        )

    ranked = []
    for idx, concept in enumerate(concepts):
        text_blob = " ".join(
            part for part in [concept.get("title", ""), concept.get("brief", "")]
            if part
        )
        characters = _extract_nightnight_characters(text_blob)
        lead_character = characters[0] if characters else None

        franchises = []
        seen_franchises = set()
        for character in characters:
            franchise = NIGHTNIGHT_CHARACTER_FRANCHISE.get(character)
            if franchise and franchise not in seen_franchises:
                seen_franchises.add(franchise)
                franchises.append(franchise)

        ranked.append({
            "concept": concept,
            "index": idx,
            "characters": characters,
            "lead_character": lead_character,
            "franchises": franchises,
        })

    selected = []
    used_characters = set()
    used_franchises = set()
    selected_overused_leads = 0
    pool = ranked[:]

    while pool and len(selected) < remaining:
        def concept_score(item: dict) -> tuple[int, int, int, int, int, int, int]:
            lead = item["lead_character"]
            franchises = item["franchises"]
            lead_history = historical_char_counts.get(lead, 0) if lead else 0
            franchise_history = sum(historical_franchise_counts.get(franchise, 0) for franchise in franchises)
            fresh_lead = 1 if lead and lead not in used_characters else 0
            fresh_franchise = sum(1 for franchise in franchises if franchise not in used_franchises)
            overused_penalty = 1 if lead in NIGHTNIGHT_OVERUSED_CHARACTERS else 0

            return (
                1 if not overused_penalty else 0,
                1 if not (overused_penalty and selected_overused_leads) else 0,
                fresh_lead,
                fresh_franchise,
                -lead_history,
                -franchise_history,
                -item["index"],
            )

        best = max(pool, key=concept_score)
        selected.append(best["concept"])
        used_characters.update(best["characters"][:2])
        used_franchises.update(best["franchises"])
        if best["lead_character"] in NIGHTNIGHT_OVERUSED_CHARACTERS:
            selected_overused_leads += 1
        pool.remove(best)

    return selected


def _extract_nature_receipts_animals(text: str) -> list[str]:
    """Return canonical animal names mentioned in text, in reading order."""
    matches = []
    lowered = text.lower()
    for alias, canonical in _NATURE_RECEIPTS_ANIMAL_PATTERNS:
        for match in alias.finditer(lowered):
            matches.append((match.start(), canonical))

    matches.sort(key=lambda item: item[0])
    ordered = []
    seen = set()
    for _, canonical in matches:
        if canonical in seen:
            continue
        seen.add(canonical)
        ordered.append(canonical)
    return ordered


def _extract_nature_receipts_target(text: str) -> str | None:
    """Extract the key thing/place/system the animal collides with."""
    lowered = text.lower()
    patterns = [
        r"\bdiscovered(?: it was running)? ([a-z0-9' -]+)$",
        r"\braised by ([a-z0-9' -]+)$",
        r"\binvaded ([a-z0-9' -]+?)(?: and|$)",
        r"\bimprinted on ([a-z0-9' -]+)$",
        r"\bran (?:the )?([a-z0-9' -]+)$",
        r"\bowned ([a-z0-9' -]+)$",
        r"\bruled ([a-z0-9' -]+)$",
        r"\bwanted to ([a-z0-9' -]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        target = re.sub(r"^(a|an|the)\s+", "", match.group(1).strip())
        return target
    return None


def _classify_nature_receipts_scenarios(text: str) -> list[str]:
    """Bucket Nature Receipts concepts by premise engine."""
    lowered = text.lower()
    buckets = []
    if any(phrase in lowered for phrase in [
        "size of", "as tall as", "as big as", "100 feet tall", "mountain", "moon", "skyscraper", "godzilla",
    ]):
        buckets.append("giant_scale")
    if any(phrase in lowered for phrase in [
        "fastest", "supersonic", "cheetah speed", "speed of", "moved at",
    ]):
        buckets.append("super_speed")
    if any(phrase in lowered for phrase in [
        "indestructible", "invisible", "could fly", "could breathe air", "strength of", "as strong as",
        "apex predator", "billionaire",
    ]):
        buckets.append("power_swap")
    if any(phrase in lowered for phrase in [
        "president", "taxes", "wall street", "government", "power grid", "owned an entire country",
        "ran an entire city", "ran the government", "ruled the world", "press conferences",
    ]):
        buckets.append("human_system")
    if any(phrase in lowered for phrase in [
        "raised by", "lived on land", "sahara", "airport", "first class cabin", "fighter jet",
        "construction site", "racetrack", "highway", "grocery store", "shopping mall", "city fountain",
        "downtown", "city", "desert", "bamboo forest",
    ]):
        buckets.append("habitat_collision")
    if any(phrase in lowered for phrase in [
        "invaded", "millions of", "took over", "ran an entire city",
    ]):
        buckets.append("swarm_takeover")
    if any(phrase in lowered for phrase in [
        "imprinted on", "wanted to play", "laser pointer",
    ]):
        buckets.append("obsession")
    if "discovered " in lowered:
        buckets.append("discovery_template")

    return buckets or ["other"]


def _diversify_nature_receipts_concepts(concepts: list[dict], past_titles: list[str], remaining: int) -> list[dict]:
    """Prefer fresher Nature Receipts animals, premise engines, and targets."""
    if remaining <= 0 or len(concepts) <= remaining:
        return concepts[:remaining]

    recent_titles = past_titles[-80:]
    historical_animal_counts = Counter()
    historical_scenario_counts = Counter()
    historical_target_counts = Counter()
    for title in recent_titles:
        animals = _extract_nature_receipts_animals(title)
        target = _extract_nature_receipts_target(title)
        scenarios = _classify_nature_receipts_scenarios(title)
        if animals:
            historical_animal_counts.update(animals[:1])
        historical_scenario_counts.update(scenarios)
        if target:
            historical_target_counts.update([target])

    ranked = []
    for idx, concept in enumerate(concepts):
        text_blob = " ".join(
            part for part in [concept.get("title", ""), concept.get("brief", "")]
            if part
        )
        animals = _extract_nature_receipts_animals(text_blob)
        lead_animal = animals[0] if animals else None
        scenarios = _classify_nature_receipts_scenarios(text_blob)
        target = _extract_nature_receipts_target(text_blob)
        ranked.append({
            "concept": concept,
            "index": idx,
            "lead_animal": lead_animal,
            "scenarios": scenarios,
            "target": target,
            "uses_discovery_template": "discovery_template" in scenarios,
        })

    selected = []
    used_animals = set()
    used_scenarios = set()
    used_targets = set()
    selected_giant_scale = 0
    selected_discovery_template = 0
    pool = ranked[:]

    while pool and len(selected) < remaining:
        def concept_score(item: dict) -> tuple[int, int, int, int, int, int, int, int, int, int]:
            lead_animal = item["lead_animal"]
            scenarios = item["scenarios"]
            target = item["target"]
            animal_history = historical_animal_counts.get(lead_animal, 0) if lead_animal else 0
            scenario_history = sum(historical_scenario_counts.get(scenario, 0) for scenario in scenarios)
            target_history = historical_target_counts.get(target, 0) if target else 0
            fresh_animal = 1 if lead_animal and lead_animal not in used_animals else 0
            fresh_scenario = sum(1 for scenario in scenarios if scenario not in used_scenarios)
            fresh_target = 1 if target and target not in used_targets else 0
            giant_penalty = 1 if "giant_scale" in scenarios and selected_giant_scale else 0
            discovery_penalty = 1 if item["uses_discovery_template"] and selected_discovery_template else 0
            generic_target_penalty = 1 if target in _NATURE_RECEIPTS_GENERIC_TARGETS else 0

            return (
                1 if not item["uses_discovery_template"] else 0,
                1 if "giant_scale" not in scenarios else 0,
                1 if not generic_target_penalty else 0,
                1 if not giant_penalty else 0,
                1 if not discovery_penalty else 0,
                fresh_animal,
                fresh_scenario,
                fresh_target,
                -(animal_history + scenario_history + target_history),
                -item["index"],
            )

        best = max(pool, key=concept_score)
        selected.append(best["concept"])
        if best["lead_animal"]:
            used_animals.add(best["lead_animal"])
        used_scenarios.update(best["scenarios"])
        if best["target"]:
            used_targets.add(best["target"])
        if "giant_scale" in best["scenarios"]:
            selected_giant_scale += 1
        if best["uses_discovery_template"]:
            selected_discovery_template += 1
        pool.remove(best)

    return selected

REPLENISH_INTERVAL = 120  # check every 2 minutes
DRAFTS_PER_CHANNEL = 5
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
_RESEARCH_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output", "research_cache")
NIGHTNIGHT_CHARACTER_FRANCHISE = {
    "naruto": "naruto",
    "sasuke": "naruto",
    "kakashi": "naruto",
    "madara": "naruto",
    "itachi": "naruto",
    "gaara": "naruto",
    "luffy": "one piece",
    "zoro": "one piece",
    "sanji": "one piece",
    "shanks": "one piece",
    "goku": "dragon ball",
    "vegeta": "dragon ball",
    "piccolo": "dragon ball",
    "gohan": "dragon ball",
    "frieza": "dragon ball",
    "saitama": "one punch man",
    "genos": "one punch man",
    "garou": "one punch man",
    "tanjiro": "demon slayer",
    "nezuko": "demon slayer",
    "muzan": "demon slayer",
    "rengoku": "demon slayer",
    "light": "death note",
    "l": "death note",
    "ryuk": "death note",
    "gojo": "jujutsu kaisen",
    "yuji": "jujutsu kaisen",
    "sukuna": "jujutsu kaisen",
    "megumi": "jujutsu kaisen",
    "todo": "jujutsu kaisen",
    "denji": "chainsaw man",
    "makima": "chainsaw man",
    "power": "chainsaw man",
    "aki": "chainsaw man",
    "ichigo": "bleach",
    "aizen": "bleach",
    "rukia": "bleach",
    "eren": "attack on titan",
    "levi": "attack on titan",
    "mikasa": "attack on titan",
    "reiner": "attack on titan",
    "gon": "hunter x hunter",
    "killua": "hunter x hunter",
    "hisoka": "hunter x hunter",
    "meruem": "hunter x hunter",
    "edward elric": "fullmetal alchemist",
    "roy mustang": "fullmetal alchemist",
    "mob": "mob psycho 100",
    "reigen": "mob psycho 100",
    "lelouch": "code geass",
    "frieren": "frieren",
    "fern": "frieren",
    "aqua": "konosuba",
    "subaru": "re:zero",
    "rimuru": "that time i got reincarnated as a slime",
    "jotaro": "jojo's bizarre adventure",
    "dio": "jojo's bizarre adventure",
    "yusuke": "yu yu hakusho",
    "hiei": "yu yu hakusho",
}
NIGHTNIGHT_OVERUSED_CHARACTERS = {
    "goku",
    "gojo",
    "light",
    "luffy",
    "naruto",
    "saitama",
    "tanjiro",
}
_NIGHTNIGHT_CHARACTER_PATTERNS = [
    (name, re.compile(rf"\b{re.escape(name)}\b"))
    for name in sorted(NIGHTNIGHT_CHARACTER_FRANCHISE, key=len, reverse=True)
]
NATURE_RECEIPTS_ANIMAL_ALIASES = {
    "golden retriever": "dog",
    "corgi": "dog",
    "puppy": "dog",
    "dog": "dog",
    "baby duck": "duck",
    "duck": "duck",
    "bunny rabbit": "rabbit",
    "bunny": "rabbit",
    "rabbit": "rabbit",
    "hamster": "hamster",
    "guinea pig": "guinea pig",
    "capybara": "capybara",
    "parrot": "parrot",
    "panda": "panda",
    "penguin": "penguin",
    "sloth": "sloth",
    "turtle": "turtle",
    "hedgehog": "hedgehog",
    "raccoon": "raccoon",
    "otter": "otter",
    "squirrel": "squirrel",
    "cat": "cat",
    "dolphin": "dolphin",
    "frog": "frog",
    "snail": "snail",
    "octopus": "octopus",
    "electric eel": "eel",
    "eel": "eel",
    "mantis shrimp": "shrimp",
    "pistol shrimp": "shrimp",
    "shrimp": "shrimp",
    "spider": "spider",
    "jellyfish": "jellyfish",
    "worm": "worm",
    "bird": "bird",
    "fish": "fish",
}
_NATURE_RECEIPTS_ANIMAL_PATTERNS = [
    (re.compile(rf"\b{re.escape(alias)}\b"), canonical)
    for alias, canonical in sorted(NATURE_RECEIPTS_ANIMAL_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
]
_NATURE_RECEIPTS_GENERIC_TARGETS = {
    "city",
    "downtown",
    "grocery store",
    "highway",
    "shopping mall",
    "rush hour",
    "taxes",
    "wall street",
    "construction site",
    "neighbor's yard",
    "neighbor's fence",
}


def _research_niche(niche: str, max_results: int = 15, form_type: str = "short") -> str:
    """Search YouTube for viral content from small channels in this niche.

    Returns a text block of video titles + view counts to feed into concept generation.
    Uses disk cache (survives worker restarts) to avoid burning YouTube API quota.
    """
    if not YOUTUBE_API_KEY:
        return ""

    # Disk cache — survives worker restarts (YouTube Search = 100 units per call)
    import time as _time
    import hashlib
    video_duration = "medium" if form_type == "long" else "short"
    cache_key = f"{niche.lower().strip()}_{form_type}"
    os.makedirs(_RESEARCH_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(_RESEARCH_CACHE_DIR, hashlib.md5(cache_key.encode()).hexdigest() + ".json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cached = json.load(f)
            if _time.time() - cached.get("timestamp", 0) < 604800:  # 7 days
                logger.info("using cached niche research (disk)", niche=niche)
                return cached.get("result", "")
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        import requests as _req

        # Search for shorts in this niche, sorted by view count
        if form_type == "long":
            search_queries = [
                f"{niche} documentary",
                f"{niche} deep dive",
                f"{niche} explained",
            ]
        else:
            search_queries = [
                f"{niche} #shorts",
                f"{niche} facts #shorts",
            ]

        videos = []
        for query in search_queries:
            resp = _req.get("https://www.googleapis.com/youtube/v3/search", params={
                "key": YOUTUBE_API_KEY,
                "q": query,
                "type": "video",
                "videoDuration": video_duration,
                "order": "viewCount",
                "part": "snippet",
                "maxResults": max_results,
                "publishedAfter": "2025-01-01T00:00:00Z",
            }, timeout=10)
            if resp.status_code != 200:
                continue

            for item in resp.json().get("items", []):
                videos.append({
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                })

        if not videos:
            return ""

        # Get video stats + channel stats to find small channels with big views
        video_ids = [v["id"] for v in videos[:25]]
        stats_resp = _req.get("https://www.googleapis.com/youtube/v3/videos", params={
            "key": YOUTUBE_API_KEY,
            "id": ",".join(video_ids),
            "part": "statistics",
        }, timeout=10)

        if stats_resp.status_code != 200:
            return ""

        stats = {item["id"]: item["statistics"] for item in stats_resp.json().get("items", [])}

        # Get channel subscriber counts
        channel_names = list(set(v["channel"] for v in videos))
        # Search for channels to get their IDs
        viral_from_small = []
        for v in videos:
            s = stats.get(v["id"], {})
            views = int(s.get("viewCount", 0))
            if views > 50000:  # only care about videos that actually went viral
                viral_from_small.append({
                    "title": v["title"],
                    "channel": v["channel"],
                    "views": views,
                })

        # Sort by views descending
        viral_from_small.sort(key=lambda x: x["views"], reverse=True)

        if not viral_from_small:
            return ""

        lines = ["VIRAL SHORTS IN THIS NICHE (use these as inspiration for topics — don't copy titles directly):"]
        for v in viral_from_small[:10]:
            lines.append(f"- \"{v['title']}\" ({v['views']:,} views) — {v['channel']}")

        result = "\n".join(lines)
        # Write to disk cache
        try:
            with open(cache_file, "w") as f:
                json.dump({"timestamp": _time.time(), "result": result, "key": cache_key}, f)
        except Exception:
            pass
        logger.info("niche research complete", niche=niche, viral_found=len(viral_from_small))
        return result

    except Exception as e:
        logger.warning("niche research failed (non-fatal)", error=str(e)[:100])
        return ""


async def _get_youtube_trending(niche: str, channel_name: str) -> str:
    """Use Claude to generate search queries, then YouTube autocomplete to find what people are searching.

    Free, no auth, no quota — runs on every concept generation.
    Returns a text block of trending searches to feed into concept generation.
    """
    import urllib.request
    import urllib.parse

    try:
        from packages.clients.claude import generate

        # Step 1: Ask Claude to brainstorm search queries people in this niche would type
        loop = asyncio.get_event_loop()
        seed_response = await loop.run_in_executor(None, lambda: generate(
            system=f"You generate YouTube search queries for the niche: {niche}",
            prompt=f"""List 12 YouTube search queries that fans of "{channel_name}" ({niche}) would actually type into YouTube search.

Mix these types:
- Direct topic searches ("pokemon vs", "what if earth")
- Question searches ("why does", "how does")
- Trending format searches ("tier list", "who would win")
- Specific character/topic searches relevant to the niche

Return ONLY a JSON array of strings, no markdown:
["query one", "query two", ...]""",
            max_tokens=500,
            model="claude-haiku-4-5-20251001",
        ))

        # Parse seed queries
        try:
            seeds = json.loads(seed_response.strip())
            if not isinstance(seeds, list):
                seeds = []
        except json.JSONDecodeError:
            import re
            match = re.search(r'\[.*\]', seed_response, re.DOTALL)
            if match:
                seeds = json.loads(match.group())
            else:
                seeds = []

        if not seeds:
            return ""

        # Step 2: Hit YouTube autocomplete for each seed query
        all_suggestions = []
        for query in seeds[:12]:
            try:
                url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={urllib.parse.quote(query)}"
                raw = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
                data = json.loads(raw.split("(", 1)[1].rsplit(")", 1)[0])
                for suggestion in data[1][:3]:
                    s = suggestion[0]
                    if s and s != query:
                        all_suggestions.append(s)
            except Exception:
                continue

        if not all_suggestions:
            return ""

        # Deduplicate
        seen = set()
        unique = []
        for s in all_suggestions:
            key = s.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(s)

        lines = ["TRENDING YOUTUBE SEARCHES (people are actively searching for these — use them as inspiration):"]
        for s in unique[:20]:
            lines.append(f"- \"{s}\"")

        result = "\n".join(lines)
        logger.info("youtube trending complete", channel=channel_name, suggestions=len(unique))
        return result

    except Exception as e:
        logger.warning("youtube trending failed (non-fatal)", error=str(e)[:100])
        return ""


def _get_engine():
    return get_engine()


async def generate_drafts_for_channel(channel_id: int, count: int = 5, form_type: str = "short") -> list[int]:
    """Generate concept drafts for a channel. Returns list of new draft IDs."""
    engine = _get_engine()
    try:
        async with AsyncSession(engine) as s:
            # Get channel info
            row = await s.execute(text("""
                SELECT c.name, c.niche, COALESCE(cs.voice_id, 'fIGaHjfrR8KmMy0vGEVJ') as voice_id
                FROM channels c
                LEFT JOIN channel_schedules cs ON cs.channel_id = c.id
                WHERE c.id = :cid
            """), {"cid": channel_id})
            ch = row.fetchone()
            if not ch:
                logger.warning("channel not found", channel_id=channel_id)
                return []

            channel_name, niche, voice_id = ch[0], ch[1], ch[2]

            # Gather past titles (content_bank + concept_drafts + published)
            past = await s.execute(text("""
                SELECT DISTINCT title FROM (
                    SELECT title FROM content_bank WHERE channel_id = :cid
                    UNION ALL
                    SELECT title FROM concept_drafts WHERE channel_id = :cid
                    UNION ALL
                    SELECT a.content::json->>'title' as title
                    FROM assets a
                    JOIN content_runs cr ON cr.id = a.run_id
                    WHERE cr.channel_id = :cid AND a.asset_type = 'publish_metadata'
                ) t WHERE title IS NOT NULL AND title != ''
            """), {"cid": channel_id})
            past_titles = [r[0] for r in past.fetchall()]

        # Research trending content in this niche
        trending = _research_niche(niche, form_type=form_type)

        # Add YouTube autocomplete trending (free, always fresh)
        yt_trending = await _get_youtube_trending(niche, channel_name)
        if yt_trending:
            trending = f"{trending}\n\n{yt_trending}" if trending else yt_trending

        from packages.clients.claude import generate

        from packages.prompts.concept_drafts import KIDS_CHANNELS, MID_LENGTH_CHANNELS, EDUCATIONAL_CHANNELS, WEEKLY_RECAP_CHANNELS, RESEARCH_CHANNELS, SATISFYING_CHANNELS

        if channel_id in RESEARCH_CHANNELS:
            draft_ids = await _generate_research_concepts(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, count, form_type,
            )
        elif channel_id in WEEKLY_RECAP_CHANNELS:
            draft_ids = await _generate_weekly_recap_draft(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, trending=trending,
            )
        elif channel_id in KIDS_CHANNELS:
            draft_ids = await _generate_kids_drafts(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, trending, count,
            )
        elif form_type == "long":
            # Long-form stays narrated
            if channel_id in EDUCATIONAL_CHANNELS:
                draft_ids = await _generate_unified_topic_drafts(
                    engine, channel_id, channel_name, niche, voice_id,
                    past_titles, trending, count, form_type,
                )
            else:
                draft_ids = await _generate_longform_drafts(
                    engine, channel_id, channel_name, niche, voice_id,
                    past_titles, trending, count, form_type,
                )
        else:
            # Schmoney Facts is narration-first in production, so generate reviewed drafts
            # in the same format the builder actually consumes.
            if channel_id == 31:
                draft_ids = await _generate_short_drafts(
                    engine, channel_id, channel_name, niche, voice_id,
                    past_titles, trending, count, form_type,
                )
            else:
                # All other shorts use the scene-first no-narration flow
                draft_ids = await _generate_no_narration_drafts(
                    engine, channel_id, channel_name, niche,
                    past_titles, trending, count,
                )

        logger.info("concept drafts generated", channel=channel_name, count=len(draft_ids),
                     form_type=form_type)
        return draft_ids

    except Exception as e:
        logger.error("concept generation failed", channel_id=channel_id, error=str(e)[:200])
        return []


async def _generate_short_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count, form_type,
) -> list[int]:
    """Generate short-form concept drafts (existing flow)."""
    from packages.prompts.concept_drafts import build_concept_pitches_prompt, build_script_prompt
    from packages.clients.claude import generate

    system, user = build_concept_pitches_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating short pitches", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000))

    pitches = json.loads(resp)
    if not isinstance(pitches, list):
        pitches = [pitches]

    logger.info("phase 1 complete", channel=channel_name, pitches=len(pitches))

    draft_ids = []
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = :ft"
        ), {"cid": channel_id, "ft": form_type})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid_pitches = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    for pitch in valid_pitches:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        structure = pitch.get("structure", "")
        key_facts = pitch.get("key_facts", "")

        logger.info("phase 2: writing script", title=title)

        sys2, usr2 = build_script_prompt(
            channel_name=channel_name,
            niche=niche,
            voice_id=voice_id,
            channel_id=channel_id,
            title=title,
            brief=brief,
            structure=structure,
            key_facts=key_facts,
            format_strategy=pitch.get("format_strategy", "mini_story"),
        )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, form_type)
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _generate_unified_topic_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count, form_type,
) -> list[int]:
    """Generate topics then write scripts adapted to the requested format.

    Same topic pool for both shorts and mid-form. The script is what changes.
    """
    from packages.prompts.concept_drafts import (
        build_unified_topic_prompt,
        build_short_script_from_topic,
        build_midform_script_from_topic,
        MID_LENGTH_CHANNELS,
    )
    from packages.clients.claude import generate

    # Phase 1: Generate format-agnostic topics
    system, user = build_unified_topic_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating topics", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000))

    topics = json.loads(resp)
    if not isinstance(topics, list):
        topics = [topics]

    logger.info("phase 1 complete", channel=channel_name, topics=len(topics))

    # Filter duplicates
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = :ft"
        ), {"cid": channel_id, "ft": form_type})
        current_pending = pending.scalar()
        target = DRAFTS_PER_CHANNEL if form_type == "short" else 2
        remaining = max(0, target - current_pending)

    valid_topics = await _filter_duplicate_pitches(engine, channel_id, topics, remaining)

    # Phase 2: Write scripts — format depends on form_type
    draft_ids = []
    for topic in valid_topics:
        title = topic.get("title", "Untitled")
        brief = topic.get("brief", "")
        key_facts = topic.get("key_facts", "")

        if form_type == "long":
            # Mid-form script
            actual_form = "long"
            logger.info("phase 2: writing mid-form script", title=title)
            sys2, usr2 = build_midform_script_from_topic(
                channel_name=channel_name, niche=niche, voice_id=voice_id,
                channel_id=channel_id, title=title, brief=brief, key_facts=key_facts,
            )
        else:
            # Short script
            actual_form = "short"
            logger.info("phase 2: writing short script", title=title)
            sys2, usr2 = build_short_script_from_topic(
                channel_name=channel_name, niche=niche, voice_id=voice_id,
                channel_id=channel_id, title=title, brief=brief, key_facts=key_facts,
            )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=8000 if actual_form == "long" else 4000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, actual_form)
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _generate_educational_short_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count,
) -> list[int]:
    """Generate educational short-form concept drafts — explainers, not stories."""
    from packages.prompts.concept_drafts import build_educational_shorts_pitches_prompt, build_educational_shorts_script_prompt
    from packages.clients.claude import generate

    system, user = build_educational_shorts_pitches_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating educational short pitches", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000))

    pitches = json.loads(resp)
    if not isinstance(pitches, list):
        pitches = [pitches]

    logger.info("phase 1 complete", channel=channel_name, pitches=len(pitches))

    draft_ids = []
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = 'short'"
        ), {"cid": channel_id})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid_pitches = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    for pitch in valid_pitches:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        structure = pitch.get("structure", "")
        key_facts = pitch.get("key_facts", "")

        logger.info("phase 2: writing educational script", title=title)

        sys2, usr2 = build_educational_shorts_script_prompt(
            channel_name=channel_name,
            niche=niche,
            voice_id=voice_id,
            channel_id=channel_id,
            title=title,
            brief=brief,
            structure=structure,
            key_facts=key_facts,
        )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, "short")
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


def _fetch_weekly_news(news_type: str = "tech") -> tuple[list[dict], str]:
    """Fetch this week's top news. Returns (stories, formatted_block).

    news_type: "tech" for Hacker News, "world" for Reddit world news.
    """
    from datetime import datetime, timedelta
    import urllib.request

    stories = []
    cutoff = datetime.now() - timedelta(days=7)

    if news_type == "world":
        # Reddit world news — no API key needed for top posts
        subreddits = ["worldnews", "news", "geopolitics"]
        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}/top.json?t=week&limit=15"
                req = urllib.request.Request(url, headers={"User-Agent": "globe-dump/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                for post in data.get("data", {}).get("children", []):
                    p = post["data"]
                    created = datetime.fromtimestamp(p.get("created_utc", 0))
                    if created < cutoff:
                        continue
                    stories.append({
                        "title": p.get("title", ""),
                        "score": p.get("score", 0),
                        "num_comments": p.get("num_comments", 0),
                        "source": f"r/{sub}",
                    })
            except Exception as e:
                logger.warning(f"Reddit r/{sub} fetch failed", error=str(e)[:100])
    else:
        # Hacker News for tech
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            with urllib.request.urlopen(url, timeout=10) as resp:
                story_ids = json.loads(resp.read())[:60]

            for sid in story_ids:
                if len(stories) >= 30:
                    break
                try:
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                    with urllib.request.urlopen(item_url, timeout=5) as resp:
                        item = json.loads(resp.read())
                    if not item or item.get("type") != "story":
                        continue
                    created = datetime.fromtimestamp(item.get("time", 0))
                    if created < cutoff:
                        continue
                    stories.append({
                        "title": item.get("title", ""),
                        "score": item.get("score", 0),
                        "num_comments": item.get("descendants", 0),
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.error("HN fetch failed", error=str(e)[:200])
            return [], ""

    # Deduplicate by similar titles
    seen = set()
    unique = []
    for s in stories:
        key = s["title"].lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    stories = unique

    stories.sort(key=lambda s: s["score"], reverse=True)

    date_str = datetime.now().strftime("%B %d, %Y")
    label = "TOP WORLD NEWS" if news_type == "world" else "TOP TECH NEWS"
    lines = [f"{label} THIS WEEK ({date_str}):\n"]
    for i, s in enumerate(stories[:30], 1):
        source = s.get("source", "")
        prefix = f"[{source}] " if source else ""
        lines.append(f"{i}. {prefix}{s['title']} (score: {s['score']}, comments: {s.get('num_comments', 0)})")
    news_block = "\n".join(lines)

    return stories, news_block


async def _generate_research_concepts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, count, form_type,
) -> list[int]:
    """Generate concepts using Claude web search to find genuinely obscure stories."""
    from packages.clients.claude import generate
    from packages.prompts.concept_drafts import build_concept_pitches_prompt, build_script_prompt

    logger.info("researching obscure stories via web search", channel=channel_name)

    # Use Claude with web search to find genuinely unknown stories
    try:
        from anthropic import Anthropic
        client = Anthropic(timeout=60.0)

        past_block = ""
        if past_titles:
            past_block = "\n".join(f"- {t}" for t in past_titles[-50:])

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{
                "role": "user",
                "content": f"""Search the web for {count} genuinely obscure, unknown true stories from history that almost nobody has heard of. I need stories for a YouTube Shorts channel called "{channel_name}" — {niche}.

DO NOT suggest famous stories. If most people would recognize the story, it's too well-known. Search for:
- Obscure declassified government documents
- Forgotten incidents from local newspapers
- Unknown people who did extraordinary things
- Bizarre true events that never made mainstream media
- Strange historical accidents or coincidences

{f'ALREADY USED (do NOT repeat):' + chr(10) + past_block if past_block else ''}

For each story, return:
- title: ALL CAPS clickbait title
- brief: one sentence hook
- key_facts: the SPECIFIC real details (names, dates, places, what happened)

Return as a JSON array. Return ONLY valid JSON, no markdown.""",
            }],
        )

        # Extract text from response
        resp_text = ""
        for block in resp.content:
            if block.type == "text":
                resp_text = block.text.strip()

        resp_text = _strip_code_block(resp_text)

        pitches = json.loads(resp_text)
        if not isinstance(pitches, list):
            pitches = [pitches]

        logger.info("research complete", channel=channel_name, stories=len(pitches))

    except Exception as e:
        logger.error("research failed, falling back to standard generation", error=str(e)[:200])
        # Fall back to standard concept generation
        return await _generate_short_drafts(
            engine, channel_id, channel_name, niche, voice_id,
            past_titles, "", count, form_type,
        )

    # Filter duplicates
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = :ft"
        ), {"cid": channel_id, "ft": form_type})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    # Write scripts for each
    draft_ids = []
    for pitch in valid:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        structure = pitch.get("structure", "")
        key_facts = pitch.get("key_facts", "")

        logger.info("writing script for researched story", title=title)
        sys2, usr2 = build_script_prompt(
            channel_name=channel_name, niche=niche, voice_id=voice_id,
            channel_id=channel_id, title=title, brief=brief,
            structure=structure, key_facts=key_facts,
            format_strategy=pitch.get("format_strategy", "mini_story"),
        )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, form_type)
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _generate_weekly_recap_draft(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending="",
) -> list[int]:
    """Generate all three news formats from one research fetch:
    - Shorts: 3-5 individual story highlights
    - Mid-form (long_form=true but ~3-5 min): deep dive on the biggest story
    - Long-form: weekly recap covering 5-7 stories
    """
    from packages.prompts.concept_drafts import (
        build_weekly_recap_script_prompt,
        build_news_short_script_prompt,
        build_news_deep_dive_prompt,
    )
    from packages.clients.claude import generate
    from datetime import datetime

    # Determine news type based on channel niche
    news_type = "world" if "world" in niche.lower() or "current event" in niche.lower() or "politics" in niche.lower() else "tech"
    logger.info("fetching news", channel=channel_name, type=news_type)
    stories, news_block = _fetch_weekly_news(news_type=news_type)
    if not stories:
        return []

    logger.info("news research complete", stories=len(stories))
    date_str = datetime.now().strftime("%B %d, %Y")
    draft_ids = []

    # Check what we already have pending
    async with AsyncSession(engine) as s:
        short_pending = (await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = 'short'"
        ), {"cid": channel_id})).scalar()
        long_pending = (await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = 'long'"
        ), {"cid": channel_id})).scalar()

    # Get all existing titles for this channel to avoid duplicates
    async with AsyncSession(engine) as s:
        existing = await s.execute(text(
            "SELECT LOWER(title) FROM concept_drafts WHERE channel_id = :cid UNION ALL SELECT LOWER(title) FROM content_bank WHERE channel_id = :cid"
        ), {"cid": channel_id})
        existing_titles = {r[0] for r in existing.fetchall()}

    def _story_already_covered(story_title: str) -> bool:
        """Check if a story has already been covered by fuzzy matching."""
        title_lower = story_title.lower()
        # Check if any significant words overlap with existing titles
        story_words = {w.lower() for w in title_lower.split() if len(w) > 4}
        for existing in existing_titles:
            existing_words = {w.lower() for w in existing.split() if len(w) > 4}
            overlap = story_words & existing_words
            if len(overlap) >= 3:  # 3+ shared significant words = duplicate
                return True
        return False

    # Re-rank stories: boost ones that match YouTube trending searches
    if trending:
        trending_lower = trending.lower()
        for story in stories:
            title_words = {w.lower() for w in story["title"].split() if len(w) > 3}
            # Count how many words from the title appear in trending searches
            matches = sum(1 for w in title_words if w in trending_lower)
            story["trending_boost"] = matches
        # Sort by trending match first, then original score
        stories.sort(key=lambda s: (s.get("trending_boost", 0), s.get("score", 0)), reverse=True)
        boosted = [s for s in stories if s.get("trending_boost", 0) > 0]
        if boosted:
            logger.info("trending-boosted stories", count=len(boosted),
                       top=boosted[0]["title"][:60])

    # 1. SHORTS — individual story highlights (top stories, skip already covered)
    if short_pending < DRAFTS_PER_CHANNEL:
        shorts_needed = min(DRAFTS_PER_CHANNEL - short_pending, 5)
        shorts_generated = 0
        for story in stories:
            if shorts_generated >= shorts_needed:
                break
            if _story_already_covered(story["title"]):
                logger.info("skipping already covered story", story=story["title"][:60])
                continue
            logger.info("generating news short", story=story["title"][:60])
            sys2, usr2 = build_news_short_script_prompt(
                channel_name=channel_name, niche=niche, voice_id=voice_id,
                channel_id=channel_id, story_title=story["title"],
                story_details=f"Score: {story['score']}, Comments: {story['num_comments']}",
            )
            resp = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))
            try:
                concept = json.loads(resp)
                title = concept.get("title", story["title"])
                did = await _insert_draft(engine, channel_id, title, concept, story["title"], "short")
                if did:
                    draft_ids.append(did)
                    shorts_generated += 1
            except json.JSONDecodeError:
                logger.warning("news short JSON parse failed", story=story["title"][:60])

    # 2. DEEP DIVE (mid-form, stored as "long") — biggest story of the week
    if long_pending < 2:
        biggest = stories[0]
        logger.info("generating deep dive", story=biggest["title"][:60])
        sys2, usr2 = build_news_deep_dive_prompt(
            channel_name=channel_name, niche=niche, voice_id=voice_id,
            channel_id=channel_id, story_title=biggest["title"],
            story_details=f"Score: {biggest['score']}, Comments: {biggest['num_comments']}",
            news_block=news_block,
        )
        resp = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=8000))
        try:
            concept = json.loads(resp)
            title = concept.get("title", f"Deep Dive: {biggest['title']}")
            did = await _insert_draft(engine, channel_id, title, concept, f"Deep dive on {biggest['title']}", "long")
            if did:
                draft_ids.append(did)
        except json.JSONDecodeError:
            logger.warning("deep dive JSON parse failed")

        # 3. WEEKLY RECAP (long-form)
        logger.info("generating weekly recap", channel=channel_name)
        sys3, usr3 = build_weekly_recap_script_prompt(
            channel_name=channel_name, niche=niche, voice_id=voice_id,
            channel_id=channel_id, news_block=news_block, duration_minutes=7,
        )
        resp = _strip_code_block(generate(prompt=usr3, system=sys3, model="claude-sonnet-4-6", max_tokens=8000))
        try:
            concept = json.loads(resp)
            title = concept.get("title", f"Ctrl Z The Week — {date_str}")
            did = await _insert_draft(engine, channel_id, title, concept, f"Weekly recap for {date_str}", "long")
            if did:
                draft_ids.append(did)
        except json.JSONDecodeError:
            logger.warning("weekly recap JSON parse failed")

    return draft_ids


async def _generate_longform_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count, form_type,
) -> list[int]:
    """Generate long-form concept drafts with chapter-by-chapter scripting."""
    from packages.prompts.long_form import (
        build_longform_pitches_prompt,
        build_longform_chapter_script_prompt,
    )
    from packages.clients.claude import generate

    # Phase 1: Generate long-form pitches with chapter outlines
    system, user = build_longform_pitches_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating long-form pitches", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=8000))

    pitches = json.loads(resp)
    if not isinstance(pitches, list):
        pitches = [pitches]

    logger.info("phase 1 complete", channel=channel_name, pitches=len(pitches))

    # Filter duplicates
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = :ft"
        ), {"cid": channel_id, "ft": form_type})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid_pitches = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    draft_ids = []
    for pitch in valid_pitches:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        chapters = pitch.get("chapters", [])
        key_facts = pitch.get("key_facts", "")
        open_loops = pitch.get("open_loops", [])

        if not chapters:
            logger.warning("long-form pitch has no chapters, skipping", title=title)
            continue

        logger.info("phase 2: writing chapter scripts", title=title, chapters=len(chapters))

        # Phase 2: Write narration chapter by chapter
        all_narration = []
        previous_summary = ""

        for ch_idx, chapter in enumerate(chapters):
            logger.info("writing chapter", title=title, chapter=ch_idx + 1, of=len(chapters))

            sys2, usr2 = build_longform_chapter_script_prompt(
                channel_name=channel_name,
                niche=niche,
                voice_id=voice_id,
                channel_id=channel_id,
                title=title,
                chapter=chapter,
                chapter_index=ch_idx,
                total_chapters=len(chapters),
                full_outline=chapters,
                previous_narration_summary=previous_summary,
                key_facts=key_facts,
                open_loops=open_loops,
            )

            resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))

            try:
                chapter_result = json.loads(resp2)
            except json.JSONDecodeError:
                logger.warning("chapter script JSON parse failed", title=title, chapter=ch_idx)
                continue

            chapter_lines = chapter_result.get("narration", [])
            # Cap at 8 lines per chapter to prevent runaway scripts
            all_narration.extend(chapter_lines[:8])

            # Build condensed summary of previous chapters for context
            # Keep last 5 lines verbatim, summarize earlier ones
            if len(all_narration) <= 10:
                previous_summary = "\n".join(f"- {line}" for line in all_narration)
            else:
                previous_summary = (
                    f"[{len(all_narration) - 5} earlier lines covering: {', '.join(ch['title'] for ch in chapters[:ch_idx])}]\n"
                    + "\n".join(f"- {line}" for line in all_narration[-5:])
                )

            # Small delay between chapter calls
            await asyncio.sleep(2)

        if not all_narration:
            logger.warning("no narration generated for long-form concept", title=title)
            continue

        logger.info("long-form script complete", title=title, total_lines=len(all_narration))

        # Build the concept JSON
        concept = {
            "title": title,
            "narration": all_narration,
            "caption": brief,
            "tags": [],
            "voice_id": voice_id,
            "channel_id": channel_id,
            "format_version": 2,
            "long_form": True,
            "chapters": chapters,
            "open_loops": open_loops,
        }

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, form_type)
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _generate_midform_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count, form_type,
) -> list[int]:
    """Generate mid-length (3-5 min) concept drafts — single-flow, no chapters."""
    from packages.prompts.concept_drafts import (
        build_midform_pitches_prompt,
        build_midform_script_prompt,
    )
    from packages.clients.claude import generate

    # Phase 1: Generate mid-form pitches
    system, user = build_midform_pitches_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating mid-form pitches", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=6000))

    pitches = json.loads(resp)
    if not isinstance(pitches, list):
        pitches = [pitches]

    logger.info("phase 1 complete", channel=channel_name, pitches=len(pitches))

    # Filter duplicates
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = :ft"
        ), {"cid": channel_id, "ft": form_type})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid_pitches = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    draft_ids = []
    for pitch in valid_pitches:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        flow = pitch.get("flow", "")
        key_facts = pitch.get("key_facts", "")

        logger.info("phase 2: writing mid-form script", title=title)

        # Phase 2: Write full narration in one shot (no chapters)
        sys2, usr2 = build_midform_script_prompt(
            channel_name=channel_name,
            niche=niche,
            voice_id=voice_id,
            channel_id=channel_id,
            title=title,
            brief=brief,
            flow=flow,
            key_facts=key_facts,
        )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=8000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("mid-form script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, form_type)
        if draft_id:
            draft_ids.append(draft_id)

        await asyncio.sleep(2)

    return draft_ids


async def _generate_kids_drafts(
    engine, channel_id, channel_name, niche, voice_id,
    past_titles, trending, count,
) -> list[int]:
    """Generate kids cartoon concept drafts — uses dedicated kids prompts."""
    from packages.prompts.concept_drafts import build_kids_pitches_prompt, build_kids_script_prompt
    from packages.clients.claude import generate

    system, user = build_kids_pitches_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        count=count,
        trending=trending,
    )

    logger.info("phase 1: generating kids pitches", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000))

    pitches = json.loads(resp)
    if not isinstance(pitches, list):
        pitches = [pitches]

    logger.info("phase 1 complete", channel=channel_name, pitches=len(pitches))

    draft_ids = []
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = 'short'"
        ), {"cid": channel_id})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid_pitches = await _filter_duplicate_pitches(engine, channel_id, pitches, remaining)

    for pitch in valid_pitches:
        title = pitch.get("title", "Untitled")
        brief = pitch.get("brief", "")
        structure = pitch.get("structure", "")
        key_facts = pitch.get("key_facts", "")

        logger.info("phase 2: writing kids script", title=title)

        sys2, usr2 = build_kids_script_prompt(
            channel_name=channel_name,
            niche=niche,
            voice_id=voice_id,
            channel_id=channel_id,
            title=title,
            brief=brief,
            structure=structure,
            key_facts=key_facts,
        )

        resp2 = _strip_code_block(generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000))

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("kids script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, "short")
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _generate_no_narration_drafts(
    engine, channel_id, channel_name, niche,
    past_titles, trending, count,
) -> list[int]:
    """Generate no-narration concept drafts (memes, satisfying) in one shot.

    No two-phase needed — Claude returns complete concepts with scenes[].
    """
    from packages.prompts.concept_drafts import build_no_narration_prompt
    from packages.clients.claude import generate

    system, user = build_no_narration_prompt(
        channel_name=channel_name,
        niche=niche,
        past_titles=past_titles,
        channel_id=channel_id,
        count=count,
        trending=trending,
    )

    logger.info("generating no-narration concepts", channel=channel_name, count=count)

    resp = _strip_code_block(generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=6000))

    concepts = json.loads(resp)
    if not isinstance(concepts, list):
        concepts = [concepts]

    logger.info("no-narration concepts generated", channel=channel_name, count=len(concepts))

    # Filter duplicates
    async with AsyncSession(engine) as s:
        pending = await s.execute(text(
            "SELECT count(*) FROM concept_drafts WHERE channel_id = :cid AND status = 'pending' AND form_type = 'short'"
        ), {"cid": channel_id})
        current_pending = pending.scalar()
        remaining = max(0, DRAFTS_PER_CHANNEL - current_pending)

    valid = await _filter_duplicate_pitches(engine, channel_id, concepts, len(concepts))
    if channel_id == 28:
        valid = _diversify_nightnight_concepts(valid, past_titles, remaining)
    elif channel_id == 25:
        valid = _diversify_nature_receipts_concepts(valid, past_titles, remaining)
    else:
        valid = valid[:remaining]

    draft_ids = []
    for concept in valid:
        title = concept.get("title", "Untitled")
        brief = concept.get("brief", "")

        # Ensure required fields
        concept.setdefault("narration_style", "none")
        concept.setdefault("format_version", 2)
        concept.setdefault("channel_id", channel_id)

        if not concept.get("scenes"):
            logger.warning("no-narration concept has no scenes, skipping", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, "short")
        if draft_id:
            draft_ids.append(draft_id)

    return draft_ids


async def _filter_duplicate_pitches(engine, channel_id, pitches, remaining) -> list:
    """Filter out duplicate pitches and respect remaining slot count."""
    valid = []
    async with AsyncSession(engine) as s:
        for pitch in pitches:
            if len(valid) >= remaining:
                break
            title = pitch.get("title", "Untitled")
            dup = await s.execute(text("""
                SELECT id FROM concept_drafts WHERE channel_id = :cid AND LOWER(title) = LOWER(:title)
                UNION ALL
                SELECT id FROM content_bank WHERE channel_id = :cid AND LOWER(title) = LOWER(:title)
            """), {"cid": channel_id, "title": title})
            if dup.fetchone():
                logger.info("skipping duplicate pitch", title=title)
                continue
            valid.append(pitch)
    return valid


async def _insert_draft(engine, channel_id, title, concept, brief, form_type) -> int | None:
    """Insert a concept draft and return its ID."""
    try:
        from packages.utils.concept_formats import apply_format_strategy_defaults

        concept = apply_format_strategy_defaults(concept, form_type=form_type)
        concept = normalize_hardcore_ranked_concept(concept, channel_id=channel_id)
        title = normalize_hardcore_ranked_viewer_text(concept.get("title") or title)
        brief = normalize_hardcore_ranked_viewer_text(concept.get("brief") or brief)
        async with AsyncSession(engine) as s:
            from packages.clients.workflow_state import ensure_concept

            row = await s.execute(text("""
                INSERT INTO concept_drafts (channel_id, title, concept_json, brief, form_type)
                VALUES (:cid, :title, :cjson, :brief, :ft)
                RETURNING id
            """), {
                "cid": channel_id,
                "title": title,
                "cjson": json.dumps(concept),
                "brief": brief,
                "ft": form_type,
            })
            draft_id = row.scalar()
            await ensure_concept(
                channel_id=channel_id,
                title=title,
                concept_json=concept,
                origin="auto",
                status="draft",
                form_type=form_type,
                notes=brief,
                draft_id=draft_id,
                session=s,
            )
            await s.commit()
            logger.info("concept draft created", id=draft_id, title=title, form_type=form_type)
            return draft_id
    except Exception as e:
        logger.error("draft insert failed", title=title, error=str(e)[:100])
        return None


async def run_concept_replenish_loop():
    """Periodically fill each active channel to 5 pending concept drafts."""
    logger.info("concept replenish loop started")

    while True:
        try:
            engine = _get_engine()
            async with AsyncSession(engine) as s:
                # Get active channels with their pending draft counts
                # Short-form replenish
                result = await s.execute(text("""
                    SELECT c.id, c.name,
                           COALESCE(d.cnt, 0) as pending_count
                    FROM channels c
                    JOIN channel_schedules cs ON cs.channel_id = c.id AND cs.paused = false
                    LEFT JOIN (
                        SELECT channel_id, count(*) as cnt
                        FROM concept_drafts WHERE status = 'pending' AND form_type = 'short'
                        GROUP BY channel_id
                    ) d ON d.channel_id = c.id
                    ORDER BY COALESCE(d.cnt, 0) ASC
                """))
                channels = result.fetchall()

                # Long-form replenish
                result_long = await s.execute(text("""
                    SELECT c.id, c.name,
                           COALESCE(d.cnt, 0) as pending_count
                    FROM channels c
                    JOIN channel_schedules cs ON cs.channel_id = c.id AND cs.paused = false
                    LEFT JOIN (
                        SELECT channel_id, count(*) as cnt
                        FROM concept_drafts WHERE status = 'pending' AND form_type = 'long'
                        GROUP BY channel_id
                    ) d ON d.channel_id = c.id
                    ORDER BY COALESCE(d.cnt, 0) ASC
                """))
                channels_long = result_long.fetchall()

            # Replenish short-form concepts
            for ch_id, ch_name, pending in channels:
                deficit = DRAFTS_PER_CHANNEL - pending
                if deficit > 0:
                    logger.info("replenishing concepts", channel=ch_name, deficit=deficit, form_type="short")
                    await generate_drafts_for_channel(ch_id, deficit, form_type="short")
                    await asyncio.sleep(5)

            # Replenish long-form concepts (2 per channel)
            # Skip kids channels — they only produce short-form content
            from packages.prompts.concept_drafts import KIDS_CHANNELS
            LONGFORM_DRAFTS_PER_CHANNEL = 2
            for ch_id, ch_name, pending in channels_long:
                if ch_id in KIDS_CHANNELS:
                    continue
                deficit = LONGFORM_DRAFTS_PER_CHANNEL - pending
                if deficit > 0:
                    logger.info("replenishing concepts", channel=ch_name, deficit=deficit, form_type="long")
                    await generate_drafts_for_channel(ch_id, deficit, form_type="long")
                    await asyncio.sleep(10)  # longer delay — long-form generation is heavier

        except Exception as e:
            logger.error("concept replenish error", error=str(e)[:200])

        await asyncio.sleep(REPLENISH_INTERVAL)
