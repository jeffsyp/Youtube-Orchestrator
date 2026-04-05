"""Top 5 Ancient Weapons v3 — shorter narration, persistent labels, fixed subtitle sync."""
import asyncio, base64, json, os, subprocess
os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, 3D Pixar style cartoon animation, vibrant colors, "
    "smooth animation, funny expressive characters, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {"duration": 4,
     "narration": "Top 5 ancient weapons that were terrifying.",
     "label": "TOP 5 ANCIENT WEAPONS",
     "prompt": f"{STYLE} A cartoon museum hallway with ancient weapons displayed on walls in glass cases. A small cartoon character with big eyes walks through looking up nervously. Grand hallway with stone columns and dramatic lighting."},

    {"duration": 8,
     "narration": "Number 5. War Elephants. Imagine a tank. But alive. And angry.",
     "label": "#5 WAR ELEPHANTS",
     "prompt": f"{STYLE} A cartoon soldier character in ancient armor sits on top of a massive grey elephant on a dusty battlefield. The elephant is enormous and charges forward. The cartoon soldier holds on with wide scared eyes. Everything in front of the elephant scatters — wooden fences break, barrels fly, other cartoon soldiers dive out of the way. The elephant trumpets loudly. Dust clouds everywhere."},

    {"duration": 8,
     "narration": "Number 4. The Trebuchet. 500 pounds. 300 meters. One shot.",
     "label": "#4 TREBUCHET",
     "prompt": f"{STYLE} A cartoon medieval soldier stands next to a massive wooden trebuchet three times taller than him on a grassy field. He loads a huge boulder and pulls a lever proudly. The trebuchet arm swings and launches the boulder high into the sky. The boulder arcs up then curves back down directly onto the soldier. He is squished flat. His hand pops up and gives a thumbs up."},

    {"duration": 8,
     "narration": "Number 3. The Macuahuitl. Volcanic glass sharper than a surgeon's blade.",
     "label": "#3 MACUAHUITL",
     "prompt": f"{STYLE} A cartoon Aztec warrior with a feathered headdress holds a wooden club with black glass blades along the edges. He stands in a jungle clearing next to a large tree. He swings the weapon at the tree trunk. The tree slides apart in a perfectly clean cut and falls over. He looks at the weapon with huge wide cartoon eyes, amazed."},

    {"duration": 8,
     "narration": "Number 2. The Chu Ko Nu. Ancient China's machine gun.",
     "label": "#2 CHU KO NU",
     "prompt": f"{STYLE} A cartoon Chinese soldier in traditional armor picks up a wooden crossbow with a box on top. He touches the trigger. It fires a bolt. Then another automatically. Then bolts fire rapidly one after another. He cannot stop it. He spins around as bolts fly in every direction. His cartoon friends dive behind cover. Chaotic and funny."},

    {"duration": 8,
     "narration": "Number 1. The Katana. One blade. One cut. That's all it took.",
     "label": "#1 KATANA",
     "prompt": f"{STYLE} A cartoon samurai stands in a peaceful Japanese garden with cherry blossom trees. Petals fall gently. He slowly draws a gleaming katana. He does one perfect slow slash. Everything around him slides apart in slow motion — the stone lantern, the wooden bridge, a tree trunk. All cut perfectly clean. He sheathes the blade with a click. A cherry blossom petal lands on his head. He walks away."},
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

        # Generate narration and measure durations
        print("Narration...")
        narration_durations = []
        for i, clip in enumerate(CLIPS):
            vo = f"{out}/narration/n_{i}.mp3"
            generate_speech(clip["narration"], voice=ANIME_VOICE, output_path=vo)
            # Get actual narration duration
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", vo], capture_output=True, text=True)
            dur = float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 3.0
            narration_durations.append(dur)
            print(f"  [{i+1}] {dur:.1f}s — {clip['narration'][:40]}...")

        # Generate Sora clips
        print("\nClips...")
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"Clip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/t5v3_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Trim intro clip to narration + 1s
        intro_trim = narration_durations[0] + 1.0
        trimmed_intro = f"{out}/clips/clip_00_trimmed.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", clip_paths[0], "-t", str(intro_trim), "-c", "copy", trimmed_intro], capture_output=True)
        if os.path.exists(trimmed_intro):
            clip_paths[0] = trimmed_intro

        # Mix narration
        print("\nMixing...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.4[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        # Burn persistent label into each clip
        print("Labels...")
        labeled = []
        for i, p in enumerate(mixed):
            lb = f"{out}/clips/labeled_{i:02d}.mp4"
            label_text = CLIPS[i]["label"].replace("'", "'\\''")
            subprocess.run([
                "ffmpeg", "-y", "-i", p,
                "-vf", f"drawtext=text='{label_text}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=36:fontcolor=white:borderw=3:bordercolor=black@0.5:x=(w-text_w)/2:y=80",
                "-c:a", "copy", lb,
            ], capture_output=True)
            labeled.append(lb if os.path.exists(lb) else p)

        # Normalize
        print("Normalize + concat...")
        norms = []
        for i, p in enumerate(labeled):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        # Get actual durations of normalized clips for accurate subtitle offsets
        actual_durations = []
        for n in norms:
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", n], capture_output=True, text=True)
            actual_durations.append(float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 8.0)

        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
        raw = f"{out}/raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", raw], capture_output=True)
        if not os.path.exists(raw): raise RuntimeError("Concat failed")

        # Subtitles using ACTUAL clip durations for accurate offsets
        print("Subtitles...")
        model = WhisperModel("base", device="cpu")
        chunks = []
        offset = 0.0
        for i in range(len(CLIPS)):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            words = [(offset+w.start, offset+w.end, w.word.strip()) for seg in segments for w in seg.words]
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')): chunks.append((start, e, ' '.join(group))); group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))
            offset += actual_durations[i]  # Use actual duration, not intended

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
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "rendered_yeah_thats_clean_short", "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "publish_metadata", "c": json.dumps({"title": "Top 5 Ancient Weapons That Were Terrifying", "description": "Number 1 only needed one cut.\n\n#top5 #ancient #weapons #history #Shorts", "tags": ["top 5", "ancient weapons", "history", "cartoon", "Shorts"], "category": "Education"})})
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
