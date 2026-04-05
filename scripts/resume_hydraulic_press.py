"""Resume the hydraulic press pipeline from the Sora polling step.

The Sora job was submitted but timed out. This script polls until done,
downloads the video, and finishes the pipeline (render, QA, review).
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import structlog
from sqlalchemy import text

from packages.clients.db import async_session

logger = structlog.get_logger()

RUN_ID = 205
CHANNEL_ID = 4
SORA_VIDEO_ID = "video_69bac6881444819197bb3c02191eb07801fa6cb7c791d6e4"
OUTPUT_PATH = f"output/satisdefying_run_{RUN_ID}/clips/clip_00.mp4"

CONCEPT = {
    "title": "Hydraulic Press vs Crystal Ball",
    "brief": "A massive hydraulic press slowly descends onto a perfect crystal ball sitting on a steel plate. The ball resists, then spectacularly shatters into thousands of glittering fragments.",
    "caption": "It held on until it couldn't",
    "description": "Hydraulic press meets crystal ball. The pressure builds... and then everything shatters beautifully. #oddlysatisfying #hydraulicpress #satisfying #Shorts",
    "tags": ["oddly satisfying", "hydraulic press", "crystal ball", "crushing", "satisfying", "Shorts"],
    "score": 9.5,
    "sora_prompts": ["(already submitted to Sora)"],
    "clip_durations": [12],
}


async def main():
    from packages.clients.sora import _get_client

    client = _get_client()
    print(f"Resuming Run #{RUN_ID} — polling Sora video {SORA_VIDEO_ID}")

    # Poll for completion with no timeout
    start_time = time.time()
    while True:
        video = client.videos.retrieve(SORA_VIDEO_ID)
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] Status: {video.status}, progress: {video.progress}")

        if video.status == "completed":
            print("  Sora generation complete!")
            break
        elif video.status == "failed":
            error = getattr(video, "error", "unknown error")
            print(f"  FAILED: {error}")
            return

        await asyncio.sleep(10)

    # Download the video
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    content = client.videos.download_content(SORA_VIDEO_ID)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(content.read())
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"  Saved: {OUTPUT_PATH} ({file_size / (1024*1024):.1f}MB)")

    clip_paths = [OUTPUT_PATH]

    # Store clip info
    async with async_session() as session:
        await session.execute(
            text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                   VALUES (:run_id, :channel_id, :type, :content)"""),
            {
                "run_id": RUN_ID, "channel_id": CHANNEL_ID,
                "type": "satisdefying_clips",
                "content": json.dumps({"clips": clip_paths, "concept_title": CONCEPT["title"]}),
            },
        )
        await session.commit()

    # Prescreen with Gemini
    print(f"\n--- Prescreening with Gemini ---")
    USE_GEMINI = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    if USE_GEMINI:
        from packages.clients.gemini import review_video
        from packages.prompts.video_review import build_review_prompt

        review_prompt = build_review_prompt(CONCEPT, "Satisdefying", "AI-generated ASMR satisfying videos")
        try:
            response = review_video(OUTPUT_PATH, review_prompt)
            text_resp = response.strip()
            if text_resp.startswith("```"):
                lines = text_resp.split("\n")
                start = 1
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                text_resp = "\n".join(lines[start:end])
            review = json.loads(text_resp)
            print(f"  Clip: {'PASS' if review.get('passed') else 'FAIL'} (match={review.get('match_score')}, quality={review.get('quality_score')})")
        except Exception as e:
            print(f"  Prescreen error ({e}), passing by default")
    else:
        print("  Gemini not configured, skipping")

    # Render
    print(f"\n--- Rendering final short ---")
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET current_step = 'render' WHERE id = :run_id"),
            {"run_id": RUN_ID},
        )
        await session.commit()

    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render

    render_output_dir = f"output/satisdefying_run_{RUN_ID}"
    rendered = do_render(
        clips=clip_paths,
        caption_text=CONCEPT.get("caption", ""),
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
                "run_id": RUN_ID, "channel_id": CHANNEL_ID,
                "type": "rendered_satisdefying_short",
                "content": json.dumps(rendered),
            },
        )
        await session.commit()

    # QA check
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
    print(f"  Audio: {'yes' if has_audio else 'NO'}")

    qa_passed = (8 <= actual_duration <= 59) and (height > width) and (1 <= file_mb <= 500) and has_audio
    print(f"  QA: {'PASSED' if qa_passed else 'FAILED'}")

    # Gemini video review
    print(f"\n--- Gemini video review ---")
    if USE_GEMINI:
        from packages.clients.gemini import review_video

        review_prompt = f"""Watch this AI-generated ASMR/satisfying YouTube Short and critique it.

Title: {CONCEPT.get('title')}
Caption: {CONCEPT.get('caption')}

Score 1-10 on:
1. SATISFYING FACTOR: How satisfying is this to watch?
2. AUDIO QUALITY: Are there good ASMR sounds?
3. VISUAL QUALITY: Macro detail, lighting, textures?
4. CONTINUITY: Do the clips feel connected?
5. HOOK: Does it grab attention from frame 1?

Return JSON (no markdown):
{{"satisfying_score": 8, "audio_score": 7, "visual_score": 8, "continuity_score": 7, "hook_score": 7, "overall_score": 7.4, "publish_recommendation": "yes/no/maybe", "top_issue": "...", "summary": "...", "suggestions": ["..."], "reviewed": true}}"""

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
            if review.get("suggestions"):
                print(f"  Suggestions:")
                for s in review["suggestions"]:
                    print(f"    - {s}")

            # Store review
            async with async_session() as session:
                await session.execute(
                    text("""INSERT INTO assets (run_id, channel_id, asset_type, content)
                           VALUES (:run_id, :channel_id, :type, :content)"""),
                    {
                        "run_id": RUN_ID, "channel_id": CHANNEL_ID,
                        "type": "video_review", "content": json.dumps(review),
                    },
                )
                await session.commit()

            from apps.orchestrator.feedback_loop import store_feedback
            await store_feedback(CHANNEL_ID, review)
        except Exception as e:
            print(f"  Review failed: {e}")
    else:
        print("  Gemini not configured, skipping")

    # Mark complete
    async with async_session() as session:
        await session.execute(
            text("UPDATE content_runs SET status = 'completed', completed_at = NOW(), current_step = 'done' WHERE id = :run_id"),
            {"run_id": RUN_ID},
        )
        await session.commit()

    print(f"\n{'='*60}")
    print(f"DONE! Run #{RUN_ID}")
    print(f"Concept: {CONCEPT['title']}")
    print(f"Video: {rendered.get('path')}")
    print(f"NOT uploaded to YouTube (render only)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
