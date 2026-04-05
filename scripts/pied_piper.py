"""Fundational — The Pied Piper: a fairy tale retold in 60 seconds."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE = (
    "Vertical 9:16 aspect ratio, dreamlike cinematic style, slightly surreal lighting, "
    "warm golden tones, shallow depth of field, atmospheric fog and particles in the air, "
    "photorealistic but with a magical quality, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "The town had a rat problem. ...They had no idea the solution would be worse.",
        "prompt": (
            f"{STYLE}"
            "A medieval fairy tale town at dusk, cobblestone streets, crooked timber houses, warm lantern light. "
            "The streets are overrun with hundreds of rats — rats pouring out of doorways, running along rooftops, "
            "swimming through gutters. Townspeople stand on tables and chairs looking horrified. "
            "A woman lifts her skirts as rats run past her feet. A baker watches rats devour his bread. "
            "The mayor, a fat man in a velvet coat, stands on the town hall steps looking desperate. "
            "He holds up a bag of gold coins, shaking it, shouting to the crowd. "
            "From the fog at the end of the street, a tall thin figure appears — a silhouette walking toward the town. "
            "He wears a long patchwork coat of many colors. A wooden flute hangs from his belt. "
            "The townspeople all turn to look at him. The rats pause."
        ),
    },
    {
        "duration": 12,
        "narration": "He didn't say a word. He just... played.",
        "prompt": (
            f"{STYLE}"
            "Same medieval town, now night, moonlight casting blue-silver light on the cobblestones. "
            "The tall thin man in the patchwork coat stands in the center of the town square. "
            "He lifts the wooden flute to his lips. Close-up of his fingers on the flute. "
            "He begins to play — a haunting, beautiful melody. Golden light flows from the flute like smoke. "
            "The golden musical light drifts through the streets like a living thing. "
            "Every rat in the town freezes. Their ears perk up. They turn toward the music. "
            "One by one, rats start walking toward the piper. Then more. Then hundreds. "
            "A river of rats flows through the streets toward him, hypnotized by the music. "
            "The piper turns and walks toward the edge of town. The rats follow in a massive wave behind him. "
            "Townspeople watch from windows, amazed, as the river of rats flows past."
        ),
    },
    {
        "duration": 12,
        "narration": "He led them to the river. Every last one. The town was free. ...Then he came back for his payment.",
        "prompt": (
            f"{STYLE}"
            "A wide river outside the medieval town at night, moonlight sparkling on the water. "
            "The piper stands at the riverbank playing his flute, golden light flowing from it. "
            "Behind him, a massive wave of rats pours over the riverbank and into the water. "
            "Thousands of rats splash into the river and are carried away by the current. "
            "The last rat falls into the water. The piper stops playing. Silence. "
            "He turns and walks back toward the town. "
            "Cut to the town square — daytime now, bright and clean. Not a single rat anywhere. "
            "The piper stands before the mayor with his hand out, waiting. "
            "The mayor looks at the bag of gold. He looks at the piper. "
            "The mayor laughs and waves his hand dismissively. He turns away, keeping the gold. "
            "Close-up of the piper's face. His expression goes cold. His eyes narrow."
        ),
    },
    {
        "duration": 12,
        "narration": "They refused to pay him. ...So he played a different song.",
        "prompt": (
            f"{STYLE}"
            "Same medieval town, night has fallen again. The piper stands alone in the empty town square. "
            "Moonlight casts long shadows. The town is quiet — everyone is sleeping in their homes. "
            "The piper lifts his flute to his lips again. But this time the light that flows from it is silver, not gold. "
            "The silver musical light drifts through the streets, under doors, through windows. "
            "One by one, the doors of houses open on their own. "
            "Children step out of their homes, one after another. They are sleepwalking — eyes open but dreaming. "
            "They follow the silver light, walking slowly toward the piper. "
            "More and more children emerge from every house. Dozens of children walking in a line. "
            "The piper turns and walks toward the edge of town. The children follow him silently. "
            "Parents begin appearing in doorways behind them, still half asleep, confused."
        ),
    },
    {
        "duration": 12,
        "narration": "He walked them into the mountain. The door closed. ...And they were never seen again.",
        "prompt": (
            f"{STYLE}"
            "A massive dark mountain outside the medieval town at night, lit by moonlight. "
            "The piper walks toward the base of the mountain playing his silver-glowing flute. "
            "A long line of sleepwalking children follows behind him, bathed in silver light. "
            "As the piper approaches the mountain, a crack appears in the rock face — a doorway of light. "
            "The piper walks through the glowing doorway into the mountain. "
            "The children follow one by one, disappearing into the mountain. "
            "Behind them, far in the distance, parents are running from the town, arms reaching out, crying. "
            "The last child steps through the doorway. "
            "The crack in the mountain seals shut. The silver light vanishes. "
            "The mountain is just a mountain again. Dark. Silent. "
            "Final shot — the parents reaching the mountain, falling to their knees, "
            "hands pressed against the cold stone where the door was. Nothing. "
            "Wide shot — the tiny town below, the dark mountain above, and silence."
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
                 "VALUES (5, 'running', 'generate_clips', 'fundational') RETURNING id")
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
    output_dir = f"output/fundational_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    print("Generating narration (George voice)...")
    narration_paths = []
    for i, clip in enumerate(CLIPS):
        vo_path = f"{output_dir}/narration/narration_{i:02d}.mp3"
        try:
            generate_speech(clip["narration"], output_path=vo_path)
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
        ft = f"/tmp/piper_{i}.jpg"
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

    final = f"{output_dir}/fundational_short.mp4"
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
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 5, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_fundational_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final),
                "size_bytes": os.path.getsize(final), "content_type": "fundational_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "The Pied Piper",
        "description": "They refused to pay him. So he played a different song. #fairytale #legend #piedpiper #story #Shorts",
        "tags": ["fairy tale", "pied piper", "legend", "story", "dark", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
