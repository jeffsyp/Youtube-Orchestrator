"""Meteor Kid v3 — full regenerate with better hook, consistent style, pop-in subtitles."""
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
    "Dragon Ball Z energy effects, cinematic, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "He reached up... and the meteor reached back.",
        "prompt": (
            f"{STYLE}"
            "A MASSIVE glowing orange meteor fills the entire top half of the screen, falling toward a city below. "
            "Flames and debris trail behind it. The sky is orange and red from the heat. "
            "A young anime boy with messy dark hair flies upward toward the meteor at incredible speed. "
            "His entire body glows bright white-orange. Energy radiates from his whole body like a sun. "
            "Speed lines streak past him. His clothes ripple and tear from the wind. "
            "He reaches the meteor and presses both palms flat against its glowing surface. "
            "Massive cracks of white light spread across the meteor from where his hands touch. "
            "Orange energy streams from the meteor into his glowing body. "
            "Shockwave rings expand outward from the contact point. "
            "The meteor visibly shrinks as he absorbs it. The scale is enormous — tiny boy, planet-sized meteor."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind. He couldn't even hold a spark. Dead last. The weakest in the whole academy.",
        "prompt": (
            f"{STYLE}"
            "A bright anime academy classroom during the day. Large windows, sunlight streaming in. "
            "Rows of student desks. Other anime students sit confidently holding "
            "glowing energy orbs in their palms — some orbs are big and bright. "
            "At the very back of the class, the same boy sits alone at his desk. "
            "His hands are cupped together. A tiny pathetic flicker of light "
            "blinks between his palms and dies. Not even a spark. "
            "An anime instructor with glasses walks past his desk, glances down, shakes his head. "
            "Two students in front of him turn and snicker, pointing at his empty hands. "
            "The boy stares at his own palms. Nothing there. His face shows quiet frustration."
        ),
    },
    {
        "duration": 12,
        "narration": "When the meteor came... everyone ran. He just stood there. He had nothing to lose.",
        "prompt": (
            f"{STYLE}"
            "A wide anime city street at dusk. The sky is deep orange from a massive glowing meteor "
            "visible high above, getting closer. It leaves a long burning trail across the sky. "
            "People on the street run in panic — grabbing children, screaming, fleeing. "
            "Cars abandoned in the road. Alarms blare from buildings. "
            "One person stands completely still in the middle of the empty street — the boy. "
            "Everyone runs past him but he does not move. "
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
            "Citizens on rooftops and streets are looking UP at the sky, pointing, mouths open. "
            "High above the city, a brilliant white light shines where the meteor used to be. "
            "The meteor has stopped moving. It hangs frozen in the sky. "
            "Bright orange and white energy streams downward from the meteor "
            "into a tiny glowing figure below it — barely visible, a small silhouette. "
            "The meteor is visibly shrinking — getting smaller as energy drains from it. "
            "People on the rooftops shield their eyes from the blinding light. "
            "Everything is still except the energy flowing downward. "
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
            "The boy kneels at the center of the crater alone. Head down. Exhausted. "
            "The city behind him is completely untouched — he saved every building, every person. "
            "Faint orange cracks of light still glow on his skin, slowly fading. "
            "Steam rises from his body into the cold morning air. "
            "His hands press against the scorched ground. They are trembling. "
            "He slowly lifts his head and looks at the saved city in the distance. "
            "His eyes flash orange for just a moment — the power is still inside him. "
            "Wide final shot — tiny boy in the center of the massive crater, "
            "untouched city behind, golden sunrise, steam rising around him."
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
            generate_speech(clip["narration"], voice=ANIME_VOICE, output_path=f"{out}/narration/n_{i}.mp3")
        print("Done")

        # Sora clips with frame chaining
        print("\nSora clips...")
        clip_paths = []
        prev_ref = None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"\nClip {i+1}/5...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp,
                duration=12, size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/mv3_{i}.jpg"
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

        # Add to review queue
        async with async_session() as session:
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "rendered_yeah_thats_clean_short",
                 "c": json.dumps({"status": "rendered", "path": os.path.abspath(final),
                                  "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(
                text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"),
                {"rid": run_id, "a": "publish_metadata",
                 "c": json.dumps({"title": "The Kid Who Caught a Meteor",
                                  "description": "Everyone ran. He didn't. #anime #meteor #action #Shorts",
                                  "tags": ["anime", "meteor", "action", "power", "Shorts"],
                                  "category": "Entertainment"})})
            await session.execute(text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"),
                {"rid": run_id})
            await session.commit()
        print(f"Review queue: Run #{run_id}")

    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                                  {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise

asyncio.run(main())
