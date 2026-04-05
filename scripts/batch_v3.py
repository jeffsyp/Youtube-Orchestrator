"""Batch v3: Black Hole, Extinct Animals, Fall Into Jupiter. Run with index: python batch_v3.py 0"""
import asyncio, base64, json, os, subprocess, sys
os.chdir("/home/jeff/youtube-orchestrator")

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
    # 0. How a Black Hole Actually Works
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "How a Black Hole Actually Works",
        "description": "You wouldn't even know you crossed the line.\n\n#blackhole #space #science #howitworks #Shorts",
        "tags": ["black hole", "space", "science", "how it works", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"label": "HOW A BLACK HOLE\nACTUALLY WORKS",
             "narration": "This thing eats light for breakfast. And you'd never even see it coming.",
             "prompt": f"{CARTOON} A small cartoon astronaut gets yanked toward a giant black hole. The black hole has a bright orange glowing ring around it. All the stars and light around it bend and warp toward the center. The astronaut slides across space toward it, arms flailing."},

            {"label": "THE EVENT HORIZON",
             "narration": "First, the event horizon. Cross this invisible line and nothing escapes. Not light. Not you. Not even your screams.",
             "prompt": f"{CARTOON} A cartoon astronaut floats near a glowing circle line in space. He puts one hand past the line. His hand disappears. He pulls back but his hand is gone. He looks at his missing hand in shock. Light beams fly past him and vanish past the same line. Nothing comes back out."},

            {"label": "SPAGHETTIFICATION",
             "narration": "Then spaghettification. The gravity pulls your feet faster than your head. You stretch like taffy until you're a noodle.",
             "prompt": f"{CARTOON} A cartoon astronaut stretches into a long noodle shape. His feet pull far downward while his head stays up. His body is like stretched taffy, thin and long. He looks down at his noodle body with huge shocked cartoon eyes. Stars streak past him vertically."},

            {"label": "THE SINGULARITY",
             "narration": "At the center, the singularity. All the mass of a million suns crushed into a point smaller than an atom. We don't know what happens here. Nobody has come back to tell us.",
             "prompt": f"{CARTOON} Complete darkness. One tiny bright white dot in the center of the screen. Colorful light ribbons spiral inward toward the dot from all directions. A tiny cartoon astronaut silhouette falls toward the dot, getting smaller. He waves goodbye at the camera. The dot pulses brighter."},
        ],
    },
    # 1. Top 5 Extinct Animals That Would Terrify You
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "Top 5 Extinct Animals That Would Terrify You",
        "description": "Number 1 could swallow a bus.\n\n#top5 #extinct #animals #prehistoric #Shorts",
        "tags": ["top 5", "extinct", "animals", "prehistoric", "terrifying", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"label": "TOP 5 EXTINCT ANIMALS\nTHAT WOULD TERRIFY YOU",
             "narration": "Top 5 extinct animals that would absolutely terrify you. This thing was fifty feet long and could swallow you whole. And it's not even number one.",
             "prompt": f"{CINEMATIC} A massive prehistoric shark mouth opens wide directly at the camera underwater. Rows of giant teeth fill the frame. A scuba diver floats in front of the open jaws, tiny by comparison. The shark is so large only its mouth fits in the frame. Dark deep ocean water behind. Photorealistic."},

            {"label": "#5 GIANT SCORPION",
             "narration": "Number 5. The giant sea scorpion. Eight feet long. Claws the size of your head. It hunted in the ocean 400 million years ago.",
             "prompt": f"{CINEMATIC} A massive eight-foot sea scorpion sits on the ocean floor. Its claws are enormous and snap open. A scuba diver nearby freezes when he sees it. The scorpion turns toward the diver. Photorealistic prehistoric ocean with murky green water and rocks."},

            {"label": "#4 TERROR BIRD",
             "narration": "Number 4. The terror bird. Ten feet tall. Couldn't fly. Didn't need to. It could outrun a horse.",
             "prompt": f"{CINEMATIC} A ten-foot-tall prehistoric bird with a massive hooked beak sprints across a grassy plain. Its tiny wings are useless. Its powerful legs take huge strides. It chases a human running ahead of it and gains ground easily. Dust kicks up behind it. Photorealistic prehistoric grassland."},

            {"label": "#3 SHORT-FACED BEAR",
             "narration": "Number 3. The short-faced bear. Twelve feet tall standing up. It made grizzlies look like puppies.",
             "prompt": f"{CINEMATIC} A massive prehistoric bear stands upright on hind legs in a snowy forest. It towers above the pine trees at twelve feet tall. A regular grizzly bear stands next to it and only reaches its knee. The giant bear looks down. Photorealistic snowy forest with dramatic lighting."},

            {"label": "#2 TITANOBOA",
             "narration": "Number 2. Titanoboa. Fifty feet long. Two thousand pounds. A snake the size of a school bus.",
             "prompt": f"{CINEMATIC} A fifty-foot snake as wide as a tree trunk slithers through a jungle river. It coils around a large tree and the tree bends. Its head rises out of the water, massive. A person standing on the riverbank is tiny compared to the snake's head. Photorealistic prehistoric jungle."},

            {"label": "#1 MEGALODON",
             "narration": "Number 1. Megalodon. Sixty feet of pure nightmare. Jaws wide enough to swallow a car whole. Good thing it's gone. Probably.",
             "prompt": f"{CINEMATIC} A sixty-foot megalodon shark swims through deep blue ocean. A submarine floats nearby and is smaller than the shark. The megalodon opens its jaws wide showing rows of massive teeth. The submarine is dwarfed. The shark swims past casting a shadow over everything. Photorealistic deep ocean."},
        ],
    },
    # 2. What If You Fell Into Jupiter
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "What If You Fell Into Jupiter",
        "description": "There is no surface. You just keep falling.\n\n#whatif #jupiter #space #science #Shorts",
        "tags": ["what if", "jupiter", "space", "science", "falling", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"label": "WHAT IF YOU FELL\nINTO JUPITER",
             "narration": "What if you fell into Jupiter. There is no ground. No bottom. You just fall forever.",
             "prompt": f"{CINEMATIC} The massive planet Jupiter fills the entire frame seen from space. Its orange brown and red bands swirl violently. A tiny astronaut silhouette falls toward the cloud tops from above. The planet is enormous and the astronaut is a speck against it."},

            {"label": "THE CLOUDS",
             "narration": "First you hit the clouds. Winds at 400 miles per hour rip you sideways. The clouds are ammonia. It smells like the worst cleaning product ever made.",
             "prompt": f"{CINEMATIC} POV camera plunges into thick swirling orange and yellow clouds. Massive lightning bolts flash across the frame illuminating the clouds from within. The clouds whip sideways violently. Green ammonia gas streaks past. The turbulence is extreme. Everything spins and churns."},

            {"label": "THE PRESSURE",
             "narration": "Then the pressure. Every second you fall deeper it crushes harder. Your suit crumples like a soda can. There is no surface. You just keep falling.",
             "prompt": f"{CINEMATIC} Deep below Jupiter's cloud layer. Everything is dark reddish-brown. Thick dense atmosphere presses in from all sides. Faint light from above barely penetrates. The camera pushes downward through layers that get darker and heavier. No ground visible anywhere, just endless dense gas fading to black."},

            {"label": "THE CORE",
             "narration": "At the center, a core of liquid metal hydrogen hotter than the surface of the sun. You wouldn't make it this far. But Jupiter doesn't care.",
             "prompt": f"{CINEMATIC} Camera rushes through total darkness toward a blinding glowing sphere of liquid metallic hydrogen. The sphere radiates intense white and blue light. Streams of glowing metallic liquid orbit around it. The light grows brighter and brighter consuming the entire frame as the camera approaches."},
        ],
    },
    # 3. How a Black Hole Actually Works (REALISTIC)
    {
        "channel_id": 7, "content_type": "yeah_thats_clean", "asset_type": "rendered_yeah_thats_clean_short",
        "title": "How a Black Hole Actually Works",
        "description": "You wouldn't even know you crossed the line.\n\n#blackhole #space #science #howitworks #Shorts",
        "tags": ["black hole", "space", "science", "how it works", "Shorts"],
        "voice": GEORGE_VOICE,
        "clips": [
            {"label": "WHAT ACTUALLY HAPPENS\nWHEN YOU FALL INTO\nA BLACK HOLE",
             "narration": "What actually happens when you fall into a black hole. This thing eats light for breakfast. And you'd never even see it coming.",
             "prompt": f"{CINEMATIC} A massive black hole in deep space with a blazing bright orange accretion disk swirling around it. All nearby stars warp and bend toward it. The black hole dominates the frame. An astronaut drifts slowly toward it, tiny compared to the hole."},

            {"label": "THE EVENT HORIZON",
             "narration": "First, the event horizon. Cross this invisible line and nothing escapes. Not light. Not you. Not even your screams.",
             "prompt": f"{CINEMATIC} An astronaut reaches one gloved hand past a faint glowing boundary line in space. The hand distorts and warps as it crosses. Bright light beams curve sharply and vanish past the line. The astronaut pulls back but the distortion follows. Stars bend around the boundary."},

            {"label": "SPAGHETTIFICATION",
             "narration": "Then spaghettification. The gravity pulls your feet faster than your head. You stretch like taffy until you're a noodle.",
             "prompt": f"{CINEMATIC} An astronaut stretched extremely long vertically in space like a rubber band. The body is impossibly elongated, hundreds of feet long and paper thin. Feet far below near the black hole, helmet far above. The stretched figure is lit by orange accretion disk light. Stars streak vertically."},

            {"label": "THE SINGULARITY",
             "narration": "At the center, the singularity. All the mass of a million suns crushed into a point smaller than an atom. We don't know what happens here. Nobody has come back to tell us.",
             "prompt": f"{CINEMATIC} Camera flies through swirling tunnels of bright orange and blue plasma spiraling inward. The tunnel gets narrower and brighter. At the end a blinding white light grows larger and larger as the camera rushes toward it. Everything warps and bends. The light consumes the entire frame."},
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

        # Narration first — measure durations to pick Sora clip length
        narration_durations = []
        sora_durations = []
        for i, clip in enumerate(clips_config):
            vo = f"{out}/narration/n_{i}.mp3"
            generate_speech(clip["narration"], voice=voice, output_path=vo)
            dur_out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", vo], capture_output=True, text=True)
            nar_dur = float(dur_out.stdout.strip()) if dur_out.stdout.strip() else 3.0
            narration_durations.append(nar_dur)
            # Pick smallest Sora duration that fits narration + 1s buffer
            # Sora supports 4, 8, 12 second clips
            needed = nar_dur + 1.0
            if "duration" in clip:
                sora_dur = clip["duration"]
            elif needed <= 4:
                sora_dur = 4
            elif needed <= 8:
                sora_dur = 8
            else:
                sora_dur = 12
            sora_durations.append(sora_dur)
            print(f"  Narration {i}: {nar_dur:.1f}s -> Sora clip: {sora_dur}s")

        # Sora clips with dynamic durations
        clip_paths, prev_ref = [], None
        for i, clip in enumerate(clips_config):
            cp = os.path.abspath(f"{out}/clips/clip_{i:02d}.mp4")
            sora_dur = sora_durations[i]
            print(f"  Clip {i+1}/{len(clips_config)} ({sora_dur}s)...")
            r = await generate_video_async(prompt=clip["prompt"], output_path=cp, duration=sora_dur, size="720x1280", timeout=1200, reference_image_url=prev_ref)
            clip_paths.append(cp)
            print(f"    Saved: {r['file_size_bytes']} bytes")
            ft = f"/tmp/bv3_{run_id}_{i}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280", "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
            if os.path.exists(ft):
                with open(ft, "rb") as f: prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                os.remove(ft)

        # Trim intro to narration + 1s
        intro_trim = narration_durations[0] + 1.0
        if intro_trim < sora_durations[0]:
            trimmed = f"{out}/clips/clip_00_trimmed.mp4"
            subprocess.run(["ffmpeg", "-y", "-i", clip_paths[0], "-t", str(intro_trim), "-c", "copy", trimmed], capture_output=True)
            if os.path.exists(trimmed): clip_paths[0] = trimmed

        # Mix narration
        mixed = []
        for i, cp in enumerate(clip_paths):
            mx = cp.replace(".mp4", "_mx.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", cp, "-i", f"{out}/narration/n_{i}.mp3", "-filter_complex", "[0:a]volume=0.4[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)

        # Normalize
        norms = []
        for i, p in enumerate(mixed):
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

        # Build ASS subtitle file — one word at a time, center screen
        model = WhisperModel("base", device="cpu")
        word_events, offset = [], 0.0
        for i in range(len(clips_config)):
            segments, _ = model.transcribe(f"{out}/narration/n_{i}.mp3", word_timestamps=True)
            for seg in segments:
                for w in seg.words:
                    word_events.append((offset + w.start, offset + w.end, w.word.strip()))
            offset += actual_durations[i]

        # Build label timing from actual durations
        label_events = []
        label_offset = 0.0
        for i, clip in enumerate(clips_config):
            dur = actual_durations[i]
            label_events.append((label_offset, label_offset + dur, clip["label"]))
            label_offset += dur

        ass = f"{out}/subs.ass"
        with open(ass, "w") as f:
            f.write("[Script Info]\nTitle: Dual\nScriptType: v4.00+\nWrapStyle: 1\nScaledBorderAndShadow: yes\nPlayResX: 720\nPlayResY: 1280\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Title,Impact,62,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,3,0,1,4,0,5,30,30,0,1\n")
            f.write("Style: Label,Impact,42,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,3,0,8,40,40,40,1\n")
            f.write("Style: Word,Impact,58,&H00FFFFFF,&H000000FF,&H40000000,&H00000000,-1,0,0,0,100,100,2,0,1,3,0,5,30,30,0,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            # Labels — first clip uses big centered Title style, rest use top Label
            for idx, (s, e, text) in enumerate(label_events):
                ass_text = text.replace("\n", "\\N")
                style = "Title" if idx == 0 else "Label"
                f.write(f"Dialogue: 1,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},{style},,0,0,0,,{ass_text}\n")
            # One word at a time, center screen (Layer 0)
            for s, e, word in word_events:
                f.write(f"Dialogue: 0,0:{int(s)//60:02d}:{s%60:05.2f},0:{int(e)//60:02d}:{e%60:05.2f},Word,,0,0,0,,{word.upper()}\n")

        final = f"{out}/final.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", f"ass={ass}", "-c:a", "copy", final], capture_output=True)
        if not os.path.exists(final): raise RuntimeError("Subtitle burn failed")
        print(f"  Final: {os.path.getsize(final)/1024/1024:.1f} MB")

        async with async_session() as session:
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": video_config["asset_type"], "c": json.dumps({"status": "rendered", "path": os.path.abspath(final), "size_bytes": os.path.getsize(final), "content_type": ct})})
            await session.execute(sql_text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, :ch, :a, :c)"), {"rid": run_id, "ch": ch_id, "a": "publish_metadata", "c": json.dumps({"title": video_config["title"], "description": video_config["description"], "tags": video_config["tags"], "category": "Education"})})
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
