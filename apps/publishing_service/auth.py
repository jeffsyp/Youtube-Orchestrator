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
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def run_auth_flow(token_file: str | None = None, port: int = 8090):
    global TOKEN_FILE
    if token_file:
        TOKEN_FILE = token_file
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Error: {CLIENT_SECRETS_FILE} not found.")
        print("Download OAuth2 credentials from Google Cloud Console:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop App)")
        print("  3. Download the JSON and save as client_secrets.json")
        return

    from google_auth_oauthlib.flow import InstalledAppFlow

    print(f"\nSign in and select the YouTube channel you want to authorize.")
    print(f"Token will be saved to: {TOKEN_FILE}\n")

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=port)

    # Verify which channel this token is for
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=credentials)
    response = youtube.channels().list(part="snippet", mine=True).execute()
    channels = response.get("items", [])
    if channels:
        ch = channels[0]
        print(f"\nAuthenticated channel: {ch['snippet']['title']} ({ch['id']})")
    else:
        print("\nWarning: Could not determine channel name")

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": SCOPES,
    }
    if channels:
        token_data["channel_id"] = channels[0]["id"]
        token_data["channel_name"] = channels[0]["snippet"]["title"]

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Token saved to {TOKEN_FILE}")
    print("YouTube upload is now configured.")


def auth_all_channels(port: int = 8090):
    """Auth once, then list all channels and save a token for each."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"Error: {CLIENT_SECRETS_FILE} not found.")
        return

    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    print("Sign in with your Google account (the one that owns all channels)...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=port)

    # List all channels on this account
    youtube = build("youtube", "v3", credentials=credentials)

    # First get channels owned by this account
    response = youtube.channels().list(part="snippet", mine=True).execute()
    channels = response.get("items", [])

    # Also check for brand accounts / managed channels
    try:
        response2 = youtube.channels().list(part="snippet", managedByMe=True, maxResults=50).execute()
        managed = response2.get("items", [])
        # Add any channels not already in the list
        existing_ids = {c["id"] for c in channels}
        for ch in managed:
            if ch["id"] not in existing_ids:
                channels.append(ch)
    except Exception:
        pass

    if not channels:
        print("No channels found on this account.")
        return

    print(f"\nFound {len(channels)} channel(s):\n")

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": SCOPES,
    }

    for ch in channels:
        name = ch["snippet"]["title"]
        channel_id = ch["id"]
        safe_name = name.lower().replace(" ", "_").replace("'", "")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        token_file = f"youtube_token_{safe_name}.json"

        # Save token with channel_id embedded
        ch_token = {**token_data, "channel_id": channel_id, "channel_name": name}
        with open(token_file, "w") as f:
            json.dump(ch_token, f, indent=2)

        print(f"  {name} ({channel_id}) → {token_file}")

    print(f"\nSaved {len(channels)} token files.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", default=None, help="Output token file path")
    parser.add_argument("--port", type=int, default=8090, help="Local server port")
    parser.add_argument("--all", action="store_true", help="Auth once and save tokens for ALL channels on the account")
    args = parser.parse_args()

    if args.all:
        auth_all_channels(port=args.port)
    else:
        run_auth_flow(token_file=args.token_file, port=args.port)
