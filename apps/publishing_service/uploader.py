"""YouTube video uploader using OAuth2.

Phase 5: Uploads videos to YouTube using the YouTube Data API v3.

Setup required:
1. Create OAuth2 credentials in Google Cloud Console (Desktop App type)
2. Download client_secrets.json to project root
3. Run `python -m apps.publishing_service.auth` to complete OAuth flow and generate token
4. Set YOUTUBE_CLIENT_SECRETS_FILE and YOUTUBE_TOKEN_FILE in .env
"""

import os

import structlog
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")


def is_upload_configured() -> bool:
    """Check if OAuth2 credentials are set up for YouTube upload."""
    return os.path.exists(YOUTUBE_CLIENT_SECRETS) and os.path.exists(YOUTUBE_TOKEN_FILE)


def upload_video(
    title: str,
    description: str,
    tags: list[str],
    category: str = "22",  # "People & Blogs" default; "28" = Science & Technology
    privacy_status: str = "private",
) -> dict:
    """Upload a video to YouTube.

    Returns dict with video_id and url on success.

    NOTE: This is the upload metadata step. The actual video file upload
    requires a rendered video file, which is outside the scope of this
    orchestrator (it produces the package, not the final video).
    """
    if not is_upload_configured():
        logger.warning("youtube upload not configured — missing OAuth2 credentials")
        return {
            "published": False,
            "status": "oauth2_not_configured",
            "message": (
                "YouTube OAuth2 not configured. To set up:\n"
                "1. Create OAuth2 Desktop App credentials in Google Cloud Console\n"
                "2. Download client_secrets.json\n"
                "3. Run: python -m apps.publishing_service.auth\n"
                "4. Set YOUTUBE_CLIENT_SECRETS_FILE and YOUTUBE_TOKEN_FILE in .env"
            ),
        }

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    import json

    with open(YOUTUBE_TOKEN_FILE) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
    )

    youtube = build("youtube", "v3", credentials=creds)

    # Map category names to IDs
    category_map = {
        "Science & Technology": "28",
        "Education": "27",
        "Entertainment": "24",
        "People & Blogs": "22",
        "News & Politics": "25",
        "Howto & Style": "26",
    }
    category_id = category_map.get(category, category)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    log = logger.bind(title=title, privacy=privacy_status)
    log.info("video metadata prepared for upload", tags=tags[:3])

    # NOTE: Actual file upload requires MediaFileUpload with a video file.
    # This orchestrator produces the content package, not the rendered video.
    # When a video file is available, the upload would be:
    #
    # from googleapiclient.http import MediaFileUpload
    # media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)
    # request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    # response = request.execute()

    return {
        "published": False,
        "status": "metadata_ready",
        "upload_body": body,
        "message": "Upload metadata prepared. Video file rendering required before upload.",
    }
