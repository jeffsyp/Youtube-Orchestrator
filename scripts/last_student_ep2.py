"""The Last Student — Episode 2: The Teacher. One location per clip."""
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
        "narration": "After what happened at the entrance exam... only one teacher wanted him. The one nobody trusts.",
        "prompt": (
            f"{STYLE}"
            "A dark anime classroom at night. Empty desks, dusty chalkboard, moonlight through cracked windows. "
            "The boy with messy black hair from Episode 1 sits alone at a desk in the back corner. "
            "He stares at his own hands. Faint blue energy flickers across his fingertips then disappears. "
            "He clenches his fists trying to make it happen again. Nothing. "
            "The classroom door slides open. A tall figure stands in the doorway — silhouette only. "
            "A man with long silver hair tied back, a scar across one eye, wearing a black instructor coat. "
            "He leans against the doorframe with his arms crossed, studying the boy with one sharp eye. "
            "The boy looks up, startled. The man's visible eye glows faintly purple for a moment."
        ),
    },
    {
        "duration": 12,
        "narration": "His name was Kael. The academy banned his techniques ten years ago. ...He never stopped using them.",
        "prompt": (
            f"{STYLE}"
            "A secret underground anime training room beneath the academy. Stone walls, dim blue torchlight, "
            "ancient symbols carved into the floor in a circle. "
            "The silver-haired instructor Kael stands in the center of the symbol circle. "
            "Purple energy radiates from his body. His long black coat billows from the force. "
            "He holds one palm up — a sphere of swirling purple and black energy floats above his hand. "
            "The sphere is unstable, crackling, dangerous. Beautiful but terrifying. "
            "The boy stands at the edge of the room watching, eyes wide, mouth open. "
            "Kael closes his fist and the sphere vanishes. He looks at the boy. "
            "He points at the center of the symbol circle. The message is clear — your turn."
        ),
    },
    {
        "duration": 12,
        "narration": "The training was brutal. Every night. The same thing. Try to hold the energy. Fail. Try again.",
        "prompt": (
            f"{STYLE}"
            "Same underground training room, blue torchlight, symbol circle on the floor. "
            "The boy kneels in the center of the circle, hands pressed together, eyes squeezed shut. "
            "Blue energy flickers around his body weakly — appearing and disappearing randomly. "
            "Sweat drips down his face. His arms shake from effort. "
            "A small blue sphere forms between his palms. It wobbles, unstable. "
            "It grows to the size of a baseball. Bright. Promising. "
            "Then it pops like a bubble. Blue sparks scatter. The boy slumps forward exhausted. "
            "Behind him, Kael sits against the wall watching with a calm expression. "
            "He holds up one finger. Again. "
            "The boy takes a deep breath, sits back up, and presses his palms together once more."
        ),
    },
    {
        "duration": 12,
        "narration": "Then one night... Kael said something that changed everything. This power has a price. Are you willing to pay it?",
        "prompt": (
            f"{STYLE}"
            "Same underground training room. The boy sits on the floor exhausted, leaning against the wall. "
            "Blue energy residue fades from his hands. He is breathing hard. "
            "Kael sits across from him, legs crossed, face half in shadow from the blue torchlight. "
            "Kael holds up his own hand — his fingers are slightly transparent at the tips, "
            "like they are fading away. Not fully solid. A cost of his power made visible. "
            "The boy stares at Kael's fading fingers with a horrified expression. "
            "Kael's face is calm, accepting. He has lived with this cost for years. "
            "He looks the boy directly in the eyes. Serious. No more games. "
            "The boy looks at his own hands. Normal. Solid. For now. "
            "He clenches his fists. His jaw tightens. He nods slowly. He accepts."
        ),
    },
    {
        "duration": 12,
        "narration": "He chose to pay the price. ...He had no idea how high it would be. Episode 3 coming soon.",
        "prompt": (
            f"{STYLE}"
            "Same underground training room. The boy stands in the center of the symbol circle alone. "
            "Kael stands at the edge of the room, arms crossed, watching intently. "
            "The boy closes his eyes. Takes a deep breath. Presses his palms together. "
            "Blue energy appears — stronger than ever before. Stable. Bright. "
            "A perfect blue sphere forms between his palms. It grows. Bigger. Brighter. "
            "The sphere is the size of a basketball now, glowing intensely, lighting up the entire room. "
            "The ancient symbols on the floor begin glowing in response, matching his blue light. "
            "The boy opens his eyes — they are glowing bright blue. "
            "But at the very tips of his fingers, barely visible, the skin flickers slightly transparent. "
            "Just for a moment. Then solid again. The cost has begun. "
            "Kael sees it. His expression darkens. He looks away. "
            "The boy does not notice his own fading fingers. He smiles at the glowing sphere. Proud. "
            "Camera slowly zooms into his fingertips — the faint transparency visible. Fade to black."
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
        ft = f"/tmp/ep2_{i}.jpg"
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
        "title": "The Last Student - Episode 2",
        "description": "The teacher nobody trusts. The power nobody should have. The price nobody talks about. #anime #series #Shorts",
        "tags": ["anime", "series", "The Last Student", "episode 2", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
