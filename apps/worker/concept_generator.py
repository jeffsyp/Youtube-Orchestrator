"""Auto-generate concept drafts per channel using Claude."""

import asyncio
import json
import os
import re

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

REPLENISH_INTERVAL = 120  # check every 2 minutes
DRAFTS_PER_CHANNEL = 5
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
_RESEARCH_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "output", "research_cache")


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


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=2, max_overflow=1)


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

        from packages.clients.claude import generate

        from packages.prompts.concept_drafts import NO_NARRATION_CHANNELS, KIDS_CHANNELS

        if channel_id in KIDS_CHANNELS:
            draft_ids = await _generate_kids_drafts(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, trending, count,
            )
        elif channel_id in NO_NARRATION_CHANNELS:
            draft_ids = await _generate_no_narration_drafts(
                engine, channel_id, channel_name, niche,
                past_titles, trending, count,
            )
        elif form_type == "long":
            draft_ids = await _generate_longform_drafts(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, trending, count, form_type,
            )
        else:
            draft_ids = await _generate_short_drafts(
                engine, channel_id, channel_name, niche, voice_id,
                past_titles, trending, count, form_type,
            )

        logger.info("concept drafts generated", channel=channel_name, count=len(draft_ids),
                     form_type=form_type)
        return draft_ids

    except Exception as e:
        logger.error("concept generation failed", channel_id=channel_id, error=str(e)[:200])
        return []
    finally:
        await engine.dispose()


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

    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

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
        )

        resp2 = generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000)
        resp2 = resp2.strip()
        if resp2.startswith("```"):
            resp2 = re.sub(r"^```(?:json)?\s*", "", resp2)
            resp2 = re.sub(r"\s*```$", "", resp2)

        try:
            concept = json.loads(resp2)
        except json.JSONDecodeError:
            logger.warning("script JSON parse failed", title=title)
            continue

        draft_id = await _insert_draft(engine, channel_id, title, concept, brief, form_type)
        if draft_id:
            draft_ids.append(draft_id)

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

    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=8000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

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

            resp2 = generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000)
            resp2 = resp2.strip()
            if resp2.startswith("```"):
                resp2 = re.sub(r"^```(?:json)?\s*", "", resp2)
                resp2 = re.sub(r"\s*```$", "", resp2)

            try:
                chapter_result = json.loads(resp2)
            except json.JSONDecodeError:
                logger.warning("chapter script JSON parse failed", title=title, chapter=ch_idx)
                continue

            chapter_lines = chapter_result.get("narration", [])
            all_narration.extend(chapter_lines)

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

    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

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

        resp2 = generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000)
        resp2 = resp2.strip()
        if resp2.startswith("```"):
            resp2 = re.sub(r"^```(?:json)?\s*", "", resp2)
            resp2 = re.sub(r"\s*```$", "", resp2)

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

    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=6000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

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

    valid = await _filter_duplicate_pitches(engine, channel_id, concepts, remaining)

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
        async with AsyncSession(engine) as s:
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
            await engine.dispose()

            # Replenish short-form concepts
            for ch_id, ch_name, pending in channels:
                deficit = DRAFTS_PER_CHANNEL - pending
                if deficit > 0:
                    logger.info("replenishing concepts", channel=ch_name, deficit=deficit, form_type="short")
                    await generate_drafts_for_channel(ch_id, deficit, form_type="short")
                    await asyncio.sleep(5)

            # Replenish long-form concepts (2 per channel)
            LONGFORM_DRAFTS_PER_CHANNEL = 2
            for ch_id, ch_name, pending in channels_long:
                deficit = LONGFORM_DRAFTS_PER_CHANNEL - pending
                if deficit > 0:
                    logger.info("replenishing concepts", channel=ch_name, deficit=deficit, form_type="long")
                    await generate_drafts_for_channel(ch_id, deficit, form_type="long")
                    await asyncio.sleep(10)  # longer delay — long-form generation is heavier

        except Exception as e:
            logger.error("concept replenish error", error=str(e)[:200])

        await asyncio.sleep(REPLENISH_INTERVAL)
