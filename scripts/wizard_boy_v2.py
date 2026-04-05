"""Yeah Thats Clean — Wizard Boy v2. One location, one camera per clip."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, magical particle effects, dramatic lighting with lens flares, "
    "fantasy anime inspired, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "All he wanted... was to return a library book. That is it. That is all he wanted.",
        "prompt": (
            f"{STYLE}"
            "A grand anime fantasy library interior. Towering wooden bookshelves reach to a vaulted ceiling. "
            "Stained glass windows cast colorful light across the room. Dust particles float in the sunbeams. "
            "A young anime boy about 14 with messy brown hair and a simple school uniform "
            "stands at the front desk placing a book down. An old wizard librarian with long grey beard "
            "and round glasses sits behind the desk barely looking up. "
            "The boy turns away from the desk and walks past a shelf. "
            "His hand lightly brushes an ancient leather-bound book on the shelf as he passes. "
            "A faint golden glow appears on the book where his fingers touched it. "
            "The boy does not notice. He keeps walking toward the door. "
            "The camera stays fixed on the glowing book on the shelf."
        ),
    },
    {
        "duration": 12,
        "narration": "The book he touched had been sealed for three hundred years. Waiting for the right bloodline.",
        "prompt": (
            f"{STYLE}"
            "Same grand anime library interior, same bookshelves and stained glass windows. "
            "The ancient leather book on the shelf is now glowing bright gold, pulsing with light. "
            "The golden glow is spreading — the books on either side of it start glowing too. "
            "More books begin vibrating on their shelves. Pages flutter open on their own. "
            "Books start lifting off shelves and floating in the air, drifting slowly upward. "
            "Dozens of books are now hovering throughout the library, pages fluttering. "
            "Golden magical particles fill the air like fireflies. "
            "The ancient book lifts off its shelf and floats to the center of the room, "
            "spinning slowly, its pages turning rapidly, golden light pouring from between the pages. "
            "The old wizard librarian stands up from his chair, eyes wide, mouth open in shock."
        ),
    },
    {
        "duration": 12,
        "narration": "The magic found him. Whether he wanted it or not.",
        "prompt": (
            f"{STYLE}"
            "Same anime library. The boy stands frozen in the middle of the room looking terrified. "
            "The ancient book hovers directly in front of his face, open to a page with a glowing golden symbol. "
            "The golden symbol lifts off the page as pure light. "
            "The light drifts toward the boy and touches his chest. "
            "His whole body flashes bright gold. His eyes change from brown to glowing gold. "
            "Golden energy crackles across his arms and hands like electricity. "
            "He looks down at his own glowing hands in complete confusion and fear. "
            "All around him, hundreds of books are floating in the air, orbiting him slowly "
            "like planets around a sun. Golden particles swirl everywhere. "
            "The boy's hair floats upward from the energy. He has no idea what is happening to him."
        ),
    },
    {
        "duration": 12,
        "narration": "And then... he sneezed. And that is when things got really out of hand.",
        "prompt": (
            f"{STYLE}"
            "Same anime library. The boy stands in the center glowing gold, hundreds of books floating around him. "
            "His nose twitches. His face scrunches up. He is about to sneeze. "
            "He sneezes — a massive golden shockwave explodes outward from his body in all directions. "
            "Every floating book is launched outward at high speed in every direction. "
            "Books slam into walls, crash through shelves, pages scatter everywhere like confetti. "
            "Bookshelves topple over like dominoes one after another. "
            "The wizard librarian gets knocked backward, his chair rolling across the floor, "
            "his glasses fly off his face. Papers and pages fill the air like a blizzard. "
            "The boy stands in the center of the chaos with his hand over his nose, "
            "eyes wide with guilt, golden glow fading. The entire library is destroyed around him."
        ),
    },
    {
        "duration": 12,
        "narration": "The wizard looked at the destruction. Looked at the boy. And smiled. ...You start training Monday.",
        "prompt": (
            f"{STYLE}"
            "Same anime library, now completely destroyed. Books piled everywhere, shelves toppled, "
            "pages drifting down like snow, stained glass window cracked. Total devastation. "
            "The boy stands in the middle looking horrified at what he did. "
            "His golden glow is gone. He looks like a normal scared kid again. "
            "The old wizard librarian climbs out from behind his overturned desk. "
            "He picks up his bent glasses and puts them back on crooked. "
            "He brushes a page off his shoulder. He looks around at the destroyed library. "
            "He looks at the boy. The boy cringes, expecting to be yelled at. "
            "Instead the wizard breaks into a huge warm grin. He starts laughing. "
            "He puts a hand on the boy's shoulder. He points to a door in the back wall "
            "that the boy has never seen before — it glows with soft golden light. "
            "The boy looks at the door. A small smile crosses his face. "
            "Both of them stand together looking at the glowing door. Books still drift down around them."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        await _run(run_id, generate_video_async, generate_speech, async_session, text)
    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                                  {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise


async def _run(run_id, generate_video_async, generate_speech, async_session, text):
    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    print("Generating narration...")
    narration_paths = []
    for i, clip in enumerate(CLIPS):
        vo_path = f"{output_dir}/narration/narration_{i:02d}.mp3"
        try:
            generate_speech(clip["narration"], voice=ANIME_VOICE, output_path=vo_path)
            narration_paths.append(vo_path)
            print(f"  [{i+1}] OK")
        except Exception as e:
            print(f"  [{i+1}] FAILED: {e}")
            narration_paths.append(None)

    print("\nGenerating Sora clips...")
    clip_paths = []
    prev_ref = None
    for i, clip in enumerate(CLIPS):
        cp = os.path.abspath(f"{output_dir}/clips/clip_{i:02d}.mp4")
        print(f"\nClip {i+1}/{len(CLIPS)}...")
        r = await generate_video_async(
            prompt=clip["prompt"], output_path=cp,
            duration=clip["duration"], size="720x1280", timeout=1200,
            reference_image_url=prev_ref,
        )
        clip_paths.append(cp)
        print(f"  Saved: {r['file_size_bytes']} bytes")
        ft = f"/tmp/wizv2_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                         "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
        if os.path.exists(ft):
            with open(ft, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(ft)

    print("\nMixing narration...")
    mixed = []
    for i, cp in enumerate(clip_paths):
        if i < len(narration_paths) and narration_paths[i] and os.path.exists(narration_paths[i]):
            mx = cp.replace(".mp4", "_nar.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", cp, "-i", narration_paths[i],
                "-filter_complex", "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx,
            ], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)
        else:
            mixed.append(cp)

    print("Concatenating...")
    norms = []
    for i, p in enumerate(mixed):
        n = f"{output_dir}/clips/norm_{i:02d}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", p, "-vf",
            "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n,
        ], capture_output=True)
        norms.append(n if os.path.exists(n) else p)

    cl = f"{output_dir}/concat.txt"
    with open(cl, "w") as f:
        for p in norms:
            f.write(f"file '{os.path.abspath(p)}'\n")

    final = f"{output_dir}/yeah_thats_clean_short.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", final,
    ], capture_output=True)

    if not os.path.exists(final):
        raise RuntimeError("Concat failed")

    print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

    from apps.orchestrator.activities import mark_run_pending_review
    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final),
                "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "He Sneezed and Destroyed an Entire Library",
        "description": "All he wanted was to return a book. Now he is a wizard. #anime #wizard #magic #funny #Shorts",
        "tags": ["anime", "wizard", "magic", "funny", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
