"""Concept proposal endpoints — 3-stage flow: concept → art → video.

Stage 1: Propose concept (script/idea) → pending → approve → generates art
Stage 2: Review art (DALL-E frames) → art_review → approve-art → starts pipeline
Stage 3: Video generation (Sora) → creates run
"""

import base64
import json
import os

import structlog
from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlalchemy import text

from packages.clients.db import async_session
from apps.api.schemas import ExecuteConceptResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["concepts"])


@router.get("/concepts")
async def list_concepts(status: str = "pending"):
    """List proposed concepts by status: pending, generating_art, art_review, approved, rejected."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT pc.id, pc.channel_id, c.name as channel_name, pc.title,
                    pc.concept_json, pc.status, pc.created_at, pc.run_id, pc.reference_frames
                    FROM proposed_concepts pc
                    JOIN channels c ON c.id = pc.channel_id
                    WHERE pc.status = :status
                    ORDER BY pc.id DESC"""),
            {"status": status},
        )
        rows = result.fetchall()

    return [
        {
            "id": r[0],
            "channel_id": r[1],
            "channel_name": r[2],
            "title": r[3],
            "concept": json.loads(r[4]) if isinstance(r[4], str) else r[4],
            "status": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
            "run_id": r[7],
            "reference_frames": r[8] if r[8] else None,
        }
        for r in rows
    ]


