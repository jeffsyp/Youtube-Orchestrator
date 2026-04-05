"""Yeah Thats Clean — 60 second narrated pirate heist action story."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, stylized cartoon animation, bold colors, "
    "dynamic camera angles, cinematic lighting, comic book action style, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    # HOOK (12s) — start with the craziest moment
    {
        "duration": 12,
        "narration": "So there's a guy... hanging off the side of a flying pirate ship. "
                     "With a diamond the size of his head. And the captain? ...Not happy about it.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A cartoon character in a dark coat is hanging off the side of a massive flying pirate ship "
            "high above a glowing city at night. He is gripping a rope with one hand. "
            "His other hand clutches a giant glowing blue diamond. "
            "Wind blows his coat and hair wildly. Below him, city lights stretch to the horizon. "
            "Above him on the deck, a large angry pirate captain with a red coat and mechanical arm "
            "leans over the railing reaching down trying to grab him. "
            "Cannons on the ship are firing bright orange blasts into the sky. "
            "The character looks down at the city far below, then looks up at the captain, then smirks. "
            "Dramatic cinematic composition, dark sky with orange and blue lighting."
        ),
    },
    # REWIND (12s) — how it started
    {
        "duration": 12,
        "narration": "Alright... rewind. Three minutes earlier, this guy walks into the ship's vault. "
                     "No guards. No alarms. Just... a diamond sitting there. Way too easy.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "Inside a dark ornate vault room on a pirate ship. Golden walls, treasure piled in corners. "
            "A cartoon character in a dark coat walks through an open vault door. "
            "He looks around suspiciously — no guards anywhere. "
            "In the center of the room on a pedestal sits a giant glowing blue diamond. "
            "Spotlight shines down on the diamond from above. "
            "The character walks slowly toward the diamond, looking left and right. "
            "He reaches out both hands and carefully lifts the diamond off the pedestal. "
            "He holds it up and it glows bright blue on his face. He grins. "
            "Then a tiny click sound — the pedestal sinks down one inch. A trap. "
            "His grin disappears. Red alarm lights start flashing on the walls."
        ),
    },
    # ESCALATION 1 (12s) — the chase begins
    {
        "duration": 12,
        "narration": "And that's when the whole ship woke up. Every door. Every corridor. "
                     "...Full of pirates. All running straight at him.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A cartoon character in a dark coat sprints down a wooden corridor inside a pirate ship. "
            "He holds the glowing blue diamond under one arm like a football. "
            "Red alarm lights flash on the walls. "
            "Behind him, a crowd of cartoon pirates pours out of every doorway — "
            "pirates with swords, pirates with hooks, pirates with nets. "
            "The character slides under a closing metal gate just before it slams shut. "
            "He kicks open a wooden door and runs through. "
            "He grabs a hanging rope and swings across a gap in the floor. "
            "Pirates pile up at the gap unable to cross. "
            "The character lands on the other side and keeps running toward a bright light ahead — "
            "the exit to the open deck."
        ),
    },
    # ESCALATION 2 (12s) — the captain arrives
    {
        "duration": 12,
        "narration": "He almost made it. Almost. Then the captain stepped out... "
                     "and this guy was NOT the type you mess with.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "On the open deck of a flying pirate ship at night, high above a glowing city. "
            "The cartoon character in the dark coat bursts through a door onto the deck, diamond in hand. "
            "He stops suddenly. "
            "Standing in front of him is the pirate captain — massive, twice his height, "
            "red coat, mechanical arm with glowing gears, scars across his face. "
            "The captain cracks his mechanical knuckles. Steam hisses from the joints. "
            "Behind the character, pirates fill the doorway blocking his retreat. "
            "The character looks at the captain. Looks at the edge of the ship. "
            "Looks down at the diamond. Looks back at the captain. "
            "He takes a deep breath and sprints straight toward the edge of the ship."
        ),
    },
    # PAYOFF (12s) — the escape
    {
        "duration": 12,
        "narration": "He jumped. Off a flying pirate ship. With their diamond. "
                     "And the thing is? ...He planned the whole thing.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "The cartoon character leaps off the edge of the flying pirate ship into the night sky. "
            "The captain reaches out but misses him by inches. "
            "The character falls through the air, coat flapping wildly, holding the diamond tight. "
            "He is falling toward the glowing city far below. "
            "Then he pulls a cord on his coat — a hidden glider wing unfolds from his back. "
            "He catches the wind and swoops upward gracefully. "
            "He glides away from the ship in a wide arc, the diamond glowing blue under his arm. "
            "The pirate ship shrinks behind him, cannons firing but missing. "
            "The character looks back over his shoulder at the ship and grins. "
            "He flies toward the glowing city skyline, silhouetted against a massive full moon. "
            "Final wide shot — tiny glider silhouette against the huge moon, city below."
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
        await _run_pipeline(run_id, generate_video_async, generate_speech, async_session, text)
    except Exception as e:
        print(f"\nERROR: {e}")
        async with async_session() as session:
            await session.execute(
                text("UPDATE content_runs SET status='failed', error=:err WHERE id=:rid"),
                {"rid": run_id, "err": str(e)[:500]},
            )
            await session.commit()
        print(f"Run #{run_id} marked as failed")
        raise


async def _run_pipeline(run_id, generate_video_async, generate_speech, async_session, text):
    output_dir = f"output/yeah_thats_clean_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    # Generate narration
    print("Generating narration (George voice)...")
    narration_paths = []
    for i, clip in enumerate(CLIPS):
        vo_path = f"{output_dir}/narration/narration_{i:02d}.mp3"
        try:
            generate_speech(clip["narration"], output_path=vo_path)
            narration_paths.append(vo_path)
            print(f"  [{i+1}] {clip['narration'][:50]}...")
        except Exception as e:
            print(f"  [{i+1}] FAILED: {e}")
            narration_paths.append(None)

    # Generate Sora clips with frame chaining
    print("\nGenerating Sora clips...")
    clip_paths = []
    prev_ref = None

    for i, clip in enumerate(CLIPS):
        clip_path = os.path.abspath(f"{output_dir}/clips/clip_{i:02d}.mp4")
        print(f"\nClip {i+1}/{len(CLIPS)}...")

        result = await generate_video_async(
            prompt=clip["prompt"],
            output_path=clip_path,
            duration=clip["duration"],
            size="720x1280",
            timeout=1200,
            reference_image_url=prev_ref,
        )
        clip_paths.append(clip_path)
        print(f"  Saved: {result['file_size_bytes']} bytes")

        # Frame chain
        frame_tmp = f"/tmp/pirate_frame_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-i", clip_path, "-vf", "thumbnail,scale=720:1280",
             "-vframes", "1", "-update", "1", "-q:v", "10", frame_tmp],
            capture_output=True,
        )
        if os.path.exists(frame_tmp):
            with open(frame_tmp, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(frame_tmp)
            print(f"  Frame chained")

    # Mix narration into clips
    print("\nMixing narration...")
    mixed_clips = []
    for i, clip_path in enumerate(clip_paths):
        if i < len(narration_paths) and narration_paths[i] and os.path.exists(narration_paths[i]):
            mixed_path = clip_path.replace(".mp4", "_narrated.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", clip_path, "-i", narration_paths[i],
                "-filter_complex",
                "[0:a]volume=0.3[sora];[1:a]volume=1.5[vo];[sora][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                mixed_path,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if os.path.exists(mixed_path):
                mixed_clips.append(mixed_path)
                print(f"  [{i+1}] mixed")
            else:
                mixed_clips.append(clip_path)
                print(f"  [{i+1}] mix failed")
        else:
            mixed_clips.append(clip_path)

    # Normalize and concat
    print("\nConcatenating...")
    normalized = []
    for i, p in enumerate(mixed_clips):
        norm_path = f"{output_dir}/clips/norm_{i:02d}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", p,
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            norm_path,
        ], capture_output=True)
        normalized.append(norm_path if os.path.exists(norm_path) else p)

    concat_list = f"{output_dir}/concat.txt"
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{os.path.abspath(p)}'\n")

    final_path = f"{output_dir}/yeah_thats_clean_short.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        final_path,
    ], capture_output=True)

    if not os.path.exists(final_path):
        raise RuntimeError("Final concat failed")

    size = os.path.getsize(final_path)
    print(f"\nFinal: {final_path} ({size / 1024 / 1024:.1f} MB)")

    from apps.orchestrator.activities import mark_run_pending_review

    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 7, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_yeah_thats_clean_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final_path),
                "size_bytes": size, "content_type": "yeah_thats_clean_short",
            })},
        )
        await session.commit()

    await mark_run_pending_review(run_id, {
        "title": "He Stole a Diamond From a Flying Pirate Ship",
        "description": "One guy. One diamond. One very angry captain. #animation #action #pirate #heist #Shorts",
        "tags": ["animation", "action", "pirate", "heist", "cartoon", "Shorts"],
        "category": "Entertainment",
    })
    print(f"\nDone! Run #{run_id} in review queue")


asyncio.run(main())
