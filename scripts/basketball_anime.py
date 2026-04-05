"""Whistle Room — The Greatest Comeback: anime sports style, 60 second narrated story."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, anime sports animation style, bold dramatic lines, "
    "vibrant colors, dynamic speed lines, dramatic lighting with lens flares, "
    "exaggerated action poses, Slam Dunk and Haikyuu inspired art style, "
    "cinematic camera angles, no text, no watermarks, no UI elements. "
)

CLIPS = [
    # HOOK (12s) — the game-winning shot, anime style
    {
        "duration": 12,
        "narration": "Nobody expected him to be here. ...Especially not him.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A packed anime basketball arena, thousands of animated fans on their feet, bright stadium lights with lens flares. "
            "An anime basketball player with spiky dark hair in a white jersey number 7 catches the ball at the three-point line. "
            "Close-up of his intense eyes — they glow with determination. Speed lines radiate behind him. "
            "The game clock shows 3 seconds. The score is tied. "
            "He bends his knees and rises into a jump shot in dramatic slow motion. "
            "His body extends upward, arm reaching high, the ball rolls off his fingertips. "
            "Sweat drops fly off his face in slow motion, catching the arena lights. "
            "The ball arcs through the air with a glowing trail behind it. "
            "The entire arena is frozen — fans with mouths open, players mid-stride. "
            "The ball drops through the net with a bright flash. "
            "The arena EXPLODES with color — fans screaming, confetti bursting, teammates rushing in. "
            "The player drops to his knees on the court, head down, fists clenched. "
            "Tears stream down his anime face. His shoulders shake. "
            "Dramatic camera pull-back showing the entire erupting arena."
        ),
    },
    # REWIND (12s) — the injury
    {
        "duration": 12,
        "narration": "Six months ago... they told him his career was over. Done. ...Finished.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A hospital room drawn in muted anime tones — greys and blues, dim lighting. "
            "The same anime basketball player sits on a hospital bed in a gown. "
            "His right knee is wrapped in heavy bandages and a brace. "
            "An anime doctor in a white coat holds up an X-ray and shakes his head slowly. "
            "Close-up of the player's face — jaw clenched, eyes staring at the floor, shadowed. "
            "The doctor puts a hand on his shoulder sympathetically and walks out of frame. "
            "The player sits alone. The room feels empty and cold. "
            "He looks at his bandaged knee. Then at the ceiling. "
            "He closes his eyes tight. A single tear rolls down his cheek, catching the light. "
            "On the bedside table sits a framed photo of him mid-dunk in his jersey. "
            "His hand reaches over and turns the photo face down on the table. "
            "Final frame — the player alone in the dark room, hunched over, defeated. "
            "Only the beep of a heart monitor echoing."
        ),
    },
    # TRAINING (12s) — alone in the gym
    {
        "duration": 12,
        "narration": "Every night. Same gym. Nobody watching. Just him... and the sound of the ball.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A dimly lit empty anime basketball gym at night. Only a few overhead lights casting dramatic pools of light. "
            "The anime basketball player stands alone at the free throw line wearing grey sweats and a knee brace. "
            "He bounces the ball once. Twice. The sound echoes dramatically in the empty gym. "
            "He shoots. The ball bounces off the rim and rolls away across the dark polished floor. "
            "He limps slowly after it, picks it up, limps back to the line. Pain on his face. "
            "He shoots again. Misses again. He slams the ball on the floor in frustration. "
            "The ball bounces high. He bends over, hands on his knees, grimacing. "
            "Close-up of his determined eyes looking up at the basket. Anime fire in his gaze. "
            "He straightens up. Bounces the ball. Shoots. SWISH — it goes in. "
            "A tiny smile crosses his face. Speed lines appear. "
            "He grabs the rebound and shoots again. Swish. Again. Swish. Faster and faster. "
            "Montage — ball after ball dropping through the net, his movement getting smoother, "
            "his limp disappearing, his confidence growing. The gym glows brighter with each shot."
        ),
    },
    # THE GAME (12s) — stepping onto the court
    {
        "duration": 12,
        "narration": "When he walked out... the whole arena held its breath.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A packed anime basketball arena, bright lights, roaring animated crowd, championship atmosphere. "
            "A dark tunnel entrance at the edge of the court. "
            "The anime basketball player stands in the dark tunnel in his white jersey number 7. "
            "His face is half lit by the bright arena, half in dramatic shadow. "
            "Close-up of his eyes — calm, focused, burning with quiet intensity. "
            "He takes one deep breath. Steam rises from his breath in the cold tunnel air. "
            "He steps forward out of the tunnel onto the bright court. His first step onto the hardwood. "
            "The crowd noise drops to silence. Camera flashes pop like stars across the stands. "
            "Fans point. Mouths fall open in surprise. "
            "His teammates on the bench stand up one by one and start clapping. "
            "The crowd starts a slow clap that builds and builds into a thunderous roar. "
            "The player walks to center court. He bounces on his toes. Rolls his neck. "
            "Wide shot — one player standing at center court, entire arena on their feet around him. "
            "His face shows no fear. Only focus. Dramatic anime wind blows his jersey."
        ),
    },
    # THE SHOT (12s) — the final moment
    {
        "duration": 12,
        "narration": "Three seconds left. Tied game. One shot. ...Sometimes... the story writes itself.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "Same packed anime arena. Game clock shows 5 seconds. Score is tied. "
            "The player in white jersey 7 sprints to the three-point line. Speed lines trail behind him. "
            "A teammate passes the ball — it flies through the air in slow motion toward him. "
            "He catches it cleanly. Close-up of his hands gripping the ball. "
            "A defender rushes at him, arms raised, dramatic speed lines. Clock shows 3 seconds. "
            "The player pump fakes — the defender leaps past him and falls away in slow motion. "
            "The player is wide open. Time freezes. Everything goes silent. "
            "Extreme slow motion — he rises into the jump shot. His body extends upward. "
            "Close-up of his calm eyes. No fear. No doubt. "
            "The ball releases from his fingertips with perfect backspin. Glowing trail behind the ball. "
            "The buzzer sounds while the ball is in the air — dramatic sound wave ripple effect. "
            "The ball drops through the net. SWISH. Bright white flash fills the screen. "
            "One second of absolute silence. Then — the arena ERUPTS with anime energy effects. "
            "The player falls to his knees. Teammates pile on. "
            "Final wide shot — player lifted onto teammates shoulders, confetti raining down, "
            "arena glowing with light, his arms raised to the sky, tears streaming down his face."
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

        frame_tmp = f"/tmp/anime_bball_{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", clip_path, "-vf", "thumbnail,scale=720:1280",
                         "-vframes", "1", "-update", "1", "-q:v", "10", frame_tmp], capture_output=True)
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
        "description": "They said his career was over. He had other plans. #basketball #anime #sports #story #Shorts",
        "tags": ["basketball", "anime", "comeback", "sports", "story", "Shorts"],
        "category": "Sports",
    })
    print(f"\nDone! Run #{run_id} in review queue")


asyncio.run(main())
