"""Test hyper-detailed stick figure prompt."""
import asyncio
import json
import os

# Ensure we're in the project directory
os.chdir("/home/jeff/youtube-orchestrator")

async def main():
    from packages.clients.sora import generate_video_async, _extract_last_frame
    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render
    from apps.orchestrator.activities import mark_run_pending_review
    from packages.clients.db import async_session
    from sqlalchemy import text

    # Get style ref from run 261 — inline extraction with absolute paths
    import subprocess, base64
    src = "/home/jeff/youtube-orchestrator/output/yeah_thats_clean_run_262/clips/clip_00.mp4"
    frame_tmp = "/tmp/style_ref_frame.png"
    print(f"Source exists: {os.path.exists(src)}")
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", "thumbnail", "-vframes", "1", "-update", "1", frame_tmp], capture_output=True)
    if not os.path.exists(frame_tmp):
        print("ERROR: No frame ref")
        return
    with open(frame_tmp, "rb") as f:
        ref = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
    os.remove(frame_tmp)
    print("Style ref OK")

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        await _run_pipeline(run_id, ref, async_session, text)
    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]},
            )
            await session.commit()
        print(f"Run #{run_id} marked as failed")
        raise


async def _run_pipeline(run_id, ref, async_session, text):
    from packages.clients.sora import generate_video_async
    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render
    from apps.orchestrator.activities import mark_run_pending_review

    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)

    # Clip 1: Power-up — every beat spelled out
    clip1 = os.path.abspath(f"{output_dir}/clips/clip_001.mp4")
    print("Clip 1: Power-up (12s)...")
    r1 = await generate_video_async(
        prompt=(
            "Stick figure animation style, simple black stick figures on clean minimal white background, "
            "sharp clean lines, colored effects. "
            "A small black stick figure stands on the left. A large red stick figure stands on the right. "
            "The red figure throws a bright yellow ball at the small figure. "
            "The yellow ball hits the small figure. A blue flash appears around the small figure. "
            "The small figure grows slightly bigger and glows faint blue. "
            "The red figure throws another yellow ball. It hits the small figure again. "
            "Another blue flash. The small figure grows bigger again, glowing brighter blue. "
            "The red figure throws a third ball. It hits. Bigger blue flash. "
            "The small figure is now the same size as the red figure, glowing bright blue with energy crackling around it. "
            "The red figure throws one more ball. The now-large blue figure catches it with one hand. "
            "The blue figure crushes the ball in its fist. Sparks fly. "
            "The blue figure is now twice the size of the red figure, towering over it. "
            "The red figure steps backward. "
            "Continuous smooth animation."
        ),
        output_path=clip1, duration=12, size="720x1280",
        reference_image_url=ref,
    )
    print(f"  Done: {r1['file_size_bytes']} bytes")

    # Chain frame — inline extraction
    frame_tmp2 = "/tmp/clip1_chain_frame.png"
    subprocess.run(["ffmpeg", "-y", "-i", clip1, "-vf", "thumbnail", "-vframes", "1", "-update", "1", frame_tmp2], capture_output=True)
    if os.path.exists(frame_tmp2):
        with open(frame_tmp2, "rb") as f:
            ref2 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        os.remove(frame_tmp2)
        print("  Frame chained")
    else:
        print("  WARNING: Using original ref for clip 2")
        ref2 = ref

    # Clip 2: Knockout — every beat spelled out
    clip2 = os.path.abspath(f"{output_dir}/clips/clip_002.mp4")
    print("Clip 2: Knockout (8s)...")
    r2 = await generate_video_async(
        prompt=(
            "Stick figure animation style, simple black stick figures on clean minimal white background, "
            "sharp clean lines, colored effects. "
            "A massive blue-glowing stick figure towers over a small red stick figure. "
            "The blue figure pulls its right fist back behind its body. "
            "The blue figure swings its fist forward and hits the red figure directly in the center. "
            "Huge white flash at the impact point. "
            "The red figure launches to the right at extreme speed. "
            "The red figure flies across the screen getting smaller and smaller. "
            "A bright white streak trail follows behind the red figure as it flies away. "
            "The red figure becomes a tiny dot in the distance. "
            "The tiny dot sparkles like a star and disappears. "
            "The blue figure shrinks back down to normal small size. "
            "The blue glow fades away. "
            "The small black figure dusts off its hands and walks away to the left. "
            "Continuous smooth animation."
        ),
        output_path=clip2, duration=8, size="720x1280",
        reference_image_url=ref2,
    )
    print(f"  Done: {r2['file_size_bytes']} bytes")

    # Render — no music
    print("Rendering...")
    rendered = do_render(
        clips=[clip1, clip2],
        caption_text="Every hit made him stronger. Bad strategy.",
        output_dir=output_dir,
        music_volume=0.0,
        sora_volume=1.0,
    )
    print(f"Rendered: {rendered['path']}")

    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({
                "status": "rendered", "path": rendered["path"],
                "size_bytes": rendered.get("size_bytes", 0),
                "content_type": "yeah_thats_clean_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "He Levels Up After Every Hit He Takes",
        "description": "#stickfigure #animation #action #Shorts",
        "tags": ["stick figure", "animation", "action", "power up", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id} in review queue")

asyncio.run(main())
