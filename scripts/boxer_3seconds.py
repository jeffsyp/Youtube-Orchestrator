"""Yeah Thats Clean — The Boxer Who Sees 3 Seconds Ahead. Auto-upload."""
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
        "narration": "He could see every move... three seconds before it happened. Forty seven fights. Forty seven wins. ...Until tonight.",
        "prompt": (
            f"{STYLE}"
            "An anime boxing ring under bright stadium lights. Packed crowd in the stands. "
            "An anime boxer with short dark hair and white shorts stands in slow motion mid-dodge. "
            "His eyes glow faint white — supernatural. "
            "In front of him, a ghostly transparent preview of a fist coming toward his face — "
            "a phantom image showing what will happen 3 seconds from now. "
            "But the REAL fist is already there — faster than the prediction. "
            "The real fist connects with his jaw. Bright impact flash. Sweat droplets fly in slow motion. "
            "His head snaps to the side. His eyes go wide — shock. This has never happened before. "
            "The crowd in the background freezes mid-cheer. "
            "Close-up of his stunned face — the white glow in his eyes flickers. "
            "For the first time in 47 fights, someone hit him."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind. He was born with it. Three seconds. Every move. Every time. Boxing was... too easy.",
        "prompt": (
            f"{STYLE}"
            "An anime training gym during the day. Punching bags, speed bags, a worn canvas ring. "
            "The same boxer with short dark hair shadow boxes alone in the center of the gym. "
            "His eyes glow steady white. "
            "Ghostly transparent phantom images of attacks appear around him — "
            "phantom fists, phantom kicks — he sees them 3 seconds early. "
            "He weaves and dodges each phantom attack effortlessly, flowing like water. "
            "Not a single phantom image touches him. He moves with perfect grace. "
            "An old trainer sits on a stool in the corner watching, arms crossed, shaking his head in amazement. "
            "On the wall behind the trainer, a scoreboard reads 47 wins, 0 losses. "
            "The boxer looks bored. This is too easy for him."
        ),
    },
    {
        "duration": 12,
        "narration": "Then they matched him with someone different. A fighter with no technique. No plan. Just... chaos.",
        "prompt": (
            f"{STYLE}"
            "An anime locker room before a fight. Concrete walls, metal lockers, harsh fluorescent light. "
            "The boxer sits on a wooden bench in his boxing shorts and hand wraps. "
            "He stares at a small TV screen mounted on the wall. "
            "On the TV screen — footage of his opponent warming up. "
            "The opponent is wild — spiky red hair, crazy wide eyes, scars everywhere. "
            "He moves like an animal, unpredictable, twitching, bouncing off walls. "
            "No stance, no form, no rhythm. Pure chaotic energy. "
            "The boxer's eyes glow white trying to read the screen, trying to predict the opponent's moves. "
            "But the ghostly phantom previews keep flickering and shifting — the predictions can't lock on. "
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
            "The wild opponent with spiky red hair charges forward with no stance, arms swinging wildly. "
            "The boxer's eyes glow white — ghostly phantom previews appear showing the opponent's next moves. "
            "But the phantom images keep CHANGING — shifting, flickering, splitting into multiple versions. "
            "The opponent doesn't commit to any move until the last millisecond. "
            "The boxer dodges left based on a prediction — but the opponent already changed direction. "
            "A wild swing catches the boxer on the shoulder. Impact flash. "
            "Another swing from nowhere catches his ribs. Another impact flash. "
            "The boxer stumbles backward, overwhelmed. His white eye glow is flickering rapidly. "
            "The predictions are useless against someone who doesn't think."
        ),
    },
    {
        "duration": 12,
        "narration": "So he stopped looking ahead. For the first time... he just trusted himself.",
        "prompt": (
            f"{STYLE}"
            "Same anime boxing ring. The boxer is on one knee, breathing hard, blood on his lip. "
            "His eyes stop glowing. The white light fades completely. His eyes are normal dark brown now. "
            "The wild opponent winds up for a massive final swing, arm pulled all the way back. "
            "The boxer closes his eyes. Completely dark. No predictions. No phantom images. Nothing. "
            "The opponent swings. "
            "The boxer's body moves on pure instinct — he slips the wild swing by an inch. "
            "His eyes snap open — dark brown, no glow — and he throws one single clean counter. "
            "His fist connects perfectly with the opponent's jaw. Clean white impact flash. "
            "The opponent's head snaps back. His body goes limp. He falls backward in slow motion. "
            "The opponent hits the canvas. Out cold. "
            "The boxer stands alone in the ring, breathing hard, eyes normal. No power. Just him. "
            "The crowd erupts. He looks at his own fist. Smiles. He never needed the power."
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
        ft = f"/tmp/boxer_{i}.jpg"
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

    size = os.path.getsize(final)
    print(f"Final: {size/1024/1024:.1f} MB")

    # Store asset
    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final),
                "size_bytes": size, "content_type": "yeah_thats_clean_short",
            })},
        )
        await session.commit()

    # Auto-upload to Yeah Thats Clean
    print("Uploading to YouTube...")
    from apps.publishing_service.uploader import upload_video
    try:
        result = upload_video(
            video_path=final,
            title="The Boxer Who Sees 3 Seconds Ahead",
            description="47 fights. 47 wins. He could see every move before it happened. Then he fought someone who moved faster than the future.\n\n#anime #boxing #action #story #Shorts",
            tags=["anime", "boxing", "action", "underdog", "powers", "Shorts"],
            category="Entertainment",
            privacy_status="private",
            youtube_token_file="youtube_token_yeah_thats_clean.json",
            made_for_kids=False,
        )
        print(f"Uploaded: {result.get('url', '?')}")

        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='published' WHERE id=:rid"),
                {"rid": run_id},
            )
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
                {"rid": run_id, "atype": "publish_result", "content": json.dumps(result)},
            )
            await session.commit()
    except Exception as e:
        print(f"Upload failed: {e} — video saved locally, mark for review instead")
        from apps.orchestrator.activities import mark_run_pending_review
        await mark_run_pending_review(run_id, {
            "title": "The Boxer Who Sees 3 Seconds Ahead",
            "description": "#anime #boxing #action #Shorts",
            "tags": ["anime", "boxing", "action", "Shorts"],
            "category": "Entertainment",
        })

    print(f"Done! Run #{run_id}")


asyncio.run(main())
