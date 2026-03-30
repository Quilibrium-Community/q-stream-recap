"""
YouTube API client for video uploads.
Handles OAuth 2.0 authentication and resumable uploads.
"""

import os
import json
import time
import random
import logging
from pathlib import Path
from typing import Callable

from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)

# YouTube API scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# Retry settings for uploads
MAX_UPLOAD_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
RETRIABLE_EXCEPTIONS = (IOError, OSError, HttpError)


class YouTubeClient:
    """YouTube API client with OAuth and resumable upload support."""

    def __init__(
        self,
        secrets_path: str,
        token_path: str = None,
    ):
        """
        Initialize YouTube client.

        Args:
            secrets_path: Path to YouTube OAuth secrets JSON file
            token_path: Path to store/load cached credentials
        """
        self.secrets_path = secrets_path
        self.token_path = token_path or str(
            Path(secrets_path).parent / ".youtube_token.json"
        )
        self._service = None

    def authenticate(self) -> None:
        """
        Authenticate with YouTube API using OAuth 2.0.

        On first run, opens a browser for consent and saves a token.
        All subsequent runs reuse/refresh the token automatically.
        If the saved token is irrecoverably invalid, re-authenticates from scratch.
        """
        creds = self._load_cached_credentials()

        if creds and creds.valid:
            logger.info("Using cached credentials (still valid)")
        elif creds and creds.expired and creds.refresh_token:
            creds = self._refresh_credentials(creds)
        else:
            creds = self._authenticate_fresh()

        self._save_credentials(creds)
        self._service = build("youtube", "v3", credentials=creds)

    def _load_cached_credentials(self) -> Credentials | None:
        """Load cached OAuth token from disk."""
        if not os.path.exists(self.token_path):
            return None
        try:
            with open(self.token_path, "r") as f:
                creds_data = json.load(f)
            return Credentials.from_authorized_user_info(creds_data, SCOPES)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Corrupt token file, will re-authenticate: {e}")
            return None

    def _refresh_credentials(self, creds: Credentials) -> Credentials:
        """Refresh expired credentials. Falls back to fresh auth on failure."""
        try:
            creds.refresh(Request())
            logger.info("Token refreshed successfully")
            return creds
        except RefreshError as e:
            logger.warning(f"Token refresh failed ({e}), re-authenticating...")
            # Delete the stale token so we don't keep trying to refresh it
            if os.path.exists(self.token_path):
                os.remove(self.token_path)
            return self._authenticate_fresh()

    def _authenticate_fresh(self) -> Credentials:
        """Run full OAuth flow (opens browser for consent)."""
        if not os.path.exists(self.secrets_path):
            raise FileNotFoundError(
                f"YouTube secrets file not found: {self.secrets_path}\n"
                "Download it from Google Cloud Console and save to config/"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            self.secrets_path,
            SCOPES,
            redirect_uri="http://localhost",
        )
        # Use a fixed port so firewall rules are predictable
        creds = flow.run_local_server(
            port=8090,
            prompt="consent",
            authorization_prompt_message=(
                "Opening browser for YouTube authorization...\n"
                "If the browser doesn't open, visit the URL above manually."
            ),
        )
        logger.info("Fresh authentication completed")
        return creds

    def _save_credentials(self, creds: Credentials) -> None:
        """Persist credentials to disk for future runs."""
        token_dir = Path(self.token_path).parent
        token_dir.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w") as f:
            f.write(creds.to_json())
        logger.info(f"Credentials saved to {self.token_path}")

    @property
    def service(self):
        """Get authenticated YouTube service."""
        if self._service is None:
            self.authenticate()
        return self._service

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        category_id: str = "20",
        tags: list[str] = None,
        privacy_status: str = "unlisted",
        progress_callback: Callable[[float], None] = None,
    ) -> str:
        """
        Upload video to YouTube with resumable upload and automatic retry.

        Uses exponential backoff for transient errors (500, 502, 503, 504)
        and network issues. Large uploads survive brief connectivity drops.

        Args:
            video_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            category_id: YouTube category ID (default: 20 = Gaming)
            tags: List of tags
            privacy_status: "public", "unlisted", or "private"
            progress_callback: Optional callback(percent) for progress updates

        Returns:
            YouTube video ID
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Prepare metadata
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # 10MB chunks: better for large files, fewer round-trips
        media = MediaFileUpload(
            video_path,
            chunksize=10 * 1024 * 1024,
            resumable=True,
        )

        request = self.service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        # Upload with retry on transient failures
        response = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.progress() * 100)
                # Reset retry counter on successful chunk
                retry = 0

            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    retry = self._wait_and_retry(retry, e)
                else:
                    raise

            except RETRIABLE_EXCEPTIONS as e:
                retry = self._wait_and_retry(retry, e)

        if progress_callback:
            progress_callback(100)

        video_id = response["id"]
        logger.info(f"Upload complete: {video_id}")
        return video_id

    @staticmethod
    def _wait_and_retry(retry: int, error: Exception) -> int:
        """Exponential backoff with jitter. Returns incremented retry count."""
        if retry >= MAX_UPLOAD_RETRIES:
            raise error

        wait = min(2 ** retry + random.random(), 60)
        logger.warning(f"Retryable error ({error}), waiting {wait:.1f}s (attempt {retry + 1}/{MAX_UPLOAD_RETRIES})")
        time.sleep(wait)
        return retry + 1

    def get_video_url(self, video_id: str) -> str:
        """Get YouTube video URL from ID."""
        return f"https://www.youtube.com/watch?v={video_id}"

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        """
        Set custom thumbnail for a video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image (JPEG, PNG, GIF, BMP)

        Returns:
            Thumbnail resource
        """
        if not os.path.exists(thumbnail_path):
            raise FileNotFoundError(f"Thumbnail not found: {thumbnail_path}")

        media = MediaFileUpload(thumbnail_path, mimetype="image/png")
        return self.service.thumbnails().set(
            videoId=video_id,
            media_body=media,
        ).execute()

    def update_video(
        self,
        video_id: str,
        title: str = None,
        description: str = None,
        tags: list[str] = None,
    ) -> dict:
        """
        Update video metadata.

        Args:
            video_id: YouTube video ID
            title: New title (optional)
            description: New description (optional)
            tags: New tags (optional)

        Returns:
            Updated video resource
        """
        # Get current metadata
        current = self.service.videos().list(
            part="snippet",
            id=video_id,
        ).execute()

        if not current.get("items"):
            raise ValueError(f"Video not found: {video_id}")

        snippet = current["items"][0]["snippet"]

        # Update fields
        if title:
            snippet["title"] = title[:100]
        if description:
            snippet["description"] = description[:5000]
        if tags:
            snippet["tags"] = tags

        # Apply update
        return self.service.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": snippet,
            },
        ).execute()


def main():
    """CLI for testing YouTube client."""
    import argparse

    parser = argparse.ArgumentParser(description="YouTube upload client")
    parser.add_argument("--secrets", required=True, help="Path to secrets JSON")
    parser.add_argument("--video", help="Video file to upload")
    parser.add_argument("--title", default="Test Upload", help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--privacy", default="private", help="Privacy status")

    args = parser.parse_args()

    client = YouTubeClient(args.secrets)
    print("Authenticating...")
    client.authenticate()
    print("Authenticated successfully!")

    if args.video:
        print(f"Uploading: {args.video}")

        def progress(percent):
            print(f"\rProgress: {percent:.1f}%", end="", flush=True)

        video_id = client.upload_video(
            args.video,
            args.title,
            args.description,
            privacy_status=args.privacy,
            progress_callback=progress,
        )
        print(f"\nUploaded: {client.get_video_url(video_id)}")


if __name__ == "__main__":
    main()
