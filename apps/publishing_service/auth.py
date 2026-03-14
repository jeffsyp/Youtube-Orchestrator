"""OAuth2 authentication flow for YouTube uploads.

Run this script once to authorize the app and generate a token file:
    python -m apps.publishing_service.auth

Requires client_secrets.json from Google Cloud Console.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def run_auth_flow():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Error: {CLIENT_SECRETS_FILE} not found.")
        print("Download OAuth2 credentials from Google Cloud Console:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop App)")
        print("  3. Download the JSON and save as client_secrets.json")
        return

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=8090)

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": SCOPES,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Token saved to {TOKEN_FILE}")
    print("YouTube upload is now configured.")


if __name__ == "__main__":
    run_auth_flow()
