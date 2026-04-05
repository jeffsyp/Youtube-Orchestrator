"""Synth Meow — Animals doing viral dance at a beach party."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, watercolor animation style, soft painted textures, "
    "gentle brush strokes, children's book illustration come to life, warm pastel colors, "
    "dreamy painted backgrounds, no text, no watermarks, no UI elements. "
)

# Single 12s clip — a beach dance party with animals
PROMPT = (
    f"{STYLE_PREFIX}"
    "A tropical watercolor beach scene at sunset with palm trees and colorful sky. "
    "A group of cute watercolor animals are standing upright on the beach like humans. "
    "A fluffy orange cat in sunglasses is in the center. "
    "A golden retriever puppy is on the left. A penguin wearing a tiny hat is on the right. "
    "A small monkey is behind them. "
    "All four animals start dancing together in sync — they bob their heads side to side, "
    "then they all step to the left together, then step to the right together. "
    "They wave their arms up in the air. They shimmy their shoulders. "
    "They do a synchronized spin. The cat does a moonwalk across the sand. "
    "The puppy does the floss dance. The penguin waddle-dances. "
    "The monkey claps and jumps. "
    "They all come back together and do a final synchronized pose — "
    "arms out, heads tilted, one leg up. "
    "The sunset glows warm orange behind them. "
    "Watercolor splashes of color follow their movements like paint trails. "
    "Fun energetic beach party atmosphere. Smooth continuous animation."
)


async def main():
    from packages.clients.sora import generate_video_async
    from apps.rendering_service.synthzoo_compositor import render_synthzoo_short as do_render
    from apps.orchestrator.activities import mark_run_pending_review
    from packages.clients.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (2, 'running', 'generate_clips', 'synthzoo') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    output_dir = f"output/synthzoo_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    clip_path = os.path.abspath(f"{output_dir}/clips/clip_001.mp4")

    print("Generating dance clip (12s)...")
    result = await generate_video_async(
        prompt=PROMPT,
        output_path=clip_path,
        duration=12,
        size="720x1280",
        timeout=1200,
    )
    print(f"Clip: {result['file_size_bytes']} bytes")

    # Render with upbeat music
    print("Rendering...")
    rendered = do_render(
        clips=[clip_path],
        caption_text="Copa Cabana but make it animals",
        output_dir=output_dir,
        music_volume=0.7,  # Louder music for dance video
        sora_volume=0.3,
    )
    print(f"Rendered: {rendered['path']}")

    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 2, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_synthzoo_short", "content": json.dumps({
                "status": "rendered", "path": rendered["path"],
                "size_bytes": rendered.get("size_bytes", 0),
                "content_type": "synthzoo_short",
            })},
        )
        await session.commit()

    await mark_run_pending_review(run_id, {
        "title": "Copa Cabana but Make It Animals",
        "description": "When the squad hits the beach and the beat drops. #animals #dancing #funny #beach #Shorts",
        "tags": ["funny animals", "dancing", "beach party", "cute", "Shorts"],
        "category": "Pets & Animals",
    })
    print(f"Done! Run #{run_id} in review queue")

asyncio.run(main())
