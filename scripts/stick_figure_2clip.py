"""Generate a 2-clip stick figure power-up video with frame chaining."""
import asyncio
import json
import os

async def main():
    from packages.clients.sora import _extract_last_frame, generate_video_async
    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render
    from apps.orchestrator.activities import mark_run_pending_review
    from packages.clients.db import async_session
    from sqlalchemy import text

    # Use run 261's style
    src = os.path.abspath("output/yeah_thats_clean_run_261/clips/clip_00.mp4")
    print(f"Source: {src} exists={os.path.exists(src)}")

    # Manual extraction to bypass any function issues
    import subprocess as sp
    import base64
    frame_tmp = "/tmp/run261_frame.png"
    sp.run(["ffmpeg", "-y", "-i", src, "-vf", r"select=eq(n\,299)", "-vframes", "1", "-update", "1", frame_tmp], capture_output=True)
    if os.path.exists(frame_tmp):
        with open(frame_tmp, "rb") as f:
            ref = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
        os.remove(frame_tmp)
        print(f"Frame extracted manually: {len(ref)} chars")
    else:
        print("ERROR: Manual frame extraction failed too")
        return
    if not ref:
        print("ERROR: Could not extract frame from run 261")
        return
    print("Style frame extracted from run 261")

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)

    # Clip 1: Power-up (12s)
    clip1 = os.path.abspath(f"{output_dir}/clips/clip_001.mp4")
    print("Clip 1: Power-up (12s)...")
    r1 = await generate_video_async(
        prompt=(
            "Continue this exact animation style. A small black stick figure absorbs "
            "energy blasts from a larger red figure, growing bigger and glowing brighter "
            "blue with each hit. Fast martial arts exchanges and rapid energy clashes. "
            "After many hits the small figure is now massive, towering, pulsing with "
            "blue-white energy. The red figure backs away. Intense continuous action, "
            "comic book style."
        ),
        output_path=clip1, duration=12, size="720x1280",
        reference_image_url=ref,
    )
    print(f"  Clip 1 done: {r1['file_size_bytes']} bytes")

    # Chain: extract last frame of clip 1
    ref2 = _extract_last_frame(clip1)
    if not ref2:
        print("WARNING: Could not chain frame, using original ref")
        ref2 = ref
    else:
        print("  Frame chained for clip 2")

    # Clip 2: Knockout (8s)
    clip2 = os.path.abspath(f"{output_dir}/clips/clip_002.mp4")
    print("Clip 2: Knockout (8s)...")
    r2 = await generate_video_async(
        prompt=(
            "Continue this exact scene. The massive blue-glowing figure winds up and "
            "releases one enormous energy wave. Huge white flash. The red figure launches "
            "off screen at incredible speed with a bright streak trail like a shooting star, "
            "disappearing as a tiny twinkle. The hero shrinks back to normal and casually "
            "walks away. Same art style, smooth animation."
        ),
        output_path=clip2, duration=8, size="720x1280",
        reference_image_url=ref2,
    )
    print(f"  Clip 2 done: {r2['file_size_bytes']} bytes")

    # Render — no music
    print("Rendering (no background music)...")
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
            {
                "rid": run_id,
                "atype": "rendered_yeah_thats_clean_short",
                "content": json.dumps({
                    "status": "rendered",
                    "path": rendered["path"],
                    "size_bytes": rendered.get("size_bytes", 0),
                    "content_type": "yeah_thats_clean_short",
                }),
            },
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
