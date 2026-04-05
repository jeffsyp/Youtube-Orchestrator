"""Direct runner for a Hydraulic Press Satisdefying short.

Bypasses concept generation and injects a pre-built hydraulic press concept,
then runs through the normal pipeline: Sora generation -> prescreen -> render -> QA -> review.
Does NOT upload to YouTube.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import structlog
from sqlalchemy import text

from packages.clients.db import async_session

logger = structlog.get_logger()

CHANNEL_ID = 4  # Satisdefying


async def main():
    # Step 1: Create a content run
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, content_type, current_step) VALUES (:cid, 'running', 'satisdefying', 'manual_concept') RETURNING id"),
            {"cid": CHANNEL_ID},
        )
        run_id = result.scalar_one()
        await session.commit()

    print(f"\n=== Hydraulic Press Satisdefying Short ===")
    print(f"Run #{run_id}")

    # Step 2: Use Claude to generate the concept detail with hydraulic press focus
    from packages.clients.claude import generate

    concept_pitch = {
        "title": "Hydraulic Press vs Crystal Ball",
        "brief": "A massive hydraulic press slowly descends onto a perfect crystal ball sitting on a steel plate. The ball resists, then spectacularly shatters into thousands of glittering fragments that scatter across the dark surface, catching studio light like a galaxy of tiny stars.",
        "caption": "It held on until it couldn't",
        "description": "Hydraulic press meets crystal ball. The pressure builds... and then everything shatters beautifully. #oddlysatisfying #hydraulicpress #satisfying #Shorts",
        "tags": ["oddly satisfying", "hydraulic press", "crystal ball", "crushing", "satisfying", "Shorts"],
        "score": 9.5,
    }

    print(f"Concept: {concept_pitch['title']}")
    print(f"Generating detailed Sora prompts...")

    # Generate detailed Sora prompts using Phase 2
    from packages.prompts.idea_detail import build_detail_prompt
    from apps.orchestrator.feedback_loop import get_accumulated_feedback

    feedback = await get_accumulated_feedback(CHANNEL_ID)

    # Add hydraulic press specific guidance to the detail prompt
    hydraulic_guidance = """

