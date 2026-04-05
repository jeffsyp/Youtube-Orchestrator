"""Yeah Thats Clean — Power Absorber v2. Moderation-safe. Auto-upload to YTC + gamatatsengan."""
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
        "narration": "The arena was packed. Two warriors. One was a monster. The other... had never won a single match.",
        "prompt": (
            f"{STYLE}"
            "A massive anime underground arena. Stone walls, flaming torches on pillars, "
            "a roaring crowd of anime characters in the stands. "
            "Two warriors face each other in a circular dirt arena. "
            "On the left — a huge muscular anime warrior with a red energy aura, scars, shaved head, confident smirk. "
            "On the right — a small thin anime boy with messy dark hair, bandaged hands, torn white shirt. "
            "The crowd cheers for the big warrior. Some point at the small boy and laugh. "
            "The small boy takes a deep breath. Raises his fists. His hands tremble slightly."
        ),
    },
    {
        "duration": 12,
        "narration": "The first energy blast almost ended it. ...But something strange happened. He got back up. And he felt... stronger.",
        "prompt": (
            f"{STYLE}"
            "A dusty anime training yard outside the arena, stone walls in the background. "
            "The small boy is on the ground, face down in the dirt. A dust cloud settles around him. "
            "A red energy scorch mark on the ground near him shows where a blast landed. "
            "The boy pushes himself up slowly. His lip is bleeding. "
            "As he stands, a faint blue glow appears around his body. Subtle. New. "
            "His eyes have a tiny blue shimmer that was not there before. "
            "He stands fully upright. He seems slightly taller. Slightly more solid. "
            "He looks at his own glowing hands, confused. He clenches his fists. "
            "The blue glow pulses stronger for a moment."
        ),
    },
    {
        "duration": 12,
        "narration": "Every blast made him stronger. The big guy did not realize... he was feeding a monster.",
        "prompt": (
            f"{STYLE}"
            "An anime mountain cliffside at sunset, dramatic orange sky. "
            "The small boy stands on the cliff edge. He is visibly larger now — more muscular, taller. "
            "Blue energy crackles across his arms and shoulders like electricity. "
            "His eyes glow bright blue. His torn shirt stretches across broader shoulders. "
            "Blue glowing marks cover his arms where previous blasts landed — each wound made him stronger. "
            "He looks down at his massive glowing hands. He opens and closes them slowly. "
            "Wind whips his hair. Blue energy particles drift off his body like embers. "
            "The ground beneath his feet cracks from the energy pressure. "
            "He looks powerful. Transformed. Barely recognizable as the small kid from before."
        ),
    },
    {
        "duration": 12,
        "narration": "One more blast. That is all he needed. The big guy was happy to oblige.",
        "prompt": (
            f"{STYLE}"
            "Back in the anime underground arena. Torches, crowd, circular dirt floor. "
            "The big red warrior stands with his arm extended, red energy fading from his palm. "
            "He is panting, sweating, confused. His red aura is dim. "
            "Across from him the boy stands unmoved — now equal in size, glowing bright blue. "
            "A red energy scorch mark on the boy's chest fades as blue light absorbs it completely. "
            "The boy's body flashes blindingly bright blue. He grows even larger. "
            "He now towers over the red warrior. Massive. Radiating blue power. "
            "The ground cracks in a spiderweb pattern under his feet. Torches on the walls flicker wildly. "
            "The big warrior's eyes go wide. He steps backward for the first time."
        ),
    },
    {
        "duration": 12,
        "narration": "He could have destroyed him. Instead he just... raised one finger. That was enough.",
        "prompt": (
            f"{STYLE}"
            "A wide open anime field outside the arena at night. Stars above, moonlight. "
            "The big red warrior lies on the ground in the distance, defeated, not moving. "
            "A trail of disturbed earth stretches from the arena wall to where he lies — "
            "he was sent flying by an enormous force. "
            "The boy walks out of the arena entrance, shrinking back to his normal small size. "
            "Blue glow fades from his body. He is just a small thin kid again. "
            "He looks at his own hands, still trembling slightly. "
            "The crowd pours out of the arena behind him, cheering, reaching toward him. "
            "He does not turn around. He just keeps walking into the moonlit field. "
            "A tiny smile crosses his face. He walks alone under the stars."
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
        ft = f"/tmp/absv2_{i}.jpg"
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

    # Auto-upload to both channels
    from apps.publishing_service.uploader import upload_video
    for token, channel in [("youtube_token_yeah_thats_clean.json", "YTC"), ("youtube_token_gamatatsengan.json", "gamatatsengan")]:
        try:
            result = upload_video(
                video_path=final,
                title="Every Hit Made Him Stronger",
                description="He never won a match. Until they realized losing was his strategy.\n\n#anime #action #underdog #Shorts",
                tags=["anime", "action", "underdog", "power up", "Shorts"],
                category="Entertainment", privacy_status="private",
                youtube_token_file=token, made_for_kids=False,
            )
            print(f"Uploaded to {channel}: {result.get('url', '?')}")
        except Exception as e:
            print(f"Upload to {channel} failed: {e}")

    async with async_session() as session:
        await session.execute(text("UPDATE content_runs SET status='published' WHERE id=:rid"), {"rid": run_id})
        await session.commit()
    print(f"Done! Run #{run_id}")


asyncio.run(main())
