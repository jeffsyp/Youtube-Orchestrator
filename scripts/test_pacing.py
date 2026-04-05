"""Test pacing effects on the Infernape vs Hitmonchan video."""
import asyncio
import base64
import os
import subprocess
import sys

sys.stdout.reconfigure(line_buffering=True)

from packages.clients.grok import generate_image_dalle
from apps.orchestrator.deity_pipeline import _write_karaoke_ass

out = "output/run_test"
seg_dir = f"{out}/segments_fx"
narr_dir = f"{out}/narration"
img_dir = f"{out}/images"
clip_dir = f"{out}/clips"
WIDTH, HEIGHT = 720, 1280


def get_dur(path):
    return float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip())


def make_segment(vid_input, audio_path, seg_path, dur, loop=True):
    """Standard segment: video + narration audio."""
    loop_args = ["-stream_loop", "-1"] if loop else []
    subprocess.run([
        "ffmpeg", "-y", *loop_args, "-i", vid_input, "-i", audio_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-map", "0:v", "-map", "1:a", "-t", str(dur),
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
        "-movflags", "+faststart", seg_path,
    ], capture_output=True, timeout=120)


async def main():
    os.makedirs(seg_dir, exist_ok=True)
    for f in os.listdir(seg_dir):
        os.remove(f"{seg_dir}/{f}")

    segments = []

    # ========== LINE 0: NORMAL ==========
    print("Line 0: normal")
    dur = get_dur(f"{narr_dir}/line_0.mp3")
    clip = f"{clip_dir}/line_0.mp4"
    clean = clip.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip, "-map", "0:v:0", "-c:v", "copy", "-an", clean], capture_output=True, timeout=30)
    seg = f"{seg_dir}/seg_00.mp4"
    make_segment(clean if os.path.exists(clean) else clip, f"{narr_dir}/line_0.mp3", seg, dur)
    segments.append(seg)

    # ========== LINE 1: QUICK-CUT MONTAGE (3 punch images, 3s each) ==========
    print("Line 1: montage — generating 3 punch images...")
    dur1 = get_dur(f"{narr_dir}/line_1.mp3")
    punch_prompts = [
        "Bold cartoon style, thick outlines, bright colors. Hitmonchan throwing a fiery Fire Punch, fist engulfed in flames, dynamic action pose.",
        "Bold cartoon style, thick outlines, bright colors. Hitmonchan throwing an icy Ice Punch, fist covered in frost and ice crystals, dynamic action pose.",
        "Bold cartoon style, thick outlines, bright colors. Hitmonchan throwing a crackling Thunder Punch, fist surrounded by yellow lightning bolts, dynamic action pose.",
    ]
    punch_imgs = []
    for j, prompt in enumerate(punch_prompts):
        p = f"{img_dir}/montage_punch_{j}.png"
        if not os.path.exists(p):
            generate_image_dalle(prompt=prompt, output_path=p, size="1024x1536")
        punch_imgs.append(p)

    # Build montage: each image shows for dur1/3 seconds
    sub_dur = dur1 / len(punch_imgs)
    sub_segs = []
    for j, img in enumerate(punch_imgs):
        sub = f"{seg_dir}/montage_1_{j}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img,
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
            "-t", str(sub_dur), "-an", sub,
        ], capture_output=True, timeout=30)
        sub_segs.append(sub)

    # Concat montage subs + add narration
    montage_list = f"{seg_dir}/montage_1.txt"
    with open(montage_list, "w") as f:
        for s in sub_segs:
            f.write(f"file '{os.path.abspath(s)}'\n")
    montage_vid = f"{seg_dir}/montage_1_vid.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", montage_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", montage_vid], capture_output=True, timeout=30)

    seg = f"{seg_dir}/seg_01.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", montage_vid, "-i", f"{narr_dir}/line_1.mp3",
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", seg,
    ], capture_output=True, timeout=30)
    segments.append(seg)

    # ========== LINE 2: SLOW-MO (0.5x speed) ==========
    print("Line 2: slow-mo")
    dur2 = get_dur(f"{narr_dir}/line_2.mp3")
    clip2 = f"{clip_dir}/line_2.mp4"
    clean2 = clip2.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip2, "-map", "0:v:0", "-c:v", "copy", "-an", clean2], capture_output=True, timeout=30)
    slowmo = f"{seg_dir}/slowmo_2.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", clean2 if os.path.exists(clean2) else clip2,
        "-vf", f"setpts=2*PTS,scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-an", slowmo], capture_output=True, timeout=60)
    seg = f"{seg_dir}/seg_02.mp4"
    make_segment(slowmo, f"{narr_dir}/line_2.mp3", seg, dur2)
    segments.append(seg)

    # ========== LINE 3: QUICK CUTS (use existing clip but speed up) ==========
    print("Line 3: quick cuts")
    dur3 = get_dur(f"{narr_dir}/line_3.mp3")
    clip3 = f"{clip_dir}/line_3.mp4"
    clean3 = clip3.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip3, "-map", "0:v:0", "-c:v", "copy", "-an", clean3], capture_output=True, timeout=30)
    # Speed up video 1.5x for more energy
    fast = f"{seg_dir}/fast_3.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", clean3 if os.path.exists(clean3) else clip3,
        "-vf", f"setpts=0.67*PTS,scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-an", fast], capture_output=True, timeout=60)
    seg = f"{seg_dir}/seg_03.mp4"
    make_segment(fast, f"{narr_dir}/line_3.mp3", seg, dur3)
    segments.append(seg)

    # ========== LINE 4: SPEED RAMP (normal -> slow -> normal) ==========
    print("Line 4: speed ramp")
    dur4 = get_dur(f"{narr_dir}/line_4.mp3")
    clip4 = f"{clip_dir}/line_4.mp4"
    clean4 = clip4.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip4, "-map", "0:v:0", "-c:v", "copy", "-an", clean4], capture_output=True, timeout=30)
    vid4 = clean4 if os.path.exists(clean4) else clip4
    clip4_dur = get_dur(vid4)

    # Split: first half normal, second half slow-mo
    half = clip4_dur / 2
    part1 = f"{seg_dir}/ramp_4a.mp4"
    part2 = f"{seg_dir}/ramp_4b.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", vid4, "-t", str(half),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", part1],
        capture_output=True, timeout=30)
    subprocess.run(["ffmpeg", "-y", "-ss", str(half), "-i", vid4,
        "-vf", f"setpts=2*PTS,scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", part2],
        capture_output=True, timeout=30)

    ramp_list = f"{seg_dir}/ramp_4.txt"
    with open(ramp_list, "w") as f:
        f.write(f"file '{os.path.abspath(part1)}'\n")
        f.write(f"file '{os.path.abspath(part2)}'\n")
    ramp_vid = f"{seg_dir}/ramp_4_vid.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", ramp_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", ramp_vid], capture_output=True, timeout=30)
    seg = f"{seg_dir}/seg_04.mp4"
    make_segment(ramp_vid, f"{narr_dir}/line_4.mp3", seg, dur4)
    segments.append(seg)

    # ========== LINE 5: FREEZE + ZOOM PUNCH ==========
    print("Line 5: freeze + zoom punch")
    dur5 = get_dur(f"{narr_dir}/line_5.mp3")
    clip5 = f"{clip_dir}/line_5.mp4"
    clean5 = clip5.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip5, "-map", "0:v:0", "-c:v", "copy", "-an", clean5], capture_output=True, timeout=30)
    vid5 = clean5 if os.path.exists(clean5) else clip5

    # Extract frame at 1s, create freeze + zoom punch
    freeze_frame = f"{seg_dir}/freeze_5.png"
    subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", vid5, "-frames:v", "1", "-q:v", "2", freeze_frame],
        capture_output=True, timeout=10)

    # Part 1: normal clip for 1s
    p5a = f"{seg_dir}/freeze_5a.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", vid5, "-t", "1",
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", p5a],
        capture_output=True, timeout=30)

    # Part 2: freeze frame held for 0.5s
    p5b = f"{seg_dir}/freeze_5b.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", freeze_frame, "-t", "0.5",
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", p5b],
        capture_output=True, timeout=30)

    # Part 3: zoom punch on freeze frame (0.5s, zoom 1x -> 1.5x)
    p5c = f"{seg_dir}/freeze_5c.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", freeze_frame, "-t", "0.5",
        "-vf", f"scale=1200:-1,zoompan=z='min(zoom+0.035,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=15:s={WIDTH}x{HEIGHT}:fps=30",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", p5c],
        capture_output=True, timeout=30)

    # Part 4: rest of clip
    p5d = f"{seg_dir}/freeze_5d.mp4"
    subprocess.run(["ffmpeg", "-y", "-ss", "1", "-i", vid5,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", p5d],
        capture_output=True, timeout=30)

    freeze_list = f"{seg_dir}/freeze_5.txt"
    with open(freeze_list, "w") as f:
        for p in [p5a, p5b, p5c, p5d]:
            if os.path.exists(p):
                f.write(f"file '{os.path.abspath(p)}'\n")
    freeze_vid = f"{seg_dir}/freeze_5_vid.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", freeze_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14", freeze_vid], capture_output=True, timeout=30)
    seg = f"{seg_dir}/seg_05.mp4"
    make_segment(freeze_vid, f"{narr_dir}/line_5.mp3", seg, dur5)
    segments.append(seg)

    # ========== LINE 6: NORMAL ==========
    print("Line 6: normal")
    dur6 = get_dur(f"{narr_dir}/line_6.mp3")
    clip6 = f"{clip_dir}/line_6.mp4"
    clean6 = clip6.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip6, "-map", "0:v:0", "-c:v", "copy", "-an", clean6], capture_output=True, timeout=30)
    seg = f"{seg_dir}/seg_06.mp4"
    make_segment(clean6 if os.path.exists(clean6) else clip6, f"{narr_dir}/line_6.mp3", seg, dur6)
    segments.append(seg)

    # ========== LINE 7: SLOW-MO ENDING ==========
    print("Line 7: slow-mo ending")
    dur7 = get_dur(f"{narr_dir}/line_7.mp3")
    clip7 = f"{clip_dir}/line_7.mp4"
    clean7 = clip7.replace(".mp4", "_fx_clean.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", clip7, "-map", "0:v:0", "-c:v", "copy", "-an", clean7], capture_output=True, timeout=30)
    slowmo7 = f"{seg_dir}/slowmo_7.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", clean7 if os.path.exists(clean7) else clip7,
        "-vf", f"setpts=2*PTS,scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-an", slowmo7], capture_output=True, timeout=60)
    seg = f"{seg_dir}/seg_07.mp4"
    make_segment(slowmo7, f"{narr_dir}/line_7.mp3", seg, dur7)
    segments.append(seg)

    # ========== ASSEMBLE ==========
    print("\nAssembling...")
    concat_list = f"{seg_dir}/concat.txt"
    valid_segs = [s for s in segments if os.path.exists(s)]
    with open(concat_list, "w") as f:
        for s in valid_segs:
            f.write(f"file '{os.path.abspath(s)}'\n")

    concat_path = f"{out}/fx_concat.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
        concat_path,
    ], capture_output=True, timeout=300)

    # Add music + SFX
    print("Adding music...")
    bg = "assets/music/epic.mp3"
    sfx = "assets/sfx/el_page_turn.mp3"
    video_dur = get_dur(concat_path)

    boundaries = []
    cumulative = 0.0
    for i in range(7):
        cumulative += get_dur(f"{narr_dir}/line_{i}.mp3")
        boundaries.append(cumulative)

    sfx_inputs = " ".join(f"-i {sfx}" for _ in boundaries)
    delays = ";".join(f"[{k+1}]adelay={int(t*1000)}|{int(t*1000)},volume=1.5[s{k}]" for k, t in enumerate(boundaries))
    sfx_labels = "".join(f"[s{k}]" for k in range(len(boundaries)))
    bg_idx = len(boundaries) + 1
    filt = f'{delays};[{bg_idx}]volume=0.12,atrim=0:{video_dur}[bgm];[0:a]{sfx_labels}[bgm]amix=inputs={len(boundaries)+2}:duration=first:weights={" ".join(["5"] + ["1"]*len(boundaries) + ["1"])},loudnorm=I=-16:TP=-1.5:LRA=11[out]'
    cmd = f'ffmpeg -y -i {concat_path} {sfx_inputs} -i {bg} -filter_complex "{filt}" -map 0:v -map "[out]" -c:v copy -c:a aac -ar 44100 -b:a 192k -movflags +faststart {out}/fx_with_music.mp4'
    subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)

    # Subtitles
    print("Adding subtitles...")
    from faster_whisper import WhisperModel
    src = f"{out}/fx_with_music.mp4" if os.path.exists(f"{out}/fx_with_music.mp4") else concat_path
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs_w, _ = model.transcribe(src, word_timestamps=True)
    words = [(w.word.strip(), w.start, w.end) for seg in segs_w if seg.words for w in seg.words]
    ass_path = f"{out}/fx_subs.ass"
    _write_karaoke_ass(ass_path, words, is_long_form=False)

    final = f"{out}/final_fx.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", src,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-c:a", "copy", "-movflags", "+faststart", final,
    ], capture_output=True, text=True, timeout=300)

    d = get_dur(final)
    size = os.path.getsize(final) / 1024 / 1024
    print(f"\n=== DONE ===")
    print(f"Duration: {d:.1f}s, Size: {size:.1f}MB")
    print(f"http://localhost:5173/{final}")


if __name__ == "__main__":
    asyncio.run(main())
