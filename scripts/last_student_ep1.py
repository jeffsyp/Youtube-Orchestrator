"""The Last Student — Episode 1: Entrance. Force-generated."""
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
        "narration": "He hit the wall so hard the arena shook. Everyone laughed. ...But then his eyes started glowing.",
        "prompt": (
            f"{STYLE}"
            "An anime battle arena at night, stone walls, torches on pillars, hundreds of anime students in the stands. "
            "A teenage boy with messy black hair crashes into the far wall of the arena. Dust and debris explode around him. "
            "His uniform is torn. He slides down the wall and slumps to the ground. "
            "Across the arena, a large muscular student with spiky red hair stands with one arm extended, smirking. "
            "Red energy fades from his palm. The crowd of students laughs and points. "
            "Close-up of the boy on the ground. His face is pressed against the dirt. His fists clench. "
            "Then his eyes snap open — they glow bright electric blue. "
            "Blue energy crackles around his body involuntarily. The ground beneath him cracks. "
            "The laughter stops. Everyone stares. The arena goes completely silent."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind... that morning. He was just a kid with a backpack. Walking through a gate meant for gods.",
        "prompt": (
            f"{STYLE}"
            "Bright morning sunlight. A massive anime academy gate towers overhead — ornate metal with glowing symbols. "
            "A nervous teenage boy with messy black hair and a simple backpack walks toward the gate. "
            "He looks small compared to the gate. His eyes are wide, taking everything in. "
            "Around him, other students arrive using supernatural abilities — one flies overhead on wings of fire, "
            "another teleports in a flash of purple light, another walks on a path of ice forming beneath their feet. "
            "The boy watches them with his mouth open. He looks down at his own ordinary hands. "
            "He takes a deep breath and walks through the gate on foot. Just walking. "
            "Other students glance at him as he passes — confused, dismissive. "
            "He grips his backpack straps tighter and keeps walking."
        ),
    },
    {
        "duration": 12,
        "narration": "The entrance exam. Everyone had a power to show. Fire. Ice. Lightning. ...His turn came. And nothing happened.",
        "prompt": (
            f"{STYLE}"
            "An anime examination hall — large circular arena with an instructor in a white coat holding a clipboard. "
            "Students line up to demonstrate their abilities one by one. "
            "One student creates a tornado of fire in their hands. The instructor nods and writes. "
            "Another student freezes a column of water into a crystal ice sculpture. The instructor nods. "
            "Another student lifts three boulders with telekinesis. The instructor nods. "
            "Then the boy with messy black hair steps forward. He stands in the center of the arena. "
            "He closes his eyes. He concentrates hard — his face strains with effort. Veins on his forehead. "
            "Nothing happens. Absolute silence. Five seconds of nothing. "
            "The instructor looks up from his clipboard with a flat expression. "
            "He draws a red X on the clipboard. The crowd of students snickers. "
            "The boy opens his eyes. His shoulders drop. He looks at the ground, devastated."
        ),
    },
    {
        "duration": 12,
        "narration": "Then the top student decided to make an example out of him. One blast. That's all it took.",
        "prompt": (
            f"{STYLE}"
            "Same anime arena. The boy with messy black hair is walking away with his head down toward the exit. "
            "The large muscular student with spiky red hair steps into his path, blocking him. "
            "The red-haired student towers over him, arms crossed, smirking down at him. "
            "Red energy glows around the red-haired student's fist. "
            "He raises his palm and sends a massive red energy wave directly at the smaller boy. "
            "The energy wave hits the boy in the chest — bright red flash on impact. "
            "The boy is launched backward through the air, tumbling end over end. "
            "He slams into the far wall of the arena. The wall cracks from the impact. "
            "Dust billows. The crowd cheers for the red-haired student. "
            "The red-haired student turns away, already bored. "
            "The dust begins to settle around the crater in the wall."
        ),
    },
    {
        "duration": 12,
        "narration": "Everyone thought it was over. ...It was just beginning.",
        "prompt": (
            f"{STYLE}"
            "Same anime arena. The dust clears around the crater in the wall. "
            "The boy is still there — standing. Slowly rising to his feet in the rubble. "
            "His head is down. Blood drips from his forehead. His uniform is destroyed. "
            "The crowd goes quiet. The red-haired student turns back around, surprised. "
            "The boy lifts his head. His eyes are glowing bright electric blue — brighter than before. "
            "Blue lightning crackles across his entire body. His hair rises from the static energy. "
            "The ground beneath his feet cracks and splits outward in a spiderweb pattern. "
            "Small rocks float up around him from the energy pressure. "
            "The instructor drops his clipboard. His eyes go wide. "
            "The red-haired student takes a step backward for the first time. His smirk is gone. "
            "Close-up of the boy's glowing blue eyes — pure power awakening for the first time. "
            "Camera pulls back — the entire arena is watching in stunned silence. "
            "Cut to black."
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
                 "VALUES (8, 'running', 'generate_clips', 'gamatatsuken') RETURNING id")
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
    output_dir = f"output/gamatatsuken_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    # Narration
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

    # Sora clips with frame chaining
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

        # Frame chain
        ft = f"/tmp/ep1_frame_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                         "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
        if os.path.exists(ft):
            with open(ft, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(ft)
            print(f"  Frame chained")

    # Mix narration
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

    # Normalize and concat
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

    final = f"{output_dir}/gamatatsuken_short.mp4"
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
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 8, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_gamatatsuken_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final),
                "size_bytes": os.path.getsize(final), "content_type": "gamatatsuken_short",
            })},
        )
        await session.commit()

    await mark_run_pending_review(run_id, {
        "title": "The Last Student - Episode 1",
        "description": "They called him powerless. They were wrong. Episode 1 of The Last Student. #anime #series #Shorts",
        "tags": ["anime", "series", "The Last Student", "episode 1", "powers", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id} — Episode 1 in review queue")


asyncio.run(main())
