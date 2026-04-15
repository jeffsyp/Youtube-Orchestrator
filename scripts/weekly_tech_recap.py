#!/usr/bin/env python3
"""
Weekly Tech Recap — standalone test script.

1. Fetches this week's top tech news from Reddit + Hacker News
2. Claude curates and writes a recap script
3. Generates voice narration (ElevenLabs)
4. Generates visuals (Grok)
5. Renders the final video (FFmpeg)

Usage:
    uv run python scripts/weekly_tech_recap.py
    uv run python scripts/weekly_tech_recap.py --research-only   # Just fetch news, no video
    uv run python scripts/weekly_tech_recap.py --script-only     # Fetch + script, no render
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------- 1. NEWS RESEARCH ----------

def fetch_reddit_tech_news(limit: int = 30) -> list[dict]:
    """Fetch top tech posts from Reddit this week."""
    import praw

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID", ""),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
        user_agent="weekly-tech-recap/1.0",
    )

    subreddits = ["technology", "tech", "artificial", "MachineLearning", "programming"]
    posts = []

    for sub_name in subreddits:
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.top(time_filter="week", limit=limit):
                posts.append({
                    "title": post.title,
                    "score": post.score,
                    "url": post.url,
                    "subreddit": sub_name,
                    "num_comments": post.num_comments,
                    "created": datetime.fromtimestamp(post.created_utc).isoformat(),
                    "selftext": (post.selftext or "")[:500],
                })
        except Exception as e:
            print(f"  [!] Reddit r/{sub_name} error: {e}")

    # Sort by score descending
    posts.sort(key=lambda p: p["score"], reverse=True)
    return posts


def fetch_hackernews_top(limit: int = 30) -> list[dict]:
    """Fetch top Hacker News stories from this week."""
    import urllib.request
    import json as _json

    # Get top story IDs
    url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    with urllib.request.urlopen(url, timeout=10) as resp:
        story_ids = _json.loads(resp.read())[:limit * 2]  # fetch extra, filter by date

    stories = []
    cutoff = datetime.now() - timedelta(days=7)

    for sid in story_ids:
        if len(stories) >= limit:
            break
        try:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
            with urllib.request.urlopen(item_url, timeout=5) as resp:
                item = _json.loads(resp.read())

            if not item or item.get("type") != "story":
                continue

            created = datetime.fromtimestamp(item.get("time", 0))
            if created < cutoff:
                continue

            stories.append({
                "title": item.get("title", ""),
                "score": item.get("score", 0),
                "url": item.get("url", ""),
                "num_comments": item.get("descendants", 0),
                "created": created.isoformat(),
                "source": "hackernews",
            })
        except Exception:
            continue

    stories.sort(key=lambda s: s["score"], reverse=True)
    return stories


def research_tech_news() -> str:
    """Fetch and combine tech news from multiple sources."""
    print("Fetching tech news...")

    all_stories = []

    # Hacker News (no API key needed)
    print("  Fetching Hacker News...")
    hn_stories = fetch_hackernews_top(30)
    print(f"  Found {len(hn_stories)} HN stories")
    all_stories.extend(hn_stories)

    # Reddit (needs API keys)
    if os.getenv("REDDIT_CLIENT_ID"):
        print("  Fetching Reddit...")
        reddit_posts = fetch_reddit_tech_news(20)
        print(f"  Found {len(reddit_posts)} Reddit posts")
        all_stories.extend(reddit_posts)
    else:
        print("  [!] Skipping Reddit (no REDDIT_CLIENT_ID set)")

    # Deduplicate by similar titles
    seen_titles = set()
    unique = []
    for story in all_stories:
        title_key = story["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique.append(story)

    # Take top 30 by score
    unique.sort(key=lambda s: s["score"], reverse=True)
    top = unique[:30]

    # Format for Claude
    lines = [f"TOP TECH NEWS THIS WEEK ({datetime.now().strftime('%B %d, %Y')}):\n"]
    for i, s in enumerate(top, 1):
        source = s.get("source", s.get("subreddit", "unknown"))
        lines.append(f"{i}. [{source}] {s['title']} (score: {s['score']}, comments: {s.get('num_comments', 0)})")
        if s.get("selftext"):
            lines.append(f"   Context: {s['selftext'][:200]}")

    return "\n".join(lines)


# ---------- 2. SCRIPT GENERATION ----------

def generate_recap_script(news_block: str, duration_minutes: int = 5) -> dict:
    """Use Claude to curate stories and write a recap script."""
    from packages.clients.claude import generate

    system = f"""You are a scriptwriter for a weekly tech recap YouTube channel. You take this week's top tech news and write a {duration_minutes}-minute narrated recap video script.

