"""Yeah Thats Clean — The Last Dragon Egg. 60s narrated anime short."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

ANIME_VOICE = "JjsQrIrIBD6TZ656NQfi"

STYLE = (
    "Vertical 9:16 aspect ratio, anime animation style, bold dramatic lines, "
    "vibrant colors, magical particle effects, dramatic lighting with lens flares, "
    "fantasy anime inspired, no text, no watermarks, no UI elements. "
)

CLIPS = [
    {
        "duration": 12,
        "narration": "A tiny dragon. The size of her hand. ...Breathing fire that lit up the entire sky.",
        "prompt": (
            f"{STYLE}"
            "An open field at the edge of an anime village at sunset. Dramatic orange and red sky. "
            "A young anime girl about 12 with long dark hair stands in the field. "
            "On her shoulder sits a tiny dragon the size of a kitten — dark red scales, golden wings spread. "
            "The tiny dragon's mouth is open wide. "
            "A MASSIVE column of golden fire erupts from the tiny dragon's mouth — "
            "impossibly huge, towering into the sky, wider than the entire field. "
            "The fire is beautiful — golden and white, like a wall of pure light. "
            "Three dark armored hunters in front of her are being blown backward by the force. "
            "The girl stands untouched in the center of the fire, eyes closed, completely safe. "
            "The tiny dragon on her shoulder blazes with golden light, eyes burning. "
            "Wide shot — small girl, tiny dragon, wall of golden fire filling the sky behind them."
        ),
    },
    {
        "duration": 12,
        "narration": "Rewind. ...She found the egg in a cave behind her house. They said dragons were extinct.",
        "prompt": (
            f"{STYLE}"
            "A dark cave interior lit by faint blue bioluminescent moss on the walls. "
            "The same young anime girl crouches on the cave floor. "
            "In her hands she holds a large egg the size of a melon. "
            "The egg is dark red with golden cracks running across its surface like veins. "
            "A faint warm orange glow pulses from inside the cracks, like a heartbeat. "
            "The girl stares at the egg with wide amazed eyes, her face lit by the egg's warm glow. "
            "She holds it gently against her chest. The egg pulses brighter in response to her warmth. "
            "Small golden particles float up from the cracks like embers. "
            "The cave is cold and dark around her but the egg glows warm in her arms. "
            "She wraps her cloak around the egg to keep it warm."
        ),
    },
    {
        "duration": 12,
        "narration": "It hatched in her hands. Tiny. Fragile. It fit in her palm. ...She named it Ember.",
        "prompt": (
            f"{STYLE}"
            "A sunlit anime meadow in the morning. Wildflowers, tall grass, golden sunlight. "
            "The girl sits in the grass holding something tiny in her cupped hands. "
            "A baby dragon the size of a kitten sits in her palms. "
            "It has dark red scales, tiny golden wings folded against its body, big round eyes. "
            "The baby dragon looks up at the girl and chirps. Its tiny tail curls around her finger. "
            "The girl laughs, delighted. The dragon sneezes — a tiny puff of smoke comes from its nostrils. "
            "No fire, just smoke. The girl giggles. "
            "She lifts the dragon to her face. It nuzzles its head against her cheek. "
            "Golden sunlight surrounds them both. Flower petals float in the breeze."
        ),
    },
    {
        "duration": 12,
        "narration": "Then the hunters came. They heard the rumors. ...And they brought chains.",
        "prompt": (
            f"{STYLE}"
            "The anime village at dusk. Orange sky, long shadows across cobblestone streets. "
            "Three dark armored hunters on horseback ride into the village. "
            "They wear black armor with red insignias. Heavy chains hang from their saddles. "
            "They carry long spears with glowing red tips. Their faces are scarred and cruel. "
            "Villagers scatter from the streets, pulling children inside. Doors slam shut. "
            "The lead hunter holds up a wanted poster — a drawing of a dragon egg. "
            "He points toward the edge of the village where the girl's small house stands. "
            "The girl watches from her window, the tiny dragon hidden inside her cloak against her chest. "
            "Her face shows pure terror. She clutches the dragon tighter. It chirps softly."
        ),
    },
    {
        "duration": 12,
        "narration": "They said dragons were extinct. ...They were wrong. And she was never alone again.",
        "prompt": (
            f"{STYLE}"
            "A hilltop overlooking the anime village at golden hour. Warm sunset light everywhere. "
            "The girl sits on the grass at the top of the hill, peaceful and calm. "
            "The tiny dragon is curled up asleep in her lap, its small golden wings folded. "
            "Wisps of smoke drift lazily from its nostrils as it sleeps. "
            "The village below is safe and quiet. The hunters are gone. "
            "The girl strokes the dragon's head gently with one finger. It chirps softly in its sleep. "
            "She looks out over the village and the mountains beyond. A gentle wind blows her hair. "
            "The setting sun casts long golden rays across the landscape. "
            "She smiles. Content. Not scared anymore. "
            "Wide final shot — the girl and the tiny sleeping dragon on the hilltop, "
            "the entire world stretching out below them, golden sunset light."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text

    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (7, 'running', 'generate_clips', 'yeah_thats_clean') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        await _run(run_id, generate_video_async, generate_speech, async_session, text)
    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                                  {"rid": run_id, "err": str(e)[:500]})
            await session.commit()
        raise


async def _run(run_id, generate_video_async, generate_speech, async_session, text):
    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    print("Generating narration...")
    narration_paths = []
    for i, clip in enumerate(CLIPS):
        vo_path = f"{output_dir}/narration/narration_{i:02d}.mp3"
        try:
            generate_speech(clip["narration"], voice=ANIME_VOICE, output_path=vo_path)
            narration_paths.append(vo_path)
            print(f"  [{i+1}] OK")
        except Exception as e:
            print(f"  [{i+1}] FAILED: {e}")
            narration_paths.append(None)

    print("\nGenerating Sora clips...")
    clip_paths = []
    prev_ref = None
    for i, clip in enumerate(CLIPS):
        cp = os.path.abspath(f"{output_dir}/clips/clip_{i:02d}.mp4")
        print(f"\nClip {i+1}/{len(CLIPS)}...")
        r = await generate_video_async(
            prompt=clip["prompt"], output_path=cp,
            duration=clip["duration"], size="720x1280", timeout=1200,
            reference_image_url=prev_ref,
        )
        clip_paths.append(cp)
        print(f"  Saved: {r['file_size_bytes']} bytes")
        ft = f"/tmp/dragon_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", cp, "-vf", "thumbnail,scale=720:1280",
                         "-vframes", "1", "-update", "1", "-q:v", "10", ft], capture_output=True)
        if os.path.exists(ft):
            with open(ft, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(ft)

    print("\nMixing narration...")
    mixed = []
    for i, cp in enumerate(clip_paths):
        if i < len(narration_paths) and narration_paths[i] and os.path.exists(narration_paths[i]):
            mx = cp.replace(".mp4", "_nar.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", cp, "-i", narration_paths[i],
                "-filter_complex", "[0:a]volume=0.5[s];[1:a]volume=1.3[v];[s][v]amix=inputs=2:duration=first:dropout_transition=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mx,
            ], capture_output=True)
            mixed.append(mx if os.path.exists(mx) else cp)
        else:
            mixed.append(cp)

    print("Concatenating...")
    norms = []
    for i, p in enumerate(mixed):
        n = f"{output_dir}/clips/norm_{i:02d}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", p, "-vf",
            "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", n,
        ], capture_output=True)
        norms.append(n if os.path.exists(n) else p)

    cl = f"{output_dir}/concat.txt"
    with open(cl, "w") as f:
        for p in norms:
            f.write(f"file '{os.path.abspath(p)}'\n")

    final = f"{output_dir}/yeah_thats_clean_short.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cl,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", final,
    ], capture_output=True)

    if not os.path.exists(final):
        raise RuntimeError("Concat failed")

    print(f"Final: {os.path.getsize(final)/1024/1024:.1f} MB")

    from apps.orchestrator.activities import mark_run_pending_review
    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final),
                "size_bytes": os.path.getsize(final), "content_type": "yeah_thats_clean_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "The Last Dragon Egg",
        "description": "They said dragons were extinct. She found one in a cave. It fit in her palm. It could burn down the world. #anime #dragon #fantasy #Shorts",
        "tags": ["anime", "dragon", "fantasy", "magic", "Shorts"],
        "category": "Entertainment",
    })
    print(f"Done! Run #{run_id}")


asyncio.run(main())
