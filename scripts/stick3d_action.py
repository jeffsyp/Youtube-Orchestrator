"""3D Stick People — Action: Stick guy escapes a collapsing room. 20 seconds."""
import asyncio, base64, json, os, subprocess
os.chdir("/home/jeff/youtube-orchestrator")

STYLE = (
    "Vertical 9:16 aspect ratio, 3D rendered animation, simple white stick figure characters "
    "with round heads, clean minimal environment, dramatic lighting, "
    "smooth animation, cinematic camera, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {"duration": 4,
     "narration": "The floor disappeared.",
     "prompt": f"{STYLE} A 3D white stick figure person stands in a large white room. The floor beneath him suddenly cracks and breaks apart into large pieces. The pieces tilt and fall downward into darkness below. The stick figure jumps from one falling piece to another, leaping upward as everything collapses beneath him. Dramatic lighting from above."},

    {"duration": 8,
     "narration": "He had three seconds.",
     "prompt": f"{STYLE} A 3D white stick figure person leaps between large white platforms that are breaking apart and falling. He runs across a crumbling platform, it tilts under his weight, he jumps to the next one just as the previous one falls into the dark void below. Debris falls around him. He grabs onto the edge of a platform with one hand, pulls himself up, keeps running. Dynamic camera follows him."},

    {"duration": 8,
     "narration": "Made it.",
     "prompt": f"{STYLE} A 3D white stick figure person makes one final leap toward a bright white doorway at the top of the collapsing room. He reaches the doorway and lands on solid ground on the other side. Behind him the entire room collapses into darkness — all the platforms falling away. He stands in the bright white doorway looking back at the void. He dusts off his hands. He turns and walks through the bright doorway into white light. Calm. Safe."},
]

async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text as sql_text
    from faster_whisper import WhisperModel

    async with async_session() as session:
        result = await session.execute(sql_text("INSERT INTO content_runs (channel_id, status, current_step, content_type) VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/yeah_thats_clean_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        print("Narration...")
        for i, clip in enumerate(CLIPS):
            generate_speech(clip["narration"], voice="JjsQrIrIBD6TZ656NQfi", output_path=f"{out}/narration/n_{i}.mp3")

        print("\nClips...")
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"Clip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/s3da_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        print("\nMixing + concat + subs...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        norms = []
        for i, p in enumerate(mixed):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
        raw = f"{out}/raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", raw], capture_output=True)

        model = WhisperModel("base", device="cpu")
        chunks, offset = [], 0
        for i in range(len(CLIPS)):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            words = [(offset+w.start, offset+w.end, w.word.strip()) for seg in segments for w in seg.words]
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')): chunks.append((start, e, ' '.join(group))); group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))
            offset += CLIPS[i]["duration"]

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Pop\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Pop,Impact,52,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,2,20,20,120,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for s, e, text in chunks:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Pop,,0,0,0,,{text.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Failed")
        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "rendered_yeah_thats_clean_short", "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "publish_metadata", "c": json.dumps({"title": "The Floor Disappeared", "description": "He had three seconds. He made it.\n\n#animation #action #3d #stickfigure #escape #Shorts", "tags": ["animation", "action", "3d", "stick figure", "escape", "Shorts"], "category": "Entertainment"})})
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