YOUR GOAL: A tight, engaging recap of the 5-7 most important/interesting tech stories this week. The viewer should feel caught up on tech news after watching.

PROCESS:
1. From the news provided, pick the 5-7 most significant/interesting stories
2. Order them for flow — lead with the biggest story, end with something fun/memorable
3. Write narration for each story segment (30-60 seconds each)
4. Add transitions between stories

WRITING STYLE:
- Conversational and energetic, like a tech-savvy friend catching you up
- Each story gets: what happened, why it matters, one interesting detail
- No jargon without explanation
- Start with a cold open: "This week in tech — [biggest headline]"
- End with a quick sign-off teasing next week

NARRATION FORMAT:
- Each line = one visual on screen
- Keep lines short and punchy
- Mark story transitions clearly

OUTPUT — return a JSON object:
{{
  "title": "This Week in Tech — [Date Range]",
  "stories_covered": ["Story 1 headline", "Story 2 headline", ...],
  "narration": [
    "Cold open line — the biggest story hook",
    "Story 1 line 1",
    "Story 1 line 2",
    "Story 1 line 3",
    "Transition to story 2",
    "Story 2 line 1",
    ...
    "Sign-off line"
  ],
  "visual_notes": [
    "Visual suggestion for each narration line — what should be on screen"
  ],
  "caption": "YouTube description with key stories mentioned and hashtags",
  "tags": ["weekly recap", "tech news", "specific tags"]
}}

Return ONLY valid JSON, no markdown."""

    user = f"""Here are this week's top tech stories from Reddit and Hacker News. Pick the 5-7 most important/interesting and write a {duration_minutes}-minute recap script.

{news_block}

