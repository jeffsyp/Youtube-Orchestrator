"""Top 5 Ancient Weapons v2 — cartoon characters, detailed narration, subtitles."""
import asyncio, base64, json, os, subprocess
os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, 3D Pixar style cartoon animation, vibrant colors, "
    "smooth animation, funny expressive characters, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {"duration": 4,
     "narration": "Top 5 ancient weapons so terrifying they were banned from war.",
     "prompt": f"{STYLE} A cartoon museum hallway with ancient weapons displayed on the walls in glass cases. A small cartoon character with big eyes walks through the hallway looking up at the weapons nervously. The hallway is grand with stone columns and dramatic lighting. The character gulps and keeps walking."},

    {"duration": 12,
     "narration": "Number 5. Greek Fire. The Byzantine Empire created a liquid that burned on water. Nobody could put it out. Water made it worse. The secret recipe was so dangerous that when the empire fell they destroyed it. To this day nobody knows exactly how it was made.",
     "prompt": f"{STYLE} A goofy cartoon sailor character on a small wooden ship at night on a dark ocean. He accidentally tips over a large barrel off the side of the ship. The ocean surface erupts in bright green flames spreading outward from where the barrel fell. The sailor throws a bucket of water on the flames. The green flames get BIGGER and spread faster. He stands on the ship surrounded by green fire on the water in every direction. His face shows total panic. Green light illuminates everything."},

    {"duration": 12,
     "narration": "Number 4. The Trebuchet. It stood three stories tall and could launch a 500 pound boulder over 300 meters. Entire castle walls crumbled in a single hit. Armies would surrender just watching one get built outside their gates.",
     "prompt": f"{STYLE} A cartoon medieval soldier character stands next to a massive wooden trebuchet that is three times taller than him on a grassy field. He loads a huge round boulder into the sling. He pulls a wooden lever proudly. The trebuchet arm swings and launches the boulder high into the sky. The boulder arcs way up and then curves back down directly toward the soldier. It lands right on top of him. He is squished flat into the ground like a pancake. His hand pops up from under the boulder and gives a thumbs up."},

    {"duration": 12,
     "narration": "Number 3. The Macuahuitl. The Aztec Empire lined wooden clubs with obsidian. Volcanic glass sharper than any modern surgical blade. Spanish conquistadors reported that a single swing could remove a horse's head clean off. The weapon was so effective it terrified soldiers who had steel armor.",
     "prompt": f"{STYLE} A cartoon Aztec warrior character with a feathered headdress holds a wooden club with black glass blades along the edges. He stands in a jungle clearing next to a large tree. He swings the weapon at the tree trunk. The tree slides apart in a perfectly clean cut and falls over. He looks surprised. He swings at a large boulder next to him. The boulder slides in half perfectly. He looks at the weapon with huge wide cartoon eyes, mouth hanging open, amazed at what it can do."},

    {"duration": 12,
     "narration": "Number 2. The Chu Ko Nu. Ancient China invented a repeating crossbow over 2000 years before the machine gun. It held ten bolts in a top mounted magazine and could fire all of them in fifteen seconds. Entire rows of soldiers could unleash a wall of bolts that no army could advance through.",
     "prompt": f"{STYLE} A cartoon Chinese soldier character in traditional armor picks up a wooden crossbow with a rectangular box on top. He touches the trigger mechanism curiously. It fires a bolt into the wall. Then another fires automatically. Then more bolts fire rapidly one after another in quick succession. He cannot stop it. He spins around trying to control the weapon as bolts fly in every direction. His cartoon soldier friends dive behind cover. The bolts stick into walls and objects all around the room in a chaotic pattern."},

    {"duration": 12,
     "narration": "Number 1. The Katana. Japanese swordsmiths folded the steel over a thousand times to remove every impurity. The result was a blade so sharp it could cut through bone and armor in a single stroke. Samurai spent their entire lives mastering just one weapon. The katana wasn't just a sword. It was considered the soul of the warrior.",
     "prompt": f"{STYLE} A cartoon samurai character stands in a peaceful Japanese garden with cherry blossom trees. Petals fall gently around him. He slowly draws a gleaming katana from its sheath. The blade catches the light beautifully. He performs one slow perfect horizontal slash through the air. Everything around him slides apart in slow motion — the stone lantern splits in half, the wooden bridge separates, a tree trunk slides cleanly. All cut perfectly. He sheathes the blade with a satisfying click. A single cherry blossom petal lands on top of his head. He walks away calmly."},
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
            generate_speech(clip["narration"], voice=ANIME_VOICE, output_path=f"{out}/narration/n_{i}.mp3")
        print("Done")

        print("\nClips...")
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(CLIPS):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"Clip {i+1}/{len(CLIPS)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"  Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/t5v2_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        print("\nMixing...")
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.4[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
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
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "rendered_yeah_thats_clean_short", "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short"})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :a, :c)"), {"rid": run_id, "a": "publish_metadata", "c": json.dumps({"title": "Top 5 Ancient Weapons That Were Terrifying", "description": "Number 1 was considered the soul of the warrior.\n\n#top5 #ancient #weapons #history #Shorts", "tags": ["top 5", "ancient weapons", "history", "cartoon", "Shorts"], "category": "Education"})})
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
