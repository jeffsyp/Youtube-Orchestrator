"""Batch: 6 different format videos. Run one at a time sequentially."""
import asyncio, base64, json, os, subprocess, sys
os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"
GEORGE_VOICE = "George"

CARTOON = (
    "Vertical 9:16 aspect ratio, 3D Pixar style cartoon animation, vibrant colors, "
    "smooth animation, funny expressive characters, no text, no watermarks, no UI elements. "
)
CINEMATIC = (
    "Vertical 9:16 aspect ratio, cinematic, dramatic lighting, photorealistic, "
    "no text, no watermarks, no UI elements. "
)

VIDEOS = [
    # 1. What Would Happen If the Moon Disappeared
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "What If the Moon Disappeared",
        "description": "First the tides. Then the seasons. Then everything.\n\n#whatif #moon #space #science #Shorts",
        "tags": ["what if", "moon", "space", "science", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 4, "label": "WHAT IF THE MOON DISAPPEARED",
             "narration": "What would happen if the moon just... vanished.",
             "prompt": f"{CINEMATIC} A beautiful full moon in a dark starry night sky over an ocean. The moon suddenly flickers and disappears completely. The sky goes dark. The ocean below reflects only stars now. Eerie silence."},
            {"duration": 8, "label": "THE TIDES",
             "narration": "First the tides would go insane. Oceans would surge without the moon's gravity holding them steady.",
             "prompt": f"{CINEMATIC} A coastal city at night. The ocean suddenly rises dramatically — massive waves surge inland flooding streets. Water rushes between buildings. Cars float. People on rooftops watch the water rise. No moon in the sky above. Dramatic and terrifying."},
            {"duration": 8, "label": "THE DARKNESS",
             "narration": "Then the nights. Pitch black. No moonlight. The entire planet in total darkness every single night.",
             "prompt": f"{CINEMATIC} A vast dark landscape at night with no moon. Complete pitch black darkness except for distant stars. A person stands in a field holding a tiny lantern — the only light source. The darkness stretches endlessly in every direction. The person looks up at the empty sky where the moon used to be."},
            {"duration": 8, "label": "THE END",
             "narration": "Without the moon Earth's tilt would shift. Seasons would become extreme. The planet we know would slowly become unrecognizable.",
             "prompt": f"{CINEMATIC} Earth seen from space. The planet slowly tilts on its axis without the moon's stabilizing gravity. One half becomes scorching bright. The other half becomes frozen dark. Ice covers continents. Deserts expand. The planet looks wounded. Beautiful but dying. Slow zoom out showing empty space where the moon should be."},
        ],
    },
    # 2. Day 1 vs Day 1000 Swordsmanship
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "Day 1 vs Day 1000 Swordsmanship",
        "description": "The difference is insane.\n\n#day1 #day1000 #swordsmanship #progress #Shorts",
        "tags": ["day 1", "day 1000", "sword", "progress", "Shorts"],
        "voice": ANIME_VOICE,
        "clips": [
            {"duration": 8, "label": "DAY 1",
             "narration": "Day 1. He couldn't even hold it right.",
             "prompt": f"{CARTOON} A cartoon character in a training dojo holds a wooden practice sword completely wrong — upside down, backwards. He swings it and it flies out of his hands across the room. He chases after it. He picks it up and tries again. It flies out again. His instructor in the background facepalms."},
            {"duration": 8, "label": "DAY 1000",
             "narration": "Day 1000. He didn't even need to open his eyes.",
             "prompt": f"{CARTOON} Same cartoon character in the same dojo but now older and confident. He stands blindfolded. Five wooden training dummies surround him in a circle. He draws a real sword and does a single spinning slash. All five dummies split apart at the same time and fall to pieces. He sheathes the sword without removing his blindfold. His instructor in the background drops his tea cup in shock."},
        ],
    },
    # 3. POV Medieval Knight Sees a Tank
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "POV Medieval Knight Sees a Tank",
        "description": "He brought a sword.\n\n#pov #medieval #knight #tank #funny #Shorts",
        "tags": ["POV", "medieval", "knight", "tank", "funny", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 12, "label": "POV: MEDIEVAL KNIGHT SEES A TANK",
             "narration": "He had trained his whole life for battle. He had the best armor. The finest sword. And then... that thing showed up.",
             "prompt": f"{CARTOON} A proud cartoon medieval knight in shining armor sits on a horse on a grassy battlefield. He holds up his sword confidently. The ground starts shaking. A massive modern military tank rolls over the hill in front of him. It is enormous — ten times the size of his horse. The tank barrel points at him. The knight stares up at it with huge terrified cartoon eyes. His horse turns and runs away without him. He stands alone holding his tiny sword looking up at the tank barrel. He slowly lowers his sword."},
        ],
    },
    # 4. How Wi-Fi Actually Works
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "How Wi-Fi Actually Works",
        "description": "It's basically tiny invisible screaming.\n\n#wifi #howthingswork #tech #funny #Shorts",
        "tags": ["wifi", "how things work", "tech", "funny", "education", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 4, "label": "HOW WI-FI ACTUALLY WORKS",
             "narration": "Your Wi-Fi router is basically screaming.",
             "prompt": f"{CARTOON} A cartoon Wi-Fi router sitting on a desk in a living room. The router has a tiny cartoon face. Its mouth opens wide and it screams — visible sound waves pulse outward from it in all directions through the room. The waves pass through walls and furniture."},
            {"duration": 8, "label": "THE SIGNAL",
             "narration": "It yells your data into the air as invisible waves. Those waves bounce off walls, through doors, around furniture.",
             "prompt": f"{CARTOON} A cutaway view of a cartoon house showing multiple rooms. Colorful waves emanate from a cartoon router in one room. The waves bounce off walls, pass through doors, curve around furniture. Tiny cartoon data packets ride the waves like surfers — little envelopes with faces holding on as they bounce through the house."},
            {"duration": 8, "label": "YOUR PHONE",
             "narration": "Your phone catches those waves and translates the screaming back into cat videos. That's it. That's Wi-Fi.",
             "prompt": f"{CARTOON} A cartoon smartphone lying on a couch. The colorful signal waves arrive and enter the phone. Inside the phone through a cutaway view a tiny cartoon character catches the waves with a net and unfolds them into pictures and videos. The character gives a thumbs up. On the phone screen a cat video starts playing."},
        ],
    },
    # 5. Mantis Shrimp Punches Like a Bullet
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "This Shrimp Punches Harder Than a Bullet",
        "description": "Don't let the size fool you.\n\n#mantisshrimp #animals #facts #nature #Shorts",
        "tags": ["mantis shrimp", "animals", "facts", "nature", "punch", "Shorts"],
        "voice": ANIME_VOICE,
        "clips": [
            {"duration": 4, "label": "THE MANTIS SHRIMP",
             "narration": "This is a mantis shrimp. It looks cute. It is not cute.",
             "prompt": f"{CARTOON} A tiny colorful cartoon mantis shrimp sitting on a rock underwater. It has bright rainbow colors — red, orange, green, blue. It has big round cute cartoon eyes. It looks harmless and adorable. Bubbles float around it. Coral and fish in the background. Peaceful underwater scene."},
            {"duration": 8, "label": "THE PUNCH",
             "narration": "It can punch with the force of a bullet. The water around its fist literally boils from the speed.",
             "prompt": f"{CARTOON} The same cartoon mantis shrimp pulls back its front claw. It winds up. It throws a punch at a large rock next to it. A massive shockwave explodes from the impact point. The rock shatters into pieces. Bubbles and debris fly everywhere. The water around the punch point glows from the heat. A shockwave ring expands outward knocking nearby fish tumbling. The tiny shrimp stands on its rock looking satisfied."},
            {"duration": 4, "label": "DON'T TOUCH IT",
             "narration": "It has broken aquarium glass. With its fists. Don't touch it.",
             "prompt": f"{CARTOON} The cartoon mantis shrimp is now inside a glass aquarium tank. It taps the glass with one claw. A crack appears. It taps again. The crack spreads. A cartoon scientist watches from outside the tank with a horrified expression backing away slowly. The shrimp looks at the camera with its big cute eyes."},
        ],
    },
    # 6. Level 1 Chef vs Level 100 Chef
    {
        "channel_id": 7, "content_type": "yeah_thats_clean",
        "asset_type": "rendered_yeah_thats_clean_short",
        "title": "Level 1 Chef vs Level 100 Chef",
        "description": "The gap is not even fair.\n\n#chef #cooking #levels #funny #Shorts",
        "tags": ["chef", "cooking", "levels", "level 1", "level 100", "funny", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 8, "label": "LEVEL 1 CHEF",
             "narration": "Level 1. He burned water. The kitchen is on fire. He doesn't know how this happened.",
             "prompt": f"{CARTOON} A cartoon chef character in a white hat stands in a kitchen. Everything is on fire. Flames come from the toaster, the stove, even the sink somehow. The chef holds a pan with a completely black burnt object in it. Smoke fills the room. The fire alarm blares. The chef looks at the camera with a confused helpless expression. He has no idea what went wrong."},
            {"duration": 8, "label": "LEVEL 100 CHEF",
             "narration": "Level 100. He doesn't even look at the food anymore. The food cooks itself out of respect.",
             "prompt": f"{CARTOON} Same cartoon kitchen but now spotless and gleaming. A calm confident chef character stands with his arms crossed. He is not touching anything. Food flies through the air on its own — vegetables chop themselves, sauces pour perfectly, a steak flips itself in a pan. Everything moves in perfect choreography around the chef. A beautiful plated dish assembles itself on the counter. The chef nods once. Perfection. He walks away without looking back."},
        ],
    },
]


