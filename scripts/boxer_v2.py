"""Yeah Thats Clean — Boxer v2. Moderation-safe. Auto-upload to YTC + gamatatsengan."""
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
        "narration": "He could see every move... three seconds before it happened. Forty seven wins. Zero losses. ...Until tonight.",
        "prompt": (
            f"{STYLE}"
            "An anime boxing ring under bright stadium lights. Packed crowd in the stands. "
            "An anime boxer with short dark hair and white shorts stands in slow motion. "
            "His eyes glow faint white — supernatural. "
            "Ghostly transparent phantom images float in the air around him — "
            "previews of moves that will happen 3 seconds from now, like afterimages. "
            "But his face shows shock — for the first time the predictions are wrong. "
            "His head is snapped to one side, sweat droplets flying in slow motion. "
            "The white glow in his eyes flickers and stutters. "
            "The crowd in the background is frozen mid-gasp."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind. He was born with it. Three seconds into the future. Every time. Boxing was... too easy.",
        "prompt": (
            f"{STYLE}"
            "An anime training gym during the day. Punching bags, speed bags, a worn canvas ring. "
            "The same boxer shadow boxes alone in the center of the gym. "
            "His eyes glow steady white. "
            "Ghostly transparent phantom images of incoming moves appear around him — "
            "he sees them 3 seconds early and weaves around each one effortlessly. "
            "He flows like water, dodging invisible moves with perfect grace. "
            "An old trainer sits on a stool in the corner, arms crossed, shaking his head in amazement. "
            "On the wall behind the trainer, a scoreboard reads 47 wins, 0 losses. "
            "The boxer looks bored. This is too easy for him."
        ),
    },
    {
        "duration": 12,
        "narration": "Then they matched him with someone different. No technique. No plan. Just... chaos.",
        "prompt": (
            f"{STYLE}"
            "An anime locker room. Concrete walls, metal lockers, harsh fluorescent light. "
            "The boxer sits on a wooden bench in his shorts and hand wraps. "
            "He stares at a small TV screen mounted on the wall. "
            "On the TV — footage of his opponent warming up. "
            "The opponent is wild — spiky red hair, crazy wide eyes, scars everywhere. "
            "He moves unpredictably, twitching, bouncing, no stance or form at all. "
            "The boxer's eyes glow white trying to read the screen. "
            "But the ghostly phantom previews keep flickering and shifting — can't lock on. "
            "The white glow in his eyes stutters like a broken signal. "
            "The boxer's face shows concern for the first time. He clenches his wrapped fists."
        ),
    },
    {
        "duration": 12,
        "narration": "His power showed him everything. But this guy moved before he even decided to move.",
        "prompt": (
            f"{STYLE}"
            "An anime boxing ring under bright lights. Roaring crowd. "
            "The wild opponent with spiky red hair charges forward chaotically, arms swinging. "
            "The boxer's eyes glow white — ghostly phantom previews appear. "
            "But the phantom images keep CHANGING — splitting into multiple versions, flickering. "
            "The opponent doesn't commit until the last millisecond. "
            "The boxer dodges left based on a prediction — but the opponent already changed direction. "
            "Energy impact flashes appear on the boxer's shoulder and ribs. "
            "The boxer stumbles backward. His white eye glow is flickering rapidly. "
            "The phantom previews shatter like glass around him. "
            "The predictions are useless against someone who doesn't think."
        ),
    },
    {
        "duration": 12,
        "narration": "So he stopped looking ahead. For the first time in his life... he just trusted himself.",
        "prompt": (
            f"{STYLE}"
            "A rain-soaked anime rooftop at night. City lights below. Dramatic moonlight. "
            "The boxer stands alone on the rooftop. His eyes are normal dark brown — no white glow. "
            "Rain pours down on his face. His boxing shorts and wraps are soaked. "
            "He holds his fists up in front of his face in a fighting stance. "
            "His eyes are calm. Clear. No supernatural light. Just human determination. "
            "Behind him, a ghostly white afterimage of his old self with glowing eyes fades away like smoke. "
            "The old power dissolving. Leaving just the man. "
            "He lowers his fists. Opens his hands. Raindrops land in his palms. "
            "A small confident smile crosses his face. He doesn't need the power anymore. "
            "Wide shot — lone figure on the rainy rooftop, city glowing below, at peace."
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
        ft = f"/tmp/boxv2_{i}.jpg"
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

    from apps.publishing_service.uploader import upload_video
    for token, channel in [("youtube_token_yeah_thats_clean.json", "YTC"), ("youtube_token_gamatatsengan.json", "gamatatsengan")]:
        try:
            result = upload_video(
                video_path=final,
                title="The Boxer Who Sees 3 Seconds Ahead",
                description="47 wins. Zero losses. He could see every move before it happened. Then he met someone faster than the future.\n\n#anime #boxing #action #Shorts",
                tags=["anime", "boxing", "action", "underdog", "powers", "Shorts"],
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
