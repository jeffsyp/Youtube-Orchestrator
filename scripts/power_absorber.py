"""Yeah Thats Clean — He Gets Stronger Every Hit. Anime style, no flashback, full story."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, dynamic speed lines, dramatic lighting with lens flares, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "The arena was packed. Two fighters. One was a monster. The other... had never won a single match.",
        "prompt": (
            f"{STYLE}"
            "A massive anime underground fighting arena. Stone walls, flaming torches, "
            "a roaring crowd of anime characters in the stands pounding on railings. "
            "Two fighters face each other in the center of a circular dirt arena. "
            "On the left — a huge muscular anime fighter with red glowing fists, scars, shaved head, "
            "radiating confidence, cracking his knuckles. Red energy aura surrounds his body. "
            "On the right — a small thin anime boy with messy dark hair, bandaged hands, "
            "wearing a torn white shirt. He looks nervous but stands his ground. "
            "The crowd is clearly cheering for the big fighter. Some point at the small boy and laugh. "
            "The small boy takes a deep breath and raises his fists. His hands are trembling."
        ),
    },
    {
        "duration": 12,
        "narration": "The first hit almost ended it. ...But something strange happened. He got back up. And he felt... stronger.",
        "prompt": (
            f"{STYLE}"
            "Same anime underground arena, stone walls, torches, crowd. "
            "The small boy is on the ground, face down in the dirt. "
            "A dust cloud settles around him from the impact. The crowd cheers. "
            "The big red fighter stands over him, fist still extended from the blow. "
            "The small boy pushes himself up slowly. His lip is bleeding. "
            "But as he stands, a faint blue glow appears around his body. Very subtle. "
            "His eyes have a tiny blue shimmer that was not there before. "
            "He stands fully upright. He seems slightly taller. Slightly more solid. "
            "The big fighter raises an eyebrow, confused. The boy raises his fists again. "
            "The crowd goes quiet — they expected him to stay down."
        ),
    },
    {
        "duration": 12,
        "narration": "Every hit made him stronger. The big guy did not realize... he was feeding a monster.",
        "prompt": (
            f"{STYLE}"
            "Same anime arena. The small boy stands in the center. He is visibly larger now — "
            "more muscular, more defined. Blue energy crackles across his arms and shoulders. "
            "His eyes glow bright blue. His torn shirt stretches across broader shoulders. "
            "He has been hit many times — cuts and bruises on his face and arms — "
            "but each wound has a faint blue glow around it. Every injury made him stronger. "
            "The big red fighter stands across from him, panting, sweating, confused. "
            "His red aura is dimmer now. He has thrown everything and the kid keeps growing. "
            "The small boy — now equal in size to the big fighter — clenches his fists. "
            "Blue energy surges around his whole body. The ground cracks beneath his feet. "
            "The crowd is dead silent. Staring."
        ),
    },
    {
        "duration": 12,
        "narration": "One more hit. That is all he needed. ...The big guy was happy to oblige.",
        "prompt": (
            f"{STYLE}"
            "Same anime arena. Close-up of the big red fighter's face — desperate, angry. "
            "He pulls his fist back, red energy concentrated into one massive blow. "
            "He swings with everything he has. Red energy trail behind his fist. "
            "The fist connects with the blue-glowing boy's chest. Massive red impact flash. "
            "But the boy does not move. He absorbs the impact completely. "
            "His body flashes blindingly bright blue. He grows even larger. "
            "He is now towering over the red fighter. Massive. Radiating blue power. "
            "The ground cracks in a spiderweb pattern. The torches on the walls flicker wildly. "
            "The big fighter's eyes go wide with fear. He steps backward. "
            "The boy looks down at him calmly. Blue lightning arcs across his body."
        ),
    },
    {
        "duration": 12,
        "narration": "He could have destroyed him. ...Instead he just flicked him. That was enough.",
        "prompt": (
            f"{STYLE}"
            "Same anime arena. The massive blue-glowing boy towers over the cowering red fighter. "
            "The boy raises one hand. Just his index finger. "
            "He flicks the big fighter on the forehead with one finger. "
            "A small blue flash at the contact point. "
            "The red fighter is launched backward across the entire arena at incredible speed, "
            "flying through the air with a blue streak trail behind him. "
            "He crashes into the far stone wall. The wall cracks from the impact. "
            "He slides down the wall and slumps to the ground, unconscious. "
            "The massive boy shrinks back down to his normal small thin size. "
            "Blue glow fades. He is just a small kid again, standing alone in the arena. "
            "The crowd erupts. The boy looks at his own hands, still trembling. "
            "A tiny smile crosses his face. He turns and walks toward the exit."
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
        ft = f"/tmp/absorb_{i}.jpg"
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
        "title": "Every Hit Made Him Stronger",
        "description": "He never won a single match. Until they realized losing was his strategy. #anime #action #underdog #Shorts",
        "tags": ["anime", "action", "underdog", "power up", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
