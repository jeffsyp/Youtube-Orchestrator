"""Whistle Room — The Greatest Comeback: 60 second narrated sports story."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, cinematic sports documentary style, "
    "dramatic lighting, shallow depth of field, slow motion moments, "
    "photorealistic, emotional atmosphere, no text, no watermarks, no UI elements. "
)

CLIPS = [
    # HOOK (12s) — the game-winning shot
    {
        "duration": 12,
        "narration": "Nobody expected him to be here. ...Especially not him.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A packed basketball arena at night, thousands of fans on their feet, bright stadium lights. "
            "A basketball player in a white jersey number 7 catches the ball at the three-point line. "
            "The game clock on the scoreboard shows 3 seconds left. The score is tied. "
            "The player squares up, bends his knees, and rises into a jump shot in slow motion. "
            "His face is calm and focused. Sweat drips from his forehead. "
            "The ball leaves his fingertips with perfect backspin, arcing high through the air. "
            "The entire arena holds their breath — fans frozen mid-scream, mouths open. "
            "The ball drops through the net. Nothing but net. Clean swish. "
            "The arena EXPLODES — fans jumping, screaming, arms raised. "
            "The player stands still for a moment, looking at his hands in disbelief. "
            "His teammates rush toward him. He drops to his knees on the court. "
            "He covers his face with both hands. His shoulders shake — he is crying. "
            "The crowd roars. Confetti falls from above."
        ),
    },
    # REWIND (12s) — the injury
    {
        "duration": 12,
        "narration": "Six months ago... they told him his career was over. Done. Finished.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A sterile white hospital room, harsh fluorescent lighting, cold blue tones. "
            "The same basketball player sits on the edge of a hospital bed wearing a hospital gown. "
            "His right knee is wrapped in heavy bandages and a brace. "
            "A doctor in a white coat stands in front of him holding an X-ray up to the light. "
            "The doctor shakes his head slowly, pointing at the X-ray. "
            "The player stares at the floor, jaw clenched, hands gripping the bed edge. "
            "The doctor puts a hand on the player's shoulder sympathetically and walks out. "
            "The player sits alone in the empty room. "
            "He looks at his bandaged knee. He looks at the ceiling. "
            "He closes his eyes tight. A single tear rolls down his cheek. "
            "On the bedside table sits a framed photo of him mid-dunk in his jersey. "
            "He reaches over and turns the photo face down. "
            "The room is silent. Only the beep of a heart monitor."
        ),
    },
    # TRAINING (12s) — alone in the gym
    {
        "duration": 12,
        "narration": "Every night. Same gym. Nobody watching. Just him... and the sound of the ball.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A dimly lit empty basketball gym at night. Only a few overhead lights are on, casting pools of light. "
            "The basketball player stands alone at the free throw line. He wears grey sweats and a knee brace. "
            "He bounces the ball once. Twice. Three times. The sound echoes in the empty gym. "
            "He shoots. The ball bounces off the rim and rolls away across the dark court. "
            "He limps after it, picks it up, limps back to the line. "
            "He shoots again. Misses again. He grabs the ball and slams it on the floor in frustration. "
            "He bends over, hands on his knees, breathing hard, grimacing in pain. "
            "He looks up at the empty basket. Determination on his face. "
            "He straightens up, bounces the ball, and shoots again. Swish. It goes in. "
            "A tiny smile crosses his face. He grabs the rebound and shoots again. Swish. "
            "Again. Swish. Again. Swish. Faster and faster. "
            "His limp is gone. His movement is fluid. The sound of swish after swish echoes."
        ),
    },
    # THE GAME (12s) — stepping onto the court
    {
        "duration": 12,
        "narration": "When he walked out... the whole arena held its breath.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A packed basketball arena, bright lights, roaring crowd, championship game atmosphere. "
            "A tunnel entrance at the edge of the court. The basketball player stands in the dark tunnel "
            "in his white jersey number 7, looking out at the bright court ahead. "
            "His face is lit half by the arena lights, half in shadow. He takes a deep breath. "
            "He steps out of the tunnel onto the court. His first step onto the hardwood. "
            "The crowd noise DROPS to near silence as fans recognize him. "
            "People in the stands point. Mouths fall open. Camera flashes pop everywhere. "
            "The player walks slowly to center court, each step deliberate and steady. "
            "The opposing team watches from their bench, surprised. "
            "His own teammates stand and start clapping. One by one. Then the whole bench. "
            "The crowd starts a slow clap that builds into a roar. "
            "The player reaches center court, bounces on his toes, rolls his neck. "
            "He is ready. His face shows no fear. Only focus."
        ),
    },
    # THE SHOT (12s) — the final moment
    {
        "duration": 12,
        "narration": "Three seconds left. Tied game. One shot. ...Sometimes the story writes itself.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "Same packed arena from the hook scene. Game clock shows 5 seconds. Score is tied. "
            "The player in white jersey number 7 sprints to the three-point line. "
            "A teammate passes him the ball. He catches it cleanly. "
            "A defender rushes at him with arms raised. The clock shows 3 seconds. "
            "The player pump fakes — the defender jumps past him and falls away. "
            "The player is wide open. Time seems to slow down. "
            "He rises into the jump shot — knees bending, body extending upward, arm extending. "
            "His face is perfectly calm. No fear. No doubt. "
            "The ball releases from his fingertips in extreme slow motion. "
            "It rotates with perfect backspin, arcing through the air toward the basket. "
            "The buzzer sounds — BZZZZZ — while the ball is still in the air. "
            "The ball drops through the net. SWISH. Nothing but net. "
            "One second of silence. Then the arena ERUPTS. "
            "The player falls to his knees. Teammates pile on top of him. "
            "Final wide shot — the player lifted onto his teammates' shoulders, "
            "confetti falling, arena going insane, his arms raised to the sky."
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
                 "VALUES (3, 'running', 'generate_clips', 'whistle_room') RETURNING id")
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
    output_dir = f"output/whistle_room_run_{run_id}"
    os.makedirs(f"{output_dir}/clips", exist_ok=True)
    os.makedirs(f"{output_dir}/narration", exist_ok=True)

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

    print("\nGenerating Sora clips...")
    clip_paths = []
    prev_ref = None

    for i, clip in enumerate(CLIPS):
        clip_path = os.path.abspath(f"{output_dir}/clips/clip_{i:02d}.mp4")
        print(f"\nClip {i+1}/{len(CLIPS)}...")
        result = await generate_video_async(
            prompt=clip["prompt"], output_path=clip_path,
            duration=clip["duration"], size="720x1280", timeout=1200,
            reference_image_url=prev_ref,
        )
        clip_paths.append(clip_path)
        print(f"  Saved: {result['file_size_bytes']} bytes")

        frame_tmp = f"/tmp/bball_frame_{i}.jpg"
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

    print("\nMixing narration...")
    mixed_clips = []
    for i, clip_path in enumerate(clip_paths):
        if i < len(narration_paths) and narration_paths[i] and os.path.exists(narration_paths[i]):
            mixed_path = clip_path.replace(".mp4", "_narrated.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-i", clip_path, "-i", narration_paths[i],
                "-filter_complex",
                "[0:a]volume=0.5[sora];[1:a]volume=1.3[vo];[sora][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", mixed_path,
            ], capture_output=True)
            mixed_clips.append(mixed_path if os.path.exists(mixed_path) else clip_path)
            print(f"  [{i+1}] mixed")
        else:
            mixed_clips.append(clip_path)

    print("\nConcatenating...")
    normalized = []
    for i, p in enumerate(mixed_clips):
        norm_path = f"{output_dir}/clips/norm_{i:02d}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", p,
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", norm_path,
        ], capture_output=True)
        normalized.append(norm_path if os.path.exists(norm_path) else p)

    concat_list = f"{output_dir}/concat.txt"
    with open(concat_list, "w") as f:
        for p in normalized:
            f.write(f"file '{os.path.abspath(p)}'\n")

    final_path = f"{output_dir}/whistle_room_short.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", final_path,
    ], capture_output=True)

    if not os.path.exists(final_path):
        raise RuntimeError("Final concat failed")

    size = os.path.getsize(final_path)
    print(f"\nFinal: {final_path} ({size / 1024 / 1024:.1f} MB)")

    from apps.orchestrator.activities import mark_run_pending_review
    async with async_session() as session:
        await session.execute(
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 3, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_whistle_room_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final_path),
                "size_bytes": size, "content_type": "whistle_room_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "The Greatest Comeback in Basketball",
        "description": "They said his career was over. He had other plans. #basketball #comeback #sports #story #Shorts",
        "tags": ["basketball", "comeback", "sports", "inspirational", "story", "Shorts"],
        "category": "Sports",
    })
    print(f"\nDone! Run #{run_id} in review queue")

asyncio.run(main())