SPECIFIC GUIDANCE FOR THIS CONCEPT:
- This is a HYDRAULIC PRESS video — ONE single continuous clip showing the press descending and crushing the object
- The press should move SLOWLY for maximum tension and satisfaction
- The crystal ball should resist, compress slightly, then SHATTER spectacularly
- Glossy 3D render style with dramatic studio lighting
- Camera angle: slightly low, looking up at the press descending
- The fragments should scatter beautifully, catching light
- Sound: deep mechanical hum of the press, building tension, then explosive crunch and tinkling glass
- This is ONE CLIP — the entire press action from start to shatter in one continuous shot
- Duration should be 8-12 seconds to build proper tension
"""

    def detail_builder(concept, name, niche):
        system, user = build_detail_prompt(concept, name, niche, feedback=feedback)
        system += hydraulic_guidance
        return system, user

    from apps.orchestrator.concept_engine import generate_detailed_prompts

    concept = await generate_detailed_prompts(
        concept=concept_pitch,
        channel_name="Satisdefying",
        channel_niche="AI-generated ASMR satisfying videos",
        detail_prompt_builder=detail_builder,
    )

    print(f"Sora prompts generated: {len(concept.get('sora_prompts', []))} clips")
    print(f"Clip durations: {concept.get('clip_durations', [])}")
    for i, p in enumerate(concept.get("sora_prompts", [])):
        print(f"\n  Clip {i+1}: {p[:150]}...")

    # Store concept
    async with async_session() as session:
        await session.execute(
            text("""INSERT INTO scripts (run_id, channel_id, idea_title, stage, content, word_count)
                   VALUES (:run_id, :channel_id, :title, :stage, :content, :wc)"""),
            {
                "run_id": run_id, "channel_id": CHANNEL_ID,
                "title": concept.get("title", ""), "stage": "final",
                "content": concept.get("caption", ""), "wc": 0,
            },
        )
        # Store as idea too
        await session.execute(
            text("""INSERT INTO ideas (run_id, channel_id, title, hook, angle, target_length_seconds, score, selected)
                   VALUES (:run_id, :channel_id, :title, :hook, :angle, :length, :score, true)"""),
            {
                "run_id": run_id, "channel_id": CHANNEL_ID,
                "title": concept["title"], "hook": concept.get("caption", ""),
                "angle": "satisdefying", "length": 25,
                "score": concept.get("score", 9.5),
            },
        )
        await session.commit()

    # Step 3: Generate Sora clips
    print(f"\n--- Generating Sora clips ---")
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET current_step = 'generate_clips' WHERE id = :run_id"),
            {"run_id": run_id},
        )
        await session.commit()

    from packages.clients.sora import generate_video_async
    from packages.prompts.satisdefying import refine_sora_prompt

    # Get channel config for sora settings
    async with async_session() as session:
        result = await session.execute(
            text("SELECT config FROM channels WHERE id = :id"),
            {"id": CHANNEL_ID},
        )
        row = result.fetchone()
        channel_config = json.loads(row[0]) if row and row[0] else {}

    sora_size = channel_config.get("sora_size", "720x1280")
    sora_prompts = concept.get("sora_prompts", [])
    clip_durations = concept.get("clip_durations", [10] * len(sora_prompts))

    output_dir = f"output/satisdefying_run_{run_id}/clips"
    os.makedirs(output_dir, exist_ok=True)

    clip_paths = []
    for i, prompt in enumerate(sora_prompts):
        refined = refine_sora_prompt(concept, i, len(sora_prompts))
        output_path = os.path.join(output_dir, f"clip_{i:02d}.mp4")
        duration = clip_durations[i] if i < len(clip_durations) else 8

        print(f"  Generating clip {i+1}/{len(sora_prompts)} ({duration}s)...")
        result = await generate_video_async(
            prompt=refined,
            output_path=output_path,
            duration=duration,
            size=sora_size,
            timeout=1200,
        )
        clip_paths.append(result["path"])
        print(f"  Clip {i+1} done: {result['path']}")

    # Store clip info
    async with async_session() as session:
        await session.execute(
            text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                   VALUES (:run_id, :channel_id, :type, :content)"""),
            {
                "run_id": run_id, "channel_id": CHANNEL_ID,
                "type": "satisdefying_clips",
                "content": json.dumps({"clips": clip_paths, "concept_title": concept.get("title")}),
            },
        )
        await session.commit()

    print(f"  All {len(clip_paths)} clips generated")

    # Step 4: Prescreen with Gemini
    print(f"\n--- Prescreening clips with Gemini ---")
    USE_GEMINI = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if USE_GEMINI:
        from packages.clients.gemini import review_video
        from packages.prompts.video_review import build_review_prompt

        reviews = []
        for i, clip_path in enumerate(clip_paths):
            if not os.path.exists(clip_path):
                reviews.append({"clip": i, "passed": False, "reason": "file not found"})
                continue

            review_prompt = build_review_prompt(concept, "Satisdefying", "AI-generated ASMR satisfying videos")
            try:
                response = review_video(clip_path, review_prompt)
                text_resp = response.strip()
                if text_resp.startswith("```"):
                    lines = text_resp.split("\n")
                    start = 1
                    end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                    text_resp = "\n".join(lines[start:end])
                review = json.loads(text_resp)
                review["clip"] = i
                reviews.append(review)
                print(f"  Clip {i+1}: {'PASS' if review.get('passed') else 'FAIL'} (match={review.get('match_score')}, quality={review.get('quality_score')})")
            except Exception as e:
                print(f"  Clip {i+1}: prescreen error ({e}), passing by default")
                reviews.append({"clip": i, "passed": True, "reason": f"error: {str(e)}"})
    else:
        print("  Gemini not configured, skipping prescreen")
        reviews = [{"clip": i, "passed": True, "reason": "skipped"} for i in range(len(clip_paths))]

    # Step 5: Render
    print(f"\n--- Rendering final short ---")
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET current_step = 'render' WHERE id = :run_id"),
            {"run_id": run_id},
        )
        await session.commit()

    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render

    render_output_dir = f"output/satisdefying_run_{run_id}"
    rendered = do_render(
        clips=clip_paths,
        caption_text=concept.get("caption", ""),
        output_dir=render_output_dir,
        music_volume=0.05,
        sora_volume=0.95,
        content_type="satisdefying_short",
        output_filename="satisdefying_short.mp4",
    )

    print(f"  Rendered: {rendered.get('path')}")

    # Store render result
    async with async_session() as session:
        await session.execute(
            text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                   VALUES (:run_id, :channel_id, :type, :content)"""),
            {
                "run_id": run_id, "channel_id": CHANNEL_ID,
                "type": "rendered_satisdefying_short",
                "content": json.dumps(rendered),
            },
        )
        await session.commit()

    # Step 6: QA check
    print(f"\n--- QA check ---")
    import subprocess

    video_path = rendered.get("path")
    dur_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    actual_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    res_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    res_parts = res_result.stdout.strip().split(",") if res_result.stdout.strip() else []
    width = int(res_parts[0]) if len(res_parts) >= 2 else 0
    height = int(res_parts[1]) if len(res_parts) >= 2 else 0

    file_size = os.path.getsize(video_path)
    file_mb = file_size / (1024 * 1024)

    audio_result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True, timeout=10,
    )
    has_audio = bool(audio_result.stdout.strip())

    print(f"  Duration: {actual_duration:.1f}s")
    print(f"  Resolution: {width}x{height}")
    print(f"  File size: {file_mb:.1f}MB")
    print(f"  Audio: {'yes' if has_audio else 'NO — critical for ASMR!'}")

    qa_passed = (8 <= actual_duration <= 59) and (height > width) and (1 <= file_mb <= 500) and has_audio
    print(f"  QA: {'PASSED' if qa_passed else 'FAILED'}")

    # Step 7: Gemini video review
    print(f"\n--- Gemini video review ---")
    if USE_GEMINI:
        review_prompt = f"""Watch this AI-generated ASMR/satisfying YouTube Short and critique it.

Title: {concept.get('title')}
Caption: {concept.get('caption')}

Score 1-10 on:
1. SATISFYING FACTOR: How satisfying is this to watch? Does it trigger that "oddly satisfying" feeling?
2. AUDIO QUALITY: Are there good ASMR sounds? Crunching, slicing, squelching, dripping?
3. VISUAL QUALITY: Macro detail, lighting, textures — does it look premium?
4. CONTINUITY: Do the clips feel connected — same material, lighting, camera?
5. HOOK: Does it grab attention from frame 1?

Return JSON (no markdown):
{{"satisfying_score": 8, "audio_score": 7, "visual_score": 8, "continuity_score": 7, "hook_score": 7, "overall_score": 7.4, "publish_recommendation": "yes/no/maybe", "top_issue": "Biggest problem", "summary": "One sentence verdict", "suggestions": ["Improvement 1", "Improvement 2"], "reviewed": true}}"""

        try:
            response = review_video(video_path, review_prompt)
            text_resp = response.strip()
            if text_resp.startswith("```"):
                lines = text_resp.split("\n")
                start = 1
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                text_resp = "\n".join(lines[start:end])
            review = json.loads(text_resp)
            review["reviewed"] = True

            print(f"  Satisfying: {review.get('satisfying_score')}/10")
            print(f"  Audio: {review.get('audio_score')}/10")
            print(f"  Visual: {review.get('visual_score')}/10")
            print(f"  Continuity: {review.get('continuity_score')}/10")
            print(f"  Hook: {review.get('hook_score')}/10")
            print(f"  Overall: {review.get('overall_score')}/10")
            print(f"  Recommendation: {review.get('publish_recommendation')}")
            print(f"  Summary: {review.get('summary')}")
        except Exception as e:
            print(f"  Review failed: {e}")
            review = {"reviewed": False, "reason": str(e)}

        # Store review
        async with async_session() as session:
            await session.execute(
                text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                       VALUES (:run_id, :channel_id, :type, :content)"""),
                {
                    "run_id": run_id, "channel_id": CHANNEL_ID,
                    "type": "video_review", "content": json.dumps(review),
                },
            )
            await session.commit()

        # Store feedback
        from apps.orchestrator.feedback_loop import store_feedback
        await store_feedback(CHANNEL_ID, review)
    else:
        print("  Gemini not configured, skipping review")

    # Mark run as complete (NOT publishing)
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'completed', completed_at = NOW(), current_step = 'done' WHERE id = :run_id"),
            {"run_id": run_id},
        )
        await session.commit()

    print(f"\n{'='*60}")
    print(f"DONE! Run #{run_id}")
    print(f"Concept: {concept.get('title')}")
    print(f"Video: {rendered.get('path')}")
    print(f"NOT uploaded to YouTube (render only)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
