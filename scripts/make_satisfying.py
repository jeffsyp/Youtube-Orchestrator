"""Generate a satisfying video — no narration, just visual + SFX.

Usage: uv run python scripts/make_satisfying.py "slicing a frozen honey jar"
"""

import asyncio
import base64
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(line_buffering=True)


async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/make_satisfying.py 'description of satisfying scene'")
        return

    description = sys.argv[1]
    out = "output/run_test/satisfying_video"
    os.makedirs(out, exist_ok=True)

    # Clean previous
    for f in os.listdir(out):
        os.remove(f"{out}/{f}")

    print(f"Making: {description}")

    # Step 1: Generate the image
    print("\n=== Image ===")
    from packages.clients.grok import generate_image_dalle
    img_path = f"{out}/scene.png"
    generate_image_dalle(
        prompt=f"Photorealistic, studio lighting, satisfying aesthetic. {description}. Clean composition, bright lighting, high detail.",
        output_path=img_path,
        size="1024x1536",
    )
    print(f"  Image done")

    # Step 2: Animate (10 seconds)
    print("\n=== Video ===")
    from packages.clients.grok import generate_video_async

    compressed = f"{out}/scene_hq.jpg"
    subprocess.run(["ffmpeg", "-y", "-i", img_path, "-q:v", "2", compressed],
        capture_output=True, timeout=10)

    with open(compressed, "rb") as f:
        img_b64 = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"

    await generate_video_async(
        prompt=f"Smooth slow motion, satisfying, {description}",
        output_path=f"{out}/clip.mp4",
        duration=10,
        aspect_ratio="9:16",
        image_url=img_b64,
    )
    print(f"  Clip done")

    # Step 3: Generate satisfying sound effect
    print("\n=== Sound ===")
    import requests
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    resp = requests.post("https://api.elevenlabs.io/v1/sound-generation",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": f"satisfying {description} sound, ASMR, crisp and clean", "duration_seconds": 10.0},
        timeout=60,
    )
    if resp.status_code == 200:
        with open(f"{out}/sfx.mp3", "wb") as f:
            f.write(resp.content)
        print(f"  SFX done")
    else:
        print(f"  SFX failed, using silent")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "10",
            "-c:a", "libmp3lame", f"{out}/sfx.mp3"], capture_output=True, timeout=10)

    # Step 4: Combine video + sound
    print("\n=== Assemble ===")
    # Strip grok audio, add SFX
    subprocess.run(["ffmpeg", "-y", "-i", f"{out}/clip.mp4", "-map", "0:v:0", "-c:v", "copy", "-an",
        f"{out}/clip_noaudio.mp4"], capture_output=True, timeout=30)

    vid_input = f"{out}/clip_noaudio.mp4" if os.path.exists(f"{out}/clip_noaudio.mp4") else f"{out}/clip.mp4"

    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", vid_input,
        "-i", f"{out}/sfx.mp3",
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
        "-map", "0:v", "-map", "1:a",
        "-t", "10",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
        "-movflags", "+faststart",
        f"{out}/final.mp4",
    ], capture_output=True, timeout=120)

    if os.path.exists(f"{out}/final.mp4"):
        dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", f"{out}/final.mp4"],
            capture_output=True, text=True).stdout.strip()
        size = os.path.getsize(f"{out}/final.mp4") / 1024 / 1024
        print(f"\n=== DONE ===")
        print(f"Duration: {dur}s, Size: {size:.1f}MB")
        print(f"http://localhost:5173/{out}/final.mp4")
    else:
        print("FAILED")


if __name__ == "__main__":
    asyncio.run(main())
