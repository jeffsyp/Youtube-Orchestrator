"""Full end-to-end test pipeline with all latest improvements."""
import asyncio
import base64
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(line_buffering=True)

from packages.clients.elevenlabs import generate_speech
from packages.clients.grok import generate_image_dalle, generate_video_async, generate_image as grok_gen_image
from packages.clients.claude import generate
from apps.orchestrator.pipeline import _write_karaoke_ass


async def main():
    with open("/tmp/test_concept.json") as f:
        concept = json.load(f)

    out = "output/run_test"
    for d in ["narration", "images", "clips", "segments", "character_refs"]:
        os.makedirs(f"{out}/{d}", exist_ok=True)

    voice_id = "fIGaHjfrR8KmMy0vGEVJ"
    WIDTH, HEIGHT = 720, 1280

    # ========== STEP 1: NARRATION ==========
    print("=== STEP 1: Narration ===")
    line_audio = []
    for i, line in enumerate(concept["narration"]):
        path = f"{out}/narration/line_{i}.mp3"
        if not os.path.exists(path):
            generate_speech(text=line, voice=voice_id, output_path=path)
        dur = float(subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True).stdout.strip())
        line_audio.append({"index": i, "path": path, "duration": dur, "text": line})
        print(f"  {i}: {dur:.1f}s")
    total_dur = sum(a["duration"] for a in line_audio)
    print(f"  Total: {total_dur:.1f}s\n")

    # ========== STEP 2: VISUAL PLANNING ==========
    print("=== STEP 2: Visual Planning ===")
    narr_block = "\n".join(f'  Line {i}: "{a["text"]}"' for i, a in enumerate(line_audio))

    import re
    channel_name = concept.get("channel_name", "YouTube Shorts")
    niche = concept.get("niche", "general")
    visual_system = f"""You write image prompts for YouTube videos. Channel: "{channel_name}" ({niche}).

One prompt per narration line. Every prompt starts with "Bold cartoon style, thick outlines, bright colors."

Identify the main subject of the video from the narration. That subject should be in most images.

RULES:
- ONE scene per prompt. 1-2 sentences max.
- Comedy editor mindset — exaggerate, absurd scale, visual gags.
- Use character names. The image generator knows League champions.
- The image generator CANNOT draw: UIs, screens, menus, text, split panels
- DALL-E CANNOT understand: game jargon like "skins", "RP", "champion icons"

TYPES:
- "grok": animated video clip. DEFAULT — use for almost every line.
  "video_prompt": describe the motion/animation. The image is generated first then animated.
- "image": static still. ONLY for charts, numbers, graphs.

If a character appears in multiple lines, tag with "character": "name".
Aspect: 9:16 vertical portrait.
Return JSON: {{ "visuals": [...] }}"""

    resp = generate(prompt=f"{narr_block}\n\n{len(line_audio)} lines.", system=visual_system, model="claude-sonnet-4-6", max_tokens=3000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

    plan = json.loads(resp)
    visuals = plan["visuals"]
    with open(f"{out}/visual_plan.json", "w") as f:
        json.dump(plan, f, indent=2)

    grok_count = sum(1 for v in visuals if v["type"] == "grok")
    print(f"  {len(visuals)} visuals ({grok_count} video, {len(visuals) - grok_count} image)")
    for i, v in enumerate(visuals):
        print(f"  {i} [{v['type']}]: {v.get('prompt', '')[:80]}")
    print()

    # ========== STEP 3: CHARACTER REFERENCES ==========
    print("=== STEP 3: Character References ===")
    unique_chars = set(v.get("character") for v in visuals if v.get("character"))
    char_descriptions = {}

    for char_name in unique_chars:
        ref_path = f"{out}/character_refs/{char_name.replace(' ', '_')}.png"
        if not os.path.exists(ref_path):
            print(f"  Generating reference: {char_name}")
            try:
                generate_image_dalle(
                    prompt=f"Bold cartoon style, thick outlines, bright colors. Family-friendly full body portrait of {char_name}, facing the viewer, simple background.",
                    output_path=ref_path, size="1024x1536",
                )
            except Exception as e:
                print(f"  Reference failed for {char_name}: {str(e)[:80]}. Continuing without.")

        # Describe with Claude vision
        try:
            from anthropic import Anthropic
            client = Anthropic()
            with open(ref_path, "rb") as rf:
                ref_b64 = base64.b64encode(rf.read()).decode()
            desc_resp = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=150,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ref_b64}},
                    {"type": "text", "text": "Describe this character's visual appearance in ONE sentence — colors, outfit, key features."},
                ]}],
            )
            desc = desc_resp.content[0].text.strip()
            char_descriptions[char_name] = desc
            print(f"  {char_name}: {desc[:80]}")
        except Exception as e:
            char_descriptions[char_name] = char_name
            print(f"  {char_name}: description failed ({str(e)[:50]})")

    print(f"  View refs: http://localhost:5173/{out}/character_refs/")
    print()

    # ========== STEP 4: GENERATE IMAGES ==========
    print("=== STEP 4: Generate Images ===")
    for i, v in enumerate(visuals):
        img_path = f"{out}/images/line_{i}.png"
        if os.path.exists(img_path):
            print(f"  {i}: cached")
            continue

        prompt = v.get("prompt") or v.get("image_prompt") or f"Bold cartoon style, thick outlines, bright colors. Scene from League of Legends."
        char_name = v.get("character")
        if char_name and char_name in char_descriptions:
            prompt += f" The character {char_name} looks like: {char_descriptions[char_name]}"

        print(f"  {i}: generating...")
        try:
            generate_image_dalle(prompt=prompt, output_path=img_path, size="1024x1536")
        except Exception as e:
            print(f"  {i}: FAILED after all retries ({str(e)[:60]}). Skipping.")
    print(f"  View: http://localhost:5173/{out}/images/")
    print()

    # ========== STEP 5: GENERATE VIDEO CLIPS ==========
    print("=== STEP 5: Video Clips ===")
    for i, v in enumerate(visuals):
        if v["type"] != "grok":
            continue

        clip_path = f"{out}/clips/line_{i}.mp4"
        if os.path.exists(clip_path):
            print(f"  {i}: cached")
            continue

        # Compress image for Grok
        img_path = f"{out}/images/line_{i}.png"
        if not os.path.exists(img_path):
            print(f"  {i}: no image, skipping video clip")
            continue
        compressed = f"{out}/images/line_{i}_hq.jpg"
        if not os.path.exists(compressed):
            subprocess.run(["ffmpeg", "-y", "-i", img_path, "-q:v", "2", compressed], capture_output=True, timeout=10)

        with open(compressed, "rb") as rf:
            img_b64 = f"data:image/jpeg;base64,{base64.b64encode(rf.read()).decode()}"

        dur = min(int(line_audio[i]["duration"]) + 1, 10)
        motion = v.get("video_prompt", "subtle camera movement")

        print(f"  {i}: {dur}s — {motion[:60]}")
        await generate_video_async(
            prompt=f"Cartoon animation style. {motion}",
            output_path=clip_path, duration=dur,
            aspect_ratio="9:16", image_url=img_b64,
        )
    print()

    # ========== STEP 6: ASSEMBLE ==========
    print("=== STEP 6: Assemble ===")
    segment_paths = []
    for i, audio in enumerate(line_audio):
        seg_path = f"{out}/segments/seg_{i}.mp4"
        dur = audio["duration"]
        clip_path = f"{out}/clips/line_{i}.mp4"
        img_path = f"{out}/images/line_{i}.png"

        if os.path.exists(clip_path):
            # Video — strip audio, use narration, no loop
            clean = clip_path.replace(".mp4", "_clean.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", clip_path, "-map", "0:v:0", "-c:v", "copy", "-an", clean],
                capture_output=True, timeout=30)
            vid = clean if os.path.exists(clean) else clip_path
            subprocess.run([
                "ffmpeg", "-y", "-i", vid, "-i", audio["path"],
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-map", "0:v", "-map", "1:a", "-t", str(dur),
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                "-movflags", "+faststart", seg_path,
            ], capture_output=True, timeout=120)
        else:
            # Static image
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", img_path, "-i", audio["path"],
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", seg_path,
            ], capture_output=True, timeout=120)

        if os.path.exists(seg_path):
            segment_paths.append(seg_path)
            vtype = "video" if os.path.exists(clip_path) else "image"
            print(f"  seg {i}: {dur:.1f}s ({vtype})")

    # Concat
    concat_list = f"{out}/concat.txt"
    with open(concat_list, "w") as f:
        for seg in segment_paths:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    concat_path = f"{out}/raw_concat.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-ar", "44100", "-b:a", "192k", "-movflags", "+faststart",
        concat_path,
    ], capture_output=True, timeout=300)

    # Subtitles
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(concat_path, word_timestamps=True)
    words = [(w.word.strip(), w.start, w.end) for seg in segs if seg.words for w in seg.words]

    ass_path = f"{out}/subs.ass"
    _write_karaoke_ass(ass_path, words, is_long_form=False)

    final_path = f"{out}/final.mp4"
    result = subprocess.run([
        "ffmpeg", "-y", "-i", concat_path,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "14",
        "-c:a", "copy", "-movflags", "+faststart", final_path,
    ], capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        import shutil
        shutil.copy2(concat_path, final_path)

    dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", final_path],
        capture_output=True, text=True).stdout.strip()
    size = os.path.getsize(final_path) / 1024 / 1024
    print(f"\n=== DONE ===")
    print(f"Duration: {dur}s")
    print(f"Size: {size:.1f}MB")
    print(f"http://localhost:5173/{out}/final.mp4")


if __name__ == "__main__":
    asyncio.run(main())
