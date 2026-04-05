"""Soft body obstacle course simulation — satisfying physics video.

Balls drop through an obstacle course. Each round they get softer.
Round 1: rigid bouncy balls
Round 2: soft jelly balls
Round 3: super soft, almost liquid

Renders to video frames, assembles with ffmpeg.
"""

import math
import os
import struct
import subprocess
import sys

sys.stdout.reconfigure(line_buffering=True)

from PIL import Image, ImageDraw, ImageFont
import pymunk

# ========== CONFIG ==========
WIDTH, HEIGHT = 720, 1280
FPS = 30
DURATION_PER_ROUND = 4  # seconds per softness level
ROUNDS = 3
TOTAL_FRAMES = FPS * DURATION_PER_ROUND * ROUNDS
OUT_DIR = "output/run_test/satisfying/softbody"
os.makedirs(OUT_DIR, exist_ok=True)

# Colors (R, G, B) 0-1
COLORS = [
    (1.0, 0.3, 0.3),   # red
    (0.3, 0.8, 1.0),   # cyan
    (1.0, 0.8, 0.2),   # yellow
    (0.5, 1.0, 0.4),   # green
    (1.0, 0.5, 0.8),   # pink
    (0.6, 0.4, 1.0),   # purple
]

BG_COLOR = (0.12, 0.12, 0.15)  # dark background


def create_obstacles(space):
    """Create the obstacle course — pegs, ramps, funnels."""
    obstacles = []

    # Walls
    walls = [
        ((0, 0), (0, HEIGHT)),       # left
        ((WIDTH, 0), (WIDTH, HEIGHT)), # right
        ((0, HEIGHT), (WIDTH, HEIGHT)), # bottom
    ]
    for a, b in walls:
        seg = pymunk.Segment(space.static_body, a, b, 5)
        seg.elasticity = 0.5
        seg.friction = 0.5
        space.add(seg)

    # Pegs grid (rows of circular obstacles)
    peg_rows = [
        (300, [(120, 280), (240, 280), (360, 280), (480, 280), (600, 280)]),
        (400, [(60, 400), (180, 400), (300, 400), (420, 400), (540, 400), (660, 400)]),
        (520, [(120, 520), (240, 520), (360, 520), (480, 520), (600, 520)]),
        (640, [(60, 640), (180, 640), (300, 640), (420, 640), (540, 640), (660, 640)]),
    ]

    for _, pegs in peg_rows:
        for x, y in pegs:
            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            body.position = (x, y)
            shape = pymunk.Circle(body, 18)
            shape.elasticity = 0.6
            shape.friction = 0.3
            space.add(body, shape)
            obstacles.append((x, y, 18))

    # Ramps
    ramps = [
        ((100, 780), (350, 830)),
        ((620, 780), (370, 830)),
        ((50, 950), (300, 1000)),
        ((670, 950), (420, 1000)),
    ]
    for a, b in ramps:
        seg = pymunk.Segment(space.static_body, a, b, 6)
        seg.elasticity = 0.4
        seg.friction = 0.3
        space.add(seg)
        obstacles.append(("ramp", a, b))

    # Funnel at bottom
    funnel_l = pymunk.Segment(space.static_body, (150, 1100), (300, 1180), 6)
    funnel_r = pymunk.Segment(space.static_body, (570, 1100), (420, 1180), 6)
    funnel_l.elasticity = 0.3
    funnel_r.elasticity = 0.3
    space.add(funnel_l, funnel_r)
    obstacles.append(("ramp", (150, 1100), (300, 1180)))
    obstacles.append(("ramp", (570, 1100), (420, 1180)))

    return obstacles


def create_soft_ball(space, x, y, radius, softness, color_idx):
    """Create a ball with variable softness.

    softness 0 = rigid, 1 = very soft (uses multiple connected circles)
    """
    if softness < 0.3:
        # Rigid ball — single circle
        mass = 1.0
        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)
        body.position = (x, y)
        shape = pymunk.Circle(body, radius)
        shape.elasticity = 0.8
        shape.friction = 0.3
        space.add(body, shape)
        return [{"body": body, "shape": shape, "radius": radius, "color": COLORS[color_idx % len(COLORS)]}]

    else:
        # Soft ball — cluster of smaller circles connected by springs
        n_parts = 6 if softness < 0.7 else 10
        small_r = radius * 0.5
        parts = []
        bodies = []

        # Center body
        mass = 0.3
        moment = pymunk.moment_for_circle(mass, 0, small_r)
        center = pymunk.Body(mass, moment)
        center.position = (x, y)
        shape = pymunk.Circle(center, small_r)
        shape.elasticity = 0.3 if softness < 0.7 else 0.1
        shape.friction = 0.5
        space.add(center, shape)
        parts.append({"body": center, "shape": shape, "radius": small_r, "color": COLORS[color_idx % len(COLORS)]})
        bodies.append(center)

        # Surrounding bodies
        for i in range(n_parts):
            angle = (2 * math.pi * i) / n_parts
            px = x + math.cos(angle) * radius * 0.5
            py = y + math.sin(angle) * radius * 0.5

            body = pymunk.Body(mass * 0.5, pymunk.moment_for_circle(mass * 0.5, 0, small_r * 0.8))
            body.position = (px, py)
            shape = pymunk.Circle(body, small_r * 0.8)
            shape.elasticity = 0.2 if softness < 0.7 else 0.05
            shape.friction = 0.5
            space.add(body, shape)
            parts.append({"body": body, "shape": shape, "radius": small_r * 0.8, "color": COLORS[color_idx % len(COLORS)]})
            bodies.append(body)

            # Spring to center
            stiffness = 500 if softness < 0.7 else 100
            damping = 30 if softness < 0.7 else 10
            spring = pymunk.DampedSpring(center, body, (0, 0), (0, 0), radius * 0.5, stiffness, damping)
            space.add(spring)

        # Springs between neighbors
        for i in range(len(bodies) - 1):
            for j in range(i + 1, len(bodies)):
                dist = bodies[i].position.get_distance(bodies[j].position)
                if dist < radius * 1.2:
                    stiffness = 300 if softness < 0.7 else 50
                    spring = pymunk.DampedSpring(bodies[i], bodies[j], (0, 0), (0, 0), dist, stiffness, 20)
                    space.add(spring)

        return parts


