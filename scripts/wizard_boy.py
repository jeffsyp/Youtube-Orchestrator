"""Yeah Thats Clean — A boy discovers magic accidentally. 60s narrated anime short."""
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
            "A quiet anime fantasy village street on a sunny day. Cobblestone road, colorful shops. "
            "A young anime boy about 14 with messy brown hair and a simple school uniform "
            "walks down the street carrying a single old book under his arm. He looks bored. "
            "He reaches a tall grand library building. He pushes open the heavy wooden door. "
            "Inside — a beautiful grand library with towering bookshelves and stained glass windows. "
            "An old wizard librarian sits at the front desk reading. "
            "The boy places his book on the desk. The wizard barely looks up. "
            "The boy turns to leave. As he walks past a shelf, his hand accidentally brushes a large ancient book. "
            "The book glows faintly golden where he touched it. He does not notice. He keeps walking."
        ),
    },
    {
        "duration": 12,
        "narration": "He walked into the library. Put the book on the desk. Turned to leave. And his hand... touched the wrong book.",
        "prompt": (
            f"{STYLE}"
            "Same anime library. The ancient book on the shelf starts glowing brighter, pulsing with golden light. "
            "The glow spreads to the books next to it. Then the next shelf. Then the next. "
            "Books start vibrating on their shelves. Pages flutter on their own. "
            "The boy is near the exit door. He hears a sound behind him and turns around. "
            "His eyes go wide — the entire library is glowing. Books are sliding off shelves. "
            "The ancient book flies off the shelf and zooms through the air directly toward him. "
            "It stops right in front of his face, hovering, pages turning rapidly. "
            "The boy stumbles backward, arms up defensively. "
            "The book opens to a specific page — a glowing golden symbol lifts off the page as pure light "
            "and flies into the boy's chest. His whole body flashes gold. He gasps. "
            "His eyes turn from brown to glowing gold."
        ),
    },
    {
        "duration": 12,
        "narration": "Three hundred years that book waited. For someone with the right bloodline. ...Lucky him.",
        "prompt": (
            f"{STYLE}"
            "Same anime library. The ancient book on the shelf starts glowing brighter, pulsing with golden light. "
            "The glow spreads to the books next to it. Then the next shelf. Then the next. "
            "One by one, books start vibrating on their shelves. Pages flutter on their own. "
            "The boy is near the exit door. He hears a sound behind him and turns around. "
            "His eyes go wide — the entire library is glowing. Books are sliding off shelves. "
            "The ancient book flies off the shelf and zooms through the air directly toward him. "
            "It stops right in front of his face, hovering, pages turning on their own rapidly. "
            "The boy stumbles backward, arms up defensively. "
            "The book opens to a specific page — a glowing golden symbol on the page. "
            "The symbol lifts off the page as pure light and flies into the boy's chest. "
            "His whole body flashes gold. He gasps. His eyes turn from brown to glowing gold."
        ),
    },
    {
        "duration": 12,
        "narration": "And then... he sneezed. And that is when things got really out of hand.",
        "prompt": (
            f"{STYLE}"
            "Same anime library. The boy stands in the middle of the room glowing gold. "
            "He looks at his hands — golden energy crackles between his fingers. He is confused. "
            "His nose twitches. He squints. He tries to hold it in — his whole face scrunches up. "
            "He sneezes — a massive golden shockwave explodes outward from his body. "
            "Every single book in the library launches off its shelf simultaneously. "
            "Hundreds of books fly through the air in every direction. "
            "Bookshelves topple like dominoes. The old wizard librarian's desk flips over. "
            "The wizard gets blown backward into his chair which rolls across the room. "
            "The boy stands in the middle of the chaos, hand over his nose, eyes wide with guilt. "
            "Books orbit around him like planets around a sun. He tries to grab one — it dodges his hand."
        ),
    },
    {
        "duration": 12,
        "narration": "The old wizard looked at the destruction. Looked at the kid. And said... you start training on Monday.",
        "prompt": (
            f"{STYLE}"
            "Same anime library, now completely destroyed — books piled everywhere, shelves fallen, "
            "pages scattered like snow, the stained glass window cracked. "
            "The boy stands in the middle of it all, golden glow fading, looking horrified at what he did. "
            "Books are still gently floating down around him. "
            "The old wizard climbs out from behind his overturned desk, adjusting his crooked glasses. "
            "He brushes a page off his shoulder. He looks around at the destroyed library. "
            "He looks at the boy. The boy cringes, expecting to be yelled at. "
            "Instead, the wizard's face slowly breaks into a huge grin. "
            "He starts laughing — deep, hearty laughter. He slaps his knee. "
            "The boy looks confused. The wizard walks over and puts a hand on the boy's shoulder. "
            "The wizard points to a door the boy has never noticed before — it glows with golden light. "
            "The boy looks at the door, then back at the wizard. A small smile crosses his face. "
            "Final wide shot — the boy and the wizard walking toward the glowing door together, "
            "books still floating gently around them."
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
        ft = f"/tmp/wizard_{i}.jpg"
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
        "description": "All he wanted to do was return a book. Now he is a wizard. #anime #wizard #magic #funny #Shorts",
        "tags": ["anime", "wizard", "magic", "funny", "accidental powers", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
