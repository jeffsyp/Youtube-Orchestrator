"""Raised by Cleopatra v2 — fast, punchy, age stages."""
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
        "duration": 4,
        "narration": "What it's like being raised by Cleopatra.",
        "prompt": (
            f"{STYLE}"
            "A young man in golden Egyptian pharaoh armor stands on a sand dune at sunrise. "
            "Behind him a massive Egyptian army stretches across the desert. "
            "Thousands of soldiers, chariots, banners blowing in the wind. "
            "He stands tall and powerful, red cape blowing. "
            "The sunrise casts golden light across everything. Epic scale."
        ),
    },
    {
        "duration": 4,
        "narration": "Age one.",
        "prompt": (
            f"{STYLE}"
            "The Nile river at sunset. Calm golden water. "
            "A small woven basket floats gently on the river with a baby inside. "
            "A beautiful Egyptian queen in royal robes and golden headdress kneels at the riverbank. "
            "She reaches down and lifts the baby out of the basket carefully. "
            "She holds the baby close to her chest. Golden sunset light on both of them."
        ),
    },
    {
        "duration": 4,
        "narration": "Age eight.",
        "prompt": (
            f"{STYLE}"
            "A lush Egyptian palace garden. Palm trees, lotus pools, exotic flowers. "
            "A boy about 8 years old sits cross-legged on the grass surrounded by ancient scrolls. "
            "He writes hieroglyphics with a reed pen, deeply focused. "
            "Golden afternoon sunlight streams through the palm leaves onto him."
        ),
    },
    {
        "duration": 4,
        "narration": "Age sixteen.",
        "prompt": (
            f"{STYLE}"
            "A desert courtyard inside an Egyptian palace. Stone walls, torches. "
            "A teenager about 16 in light armor moves with a wooden training sword. "
            "He is fast and precise, spinning, striking practice targets. "
            "Palace guards stand along the walls watching, impressed. "
            "Cleopatra watches from a balcony above, arms crossed, smiling proudly."
        ),
    },
    {
        "duration": 8,
        "narration": "Age twenty five. Pharaoh.",
        "prompt": (
            f"{STYLE}"
            "A grand Egyptian temple interior. Enormous golden pillars. Hundreds of people watching. "
            "The young man kneels at the center on a golden platform. "
            "Cleopatra, older now, still regal, stands before him holding a golden pharaoh crown. "
            "She places the crown on his head slowly. "
            "He rises to his feet. The crowd bows. "
            "He turns to Cleopatra and takes her hand. She smiles at him. "
            "They stand together in the golden temple. "
            "Wide final shot — the pharaoh and the queen who raised him, golden light everywhere."
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

        print("Narration...")
        for i, clip in enumerate(CLIPS):
            generate_speech(clip["narration"], output_path=f"{out}/narration/n_{i}.mp3")
        print("Done")

        print("\nClips...")
        clip_paths = []
        prev_ref = None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"\nClip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=clip["duration"], size="720x1280", timeout=1200,
                reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/cleo2_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                             "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f:
                    prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

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
                                  "description": "What it's like being raised by the most powerful woman in the world.\n\n#cleopatra #egypt #pharaoh #story #Shorts",
                                  "tags": ["cleopatra", "egypt", "pharaoh", "story", "raised by", "Shorts"],
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
