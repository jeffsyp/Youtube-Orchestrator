"""Photorealistic cats doing a viral TikTok dance."""
import asyncio
import json
import os

os.chdir("/home/jeff/youtube-orchestrator")


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.db import async_session
    from sqlalchemy import text
    from apps.orchestrator.activities import mark_run_pending_review

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (2, 'running', 'generate_clips', 'synthzoo') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        output_dir = f"output/synthzoo_run_{run_id}"
        os.makedirs(f"{output_dir}/clips", exist_ok=True)
        clip_path = os.path.abspath(f"{output_dir}/clips/clip_001.mp4")

        prompt = (
            "Vertical 9:16 aspect ratio, photorealistic, cinematic lighting, shallow depth of field. "
            "Three real cats standing upright on their hind legs on a rooftop at golden hour sunset. "
            "The cats are photorealistic — fluffy orange tabby in the center, black tuxedo cat on the left, "
            "white persian cat on the right. "
            "All three cats start dancing in perfect sync like a TikTok dance trend. "
            "They bob their heads to the left together. Then to the right together. "
            "They raise their front paws up in the air and wave them side to side. "
            "They do a hip shimmy moving their bodies left and right. "
            "They spin around in unison. "
            "They strike a final pose — front paws on hips, heads tilted, looking cool. "
            "The sunset glows warm orange behind them. "
            "Smooth continuous motion, viral dance energy, funny and impressive. "
            "The cats look real, not cartoon. Their fur moves naturally. "
            "No text, no watermarks, no UI elements."
        )

        print("Generating cat dance clip (12s)...")
        result = await generate_video_async(
            prompt=prompt,
            output_path=clip_path,
            duration=12,
            size="720x1280",
            timeout=1200,
        )
        print(f"Clip: {result['file_size_bytes']} bytes")

        # Render — no music (user will add viral song manually)
        import subprocess
        final_path = f"{output_dir}/synthzoo_short.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", clip_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            final_path,
        ], capture_output=True)
        print(f"Rendered: {final_path}")

        async with async_session() as session:
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 2, :atype, :content)"),
                {"rid": run_id, "atype": "rendered_synthzoo_short", "content": json.dumps({
                    "status": "rendered", "path": os.path.abspath(final_path),
                    "size_bytes": os.path.getsize(final_path),
                    "content_type": "synthzoo_short",
                })},
            )
            await session.commit()

        await mark_run_pending_review(run_id, {
            "title": "These Cats Hit Every Beat",
            "description": "Three cats. One rooftop. Zero missed beats. #cats #dancing #viral #funny #Shorts",
            "tags": ["cats", "dancing", "viral", "funny", "TikTok", "Shorts"],
            "category": "Pets & Animals",
        })
        print(f"Done! Run #{run_id} in review queue")

    except Exception as e:
        print(f"ERROR: {e}")
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]},
            )
            await session.commit()
        print(f"Run #{run_id} marked as failed")
        raise


asyncio.run(main())
