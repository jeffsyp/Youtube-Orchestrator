"""Hydraulic Press vs Crystal Ball — single clip, satisfying, fantasy twist."""
import asyncio
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE = (
    "Vertical 9:16 aspect ratio, glossy 3D render style, smooth reflective surfaces, "
    "perfect geometric shapes, satisfying motion graphics, vibrant saturated colors, "
    "studio lighting on dark background, no text, no watermarks, no UI elements. "
)

PROMPT = (
    f"{STYLE}"
    "A massive chrome hydraulic press descends slowly toward a glowing purple crystal ball "
    "sitting on a polished black metal platform. The crystal ball is perfectly round, "
    "translucent purple glass with swirling mystical fog inside it. "
    "The press makes contact with the top of the crystal ball. The ball resists. "
    "Tiny cracks appear on the surface — each crack glows bright white from inside. "
    "Swirling visions appear in the cracks — faces, landscapes, storms, all flickering rapidly. "
    "The press pushes harder. More cracks spread across the entire ball. "
    "The glowing visions inside get more intense, spinning faster. "
    "The crystal ball shatters spectacularly — thousands of glowing purple and white shards "
    "explode outward in slow motion. Each shard contains a tiny frozen vision inside it. "
    "Purple and white light fills the entire scene. Shards scatter across the dark platform. "
    "The press continues downward, crushing the remaining fragments into sparkling purple dust. "
    "Satisfying crunch sound effects throughout."
)

NARRATION = "They said it could show you the future. ...They never said what happens when you break it."


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text
    from faster_whisper import WhisperModel

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (4, 'running', 'generate_clips', 'satisdefying') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        out = f"output/satisdefying_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        # Narration
        vo_path = f"{out}/narration/n_0.mp3"
        generate_speech(NARRATION, voice="JjsQrIrIBD6TZ656NQfi", output_path=vo_path)
        print("Narration OK")

        # Single 12s clip
        cp = os.path.abspath(f"{out}/clips/clip_00.mp4")
        print("Generating clip...")
        r = await generate_video_async(prompt=PROMPT, output_path=cp,
            duration=12, size="720x1280", timeout=1200)
        print(f"Saved: {r['file_size_bytes']} bytes")

        # Mix narration
        mx = f"{out}/clips/clip_00_mx.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", vo_path,
            "-filter_complex", "[0:a]volume=0.7[s];[1:a]volume=1.0[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx],
            capture_output=True)
        mixed = mx if os.path.exists(mx) else cp

        # Pop-in subtitles
        print("Subtitles...")
        model = WhisperModel("base", device="cpu")
        segments, _ = model.transcribe(vo_path, word_timestamps=True)
        chunks = []
        group, start = [], None
        for seg in segments:
            for w in seg.words:
                if start is None: start = w.start
                group.append(w.word.strip())
                if len(group) >= 3 or w.word.strip().endswith(('.','!','?','...')):
                    chunks.append((start, w.end, ' '.join(group)))
                    group, start = [], None
        if group: chunks.append((start, w.end, ' '.join(group)))

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Pop\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Pop,Impact,52,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,2,20,20,120,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for s, e, text in chunks:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Pop,,0,0,0,,{text.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", mixed, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")

        print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        # Review queue
        async with async_session() as session:
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 4, :a, :c)"),
                {"rid": run_id, "a": "rendered_satisdefying_short",
                 "c": json.dumps({"status": "rendered", "path": os.path.abspath(final),
                                  "size_bytes": os.path.getsize(final), "content_type": "satisdefying_short"})})
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 4, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata",
                 "c": json.dumps({"title": "Hydraulic Press vs Crystal Ball",
                                  "description": "It held on longer than expected... #oddlysatisfying #asmr #hydraulicpress #crystalball #Shorts",
                                  "tags": ["oddly satisfying", "ASMR", "hydraulic press", "crystal ball", "satisfying", "Shorts"],
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
