"""3D Stick People — The Worst Heist Ever. Two voice characters."""
import asyncio, base64, json, os, subprocess
os.chdir("/home/jeff/youtube-orchestrator")

STYLE = (
    "Vertical 9:16 aspect ratio, 3D rendered animation, simple white stick figure characters "
    "with round heads, clean minimal environment, soft studio lighting, "
    "smooth animation, no text, no watermarks, no UI elements. "
)

# Two voices — deep dumb guy and nervous smart guy
VOICE_DEEP = "Brian"  # Deep, Resonant
VOICE_NERVOUS = "Liam"  # Energetic

CLIPS = [
    {
        "duration": 8,
        "dialogue": [
            ("deep", "OK. You go left. I go right."),
            ("nervous", "That's the same direction."),
            ("deep", "Just go."),
        ],
        "prompt": (
            f"{STYLE}"
            "Two 3D white stick figure characters stand in front of a large silver vault door "
            "in a clean white hallway. One stick figure is slightly taller than the other. "
            "The tall one points confidently at the vault door. "
            "The short one looks at the tall one and tilts his head sideways, confused. "
            "The tall one walks forward confidently and walks directly into the vault door face first. "
            "He bounces off and falls flat on his back on the floor. "
            "The short one stares down at him."
        ),
    },
    {
        "duration": 8,
        "dialogue": [
            ("nervous", "I'm stuck."),
            ("deep", "Push harder."),
            ("nervous", "I AM pushing harder."),
            ("deep", "That was my face."),
        ],
        "prompt": (
            f"{STYLE}"
            "A white hallway with a small square vent opening high on the wall. "
            "One 3D white stick figure stands on the shoulders of the other stick figure. "
            "The top stick figure is halfway inside the vent — his upper body is inside, "
            "his legs dangle and kick outside the vent. He is stuck. "
            "The bottom stick figure pushes on the dangling legs trying to shove him through. "
            "They wobble and lose balance. Both stick figures fall in a pile on the white floor. "
            "They lie tangled together on the ground."
        ),
    },
    {
        "duration": 8,
        "dialogue": [
            ("deep", "Wait. Was that door always unlocked?"),
            ("nervous", "..."),
            ("deep", "..."),
            ("nervous", "I'm not telling anyone about this."),
        ],
        "prompt": (
            f"{STYLE}"
            "Two 3D white stick figures sit on the white floor with their backs against the silver vault door. "
            "They look exhausted and defeated. "
            "One stick figure leans backward and his head bumps the vault door handle. "
            "The vault door slowly swings wide open behind them. "
            "They both turn and look at the open vault. "
            "Inside the vault is completely empty. Nothing. Just a clean white empty room. "
            "They stare at the empty vault. They slowly turn and look at each other. "
            "They stare forward again. Silence."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text as sql_text
    from faster_whisper import WhisperModel

    async with async_session() as session:
        result = await session.execute(sql_text(
            "INSERT INTO content_runs (channel_id, status, current_step, content_type) "
            "VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/yeah_thats_clean_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/dialogue", exist_ok=True)

        # Generate dialogue audio per clip — combine all lines into one audio per clip
        print("Generating dialogue...")
        dialogue_paths = []
        for i, clip in enumerate(CLIPS):
            clip_audio_parts = []
            for j, (voice_type, line) in enumerate(clip["dialogue"]):
                voice = VOICE_DEEP if voice_type == "deep" else VOICE_NERVOUS
                part_path = f"{out}/dialogue/clip{i}_line{j}.mp3"
                generate_speech(line, voice=voice, output_path=part_path)
                clip_audio_parts.append(part_path)

            # Concatenate all lines for this clip with small gaps
            parts_list = f"{out}/dialogue/clip{i}_parts.txt"
            silence = f"{out}/dialogue/silence.mp3"
            # Generate 0.3s silence
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                           "-t", "0.3", "-c:a", "libmp3lame", silence], capture_output=True)

            with open(parts_list, "w") as f:
                for k, part in enumerate(clip_audio_parts):
                    f.write(f"file '{os.path.abspath(part)}'\n")
                    if k < len(clip_audio_parts) - 1:
                        f.write(f"file '{os.path.abspath(silence)}'\n")

            combined = f"{out}/dialogue/clip{i}_combined.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts_list,
                           "-c:a", "libmp3lame", combined], capture_output=True)
            dialogue_paths.append(combined if os.path.exists(combined) else clip_audio_parts[0])
            print(f"  Clip {i+1}: {len(clip['dialogue'])} lines OK")

        # Sora clips
        print("\nClips...")
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"Clip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=clip["duration"], size="720x1280", timeout=1200,
                reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/heist_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                             "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f:
                    prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Mix dialogue into clips
        print("\nMixing dialogue...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", dialogue_paths[i],
                "-filter_complex", "[0:a]volume=0.4[s];[1:a]volume=1.5[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx],
                capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        # Normalize + concat
        print("Concat...")
        norms = []
        for i, p in enumerate(mixed):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf",
                "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
                "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
        raw = f"{out}/raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", raw], capture_output=True)
        if not os.path.exists(raw): raise RuntimeError("Concat failed")

        # Subtitles — show dialogue lines with timing from whisper
        print("Subtitles...")
        model = WhisperModel("base", device="cpu")
        chunks, offset = [], 0
        for i in range(len(CLIPS)):
            segments, _ = model.transcribe(dialogue_paths[i], word_timestamps=True)
            words = [(offset+w.start, offset+w.end, w.word.strip()) for seg in segments for w in seg.words]
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')):
                    chunks.append((start, e, ' '.join(group))); group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))
            offset += CLIPS[i]["duration"]

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Pop\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Pop,Impact,52,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,2,20,20,120,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for s, e, text in chunks:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Pop,,0,0,0,,{text.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")
        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "rendered_yeah_thats_clean_short", "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata", "c": json.dumps({"title": "The Worst Heist Ever", "description": "They had a plan. It was not a good plan.\n\n#animation #funny #comedy #heist #stickfigure #Shorts", "tags": ["animation", "funny", "comedy", "heist", "stick figure", "Shorts"], "category": "Entertainment"})})
            await session.execute(sql_text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"), {"rid": run_id})
            await session.commit()
        print(f"Review queue: Run #{run_id}")
    except Exception as e:
        print(f"ERROR: {e}")
        async with async_session() as session:
            await session.execute(sql_text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"), {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise

asyncio.run(main())
