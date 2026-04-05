"""Fundational — Raised by Wolves: 60 second narrated story."""
import asyncio
import base64
import json
import os
import subprocess

os.chdir("/home/jeff/youtube-orchestrator")

STYLE_PREFIX = (
    "Vertical 9:16 aspect ratio, dreamlike cinematic style, slightly surreal lighting, "
    "warm golden tones, shallow depth of field, atmospheric fog and particles in the air, "
    "photorealistic but with a magical quality, no text, no watermarks, no UI elements. "
)

CLIPS = [
    # HOOK (12s) — adult running with wolves at insane speed
    {
        "duration": 12,
        "narration": "They said he was human... he wasn't so sure anymore.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A dense forest at dawn, golden light streaming through tall trees, fog low on the ground. "
            "A muscular adult man with long wild hair and bare feet sprints through the forest ON ALL FOURS "
            "at incredible speed, his body low to the ground, arms and legs pumping like an animal. "
            "His muscles ripple as he moves. Dirt and leaves kick up behind him. "
            "Running alongside him are six large grey wolves matching his exact speed. "
            "The man and the wolves weave between tree trunks together as a pack. "
            "The man's face is focused, primal, wild eyes. He breathes hard, grunting with effort. "
            "A wolf on his right howls while running. The man tilts his head back and howls too. "
            "Camera tracks alongside them at ground level, trees blurring past. "
            "They are all moving impossibly fast, the forest floor a blur beneath them. "
            "The scene ends with the pack bursting out of the treeline together."
        ),
    },
    # AGE 3 (12s) — baby with wolf pups
    {
        "duration": 12,
        "narration": "Rewind... twenty two years. They found him alone. They didn't leave him alone.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "Inside a dark wolf den carved into a hillside. Warm amber light filters in from the entrance. "
            "A large grey mother wolf lies on her side nursing four small wolf pups. "
            "Nestled among the wolf pups is a tiny human baby, about one year old, "
            "with messy dark hair and big curious eyes. "
            "The baby is pressed against the mother wolf's warm fur just like the pups. "
            "The mother wolf lifts her head and gently licks the baby's face. "
            "The baby giggles and reaches up with tiny hands to grab the wolf's ear. "
            "The wolf pups tumble over each other and over the baby playfully. "
            "The baby crawls forward clumsily on hands and knees, trying to keep up with a pup. "
            "The pup stops and looks back at the baby. The baby catches up and falls onto the pup. "
            "Both tumble together. The mother wolf watches calmly from behind. "
            "Warm cozy den atmosphere, soft sounds of the baby cooing and pups whimpering."
        ),
    },
    # AGE 10 (12s) — kid trying to keep up
    {
        "duration": 12,
        "narration": "He was slower than the rest. But he never... stopped... trying.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A wide open meadow at sunset, golden grass swaying in the wind. "
            "A pack of five grey wolves runs across the meadow at full speed, sleek and powerful. "
            "Behind them, a skinny boy about ten years old with wild messy hair and torn simple clothes "
            "runs as fast as he can trying to keep up. He runs on two legs but leans forward. "
            "His bare feet pound the grass. He is breathing hard, panting, face strained with effort. "
            "The wolves are pulling ahead of him. The gap between the boy and the pack grows wider. "
            "The boy stumbles and falls forward onto his hands and knees in the grass. "
            "He stays on all fours for a moment, catching his breath, sweat dripping from his face. "
            "He looks up at the wolves running away from him. Determination fills his face. "
            "He pushes himself back up and starts running again, harder than before. "
            "The wolves slow down slightly, looking back. One wolf stops and waits for the boy. "
            "The boy catches up to the waiting wolf. They run together side by side."
        ),
    },
    # AGE 16 (12s) — matching the wolves
    {
        "duration": 12,
        "narration": "By sixteen? ...They couldn't tell the difference.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "A rocky mountain trail at sunrise, dramatic orange sky behind snow-capped peaks. "
            "A teenage boy about sixteen with lean muscular build, long wild hair, and animal-skin clothing "
            "leaps from one rock to another alongside the wolf pack. "
            "He lands on a boulder in a crouch, perfectly balanced, then springs forward. "
            "His movements are fluid and animal-like, no wasted motion. "
            "The wolves leap across the same rocks beside him, matching his rhythm exactly. "
            "The boy and wolves move in perfect sync — they jump at the same time, land at the same time. "
            "The boy's face is calm and confident now, no struggle, no strain. "
            "He runs on all fours across a flat stretch, his speed matching the wolves stride for stride. "
            "The wolf pack alpha runs next to him and they make eye contact. "
            "A moment of recognition between them — equals. "
            "They crest the mountain ridge together, silhouetted against the massive orange sunrise. "
            "The boy lets out a howl. The wolves howl with him. The sound echoes across the valley."
        ),
    },
    # AGE 25 (12s) — he IS the fastest
    {
        "duration": 12,
        "narration": "By twenty five? ...He was the fastest one.",
        "prompt": (
            f"{STYLE_PREFIX}"
            "Same dense forest from the opening scene. Dawn light, fog, tall trees. "
            "The full grown muscular man with long wild hair LEADS the wolf pack now. "
            "He is out front, running on all fours at incredible speed, FASTER than the wolves behind him. "
            "The wolves sprint at full speed but the man is pulling ahead of them. "
            "His body moves with perfect animal efficiency, low to the ground, powerful strides. "
            "The camera is at ground level tracking his face — primal, powerful, free. "
            "He lets out a guttural roar as he accelerates even faster. "
            "Trees blur past. Leaves scatter in his wake. The ground shakes under his hands and feet. "
            "The wolves fall further behind, unable to match his speed. "
            "Final shot: the man bursts out of the forest into a wide open cliff edge. "
            "He skids to a stop at the edge, standing up on two legs for the first time. "
            "He stands tall on the cliff, chest heaving, looking out over a vast valley below. "
            "The wolf pack catches up and gathers around his legs. "
            "He looks down at them. They look up at him. He is home. "
            "Wide final shot — man standing on cliff edge, wolves around him, massive valley and sunrise behind."
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
                 "VALUES (5, 'running', 'generate_clips', 'fundational') RETURNING id")
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
    output_dir = f"output/fundational_run_{run_id}"
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

        frame_tmp = f"/tmp/wolves_frame_{i}.jpg"
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

    final_path = f"{output_dir}/fundational_short.mp4"
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
            text("INSERT INTO assets (run_id, channel_id, asset_type, content) VALUES (:rid, 5, :atype, :content)"),
            {"rid": run_id, "atype": "rendered_fundational_short", "content": json.dumps({
                "status": "rendered", "path": os.path.abspath(final_path),
                "size_bytes": size, "content_type": "fundational_short",
            })},
        )
        await session.commit()
    await mark_run_pending_review(run_id, {
        "title": "Raised by Wolves",
        "description": "They found him alone. Twenty years later... he was the fastest one. #wolves #animation #story #Shorts",
        "tags": ["wolves", "raised by wolves", "animation", "story", "survival", "Shorts"],
        "category": "Entertainment",
    })
    print(f"\nDone! Run #{run_id} in review queue")

asyncio.run(main())
