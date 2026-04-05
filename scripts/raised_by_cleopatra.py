"""Fundational — Raised by Cleopatra. Dreamlike cinematic fairy tale."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE = (
    "Vertical 9:16 aspect ratio, dreamlike cinematic style, slightly surreal lighting, "
    "warm golden tones, shallow depth of field, atmospheric fog and particles in the air, "
    "ancient Egypt, photorealistic but with a magical quality, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "She was the most powerful woman in the world. And she raised him... as her own.",
        "prompt": (
            f"{STYLE}"
            "A grand ancient Egyptian throne room. Massive golden pillars. Torchlight. "
            "Cleopatra sits on a golden throne wearing royal Egyptian robes and a golden headdress. "
            "She is beautiful, powerful, regal. "
            "On her lap sits a small child about 4 years old, leaning against her. "
            "She holds the child gently. Her hand rests on his head. "
            "Palace guards with spears stand in the background. "
            "Golden light fills the room. The child looks up at her with trust. "
            "She looks down at him with warmth — a queen who chose to be a mother."
        ),
    },
    {
        "duration": 12,
        "narration": "He learned to read before he could walk. To lead before he could speak.",
        "prompt": (
            f"{STYLE}"
            "A lush ancient Egyptian garden at golden hour. Palm trees, lotus pools, exotic birds. "
            "The same child is now about 8 years old, sitting cross-legged on the grass. "
            "Ancient scrolls are spread out around him. He reads one intently. "
            "Behind him, a wise Egyptian tutor in white robes points at hieroglyphics on a stone tablet. "
            "The boy traces the symbols with his finger, learning. "
            "In the distance, Cleopatra watches from a balcony above the garden. "
            "She smiles seeing him study. Golden sunlight catches the water in the lotus pool."
        ),
    },
    {
        "duration": 12,
        "narration": "By sixteen he commanded armies. By twenty... he commanded respect.",
        "prompt": (
            f"{STYLE}"
            "A vast desert landscape at sunrise. Sand dunes stretch to the horizon. "
            "A young man about 20 stands on a high sand dune overlooking a massive Egyptian army below. "
            "Thousands of soldiers in formation, chariots, banners blowing in the desert wind. "
            "The young man wears Egyptian royal armor — golden chest plate, red cape blowing in the wind. "
            "He stands tall and confident. His face shows quiet authority. "
            "He raises one arm. The entire army below raises their weapons in salute. "
            "The sunrise behind him casts his long shadow across the desert."
        ),
    },
    {
        "duration": 12,
        "narration": "But he never forgot where he came from. ...A basket on the river. Found by a queen.",
        "prompt": (
            f"{STYLE}"
            "The Nile river at dusk. Calm water reflecting orange and purple sky. "
            "The young man in royal armor sits alone at the riverbank. "
            "He holds a small woven basket in his hands — old, worn, the same basket he was found in as a baby. "
            "He looks at the basket quietly. Remembering. "
            "The water flows gently past him. Fireflies drift over the river surface. "
            "In the reflection of the water, for just a moment, a vision appears — "
            "a tiny baby floating in that same basket on the river, years ago. "
            "The young man holds the basket close to his chest. A single tear on his cheek."
        ),
    },
    {
        "duration": 12,
        "narration": "She found him on the river. She gave him the world. ...He became the pharaoh she always knew he would be.",
        "prompt": (
            f"{STYLE}"
            "A grand Egyptian coronation ceremony inside a massive temple. "
            "Enormous stone columns covered in gold. Hundreds of people watching. "
            "The young man kneels at the center on a golden platform. "
            "Cleopatra, older now with grey in her hair but still regal, stands before him. "
            "She lifts a golden pharaoh crown with both hands. "
            "She places the crown on his head slowly, ceremonially. "
            "He rises to his feet as pharaoh. The crowd bows. "
            "He turns to Cleopatra. She smiles at him. He takes her hand and holds it. "
            "Wide final shot — the new pharaoh and the queen who raised him, "
            "standing together in the golden temple, the world at their feet."
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
        result = await session.execute(
            sql_text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (5, 'running', 'generate_clips', 'fundational') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/fundational_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        # Narration (George voice for fairy tales)
        print("Narration...")
        for i, clip in enumerate(CLIPS):
            generate_speech(clip["narration"], output_path=f"{out}/narration/n_{i}.mp3")
        print("Done")

        # Sora clips
        print("\nClips...")
        clip_paths = []
        prev_ref = None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"\nClip {i+1}/5...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=clip["duration"], size="720x1280", timeout=1200,
                reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/cleo_{i}.jpg"
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
        for i in range(5):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            words = []
            for seg in segments:
                for w in seg.words:
                    words.append((i*12 + w.start, i*12 + w.end, w.word.strip()))
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')):
                    chunks.append((start, e, ' '.join(group)))
                    group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))

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

        # Review queue with metadata
        async with async_session() as session:
            await session.execute(
                sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 5, :a, :c)"),
                {"rid": run_id, "a": "rendered_fundational_short",
                 "c": json.dumps({"status": "rendered", "path": os.path.abspath(final),
                                  "size_bytes": os.path.getsize(final), "content_type": "fundational_short"})})
            await session.execute(
                sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 5, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata",
                 "c": json.dumps({"title": "Raised by Cleopatra",
                                  "description": "She found him on the river. She gave him the world. He became the pharaoh she always knew he would be.\n\n#cleopatra #egypt #fairytale #legend #story #Shorts",
                                  "tags": ["cleopatra", "egypt", "fairy tale", "legend", "pharaoh", "story", "Shorts"],
                                  "category": "Entertainment"})})
            await session.execute(
                sql_text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"),
                {"rid": run_id})
            await session.commit()
        print(f"Review queue: Run #{run_id}")

    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(sql_text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                                  {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise

asyncio.run(main())