def render_frame(img, draw, obstacles, all_ball_parts, round_num):
    """Render one frame using PIL."""
    # Clear background
    bg = tuple(int(c * 255) for c in BG_COLOR)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=bg)

    # Draw obstacles
    obs_color = (77, 77, 89)
    for obs in obstacles:
        if isinstance(obs[0], str) and obs[0] == "ramp":
            draw.line([obs[1], obs[2]], fill=obs_color, width=12)
        else:
            x, y, r = obs
            draw.ellipse((x - r, y - r, x + r, y + r), fill=obs_color)

    # Draw round label
    labels = ["RIGID", "JELLY", "LIQUID"]
    text = labels[min(round_num, len(labels) - 1)]
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) / 2, 40), text, fill=(255, 255, 255), font=font)

    # Draw balls
    for part in all_ball_parts:
        body = part["body"]
        r = part["radius"]
        color = tuple(int(c * 255) for c in part["color"])
        x, y = int(body.position.x), int(body.position.y)

        if 0 < x < WIDTH and 0 < y < HEIGHT:
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
            # Highlight
            hr = int(r * 0.4)
            hx, hy = x - int(r * 0.3), y - int(r * 0.3)
            draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(255, 255, 255, 80))


def main():
    print("=== Soft Body Obstacle Course ===")

    frame_dir = f"{OUT_DIR}/frames"
    os.makedirs(frame_dir, exist_ok=True)

    # Clean old frames
    for f in os.listdir(frame_dir):
        os.remove(f"{frame_dir}/{f}")

    frame_num = 0

    for round_num in range(ROUNDS):
        softness = [0.0, 0.5, 0.9][round_num]
        print(f"\nRound {round_num + 1}: softness={softness}")

        space = pymunk.Space()
        space.gravity = (0, 600)

        obstacles = create_obstacles(space)

        all_parts = []
        for i in range(8):
            x = 150 + (i % 4) * 140 + (round_num * 30)
            y = 50 + (i // 4) * 60
            radius = 22
            parts = create_soft_ball(space, x, y, radius, softness, i)
            all_parts.extend(parts)

        frames_this_round = FPS * DURATION_PER_ROUND
        for f in range(frames_this_round):
            for _ in range(3):
                space.step(1.0 / (FPS * 3))

            img = Image.new("RGB", (WIDTH, HEIGHT))
            draw = ImageDraw.Draw(img)
            render_frame(img, draw, obstacles, all_parts, round_num)

            frame_path = f"{frame_dir}/frame_{frame_num:04d}.png"
            img.save(frame_path)
            frame_num += 1

            if f % 30 == 0:
                print(f"  Frame {frame_num}/{TOTAL_FRAMES}")

    print(f"\n{frame_num} frames rendered")

    # Assemble video
    print("Assembling video...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", f"{frame_dir}/frame_%04d.png",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        f"{OUT_DIR}/softbody_nosound.mp4",
    ], capture_output=True, timeout=120)

    # Add satisfying sound
    print("Adding sound...")
    import requests
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    resp = requests.post("https://api.elevenlabs.io/v1/sound-generation",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": "bouncing balls on pegs, satisfying clicking and bouncing sounds, ASMR", "duration_seconds": 10.0},
        timeout=60,
    )
    if resp.status_code == 200:
        with open(f"{OUT_DIR}/bounce_sfx.mp3", "wb") as f:
            f.write(resp.content)

        dur = DURATION_PER_ROUND * ROUNDS
        subprocess.run([
            "ffmpeg", "-y",
            "-i", f"{OUT_DIR}/softbody_nosound.mp4",
            "-stream_loop", "-1", "-i", f"{OUT_DIR}/bounce_sfx.mp3",
            "-map", "0:v", "-map", "1:a",
            "-t", str(dur),
            "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
            "-movflags", "+faststart",
            f"{OUT_DIR}/final.mp4",
        ], capture_output=True, timeout=60)
    else:
        os.rename(f"{OUT_DIR}/softbody_nosound.mp4", f"{OUT_DIR}/final.mp4")

    d = float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", f"{OUT_DIR}/final.mp4"],
        capture_output=True, text=True).stdout.strip())
    size = os.path.getsize(f"{OUT_DIR}/final.mp4") / 1024 / 1024
    print(f"\n=== DONE ===")
    print(f"Duration: {d:.1f}s, Size: {size:.1f}MB")
    print(f"http://localhost:5173/{OUT_DIR}/final.mp4")


if __name__ == "__main__":
    main()
