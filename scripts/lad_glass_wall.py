"""Lad Walks Into a Glass Door. 20 seconds."""
import asyncio, base64, json, os, subprocess
os.chdir("/home/jeff/youtube-orchestrator")
from packages.prompts.lad_stories import CHARACTER_BIBLE, STYLE_BIBLE

STYLE = (
    "Vertical 9:16 aspect ratio, claymation stop-motion style, "
    "visible hand-crafted textures, fingerprint marks in clay, "
    "miniature handmade set/diorama, warm soft diffused lighting, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {"duration": 4,
     "narration": "Nobody told Lad about the wall. To be fair, you can't really see it.",
     "prompt": f"{STYLE} {CHARACTER_BIBLE} A tiny clay hallway with warm lighting and clay walls. Lad the small round clay character walks forward confidently with a happy bounce in his step. He walks face-first into an invisible glass surface. His whole round clay body squishes flat against the glass. He peels off the glass slowly and falls backward onto the floor. He lies on his back looking confused at the ceiling."},

    {"duration": 8,
     "narration": "So he tried again. Slowly this time. Hands out. Feeling for it. Nothing there. Safe. And then... not safe.",
     "prompt": f"{STYLE} {CHARACTER_BIBLE} A tiny clay park with green clay trees and a clay path. Lad the clay character walks very slowly and carefully down the path. Both stubby arms are stretched out in front of him feeling the air. He takes careful tiny steps. He feels nothing. He relaxes. Drops his arms. Takes one normal confident step forward. His face squishes flat against another invisible glass surface. His body compresses against it. He slides down the glass slowly to the ground."},

    {"duration": 8,
     "narration": "Lad doesn't solve problems the smart way. But he solves them.",
     "prompt": f"{STYLE} {CHARACTER_BIBLE} A tiny clay field with green clay grass. Lad the clay character stands holding a round clay rock in both stubby arms. He winds up and throws the rock forward with all his strength. The rock flies forward and hits an invisible surface — the surface cracks and shatters into many pieces of clear shiny fragments that fall to the ground. A hole opens up in the invisible barrier. Lad walks through the broken opening proudly. He dusts off his stubby hands."},
]

async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text as sql_text
    from faster_whisper import WhisperModel

    async with async_session() as session:
        result = await session.execute(sql_text("INSERT INTO content_runs (channel_id, status, current_step, content_type) VALUES (6, 'running', 'generate_clips', 'lad_stories') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/lad_stories_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        print("Narration...")
        for i, clip in enumerate(CLIPS):
            generate_speech(clip["narration"], output_path=f"{out}/narration/n_{i}.mp3")

        print("\nClips...")
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"Clip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/ladglass_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        print("\nMixing...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        print("Concat...")
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
        if not os.path.exists(raw): raise RuntimeError("Concat failed")

        print("Subtitles...")
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
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")
        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 6, :a, :c)"), {"rid": run_id, "a": "rendered_lad_stories_short", "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "lad_stories_short"})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 6, :a, :c)"), {"rid": run_id, "a": "publish_metadata", "c": json.dumps({"title": "Lad vs The Invisible Wall", "description": "Nobody told Lad about the wall. To be fair you can't really see it.\n\n#claymation #funny #animation #lad #Shorts", "tags": ["claymation", "funny", "animation", "lad", "invisible wall", "Shorts"], "category": "Entertainment"})})
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
