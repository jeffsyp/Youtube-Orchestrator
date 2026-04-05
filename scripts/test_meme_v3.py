"""Meme video: two pathetic gamer scenes with persistent text."""
import asyncio, os, base64, subprocess, sys, shutil
sys.stdout.reconfigure(line_buffering=True)
from packages.clients.grok import generate_image_dalle, generate_video_async

out = "output/run_test/meme"
os.makedirs(out, exist_ok=True)
for f in os.listdir(out): os.remove(f"{out}/{f}")

async def main():
    print("Scene 1...")
    generate_image_dalle(
        prompt="Bold cartoon style, thick outlines, bright colors. A sad cartoon gamer trying to play but their mouse cord is tangled around their arm, keyboard upside down, monitor showing 0 kills 15 deaths, energy drink spilled on desk.",
        output_path=f"{out}/p1.png", size="1024x1536",
    )

    print("Scene 2...")
    generate_image_dalle(
        prompt="Bold cartoon style, thick outlines, bright colors. A cartoon gamer who has given up completely, lying face down on the floor next to their chair, headset still on, cat sitting on the keyboard, screen showing DEFEAT.",
        output_path=f"{out}/p2.png", size="1024x1536",
    )

    print("Animating...")
    for name, motion in [
        ("p1", "Character struggles with tangled cord, knocks drink over"),
        ("p2", "Character lies motionless, cat paws at keyboard"),
    ]:
        c = f"{out}/{name}_hq.jpg"
        subprocess.run(["ffmpeg", "-y", "-i", f"{out}/{name}.png", "-q:v", "2", c], capture_output=True, timeout=10)
        with open(c, "rb") as f:
            b64 = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
        await generate_video_async(
            prompt=f"Cartoon animation style. {motion}",
            output_path=f"{out}/{name}.mp4", duration=5, aspect_ratio="9:16", image_url=b64,
        )
        print(f"  {name} animated")

    print("Assembling...")
    for name in ["p1", "p2"]:
        subprocess.run(["ffmpeg", "-y", "-i", f"{out}/{name}.mp4", "-map", "0:v:0", "-c:v", "copy", "-an", f"{out}/{name}_na.mp4"],
            capture_output=True, timeout=30)
        subprocess.run([
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", f"{out}/{name}_na.mp4", "-t", "4",
            "-vf", (
                "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
                "drawtext=text='when the enemy team is toxic':fontsize=34:fontcolor=white:borderw=3:bordercolor=black"
                ":x=(w-text_w)/2:y=160:font=Impact,"
                "drawtext=text='but you are not skilled enough':fontsize=34:fontcolor=white:borderw=3:bordercolor=black"
                ":x=(w-text_w)/2:y=205:font=Impact,"
                "drawtext=text='to beat them':fontsize=34:fontcolor=white:borderw=3:bordercolor=black"
                ":x=(w-text_w)/2:y=250:font=Impact"
            ),
            "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an",
            f"{out}/{name}_txt.mp4",
        ], capture_output=True, timeout=60)

    with open(f"{out}/concat.txt", "w") as f:
        f.write(f"file '{os.path.abspath(out)}/p1_txt.mp4'\nfile '{os.path.abspath(out)}/p2_txt.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{out}/concat.txt",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", f"{out}/concat.mp4"], capture_output=True, timeout=60)

    shutil.copy("assets/music/comical.mp3", f"{out}/music.mp3")
    dur = float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", f"{out}/concat.mp4"],
        capture_output=True, text=True).stdout.strip())
    subprocess.run(["ffmpeg", "-y", "-i", f"{out}/concat.mp4", "-i", f"{out}/music.mp3",
        "-map", "0:v", "-map", "1:a", "-t", str(dur),
        "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
        f"{out}/final.mp4"], capture_output=True, timeout=60)
    print(f"http://localhost:5173/{out}/final.mp4")

asyncio.run(main())
