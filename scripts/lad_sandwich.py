"""Lad Tries to Make a Sandwich. 20 seconds of chaos."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

from packages.prompts.lad_stories import CHARACTER_BIBLE, STYLE_BIBLE

STYLE = (
    "Vertical 9:16 aspect ratio, claymation stop-motion style, "
    "visible hand-crafted textures, fingerprint marks in clay, "
    "miniature handmade set/diorama, warm soft diffused lighting, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 4,
        "prompt": (
            f"{STYLE} {CHARACTER_BIBLE} "
            "A tiny clay kitchen is completely destroyed — ketchup splattered on every surface, "
            "broken plates, food everywhere. Lad the small round clay character slides across the floor "
            "on a river of red ketchup, arms flailing, eyes wide in panic. "
            "Behind him a piece of clay bread with tiny clay legs chases him across the floor. "
            "On the walls, melted yellow clay cheese oozes down like a blob creature. "
            "Green clay lettuce leaves fly through the air spinning. "
            "Total kitchen warzone. Lad's body language shows pure panic. "
            "Bouncy chaotic sound effects, squelchy clay noises."
        ),
    },
    {
        "duration": 8,
        "prompt": (
            f"{STYLE} {CHARACTER_BIBLE} "
            "A peaceful tiny clay kitchen. Everything is clean and tidy. Warm lighting. "
            "A small clay refrigerator stands against the wall. "
            "Lad the small round clay character walks up to the fridge and opens the door. "
            "Inside the fridge, clay food items sit on shelves — bread, cheese, lettuce, tomato. "
            "Everything is still and quiet. Lad reaches one stubby arm toward the bread. "
            "The clay bread opens one tiny eye and looks at Lad. Lad freezes. "
            "The bread JUMPS off the shelf and sprints away on tiny clay legs. "
            "The cheese wobbles and slides off its shelf. The lettuce launches itself into the air. "
            "The tomato rolls out and bounces across the floor. "
            "All the food scatters in every direction. Lad stands at the open fridge, stunned. "
            "Whimsical sound effects, bouncy foley."
        ),
    },
    {
        "duration": 8,
        "prompt": (
            f"{STYLE} {CHARACTER_BIBLE} "
            "The tiny clay kitchen is completely wrecked — ketchup on the ceiling, "
            "cheese melted down the walls, lettuce stuck to the window, broken dishes everywhere. "
            "Lad sits in the middle of the destruction on the floor. "
            "He is covered in food — ketchup on his head, cheese on his arm, a lettuce leaf stuck to his back. "
            "In his two stubby hands he holds two tiny crumbs pressed together. "
            "The world's smallest sandwich. He looks at it proudly. "
            "He lifts it to where his mouth would be and eats it. "
            "He nods slowly. Satisfied. It was worth it. "
            "He gives a tiny thumbs up to the camera. "
            "Behind him, the bread with tiny legs peeks around the corner of the fridge, watching. "
            "Comedic satisfied sound effect, then a tiny squeak from the bread."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (6, 'running', 'generate_clips', 'lad_stories') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/lad_stories_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)

        # Sora clips with frame chaining
        print("Generating clips...")
        clip_paths = []
        prev_ref = None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"\nClip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=clip["duration"], size="720x1280", timeout=1200,
                reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/lad_sand_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                             "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f:
                    prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Normalize + concat (no narration — Lad doesn't need it, sora audio only)
        print("Concat...")
        norms = []
        for i, p in enumerate(clip_paths):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf",
                "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Concat failed")

        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        # Review queue
        async with async_session() as session:
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 6, :a, :c)"),
                {"rid": run_id, "a": "rendered_lad_stories_short",
                 "c": json.dumps({"status": "rendered", "path": os.path.abspath(final),
                                  "size_bytes": os.path.getsize(final), "content_type": "lad_stories_short"})})
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 6, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata",
                 "c": json.dumps({"title": "Lad Tries to Make a Sandwich",
                                  "description": "It was supposed to be simple. It was not simple. #claymation #funny #animation #Shorts",
                                  "tags": ["claymation", "funny", "animation", "lad", "sandwich", "chaos", "Shorts"],
                                  "category": "Entertainment"})})
            await session.execute(
                text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"),
                {"rid": run_id})
            await session.commit()
        print(f"Review queue: Run #{run_id}")

    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise

asyncio.run(main())