Write a compelling weekly tech recap. Make the viewer feel caught up on everything that matters."""

    print("Generating recap script with Claude...")
    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=8000)
    resp = resp.strip()
    if resp.startswith("```"):
        import re
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)

    script = json.loads(resp)
    return script


# ---------- 3. VOICE GENERATION ----------

def generate_voice(narration_lines: list[str], output_dir: str, voice_id: str = None) -> list[str]:
    """Generate voice narration for each line using ElevenLabs."""
    from packages.clients.elevenlabs import generate_speech

    voice_id = voice_id or "56bWURjYFHyYyVf490Dp"  # default voice
    audio_paths = []

    print(f"Generating voice narration ({len(narration_lines)} lines)...")
    for i, line in enumerate(narration_lines):
        output_path = os.path.join(output_dir, f"narration_{i:03d}.mp3")
        generate_speech(text=line, voice=voice_id, output_path=output_path)
        audio_paths.append(output_path)
        print(f"  [{i+1}/{len(narration_lines)}] {line[:60]}...")

    return audio_paths


# ---------- 4. VISUAL GENERATION ----------

def generate_visuals(visual_notes: list[str], output_dir: str) -> list[str]:
    """Generate an image for each visual note using Grok."""
    from packages.clients.grok import generate_image

    image_paths = []
    print(f"Generating visuals ({len(visual_notes)} images)...")

    for i, note in enumerate(visual_notes):
        output_path = os.path.join(output_dir, f"visual_{i:03d}.png")
        prompt = f"Tech news illustration: {note}. Clean modern digital art style, bold colors, suitable for a YouTube tech recap video. No text in the image."

        try:
            generate_image(prompt=prompt, output_path=output_path)
            image_paths.append(output_path)
            print(f"  [{i+1}/{len(visual_notes)}] Generated")
        except Exception as e:
            print(f"  [{i+1}/{len(visual_notes)}] Failed: {e}")
            image_paths.append(None)

    return image_paths


# ---------- 5. RENDERING ----------

def render_video(audio_paths: list[str], image_paths: list[str], output_path: str):
    """Stitch audio + images into a video using FFmpeg."""
    import subprocess

    print("Rendering video...")

    # Get duration of each audio clip
    segments = []
    for audio, image in zip(audio_paths, image_paths):
        if not audio or not os.path.exists(audio):
            continue
        if not image or not os.path.exists(image):
            continue

        # Get audio duration
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
        segments.append({"audio": audio, "image": image, "duration": duration})

    if not segments:
        print("  [!] No valid segments to render")
        return

    # Build FFmpeg filter complex
    inputs = []
    filter_parts = []
    concat_parts = []

    for i, seg in enumerate(segments):
        inputs.extend(["-loop", "1", "-t", str(seg["duration"]), "-i", seg["image"]])
        inputs.extend(["-i", seg["audio"]])

        v_idx = i * 2
        a_idx = i * 2 + 1
        # Scale image to 1920x1080
        filter_parts.append(f"[{v_idx}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
        concat_parts.append(f"[v{i}][{a_idx}:a]")

    filter_str = ";".join(filter_parts)
    concat_str = "".join(concat_parts)
    filter_str += f";{concat_str}concat=n={len(segments)}:v=1:a=1[outv][outa]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [!] FFmpeg error: {result.stderr[-500:]}")
    else:
        print(f"  Video saved: {output_path}")


# ---------- MAIN ----------

def main():
    parser = argparse.ArgumentParser(description="Weekly Tech Recap Generator")
    parser.add_argument("--research-only", action="store_true", help="Only fetch news, don't generate video")
    parser.add_argument("--script-only", action="store_true", help="Fetch news + write script, don't render")
    parser.add_argument("--duration", type=int, default=5, help="Target video duration in minutes (default: 5)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    # Setup output directory
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_dir = args.output_dir or os.path.join("output", "weekly_recap", date_str)
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Research
    news_block = research_tech_news()
    news_path = os.path.join(output_dir, "news_research.txt")
    with open(news_path, "w") as f:
        f.write(news_block)
    print(f"\nNews research saved to {news_path}")
    print(f"\n{news_block}\n")

    if args.research_only:
        print("Done (research only)")
        return

    # Step 2: Script
    script = generate_recap_script(news_block, duration_minutes=args.duration)
    script_path = os.path.join(output_dir, "script.json")
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2)
    print(f"\nScript saved to {script_path}")
    print(f"Title: {script.get('title', 'Untitled')}")
    print(f"Stories: {len(script.get('stories_covered', []))}")
    print(f"Narration lines: {len(script.get('narration', []))}")

    if args.script_only:
        print("\nDone (script only)")
        return

    # Step 3: Voice
    narration = script.get("narration", [])
    audio_paths = generate_voice(narration, output_dir)

    # Step 4: Visuals
    visual_notes = script.get("visual_notes", [])
    # Pad visual notes to match narration length if needed
    while len(visual_notes) < len(narration):
        visual_notes.append("Generic tech background with circuit board pattern")
    image_paths = generate_visuals(visual_notes[:len(narration)], output_dir)

    # Step 5: Render
    video_path = os.path.join(output_dir, f"weekly_tech_recap_{date_str}.mp4")
    render_video(audio_paths, image_paths, video_path)

    print(f"\n{'='*50}")
    print(f"Weekly Tech Recap complete!")
    print(f"Video: {video_path}")
    print(f"Script: {script_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
