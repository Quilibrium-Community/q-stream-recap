"""
YouTube API client for video uploads.
Handles OAuth 2.0 authentication and resumable uploads.
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


# YouTube API scopes
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


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
        Will open browser for first-time authentication.
        """
        creds = None

        # Load cached credentials
        if os.path.exists(self.token_path):
            with open(self.token_path, "r") as f:
                creds_data = json.load(f)
                creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.secrets_path):
                    raise FileNotFoundError(
                        f"YouTube secrets file not found: {self.secrets_path}\n"
                        "Download it from Google Cloud Console and save to config/"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.secrets_path,
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        self._service = build("youtube", "v3", credentials=creds)

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
        Upload video to YouTube with resumable upload.

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
                "title": title[:100],  # YouTube limit
                "description": description[:5000],  # YouTube limit
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Create media upload with resumable upload
        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,  # 1MB chunks
            resumable=True,
        )

        # Start upload
        request = self.service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        # Execute with progress tracking
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(status.progress() * 100)

        if progress_callback:
            progress_callback(100)

        return response["id"]

    def get_video_url(self, video_id: str) -> str:
        """Get YouTube video URL from ID."""
        return f"https://www.youtube.com/watch?v={video_id}"

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
