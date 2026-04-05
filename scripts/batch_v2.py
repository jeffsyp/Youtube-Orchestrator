"""Batch v2: 5 videos redone properly. Run with index: python batch_v2.py 0"""
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
    # 0. What If the Moon Disappeared
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "What If the Moon Disappeared",
        "description": "First the tides. Then the darkness. Then everything.\n\n#whatif #moon #space #Shorts",
        "tags": ["what if", "moon", "space", "science", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 4, "label": "WHAT IF THE MOON DISAPPEARED",
             "narration": "What would happen if the moon just vanished.",
             "prompt": f"{CINEMATIC} A huge ocean wave crashes into a coastal city at night. Buildings are half submerged. The sky above is completely dark with no moon. Stars reflect on the flood water. Dramatic and terrifying. The wave keeps surging inland."},
            {"duration": 8, "label": "THE TIDES",
             "narration": "First the tides. Without the moon's gravity oceans would surge out of control.",
             "prompt": f"{CINEMATIC} A coastal city at night. The ocean rises dramatically flooding streets. Water rushes between buildings. Cars float. People on rooftops watch the water rise. No moon in the dark sky above. Orange emergency lights reflect off the water."},
            {"duration": 8, "label": "THE DARKNESS",
             "narration": "Then the nights. Total darkness. No moonlight anywhere on earth.",
             "prompt": f"{CINEMATIC} A vast dark landscape at night with no moon. Complete pitch black darkness except distant stars. A single person stands in a field holding a tiny lantern. The only light source for miles. The darkness stretches endlessly. The person looks up at the empty sky."},
            {"duration": 8, "label": "THE END",
             "narration": "Without the moon earths tilt would shift. The planet we know would become unrecognizable.",
             "prompt": f"{CINEMATIC} Earth seen from space. Half the planet is scorching bright desert. The other half is frozen dark ice. No moon orbiting nearby. The planet looks broken and wounded. Dramatic lighting from the sun on one side. Slow pull back showing empty space where the moon should be. Beautiful but haunting."},
        ],
    },
    # 1. Day 1 vs Day 1000 Swordsmanship
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "Day 1 vs Day 1000 Swordsmanship",
        "description": "The difference is insane.\n\n#day1 #day1000 #sword #progress #Shorts",
        "tags": ["day 1", "day 1000", "sword", "progress", "Shorts"],
        "voice": ANIME_VOICE,
        "clips": [
            {"duration": 4, "label": "DAY 1 VS DAY 1000: SWORDSMANSHIP",
             "narration": "Day 1 versus Day 1000. Swordsmanship.",
             "prompt": f"{CARTOON} A cartoon training dojo with wooden floors and practice swords on the wall. A cartoon character stands nervously holding a wooden sword for the first time. He looks unsure. The sword looks heavy in his hands."},
            {"duration": 4, "label": "DAY 1",
             "narration": "Day 1. He couldn't even hold it right.",
             "prompt": f"{CARTOON} A cartoon character in a training dojo holds a wooden sword completely wrong — upside down. He swings it and it flies out of his hands across the room and sticks in the wall. He stares at his empty hands."},
            {"duration": 4, "label": "DAY 100",
             "narration": "Day 100. Getting there.",
             "prompt": f"{CARTOON} Same cartoon character in the dojo now holding the sword correctly. He does a basic slash at a wooden training dummy. The slash is decent but sloppy. He hits the dummy but stumbles forward from his own momentum. Better but not great."},
            {"duration": 4, "label": "DAY 500",
             "narration": "Day 500. Okay now he's cooking.",
             "prompt": f"{CARTOON} Same cartoon character moving fast around three training dummies. He slashes through all three in quick succession. Clean cuts. His movement is fluid and confident. Wood chips fly. He lands in a cool pose at the end."},
            {"duration": 8, "label": "DAY 1000",
             "narration": "Day 1000. He didn't even need to open his eyes.",
             "prompt": f"{CARTOON} Same cartoon character in the dojo but now older and confident. He stands blindfolded in the center. Five wooden training dummies surround him. He draws a real gleaming sword and does a single spinning slash. All five dummies split apart at the same time. He sheathes the sword without removing his blindfold. His instructor in the background drops his tea cup in shock. The character stands still. Done."},
        ],
    },
    # 2. POV Knight vs Tank
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "POV Medieval Knight Sees a Tank",
        "description": "He brought a sword.\n\n#pov #medieval #knight #tank #funny #Shorts",
        "tags": ["POV", "medieval", "knight", "tank", "funny", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 4, "label": "POV: KNIGHT MEETS A TANK",
             "narration": "He trained his whole life for this moment.",
             "prompt": f"{CARTOON} A proud cartoon medieval knight in shining armor rides a horse across a grassy battlefield. He holds his sword high. His cape flows behind him. He looks confident and heroic. Dramatic sunset sky behind him."},
            {"duration": 8, "label": "THE TANK",
             "narration": "And then that thing showed up. His horse left without him.",
             "prompt": f"{CARTOON} Same grassy battlefield. The cartoon knight has stopped his horse. In front of him a massive modern military tank rolls over the hill. It is enormous compared to the knight. The ground shakes. The knight's horse panics and runs away leaving the knight standing alone. He watches his horse disappear into the distance."},
            {"duration": 8, "label": "THE SURRENDER",
             "narration": "He looked at his sword. He looked at the tank. He made the right choice.",
             "prompt": f"{CARTOON} The cartoon knight stands alone on the battlefield facing the massive tank. He looks down at his tiny sword in his hand. He looks up at the tank barrel pointing at him. He slowly places his sword on the ground. He puts both hands up in surrender. He turns around and walks away with his hands still up. The tank just sits there. The knight keeps walking. He does not look back."},
        ],
    },
    # 3. Mantis Shrimp
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "This Shrimp Is Stronger Than You",
        "description": "Don't let the size fool you.\n\n#mantisshrimp #animals #facts #Shorts",
        "tags": ["mantis shrimp", "animals", "facts", "nature", "Shorts"],
        "voice": ANIME_VOICE,
        "clips": [
            {"duration": 4, "label": "THE MANTIS SHRIMP",
             "narration": "This is a mantis shrimp. It looks cute. It is not cute.",
             "prompt": f"{CARTOON} A tiny colorful cartoon mantis shrimp sitting on a rock underwater. Bright rainbow colors. Big round cute cartoon eyes. It looks harmless and adorable. Bubbles float around it. Coral and fish in the background. Peaceful."},
            {"duration": 8, "label": "THE POWER",
             "narration": "Its claws move so fast the water around them boils. It can crack a crab shell like glass.",
             "prompt": f"{CARTOON} The same cartoon mantis shrimp underwater taps a large crab shell with one claw. The shell cracks instantly like glass breaking. Pieces scatter. The mantis shrimp looks satisfied. Nearby fish scatter in surprise. A shockwave ripple expands through the water from the impact point."},
            {"duration": 8, "label": "DON'T TOUCH IT",
             "narration": "It has cracked aquarium glass. With its claws. Do not touch it.",
             "prompt": f"{CARTOON} The cartoon mantis shrimp inside a glass aquarium tank. It taps the glass with one claw gently. A crack appears in the glass. It taps again casually. The crack spreads into a spiderweb pattern. Water starts leaking through. A cartoon scientist on the other side of the glass backs away slowly with a terrified face. The shrimp looks at the camera with big cute innocent eyes."},
        ],
    },
    # 4. Level 1 vs Level 100 Chef
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "Level 1 Chef vs Level 100 Chef",
        "description": "The gap is not even fair.\n\n#chef #cooking #levels #funny #Shorts",
        "tags": ["chef", "cooking", "levels", "funny", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"duration": 4, "label": "LEVEL 1 VS LEVEL 100: CHEF",
             "narration": "Level 1 versus Level 100. Cooking.",
             "prompt": f"{CARTOON} A cartoon kitchen. A nervous cartoon chef character in a white hat stands at the counter holding an egg. He looks at it like he has never seen one before. A cookbook is open in front of him. Simple kitchen setting."},
            {"duration": 4, "label": "LEVEL 1",
             "narration": "Level 1. He burned water.",
             "prompt": f"{CARTOON} A cartoon kitchen with everything on fire. Flames come from the stove the toaster and somehow the sink. Black smoke fills the room. The chef holds a pan with a completely burnt black object in it. The fire alarm flashes on the ceiling. The chef looks at the camera with a helpless confused expression."},
            {"duration": 4, "label": "LEVEL 25",
             "narration": "Level 25. Edible. Barely.",
             "prompt": f"{CARTOON} A cartoon kitchen with minor mess. The chef holds up a plate with a lopsided pancake on it. The pancake is slightly burnt on one side and raw on the other. It is not pretty but it is technically food. The chef smiles proudly despite the mess. A small grease stain on his hat."},
            {"duration": 4, "label": "LEVEL 50",
             "narration": "Level 50. Okay this is actually good.",
             "prompt": f"{CARTOON} A cleaner cartoon kitchen. The chef flips a perfect golden omelette in a pan with a smooth flick of his wrist. It lands perfectly. He plates it neatly with garnish. It looks professional. He nods with quiet confidence."},
            {"duration": 8, "label": "LEVEL 100",
             "narration": "Level 100. The food cooks itself out of respect.",
             "prompt": f"{CARTOON} A spotless gleaming cartoon kitchen. The chef stands with arms crossed not touching anything. Food flies through the air on its own. Vegetables chop themselves. Sauces pour perfectly. A steak flips itself in a pan. Everything moves in perfect choreography around the chef. A beautiful plated dish assembles itself on the counter. The chef nods once. He walks away without looking back. Perfection."},
        ],
    },
]


