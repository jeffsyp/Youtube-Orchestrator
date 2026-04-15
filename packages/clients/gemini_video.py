"""Analyze videos using Gemini's vision capabilities."""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent"


def analyze_video(video_path: str, question: str = "Describe what happens in this video in detail.") -> str:
    """Upload a video to Gemini and ask a question about it.

    Args:
        video_path: Path to the video file.
        question: What to ask about the video.

    Returns:
        Gemini's response text.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    file_size = os.path.getsize(video_path)

    # Step 1: Start resumable upload
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": "video/mp4",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        f"{UPLOAD_URL}?key={GEMINI_API_KEY}",
        headers=headers,
        json={"file": {"display_name": os.path.basename(video_path)}},
        timeout=30,
    )
    resp.raise_for_status()
    upload_url = resp.headers["X-Goog-Upload-URL"]

    # Step 2: Upload the video
    with open(video_path, "rb") as f:
        video_data = f.read()

    headers = {
        "Content-Length": str(file_size),
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize",
    }

    resp = requests.put(
        upload_url,
        headers=headers,
        data=video_data,
        timeout=300,
    )
    resp.raise_for_status()
    file_info = resp.json()
    file_uri = file_info["file"]["uri"]

    # Step 3: Wait for processing
    file_name = file_info["file"]["name"]
    for _ in range(30):
        check = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={GEMINI_API_KEY}",
            timeout=10,
        )
        state = check.json().get("state", "")
        if state == "ACTIVE":
            break
        time.sleep(2)

    # Step 4: Ask the question
    resp = requests.post(
        f"{GENERATE_URL}?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{
                "parts": [
                    {"file_data": {"mime_type": "video/mp4", "file_uri": file_uri}},
                    {"text": question},
                ],
            }],
        },
        timeout=60,
    )
    resp.raise_for_status()

    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]
