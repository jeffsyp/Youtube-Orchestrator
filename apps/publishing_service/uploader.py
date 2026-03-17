"""YouTube video uploader using OAuth2.

Uploads rendered videos to YouTube with title, description, tags, and captions.

Setup required:
1. Create OAuth2 credentials in Google Cloud Console (Desktop App type)
2. Download client_secrets.json to project root
3. Run `python -m apps.publishing_service.auth` to complete OAuth flow
4. Token is saved to youtube_token.json automatically
"""

import json
import os

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")


def is_upload_configured(youtube_token_file: str | None = None) -> bool:
    """Check if OAuth2 credentials are set up for YouTube upload.

    Args:
        youtube_token_file: Optional override for the token file path.
            If None, uses the default YOUTUBE_TOKEN_FILE.
    """
    token_file = youtube_token_file or YOUTUBE_TOKEN_FILE
    return os.path.exists(YOUTUBE_CLIENT_SECRETS) and os.path.exists(token_file)


def _get_youtube_client(youtube_token_file: str | None = None):
    """Build an authenticated YouTube API client.

    Args:
        youtube_token_file: Optional override for the token file path.
            Allows per-channel tokens for multi-channel setups.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_file = youtube_token_file or YOUTUBE_TOKEN_FILE

    with open(token_file) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
    )

    # Refresh token if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token
        token_data["token"] = creds.token
        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=2)

    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    category: str = "Science & Technology",
    privacy_status: str = "private",
    captions_path: str | None = None,
    thumbnail_path: str | None = None,
    youtube_token_file: str | None = None,
    made_for_kids: bool = False,
) -> dict:
    """Upload a video file to YouTube.

    Args:
        video_path: Path to the MP4 file.
        title: Video title.
        description: Video description.
        tags: List of tags.
        category: YouTube category name.
        privacy_status: "private", "unlisted", or "public".
        captions_path: Optional path to SRT file for captions.
        thumbnail_path: Optional path to thumbnail image.
        youtube_token_file: Optional token file override for multi-channel setups.
        made_for_kids: Whether the video is made for kids (COPPA).

    Returns:
        Dict with published status, video_id, and url.
    """
    log = logger.bind(title=title, privacy=privacy_status, video_path=video_path)

    if not is_upload_configured(youtube_token_file=youtube_token_file):
        log.error("youtube upload not configured")
        return {
            "published": False,
            "error": "YouTube OAuth2 not configured. Run: python -m apps.publishing_service.auth",
        }

    if not os.path.exists(video_path):
        log.error("video file not found", path=video_path)
        return {"published": False, "error": f"Video file not found: {video_path}"}

    from googleapiclient.http import MediaFileUpload

    youtube = _get_youtube_client(youtube_token_file=youtube_token_file)

    # Map category names to IDs
    category_map = {
        "Science & Technology": "28",
        "Education": "27",
        "Entertainment": "24",
        "People & Blogs": "22",
        "News & Politics": "25",
        "Howto & Style": "26",
        "Pets & Animals": "15",
        "Sports": "17",
    }
    category_id = category_map.get(category, "28")

    body = {
        "snippet": {
            "title": title[:100],  # YouTube max 100 chars
            "description": description,
            "tags": tags[:30],  # YouTube max 30 tags
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    log.info("uploading video to youtube")

    media = MediaFileUpload(video_path, chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # Execute with resumable upload
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info("upload progress", percent=int(status.progress() * 100))

    video_id = response["id"]
    log.info("video uploaded", video_id=video_id)

    # Upload thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            _upload_thumbnail(youtube, video_id, thumbnail_path)
            log.info("thumbnail uploaded", video_id=video_id)
        except Exception as e:
            log.warning("thumbnail upload failed", error=str(e))

    # Upload captions if provided
    if captions_path and os.path.exists(captions_path):
        try:
            _upload_captions(youtube, video_id, captions_path)
            log.info("captions uploaded", video_id=video_id)
        except Exception as e:
            log.warning("caption upload failed", error=str(e))

    result = {
        "published": True,
        "video_id": video_id,
        "url": f"https://youtube.com/watch?v={video_id}",
        "privacy": privacy_status,
    }

    log.info("publish complete", **result)
    return result


def _upload_thumbnail(youtube, video_id: str, thumbnail_path: str):
    """Upload a custom thumbnail to a YouTube video."""
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(thumbnail_path, mimetype="image/png")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()


def _upload_captions(youtube, video_id: str, srt_path: str):
    """Upload SRT captions to a YouTube video."""
    from googleapiclient.http import MediaFileUpload

    caption_body = {
        "snippet": {
            "videoId": video_id,
            "language": "en",
            "name": "English",
        },
    }

    media = MediaFileUpload(srt_path, mimetype="application/x-subrip")
    youtube.captions().insert(
        part="snippet",
        body=caption_body,
        media_body=media,
    ).execute()