async def generate_video(video_config):
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
    print(f"\n{'='*50}\nVIDEO: {video_config['title']} — Run #{run_id}\n{'='*50}")

    try:
        out = f"output/{ct}_run_{run_id}"
        os.makedirs(f"{out}/clips", exist_ok=True)
        os.makedirs(f"{out}/narration", exist_ok=True)

        # Narration + measure durations
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
            ft = f"/tmp/bv2_{run_id}_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Trim intro to narration + 1s
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

        # Normalize first, then get actual durations
        norms = []
        for i, p in enumerate(mixed):
            n = f"{out}/clips/norm_{i:02d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", p, "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n], capture_output=True)
            norms.append(n if os.path.exists(n) else p)

        actual_durations = []
        for n in norms:
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", n], capture_output=True, text=True)
            actual_durations.append(float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 8.0)

        # Burn persistent labels using drawtext on concat
        cl = f"{out}/concat.txt"
        with open(cl, "w") as f:
            for p in norms: f.write(f"file '{os.path.abspath(p)}'\n")
        raw = f"{out}/raw.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", raw], capture_output=True)
        if not os.path.exists(raw): raise RuntimeError("Concat failed")

        # Burn labels onto concat
        offset = 0
        drawtext_filters = []
        for i, clip in enumerate(clips_config):
            dur = actual_durations[i]
            end = offset + dur
            label = clip["label"].replace("'", "\\'").replace(":", "\\:")
            drawtext_filters.append(f"drawtext=text='{label}':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:fontsize=56:fontcolor=white:borderw=4:bordercolor=black@0.6:x=(w-text_w)/2:y=40:enable='between(t,{offset},{end})'")
            offset = end

        labeled = f"{out}/labeled.mp4"
        vf = ",".join(drawtext_filters)
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", vf, "-c:a", "copy", labeled], capture_output=True)
        if not os.path.exists(labeled): labeled = raw

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
        subprocess.run(["ffmpeg", "-y", "-i", labeled, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")
        print(f"  Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": video_config["asset_type"], "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": ct})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": "publish_metadata", "c": json.dumps({"title": video_config["title"], "description": video_config["description"], "tags": video_config["tags"], "category": "Entertainment"})})
            await session.execute(sql_text("UPDATE content_runs SET status='pending_review', current_step='awaiting_human_review' WHERE id=:rid"), {"rid": run_id})
            await session.commit()
        print(f"  Review queue: Run #{run_id}")
    except Exception as e:
        print(f"  ERROR: {e}")
        async with async_session() as session:
            await session.execute(sql_text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"), {"rid": run_id, "err": str(e)[:500]})
            await session.commit()


async def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if idx < len(VIDEOS):
        await generate_video(VIDEOS[idx])

asyncio.run(main())
