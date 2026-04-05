"""Yeah Thats Clean — Naruto-style ninja story, 60 second narrated anime short."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, dynamic speed lines, dramatic lighting with lens flares, "
    "Naruto and anime ninja inspired art style, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "They called him the weakest ninja in the village. ...He was about to prove them all wrong.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A massive anime battle arena at night, torches lining the walls, hundreds of anime spectators in the stands. "
            "A young anime ninja with spiky black hair and a torn headband stands alone in the center of the arena. "
            "He is covered in dirt and scratches. His eyes burn with determination — they glow faintly blue. "
            "Across from him stands a much larger, muscular anime ninja with a confident smirk and crossed arms. "
            "The crowd jeers and points at the smaller ninja. "
            "The smaller ninja drops into a fighting stance. Blue energy swirls around his feet. "
            "The ground cracks beneath him. The crowd goes silent. "
            "Close-up of his glowing blue eyes. Something has awakened."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind... six months earlier. He couldn't even land a single technique.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "An anime ninja training ground during the day, wooden training posts, dirt field. "
            "The same young ninja with spiky black hair, younger looking, no scratches, wearing a clean uniform. "
            "He attempts to throw a glowing energy ball from his hands. "
            "The energy fizzles and pops weakly. A small puff of smoke. Nothing happens. "
            "Other anime ninja students nearby laugh and point at him. "
            "A stern anime instructor shakes his head in disappointment. "
            "The young ninja looks at his own hands, frustrated. He clenches his fists. "
            "He stays after everyone leaves. The training ground is empty at sunset. "
            "He tries again. Another fizzle. He slams his fist on a training post."
        ),
    },
    {
        "duration": 12,
        "narration": "Every night... same mountain. Same waterfall. Training until his hands wouldn't move.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A dramatic anime mountain waterfall at night, moonlight casting silver on the water. "
            "The young ninja stands under the crashing waterfall, water pounding on his shoulders. "
            "He holds his hands out in front of him, concentrating intensely. "
            "A small blue glow appears between his palms. It flickers. He grits his teeth. "
            "The glow grows slightly brighter. His whole body shakes with effort. "
            "He yells with determination — the blue glow pulses outward in a small shockwave. "
            "The waterfall splits for a moment from the force. Then crashes back down on him. "
            "He falls to his knees in the water, exhausted, breathing hard. "
            "But he stands back up. Gets back under the waterfall. Tries again. "
            "Montage feel — him training night after night, the blue glow getting stronger each time."
        ),
    },
    {
        "duration": 12,
        "narration": "Six months of silence. Then... he walked into the arena. And everything changed.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "The anime battle arena at night from the opening. Torches, crowd, dramatic atmosphere. "
            "The large muscular ninja charges forward with incredible speed, fist pulled back, "
            "orange energy trailing behind his fist. "
            "The small ninja with spiky black hair stands completely still. His eyes glow bright blue. "
            "At the last possible moment the small ninja sidesteps — the large ninja's fist misses by an inch. "
            "The small ninja places one hand on the large ninja's back as he passes. "
            "A massive burst of blue energy explodes from his palm. "
            "The large ninja is launched forward across the arena, skidding across the dirt, crashing into the far wall. "
            "The crowd gasps. Complete silence. "
            "The small ninja stands calmly, blue energy crackling around his hand."
        ),
    },
    {
        "duration": 12,
        "narration": "They called him the weakest ninja in the village. ...Nobody calls him that anymore.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "The anime battle arena. The large ninja lies defeated against the far wall, unable to stand. "
            "The small ninja walks slowly to the center of the arena. The crowd is dead silent. "
            "He stops. Looks up at the stands. His blue eyes glow with quiet power. "
            "One person in the crowd starts clapping. Then another. Then the whole arena erupts. "
            "The stern instructor from earlier stands at the edge of the arena. "
            "He nods slowly with respect. A small smile crosses his face. "
            "The young ninja looks at his own hands — the same hands that couldn't make a spark six months ago. "
            "Blue energy dances across his fingertips effortlessly now. "
            "He closes his fists. Looks up at the night sky. The stars reflect in his glowing eyes. "
            "Final wide shot — the young ninja silhouetted in the arena under the stars, crowd cheering around him."
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

    print("Generating narration (anime voice)...")
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
        r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
            duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
        clip_paths.append(cp)
        print(f"  Saved: {r['file_size_bytes']} bytes")
        ft = f"/tmp/ninja_{i}.jpg"
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
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", narration_paths[i], "-filter_complex",
                "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)
        else:
            mixed.append(cp)

    print("Concatenating...")
    norms = []
    for i, p in enumerate(mixed):
        n = f"{output_dir}/clips/norm_{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", p, "-vf",
            "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
        norms.append(n if os.path.exists(n) else p)

    cl = f"{output_dir}/concat.txt"
    with open(cl, "w") as f:
        for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
    final = f"{output_dir}/yeah_thats_clean_short.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", final], capture_output=True)
    if not os.path.exists(final): raise RuntimeError("Concat failed")
    print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

    from apps.orchestrator.activities import mark_run_pending_review
    async with async_session() as session:
        await session.execute(text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
        await session.commit()
    await mark_run_pending_review(run_id, {"title": "The Weakest Ninja", "description": "They called him the weakest. He proved them all wrong. #anime #ninja #action #story #Shorts",
        "tags": ["anime", "ninja", "action", "story", "Shorts"], "category": "Entertainment"})
    print(f"Done! Run #{run_id}")

asyncio.run(main())
