"""Guy Outruns a Train. Short, punchy, no fluff."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, dynamic speed lines, dramatic lighting, cinematic, "
    "no text, no watermarks, no UI elements. "
)

# Just 3 clips — tight, no filler
CLIPS = [
    {
        "duration": 8,
        "narration": "The train was faster. Everyone knew that. ...He didn't care.",
        "prompt": (
            f"{STYLE}"
            "A long steel bridge stretching across a canyon at sunset. Dramatic orange sky. "
            "A bullet train races across the bridge from left to right at incredible speed, "
            "sleek silver metal, motion blur, sparks from the rails. "
            "Running alongside the train on the narrow walkway of the bridge — "
            "a young anime man in a tank top and shorts, sprinting at full speed. "
            "His legs are a blur. Speed lines trail behind him. "
            "Sweat flies off his face. His expression is pure determination — teeth gritted, eyes locked forward. "
            "The train is slightly ahead of him. He is losing. "
            "The canyon drops away far below them. Wind whips everything."
        ),
    },
    {
        "duration": 8,
        "narration": "His shoes started melting. He pushed harder.",
        "prompt": (
            f"{STYLE}"
            "Close-up shot of the runner's feet pounding the bridge walkway at insane speed. "
            "His running shoes are smoking — the soles are melting from friction, leaving dark marks on the metal. "
            "Sparks fly from his feet with each step. The metal walkway is denting under each footfall. "
            "Camera pulls up to his face — pure agony and determination. Veins on his neck. "
            "Beside him, the bullet train windows blur past. Passengers inside stare at him in disbelief. "
            "He is gaining on the train now. Inch by inch. His body leans forward impossibly far. "
            "The end of the bridge is visible ahead — both the train and the runner approaching the finish."
        ),
    },
    {
        "duration": 8,
        "narration": "One step. That's all he needed.",
        "prompt": (
            f"{STYLE}"
            "The end of the bridge. Wide dramatic shot from ahead looking back. "
            "The bullet train and the runner reach the end of the bridge at the exact same moment. "
            "The runner throws his body forward in a final desperate lunge, arms reaching. "
            "His foot crosses the end of the bridge ONE STEP before the train's nose passes the same point. "
            "Dramatic slow motion — his foot landing, the train nose just behind him. "
            "His melted shoes leave a smoking footprint on the ground. "
            "He stumbles forward past the bridge and falls to his hands and knees on the ground. "
            "The train rockets past behind him, wind blast blowing his hair forward. "
            "He stays on his knees, head down, breathing hard. Then he looks up. Grins."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text
    from faster_whisper import WhisperModel

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/yeah_thats_clean_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        # Narration
        print("Narration...")
        for i, clip in enumerate(CLIPS):
            generate_speech(clip["narration"], voice=ANIME_VOICE,
                          output_path=f"{out}/narration/n_{i}.mp3")
        print("Done")

        # Sora clips
        print("\nClips...")
        clip_paths = []
        prev_ref = None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"\nClip {i+1}/{len(CLIPS)}...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=clip["duration"], size="720x1280", timeout=1200,
                reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/train_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                             "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f:
                    prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Mix narration
        print("\nMixing...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            vo = f"{out}/narration/n_{i}.mp3"
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", vo,
                "-filter_complex", "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
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

        # Pop-in subtitles
        print("Subtitles...")
        model = WhisperModel("base", device="cpu")
        chunks = []
        clip_offset = 0
        for i in range(len(CLIPS)):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            words = []
            for seg in segments:
                for w in seg.words:
                    words.append((clip_offset + w.start, clip_offset + w.end, w.word.strip()))
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')):
                    chunks.append((start, e, ' '.join(group)))
                    group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))
            clip_offset += CLIPS[i]["duration"]

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Pop\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Pop,Impact,52,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,2,20,20,120,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for s, e, text in chunks:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Pop,,0,0,0,,{text.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")

        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        # Review queue
        async with async_session() as session:
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "rendered_yeah_thats_clean_short",
                 "c": json.dumps({"status": "rendered", "path": os.path.abspath(final),
                                  "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata",
                 "c": json.dumps({"title": "He Outruns a Bullet Train",
                                  "description": "They said no one could. He did. #anime #action #train #speed #Shorts",
                                  "tags": ["anime", "action", "train", "speed", "race", "Shorts"],
                                  "category": "Entertainment"})})
            await session.execute(
                text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"),
                {"rid": run_id})
            await session.commit()
        print(f"Review queue: Run #{run_id}")

    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise

asyncio.run(main())