async def generate_video(video_config):
    """Generate a single video with narration, labels, subtitles."""
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text as sql_text
    from faster_whisper import WhisperModel

    ch_id = video_config["channel_id"]
    ct = video_config["content_type"]
    clips_config = video_config["clips"]
    voice = video_config["voice"]

    async with async_session() as session:
        result = await session.execute(sql_text(f"INSERT INTO content_runs (channel_id, status, current_step, content_type) VALUES ({ch_id}, 'running', 'generate_clips', '{ct}') RETURNING id"))
        run_id = result.scalar()
        await session.commit()
    print(f"\n{'='*50}")
    print(f"VIDEO: {video_config['title']} — Run #{run_id}")
    print(f"{'='*50}")

    try:
        out = f"output/{ct}_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        # Narration
        narration_durations = []
        for i, clip in enumerate(clips_config):
            vo = f"{out}/narration/n_{i}.mp3"
            generate_speech(clip["narration"], voice=voice, output_path=vo)
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", vo], capture_output=True, text=True)
            narration_durations.append(float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 3.0)

        # Sora clips
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(clips_config):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            print(f"  Clip {i+1}/{len(clips_config)} ({clip['duration']}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=clip["duration"], size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"    Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/batch_{run_id}_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Trim intro if first clip
        intro_trim = narration_durations[0] + 1.0
        if intro_trim < clips_config[0]["duration"]:
            trimmed = f"{out}/clips/clip_00_trimmed.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", clip_paths[0], "-t", str(intro_trim), "-c", "copy", trimmed], capture_output=True)
            if os.path.exists(trimmed): clip_paths[0] = trimmed

        # Mix narration
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.4[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        # Burn persistent labels
        labeled = []
        for i, p in enumerate(mixed):
            lb = f"{out}/clips/labeled_{i:02d}.mp4"
            label = clips_config[i]["label"].replace("'", "'\\''").replace(":", "\\:")
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf", f"drawtext=text='{label}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=44:fontcolor=white:borderw=3:bordercolor=black@0.5:x=(w-text_w)/2:y=80", "-c:a", "copy", lb], capture_output=True)
            labeled.append(lb if os.path.exists(lb) else p)

        # Normalize
        norms = []
        for i, p in enumerate(labeled):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        # Get actual durations
        actual_durations = []
        for n in norms:
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", n], capture_output=True, text=True)
            actual_durations.append(float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 8.0)

        # Concat
        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
        raw = f"{out}/raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", raw], capture_output=True)
        if not os.path.exists(raw): raise RuntimeError("Concat failed")

        # Subtitles with actual offsets
        model = WhisperModel("base", device="cpu")
        chunks, offset = [], 0.0
        for i in range(len(clips_config)):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            words = [(offset+w.start, offset+w.end, w.word.strip()) for seg in segments for w in seg.words]
            group, start = [], None
            for s, e, w in words:
                if start is None: start = s
                group.append(w)
                if len(group) >= 3 or w.endswith(('.','!','?','...')): chunks.append((start, e, ' '.join(group))); group, start = [], None
            if group: chunks.append((start, words[-1][1], ' '.join(group)))
            offset += actual_durations[i]

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Pop\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Pop,Impact,52,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,2,20,20,120,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for s, e, text in chunks:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Pop,,0,0,0,,{text.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")
        print(f"  Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        # Review queue
        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": video_config["asset_type"], "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": ct})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": "publish_metadata", "c": json.dumps({"title": video_config["title"], "description": video_config["description"], "tags": video_config["tags"], "category": "Entertainment"})})
            await session.execute(sql_text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"), {"rid": run_id})
            await session.commit()
        print(f"  Review queue: Run #{run_id}")
        return run_id
    except Exception as e:
        print(f"  ERROR: {e}")
        async with async_session() as session:
            await session.execute(sql_text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"), {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        return None


async def main():
    # Run one video at a time to not overwhelm Sora
    video_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if video_index < len(VIDEOS):
        await generate_video(VIDEOS[video_index])
    else:
        print(f"No video at index {video_index}")

asyncio.run(main())
