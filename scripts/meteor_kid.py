"""Yeah Thats Clean — The Kid Who Absorbed a Meteor. Auto-upload."""
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
    "Dragon Ball Z energy effects, massive scale, cinematic, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "He reached up... and the meteor reached back.",
        "prompt": (
            f"{STYLE}"
            "A massive glowing orange meteor fills the top half of the screen, enormous, world-ending. "
            "Below it, a tiny anime boy floats in the dark sky with both arms raised toward the meteor. "
            "Orange energy streams from the meteor downward into his open palms like rivers of fire. "
            "His entire body glows white-hot. His veins pulse orange under his skin like lava. "
            "A massive Dragon Ball Z style energy aura explodes around his small body — "
            "white and orange swirling power, crackling lightning, shockwave rings expanding outward. "
            "His hair whips straight up from the force. His clothes tear from the energy pressure. "
            "The meteor visibly SHRINKS as he absorbs it — getting smaller and smaller. "
            "The boy's glow gets brighter and brighter. The whole sky turns white from the energy. "
            "Dramatic anime sound effects — deep rumbling, energy crackling, wind howling."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind. He couldn't even hold a spark. Dead last. The weakest in the whole academy.",
        "prompt": (
            f"{STYLE}"
            "A bright anime academy classroom during the day. Large windows, sunlight streaming in. "
            "Rows of student desks. Other anime students sit at their desks confidently holding "
            "glowing energy orbs in their palms — some orbs are big and bright, impressive. "
            "At the very back of the class, the same boy sits alone at his desk. "
            "His hands are cupped together in front of him. A tiny pathetic flicker of light "
            "blinks between his palms and dies. Not even a spark. "
            "An anime instructor with glasses walks past his desk, glances down, shakes his head. "
            "Two students in front of him turn around and snicker, pointing at his empty hands. "
            "The boy stares down at his own palms. Nothing there. His face shows quiet frustration."
        ),
    },
    {
        "duration": 12,
        "narration": "When the meteor came... everyone ran. ...He just stood there. He had nothing to lose.",
        "prompt": (
            f"{STYLE}"
            "A wide anime city street at dusk. The sky is turning deep orange — not from sunset, "
            "from a massive glowing meteor visible high in the sky, getting closer. "
            "The meteor leaves a long burning trail across the atmosphere. It is enormous. "
            "People on the street are running in panic — grabbing children, screaming, fleeing. "
            "Cars are abandoned in the road. Alarms blare from buildings. "
            "In the middle of the chaos, one person stands completely still — the boy. "
            "He stands in the center of the empty street while everyone runs past him. "
            "He stares straight up at the meteor. Wind from the approaching impact blows his hair. "
            "His face is calm. Not brave — empty. He has nothing to lose. "
            "The meteor's orange glow reflects in his eyes. He takes one step forward."
        ),
    },
    {
        "duration": 12,
        "narration": "Nobody saw him go up. They just saw the meteor... stop.",
        "prompt": (
            f"{STYLE}"
            "An anime city rooftop at night. The city skyline stretches below. "
            "Citizens on other rooftops and in streets are looking UP at the sky, pointing, mouths open. "
            "High above the city, a brilliant white light shines where the meteor used to be. "
            "The meteor has stopped moving. It hangs frozen in the sky. "
            "Bright orange and white energy streams downward from the meteor into a tiny glowing figure below it — "
            "barely visible, just a small silhouette against the massive meteor. "
            "The meteor is visibly shrinking — getting smaller and smaller as energy drains from it. "
            "People on the rooftops shield their eyes from the blinding light. "
            "The wind has stopped. Everything is still except the energy flowing downward. "
            "The meteor shrinks to half its size. Then a quarter. The sky is clearing."
        ),
    },
    {
        "duration": 12,
        "narration": "The meteor was gone. The city was saved. ...But he could still feel it inside him. Waiting.",
        "prompt": (
            f"{STYLE}"
            "Dawn breaking over the anime city. Golden sunrise light on the buildings. "
            "A massive smoking crater in a field just outside the city walls. "
            "The boy kneels at the center of the crater, alone. Head down. Exhausted. "
            "The city behind him is completely untouched — he saved every building, every person. "
            "Faint orange cracks of light still glow on his skin, slowly fading. "
            "Steam rises from his body into the cold morning air. "
            "His hands press against the scorched ground. They are trembling. "
            "The sunrise casts long golden rays across the crater, lighting up the steam around him. "
            "He slowly lifts his head and looks at the saved city in the distance. "
            "His eyes flash orange for just a moment — the power is still inside him. "
            "Wide final shot — tiny boy in the center of the massive crater, "
            "untouched city behind him, golden sunrise, steam rising around him."
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

    # Generate narration
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

    # Generate SRT subtitles
    print("Generating subtitles...")
    srt_path = f"{output_dir}/subtitles.srt"
    with open(srt_path, "w") as f:
        for i, clip in enumerate(CLIPS):
            start_sec = i * 12
            end_sec = start_sec + 10  # Leave 2s gap
            start_ts = f"00:00:{start_sec:02d},000"
            end_ts = f"00:00:{end_sec:02d},000"
            if start_sec >= 60:
                start_ts = f"00:01:{start_sec-60:02d},000"
            if end_sec >= 60:
                end_ts = f"00:01:{end_sec-60:02d},000"
            f.write(f"{i+1}\n{start_ts} --> {end_ts}\n{clip['narration']}\n\n")

    # Generate Sora clips
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
        ft = f"/tmp/meteor_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                         "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
        if os.path.exists(ft):
            with open(ft, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(ft)

    # Mix narration into clips
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

    # Burn subtitles into each clip
    print("Burning subtitles...")
    subtitled = []
    for i, p in enumerate(mixed):
        sub_path = f"{output_dir}/clips/sub_{i:02d}.mp4"
        # Create per-clip SRT
        clip_srt = f"{output_dir}/clips/sub_{i:02d}.srt"
        with open(clip_srt, "w") as f:
            f.write(f"1\n00:00:00,500 --> 00:00:09,500\n{CLIPS[i]['narration']}\n\n")
        subprocess.run([
            "ffmpeg", "-y", "-i", p,
            "-vf", f"subtitles={clip_srt}:force_style='FontSize=11,FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=40'",
            "-c:a", "copy", sub_path,
        ], capture_output=True)
        subtitled.append(sub_path if os.path.exists(sub_path) else p)

    # Normalize and concatenate
    print("Concatenating...")
    norms = []
    for i, p in enumerate(subtitled):
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
                title="The Kid Who Absorbed a Meteor",
                description="He couldn't even hold a spark. Then a meteor came. And he was the only one who didn't run.\n\n#anime #meteor #powers #dragonballz #Shorts",
                tags=["anime", "meteor", "powers", "dragon ball z", "action", "Shorts"],
                category="Entertainment", privacy_status="private",
                youtube_token_file=token, made_for_kids=False,
                captions_path=srt_path,
            )
            print(f"Uploaded to {channel}: {result.get('url', '?')}")
        except Exception as e:
            print(f"Upload to {channel} failed: {e}")

    async with async_session() as session:
        await session.execute(text("UPDATE content_runs SET status='published' WHERE id=:rid"), {"rid": run_id})
        await session.commit()
    print(f"Done! Run #{run_id}")


asyncio.run(main())