@router.post("/concepts")
async def propose_concept(concept: dict, skip_review: bool = False):
    """Propose a new concept for review."""
    title = concept.get("title", "Untitled")
    channel_id = concept.get("channel_id", 1)

    async with async_session() as session:
        result = await session.execute(
            text("SELECT id FROM channels WHERE id = :id"),
            {"id": channel_id},
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    # Claude concept review
    review = None
    if not skip_review:
        review = _review_concept(concept)
        if review.get("verdict") == "reject":
            return {
                "id": None,
                "title": title,
                "status": "rejected_by_review",
                "review": review,
            }

    # Sora prompt review — auto-fixes prompts for known failure modes
    sora_review = None
    if not skip_review:
        sora_review = _review_sora_prompts(concept)

    async with async_session() as session:
        concept_to_store = concept.copy()
        if review:
            concept_to_store["_concept_review"] = review
        if sora_review:
            concept_to_store["_sora_review"] = sora_review

        result = await session.execute(
            text("""INSERT INTO proposed_concepts (channel_id, title, concept_json, status)
                    VALUES (:cid, :title, :concept, 'pending') RETURNING id"""),
            {"cid": channel_id, "title": title, "concept": json.dumps(concept_to_store)},
        )
        concept_id = result.scalar_one()
        await session.commit()

    return {
        "id": concept_id, "title": title, "status": "pending",
        "review": review, "sora_review": sora_review,
    }


@router.post("/concepts/{concept_id}/approve")
async def approve_concept(concept_id: int, background_tasks: BackgroundTasks):
    """Stage 1 → Stage 2: Approve concept, generate DALL-E reference frames."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id, concept_json, status FROM proposed_concepts WHERE id = :id"),
            {"id": concept_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")
    if row[2] != "pending":
        raise HTTPException(status_code=400, detail=f"Concept is '{row[2]}', not pending")

    concept = json.loads(row[1]) if isinstance(row[1], str) else row[1]
    clips = concept.get("clips", [])

    # Check if clips already have image_path (pre-generated frames)
    has_frames = all(clip.get("image_path") for clip in clips)

    if has_frames:
        # Frames already exist — go straight to art_review
        frame_paths = [clip["image_path"] for clip in clips]
        async with async_session() as session:
            await session.execute(
                text("UPDATE proposed_concepts SET status = 'art_review', reference_frames = :frames WHERE id = :id"),
                {"id": concept_id, "frames": json.dumps(frame_paths)},
            )
            await session.commit()
        return {"id": concept_id, "status": "art_review", "message": "Frames already exist, ready for art review"}

    # No frames — generate them with DALL-E in the background
    async with async_session() as session:
        await session.execute(
            text("UPDATE proposed_concepts SET status = 'generating_art' WHERE id = :id"),
            {"id": concept_id},
        )
        await session.commit()

    background_tasks.add_task(_generate_reference_frames, concept_id, concept)
    return {"id": concept_id, "status": "generating_art", "message": "Generating DALL-E reference frames"}


@router.post("/concepts/{concept_id}/approve-art")
async def approve_art(concept_id: int, engine: str = "sora"):
    """Stage 2 → Stage 3: Approve art, start the video pipeline with chosen engine."""
    async with async_session() as session:
        result = await session.execute(
            text("""SELECT pc.id, pc.channel_id, c.name, pc.concept_json, pc.status, pc.reference_frames
                    FROM proposed_concepts pc
                    JOIN channels c ON c.id = pc.channel_id
                    WHERE pc.id = :id"""),
            {"id": concept_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")
    if row[4] not in ("art_review", "pending"):
        raise HTTPException(status_code=400, detail=f"Concept is '{row[4]}', expected art_review or pending")

    concept = json.loads(row[3]) if isinstance(row[3], str) else row[3]
    channel_id = row[1]
    channel_name = row[2]
    frame_paths = row[5] if row[5] else []

    # Attach frame paths to clips (if any) and set video engine
    clips = concept.get("clips", [])
    if frame_paths:
        if isinstance(frame_paths, str):
            frame_paths = json.loads(frame_paths)
        for i, clip in enumerate(clips):
            if i < len(frame_paths):
                clip["image_path"] = frame_paths[i]
    concept["clips"] = clips
    concept["video_engine"] = engine

    # Create run
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type) VALUES (:cid, 'running', 'unified') RETURNING id"),
            {"cid": channel_id},
        )
        run_id = result.scalar_one()

        # Store publish_metadata early
        metadata = json.dumps({
            "title": concept.get("title", "Untitled"),
            "description": concept.get("caption", ""),
            "tags": concept.get("tags", []),
            "category": "Entertainment",
        })
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :cid, :type, :content)"),
            {"rid": run_id, "cid": channel_id, "type": "publish_metadata", "content": metadata},
        )

        await session.execute(
            text("UPDATE proposed_concepts SET status = 'approved', resolved_at = NOW(), run_id = :rid WHERE id = :id"),
            {"rid": run_id, "id": concept_id},
        )
        await session.commit()

    # Run pipeline directly as background task
    from apps.orchestrator.direct_pipeline import run_pipeline
    import asyncio

    def _run_bg():
        asyncio.run(run_pipeline(run_id, concept))

    from fastapi.concurrency import run_in_threadpool
    import threading
    threading.Thread(target=_run_bg, daemon=True).start()

    return ExecuteConceptResponse(
        run_id=run_id,
        workflow_id=f"direct-run-{run_id}",
        channel_name=channel_name,
    )


@router.post("/concepts/{concept_id}/reject")
async def reject_concept(concept_id: int):
    """Reject a concept at any stage."""
    async with async_session() as session:
        result = await session.execute(
            text("SELECT status FROM proposed_concepts WHERE id = :id"),
            {"id": concept_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Concept {concept_id} not found")

    async with async_session() as session:
        await session.execute(
            text("UPDATE proposed_concepts SET status = 'rejected', resolved_at = NOW() WHERE id = :id"),
            {"id": concept_id},
        )
        await session.commit()

    return {"id": concept_id, "status": "rejected"}


def _generate_reference_frames(concept_id: int, concept: dict):
    """Generate Grok reference frames for each clip. Runs in background."""
    import asyncio
    asyncio.run(_generate_reference_frames_async(concept_id, concept))


async def _generate_reference_frames_async(concept_id: int, concept: dict):
    """Generate Grok Imagine frames (one per clip) and update concept to art_review."""
    from dotenv import load_dotenv
    load_dotenv()
    import requests as req
    from openai import OpenAI

    xai_key = os.getenv("XAI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    clips = concept.get("clips", [])
    title_slug = concept.get("title", "concept").replace(" ", "_").lower()[:30]
    output_dir = f"output/concept_refs/{concept_id}_{title_slug}"
    os.makedirs(output_dir, exist_ok=True)

    # Match reference generator to video engine
    video_engine = concept.get("video_engine", "sora")

    # Generate ONE reference image for the entire video (first clip's prompt)
    # This locks the style consistently across all clips
    first_prompt = clips[0].get("prompt", "") if clips else ""
    frame_prompt = f"Generate a single high-quality reference frame for this animated video. This image will define the art style for the entire video. Vertical 9:16 composition: {first_prompt}"
    ref_path = os.path.join(output_dir, "style_reference.png")

    frame_paths = []
    try:
        if video_engine == "grok" and xai_key:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            result = client.images.generate(model="grok-imagine-image", prompt=frame_prompt, n=1)
            url = result.data[0].url
            if url:
                r = req.get(url)
                with open(ref_path, "wb") as f:
                    f.write(r.content)
        elif openai_key:
            client = OpenAI(api_key=openai_key)
            result = client.images.generate(model="gpt-image-1", prompt=frame_prompt, size="1024x1536", quality="high", n=1)
            data = base64.b64decode(result.data[0].b64_json)
            with open(ref_path, "wb") as f:
                f.write(data)
    except Exception as e:
        logger.warning("reference frame generation failed", error=str(e)[:100])

    # Use the SAME reference for all clips
    abs_ref = os.path.abspath(ref_path) if os.path.exists(ref_path) else None
    frame_paths = [abs_ref] * len(clips)

    # Update concept with frames and move to art_review
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=1)
    async with sessionmaker(engine, class_=AsyncSession)() as session:
        await session.execute(
            text("UPDATE proposed_concepts SET status = 'art_review', reference_frames = :frames WHERE id = :id"),
            {"id": concept_id, "frames": json.dumps(frame_paths)},
        )
        await session.commit()


def _review_sora_prompts(concept: dict) -> dict:
    """Use Claude to review prompts, decide clip structure, enforce 3-second hook, and fix Sora issues."""
    from packages.clients.claude import generate

    clips = concept.get("clips", [])
    clip_text = ""
    for i, clip in enumerate(clips):
        clip_text += f"\nClip {i+1} (duration={clip.get('duration', 'auto')}): {clip.get('prompt', '')}"

    prompt = f"""You are a Sora 2 Pro video generation expert AND a YouTube Shorts scriptwriter. Review this concept and FIX issues.

TITLE: {concept.get('title', '')}
CLIPS ({len(clips)} total):{clip_text}

CHECK THESE IN ORDER:

**1. 3-SECOND HOOK (MOST IMPORTANT)**
Does the FIRST 3 seconds of clip 1 immediately show the viewer what this video is about and why they should watch? If clip 1 starts with someone walking, standing, or any unclear/slow action — REJECT and rewrite. The hook must be the most exciting/funny/shocking visual moment.
BAD: "Character walks down a hallway" / "Character stands in a room"
GOOD: "Character is MID-AIR being launched" / "Explosion with character reacting"

**2. CLIP STRUCTURE**
Should this concept be 1 clip or multiple clips? Decide based on:
- Same location + continuous action = 1 clip (use Sora 2 Pro 20s)
- Different locations or major scene changes = multiple clips (use Sora 2, 8-12s each)
- If the current clip count is wrong, suggest the correct structure
Include your reasoning.

**3. SORA FAILURE MODES**
- No small actions (phone swiping, button pressing, reading text)
- Do NOT include quoted dialogue in prompts — dialogue is handled by speech bubble overlays, not Sora
- Max 2-3 characters per scene
- Describe results directly, not cause-and-effect chains
- Use visible physical actions, not internal states
- Anchor style description at the START of every prompt

**4. BEAT TIMING**
For single-clip videos, beats should be timed (Beat 1 0-5s, Beat 2 5-10s, etc.) to guide Sora. Each beat should have ONE clear action. Don't cram too many actions into one beat.

Return JSON (no markdown):
{{
  "hook_ok": true/false,
  "hook_issue": "what's wrong with the hook if not ok",
  "recommended_clips": 1 or 2 or 3,
  "clip_reasoning": "why this many clips",
  "issues_found": ["list of specific problems"],
  "fixed_clips": [
    {{"index": 0, "original_issue": "what was wrong", "fixed_prompt": "the corrected prompt"}},
  ],
  "summary": "one sentence overall assessment"
}}

Only include clips in fixed_clips that actually needed changes."""

    try:
        response = generate(
            prompt=prompt,
            system="You are a Sora 2 prompt engineer. Fix prompts to avoid known failure modes. Return only JSON.",
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
        )
        import re
        text_resp = response.strip()
        if text_resp.startswith("```"):
            text_resp = re.sub(r"^```(?:json)?\s*", "", text_resp)
            text_resp = re.sub(r"\s*```$", "", text_resp)
        result = json.loads(text_resp)

        # Auto-apply fixes to the concept
        fixed_clips = result.get("fixed_clips", [])
        if fixed_clips:
            clips = concept.get("clips", [])
            for fix in fixed_clips:
                idx = fix.get("index", -1)
                if 0 <= idx < len(clips) and fix.get("fixed_prompt"):
                    clips[idx]["prompt"] = fix["fixed_prompt"]
            concept["clips"] = clips

        return result
    except Exception as e:
        return {"issues_found": [], "summary": f"Review failed: {str(e)[:200]}", "fixed_clips": []}


def _review_concept(concept: dict) -> dict:
    """Use Claude to review a concept against production rules."""
    from packages.clients.claude import generate

    clips = concept.get("clips", [])
    has_dialogue = any(clip.get("dialogue") for clip in clips)
    has_narration = any(clip.get("narration") for clip in clips)
    clip_descriptions = ""
    for i, clip in enumerate(clips):
        clip_descriptions += f"\nClip {i+1}: label={clip.get('label','')}"
        if clip.get("narration"):
            clip_descriptions += f"\n  Narration: {clip.get('narration', '')}"
        if clip.get("dialogue"):
            clip_descriptions += f"\n  Dialogue (speech bubbles): {clip['dialogue']}"
        clip_descriptions += f"\n  Prompt: {clip.get('prompt', '')[:500]}"

    format_note = ""
    if has_dialogue and not has_narration:
        format_note = """
FORMAT: This is a DIALOGUE-ONLY video using speech bubble overlays (like manga/comics).
There is NO narration — all story is told through speech bubbles burned onto the video.
This is a VALID format. Do NOT reject for missing narration."""

    prompt = f"""Review this YouTube Shorts concept against these production rules. Be strict.

CONCEPT: {concept.get('title', 'Untitled')}
CLIPS ({len(clips)} total):{clip_descriptions}
{format_note}

RULES TO CHECK:

1. HOOK: Does clip 1 start with the wildest/most interesting visual? Or is it a boring setup?

2. CLIP COUNT: Does the number of clips match the content?
   - Single satisfying moment (hydraulic press, one event) = 1 clip
   - Educational explainer (multiple stages/facts) = 3-5 clips
   - Story/POV (escalating scenario) = 2-4 clips
   - Comedy skit with dialogue = 2-3 clips

3. NARRATION/DIALOGUE: If narration is present, is it short and punchy? If dialogue is present (speech bubbles), does it tell the story clearly? Videos can use EITHER narration OR dialogue — not both required.

4. ENDING: Does the last clip have a satisfying punchline or full-circle moment?

5. SORA COMPATIBILITY: Does each prompt describe a single visual scene?

6. LABELS: Clip 1 label can be the title for comedy/skit content. Subsequent labels short (1-3 words).

IMPORTANT RULES FOR REVIEWING:
- Only reject for SERIOUS issues that would make the video unwatchable
- Minor style preferences are NOT rejection-worthy
- Prompts shown may appear truncated but they ARE complete
- Single-clip satisfying/press videos are a DIFFERENT format — they do NOT need complex hooks or narrative endings
- Dialogue-only videos (speech bubbles, no narration) are a VALID format — do NOT reject for missing narration
- 2-clip comedy skits are valid if the setup and payoff are clear
- Judge each concept by its OWN format, not by rules for a different format

Return JSON (no markdown):
{{
  "verdict": "pass" or "reject",
  "issues": ["only list SERIOUS problems"],
  "suggestions": ["constructive improvements"],
  "summary": "one sentence overall assessment"
}}"""

    try:
        response = generate(
            prompt=prompt,
            system="You are a YouTube Shorts production reviewer. Be strict but constructive. Return only JSON.",
            model="claude-sonnet-4-20250514",
            max_tokens=500,
        )
        import re
        text_resp = response.strip()
        if text_resp.startswith("```"):
            text_resp = re.sub(r"^```(?:json)?\s*", "", text_resp)
            text_resp = re.sub(r"\s*```$", "", text_resp)
        return json.loads(text_resp)
    except Exception as e:
        return {"verdict": "pass", "error": str(e)[:200], "summary": "Review failed, passing through"}
