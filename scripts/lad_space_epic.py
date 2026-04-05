"""Lad Goes to Space — 50 second mini story with narration and hook structure."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

from packages.prompts.lad_stories import CHARACTER_BIBLE, STYLE_BIBLE

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, claymation stop-motion style, "
    "visible hand-crafted textures, fingerprint marks in clay, "
    "miniature handmade set/diorama, warm soft diffused lighting, "
    "no text, no watermarks, no UI elements. "
)

CLIPS = [
    # HOOK (10s) — chaos from frame 1
    {
        "duration": 12,
        "narration": "Lad was NOT supposed to be here.",
        "prompt": (
            f"{STYLE_PREFIX} {CHARACTER_BIBLE} "
            "A tiny clay rocket ship is shaking violently inside. Red alarm lights flash. "
            "Sparks shoot from the control panel. The small round clay character Lad is bouncing "
            "around inside the shaking cockpit, eyes wide in panic. "
            "The rocket cracks open and EXPLODES outward — pieces of tin foil and cardboard fly everywhere. "
            "Lad is launched out of the explosion, tumbling through the air. "
            "He crashes through a clay wall and lands in a massive colorful alien city "
            "made of weird clay buildings with glowing windows. "
            "Clay alien figures with big eyes scatter in all directions as Lad slides across the floor "
            "leaving a trail of debris behind him. Lad ends up sitting on the ground, dazed, "
            "surrounded by shocked aliens staring at him. He blinks."
        ),
    },
    # REWIND (10s) — how it started
    {
        "duration": 12,
        "narration": "30 seconds earlier. He found a button. Lad always presses the button.",
        "prompt": (
            f"{STYLE_PREFIX} {CHARACTER_BIBLE} "
            "A peaceful clay backyard diorama with green clay grass and a tiny clay fence. "
            "Lad is walking through the yard and discovers a tiny clay rocket ship "
            "made of tin foil and cardboard sitting behind a bush. "
            "Lad tilts his head curiously and walks up to it. He climbs inside the tiny cockpit. "
            "Inside there is one big red button on the dashboard. Lad stares at the button. "
            "He looks left. He looks right. He reaches out one stubby arm and presses the button. "
            "The rocket instantly ignites with a HUGE flame shooting out the bottom. "
            "The rocket blasts straight up into the sky at comical speed. "
            "Lad's body squishes from the G-force, his eyes bulging. "
            "The backyard shrinks below as the rocket shoots upward. Stars appear around the rocket."
        ),
    },
    # ESCALATION 1 (10s) — the welcome gift
    {
        "duration": 12,
        "narration": "They gave him a welcome gift. It was not a gift.",
        "prompt": (
            f"{STYLE_PREFIX} {CHARACTER_BIBLE} "
            "Inside a colorful alien building made of clay. The walls have strange glowing patterns. "
            "Lad is standing up, brushing debris off himself. Pieces of his broken rocket are scattered "
            "on the floor around him. Three small grey clay aliens with big round eyes approach Lad cautiously. "
            "One alien holds out a glowing green clay orb toward Lad. "
            "Lad takes the orb in both hands and looks at it curiously. "
            "The orb starts blinking with a small light. Then it blinks faster. And faster. "
            "The three aliens look at each other nervously. "
            "All three aliens suddenly turn and run away as fast as they can. "
            "Lad stands alone holding the rapidly blinking orb. He looks down at it. "
            "He looks up at the empty room where the aliens were just standing. "
            "Lad's eyes go wide as the blinking gets extremely fast."
        ),
    },
    # ESCALATION 2 (10s) — the chase
    {
        "duration": 12,
        "narration": "The beeping got faster. That is never good.",
        "prompt": (
            f"{STYLE_PREFIX} {CHARACTER_BIBLE} "
            "A clay alien city corridor with strange architecture. "
            "Lad is running through the corridor holding the rapidly blinking green orb out in front of him. "
            "He is chasing the three grey aliens who are sprinting away from him. "
            "Lad tries to hand the orb to each alien he passes but they all dodge out of the way. "
            "As Lad runs past clay objects — clay vases, clay furniture, clay signs — "
            "each object starts floating up into the air behind him, pulled by the orb's energy. "
            "A trail of floating clay objects follows Lad down the corridor. "
            "More aliens see the floating objects and run away screaming. "
            "Lad reaches a dead end wall. He turns around. "
            "A massive pile of floating objects hovers behind him. "
            "The orb's blinking is now a solid glow. Lad gulps."
        ),
    },
    # PAYOFF (10s) — the twist
    {
        "duration": 12,
        "narration": "Turns out the orb was a test. Lad is now their king.",
        "prompt": (
            f"{STYLE_PREFIX} {CHARACTER_BIBLE} "
            "The glowing green orb in Lad's hands explodes with a bright white flash. "
            "But instead of destruction, all the floating objects gently lower back down to the ground. "
            "Everything settles perfectly into place. The corridor transforms — "
            "the walls become golden and decorated with royal clay patterns. "
            "A red clay carpet rolls out under Lad's feet leading to a massive clay throne. "
            "The three grey aliens return, now wearing tiny clay crowns. "
            "They bow deeply to Lad. More aliens appear and bow. "
            "Lad looks left and right, confused. The aliens gesture toward the throne. "
            "Lad waddles over and climbs up onto the huge throne. "
            "He sits down. The throne is way too big for him, his tiny legs dangle off the edge. "
            "He looks at the camera with a confused expression. "
            "An alien places a tiny clay crown on his head. It falls over his eyes. "
            "Lad pushes the crown up with one stubby arm and blinks."
        ),
    },
]


async def main():
    from packages.clients.sora import generate_video_async
    from packages.clients.elevenlabs import generate_speech
    from packages.clients.db import async_session
    from sqlalchemy import text

    # Create run
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO content_runs (channel_id, status, current_step, content_type) "
                 "VALUES (6, 'running', 'generate_clips', 'lad_stories') RETURNING id")
        )
        run_id = result.scalar()
        await session.commit()
    print(f"Run #{run_id}")

    try:
        await _run_pipeline(run_id, async_session, text, generate_video_async, generate_speech)
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


async def _run_pipeline(run_id, async_session, text, generate_video_async, generate_speech):
    output_dir = f"output/lad_stories_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

    # Generate narration audio for all clips
    print("Generating narration...")
    narration_paths = []
    for i, clip in enumerate(CLIPS):
        vo_path = f"{output_dir}/narration/narration_{i:02d}.mp3"
        try:
            generate_speech(clip["narration"], output_path=vo_path)
            narration_paths.append(vo_path)
            print(f"  Narration {i+1}: {clip['narration'][:50]}...")
        except Exception as e:
            print(f"  Narration {i+1} failed: {e}")
            narration_paths.append(None)

    # Generate Sora clips with frame chaining
    print("\nGenerating Sora clips...")
    clip_paths = []
    prev_ref = None

    for i, clip in enumerate(CLIPS):
        clip_path = os.path.abspath(f"{output_dir}/clips/clip_{i:02d}.mp4")
        print(f"\nClip {i+1}/{len(CLIPS)}: {clip['narration'][:40]}...")

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

        # Extract last frame for next clip — JPEG at 720x1280 (must match Sora dimensions)
        frame_tmp = f"/tmp/lad_frame_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-i", clip_path, "-vf", "thumbnail,scale=720:1280", "-vframes", "1",
             "-update", "1", "-q:v", "10", frame_tmp],
            capture_output=True,
        )
        if os.path.exists(frame_tmp):
            with open(frame_tmp, "rb") as f:
                prev_ref = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
            os.remove(frame_tmp)
            print(f"  Frame chained for next clip ({len(prev_ref)} chars)")

    # Mix narration into each clip
    print("\nMixing narration into clips...")
    mixed_clips = []
    for i, clip_path in enumerate(clip_paths):
        if i < len(narration_paths) and narration_paths[i] and os.path.exists(narration_paths[i]):
            mixed_path = clip_path.replace(".mp4", "_narrated.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", clip_path,
                "-i", narration_paths[i],
                "-filter_complex",
                "[0:a]volume=0.4[sora];[1:a]volume=1.5[vo];[sora][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                mixed_path,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if os.path.exists(mixed_path):
                mixed_clips.append(mixed_path)
                print(f"  Clip {i+1}: narration mixed")
            else:
                mixed_clips.append(clip_path)
                print(f"  Clip {i+1}: mix failed, using original")
        else:
            mixed_clips.append(clip_path)
            print(f"  Clip {i+1}: no narration, using original")

    # Concatenate all clips
    print("\nConcatenating clips...")
    concat_list = f"{output_dir}/concat.txt"
    with open(concat_list, "w") as f:
        for p in mixed_clips:
            f.write(f"file '{p}'\n")

    final_path = f"{output_dir}/lad_stories_short.mp4"
    # First normalize all clips to same resolution/framerate
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
        if os.path.exists(norm_path):
            normalized.append(norm_path)
        else:
            normalized.append(p)

    # Write new concat list with normalized clips
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        final_path,
    ], capture_output=True)

    if os.path.exists(final_path):
        size = os.path.getsize(final_path)
        print(f"\nFinal video: {final_path} ({size / 1024 / 1024:.1f} MB)")
    else:
        print("\nERROR: Final concat failed")
        return

    # Store assets and mark for review
    from apps.orchestrator.activities import mark_run_pending_review

    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 6, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_lad_stories_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final_path),
                "size_bytes": os.path.getsize(final_path),
                "content_type": "lad_stories_short",
            })},
        )
        await session.commit()

    await mark_run_pending_review(run_id, {
        "title": "Lad Goes to Space and Becomes King",
        "description": "Lad found a rocket. He pressed the button. Now he rules an alien civilization. #claymation #animation #funny #space #Shorts",
        "tags": ["claymation", "stop motion", "funny", "space", "aliens", "Shorts"],
        "category": "Entertainment",
    })
    print(f"\nDone! Run #{run_id} in review queue")


asyncio.run(main())
