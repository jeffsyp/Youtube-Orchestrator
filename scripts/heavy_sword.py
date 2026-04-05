"""Yeah Thats Clean — The Sword That's Too Heavy. 60s narrated anime short."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, dramatic lighting with lens flares, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "Every year the strongest warriors tried to pull the sword from the stone. Every year... they failed.",
        "prompt": (
            f"{STYLE}"
            "A medieval anime village town square in bright daylight. Colorful market stalls, stone buildings. "
            "In the center stands a weathered stone pedestal with an ancient glowing sword embedded in it. "
            "The sword has a golden blade and ornate handle, faintly pulsing with light. "
            "A massive muscular anime warrior with armor and a cape grips the sword handle with both hands. "
            "His muscles bulge, veins pop, face straining red with effort. He roars with exertion. "
            "The sword does not move at all. Not even slightly. "
            "A large crowd of villagers watches from around the square. Some cheer him on. "
            "The warrior lets go, defeated, shaking his head. Another warrior steps up to try. "
            "In the very back of the crowd, barely visible, a small scrawny boy with messy hair watches quietly."
        ),
    },
    {
        "duration": 12,
        "narration": "But there was one kid... who came back every single night. For years. And the sword never moved.",
        "prompt": (
            f"{STYLE}"
            "The same stone pedestal with the glowing sword, but now it is NIGHTTIME. Rain pours down heavily. "
            "The town square is completely empty and dark. Puddles reflect the faint glow of the sword. "
            "The same small scrawny anime boy kneels at the base of the pedestal, soaking wet. "
            "His hands grip the sword handle. His knuckles are white. His arms shake. "
            "He pulls upward with everything he has. Rain runs down his strained face. "
            "The sword does not move. He has done this a thousand times. "
            "His hands slip and he falls backward into a puddle. He sits there in the rain. "
            "He looks at his calloused bleeding hands. He looks up at the sword still stuck in the stone. "
            "He is exhausted, wet, alone. But his eyes still have determination in them."
        ),
    },
    {
        "duration": 12,
        "narration": "The blacksmith told him to give up. The village laughed at him. ...Then the sky turned black.",
        "prompt": (
            f"{STYLE}"
            "Inside an anime blacksmith shop during the day. Orange firelight from the forge. "
            "Hammers and swords hang on the walls. Sparks float in the air. "
            "The scrawny boy sweeps the floor with a broom, looking tired and sad. "
            "An old burly blacksmith stands at the anvil shaking his head at the boy disapprovingly. "
            "Through the open shop doorway, the outside sky is visible. "
            "The sky is turning dark — not clouds, but an unnatural pitch-black darkness "
            "creeping over the distant mountains like a living shadow. "
            "The boy stops sweeping. He stares through the doorway at the approaching darkness. "
            "The blacksmith turns and sees it too. His face goes pale with fear. "
            "In the distance, villagers start pointing at the sky and running."
        ),
    },
    {
        "duration": 12,
        "narration": "He ran to the sword one last time. But this time... he did not try to pull it. He just asked.",
        "prompt": (
            f"{STYLE}"
            "The stone pedestal at night during a massive storm. Lightning cracks across a pitch-black sky. "
            "Dark shadowy tendrils creep over the rooftops of the village in the background. "
            "The boy stands at the pedestal. Wind whips his hair and clothes. "
            "He grabs the sword handle but does not pull. "
            "Instead he rests his forehead gently against the flat of the blade. His eyes close. "
            "His lips move — he is speaking quietly to the sword. "
            "A single tear rolls down his cheek mixing with the rain. "
            "The sword begins to hum. A deep resonant vibration. "
            "Golden light pulses from the blade — faintly at first, then brighter, then BRIGHT. "
            "The boy's eyes snap open. They are glowing gold. "
            "His hand tightens on the handle. The stone around the blade begins to crack."
        ),
    },
    {
        "duration": 12,
        "narration": "He was never meant to fight the darkness. ...He was meant to protect everyone from it.",
        "prompt": (
            f"{STYLE}"
            "The village town square — darkness and shadows are pouring in from all sides. "
            "Villagers huddle together in the center, terrified, holding each other. "
            "The boy stands on top of the stone pedestal holding the sword above his head with both hands. "
            "The sword is fully free from the stone, blazing with golden light. "
            "A massive dome of golden light expands outward from the sword in all directions. "
            "The golden dome covers the entire village like a shield. "
            "Dark shadows crash against the dome of light and disintegrate on contact. "
            "The villagers look up at the golden dome in awe. Safe inside its light. "
            "The boy stands at the center, sword raised high, tears streaming down his face, "
            "golden light pouring from the blade. His scrawny arms tremble but hold firm. "
            "The same massive warrior from the first scene stares up at the boy, stunned. "
            "Wide final shot — the small boy on the pedestal, sword raised, "
            "golden dome protecting the entire village from the darkness surrounding it."
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
        ft = f"/tmp/sword_{i}.jpg"
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
        "title": "The Sword That Was Too Heavy",
        "description": "Every warrior failed to pull it. One kid tried every night for years. The sword was waiting for him. #anime #sword #legend #Shorts",
        "tags": ["anime", "sword", "legend", "underdog", "magic", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
