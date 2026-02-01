"""
YouTube upload script.
Uploads video to YouTube with metadata from recap file.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

from youtube_client import YouTubeClient


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "config.yaml"

    with open(config_path) as f:
        return yaml.safe_load(f)


def load_metadata(meta_path: str) -> dict:
    """Load video metadata JSON."""
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_recap(recap_path: str) -> str:
    """Load recap markdown content."""
    with open(recap_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_title_from_recap(recap_content: str, fallback: str = "Video Recap") -> str:
    """
    Extract title from recap markdown.
    Looks for first H1 or H2 heading.
    """
    # Try to find markdown heading
    patterns = [
        r"^#\s+(.+)$",      # # Title
        r"^##\s+(.+)$",     # ## Title
        r"^\*\*(.+)\*\*$",  # **Title**
    ]

    for pattern in patterns:
        match = re.search(pattern, recap_content, re.MULTILINE)
        if match:
            return match.group(1).strip()

    return fallback


def find_latest_video(downloads_dir: Path, transcripts_dir: Path) -> tuple[str, str]:
    """
    Find the most recent video in downloads folder and its video ID.

    Returns:
        Tuple of (video_path, video_id)
    """
    # Find all MP4 files in downloads
    mp4_files = list(downloads_dir.glob("*.mp4"))
    if not mp4_files:
        raise FileNotFoundError(f"No MP4 files found in {downloads_dir}")

    # Sort by modification time, newest first
    mp4_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    latest_video = mp4_files[0]

    # Video ID is the filename without extension
    video_id = latest_video.stem

    return str(latest_video), video_id


def extract_tags_from_recap(recap_content: str) -> list[str]:
    """
    Extract tags from recap content.
    Looks for hashtags or keyword sections.
    """
    tags = []

    # Find hashtags
    hashtags = re.findall(r"#(\w+)", recap_content)
    tags.extend(hashtags)

    # Find content in "Tags:" or "Keywords:" section
    tag_section = re.search(
        r"(?:Tags|Keywords|Topics):\s*(.+?)(?:\n\n|\n#|$)",
        recap_content,
        re.IGNORECASE | re.DOTALL,
    )
    if tag_section:
        # Split by commas, newlines, or bullet points
        section_tags = re.split(r"[,\n•⦿-]", tag_section.group(1))
        tags.extend(t.strip() for t in section_tags if t.strip())

    # Deduplicate and limit to 500 chars total (YouTube limit)
    seen = set()
    unique_tags = []
    total_chars = 0
    for tag in tags:
        tag_clean = tag.strip().lower()
        if tag_clean and tag_clean not in seen:
            if total_chars + len(tag_clean) + 1 <= 500:
                seen.add(tag_clean)
                unique_tags.append(tag.strip())
                total_chars += len(tag_clean) + 1

    return unique_tags


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload video to YouTube with metadata from recap"
    )
    parser.add_argument("--video-id", help="Video ID from transcription (auto-detects if not specified)")
    parser.add_argument("--title", help="Custom title (overrides recap title)")
    parser.add_argument("--category", help="YouTube category ID")
    parser.add_argument("--privacy", help="Privacy status: public, unlisted, private")
    parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup paths
    script_dir = Path(__file__).parent.parent
    downloads_dir = script_dir / config["paths"]["downloads"]
    transcripts_dir = script_dir / config["paths"]["transcriptions"]
    recaps_dir = script_dir / config["paths"]["recaps"]
    secrets_path = script_dir / "config" / "youtube_secrets.json"

    # Auto-detect video if not specified
    video_id = args.video_id
    if not video_id:
        try:
            video_path, video_id = find_latest_video(downloads_dir, transcripts_dir)
            print(f"Auto-detected video: {video_id}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Specify --video-id or ensure there's an MP4 in output/downloads/")
            return 1

    # Load metadata
    meta_path = transcripts_dir / f"{video_id}_meta.json"
    if not meta_path.exists():
        print(f"Error: Metadata not found: {meta_path}")
        print("Run video_transcribe.py first to download and transcribe the video.")
        return 1

    metadata = load_metadata(str(meta_path))
    print(f"Loaded metadata for: {metadata.get('title', video_id)}")

    # Check video file exists
    video_path = metadata.get("mp4_path")
    if not video_path or not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return 1

    # Load recap for description
    recap_path = recaps_dir / f"{video_id}_recap.md"
    if recap_path.exists():
        recap_content = load_recap(str(recap_path))
        description = recap_content
        title = args.title or extract_title_from_recap(recap_content, metadata.get("title", "Video"))
        tags = extract_tags_from_recap(recap_content)
    else:
        print(f"Warning: Recap not found: {recap_path}")
        print("Using basic metadata instead.")
        description = f"Video from {metadata.get('platform', 'unknown')}\n\nOriginal: {metadata.get('url', '')}"
        title = args.title or metadata.get("title", "Video")
        tags = []

    # Add default tags
    tags.extend(config["youtube"]["default_tags"])
    tags = list(dict.fromkeys(tags))  # Deduplicate preserving order

    # Get settings
    category = args.category or str(config["youtube"]["default_category"])
    privacy = args.privacy or config["youtube"]["default_privacy"]

    # Get thumbnail path
    thumbnail_path = None
    if config["youtube"].get("default_thumbnail"):
        thumbnail_path = script_dir / config["youtube"]["default_thumbnail"]
        if not thumbnail_path.exists():
            print(f"Warning: Thumbnail not found: {thumbnail_path}")
            thumbnail_path = None

    print(f"\nUpload details:")
    print(f"  Title: {title}")
    print(f"  Privacy: {privacy}")
    print(f"  Category: {category}")
    print(f"  Thumbnail: {thumbnail_path.name if thumbnail_path else 'None'}")
    print(f"  Tags: {', '.join(tags[:5])}{'...' if len(tags) > 5 else ''}")

    # Check for secrets file
    if not secrets_path.exists():
        print(f"\nError: YouTube secrets not found: {secrets_path}")
        print("\nTo set up YouTube API:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable YouTube Data API v3")
        print("3. Create OAuth 2.0 credentials (Desktop app)")
        print("4. Download the JSON and save as config/youtube_secrets.json")
        return 1

    # Initialize YouTube client
    print(f"\n1. Authenticating with YouTube...")
    try:
        client = YouTubeClient(str(secrets_path))
        client.authenticate()
        print("   Authenticated!")
    except Exception as e:
        print(f"Error authenticating: {e}")
        return 1

    # Upload with progress bar
    print(f"\n2. Uploading video...")
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"   File size: {file_size_mb:.1f} MB")

    pbar = tqdm(total=100, desc="   Uploading", unit="%", ncols=60)
    last_progress = 0

    def progress_callback(percent):
        nonlocal last_progress
        delta = percent - last_progress
        if delta > 0:
            pbar.update(delta)
            last_progress = percent

    try:
        youtube_id = client.upload_video(
            video_path,
            title=title,
            description=description,
            category_id=category,
            tags=tags,
            privacy_status=privacy,
            progress_callback=progress_callback,
        )
        pbar.close()
    except Exception as e:
        pbar.close()
        print(f"\nError uploading: {e}")
        return 1

    # Get video URL
    video_url = client.get_video_url(youtube_id)

    # Set thumbnail if configured
    if thumbnail_path:
        print(f"\n3. Setting thumbnail...")
        try:
            client.set_thumbnail(youtube_id, str(thumbnail_path))
            print(f"   Thumbnail set!")
        except Exception as e:
            print(f"   Warning: Failed to set thumbnail: {e}")
            print("   (Video uploaded successfully, thumbnail can be set manually)")

    # Update metadata with YouTube URL
    metadata["youtube_id"] = youtube_id
    metadata["youtube_url"] = video_url
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Append URL to recap if it exists
    if recap_path.exists():
        with open(recap_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\nYouTube: {video_url}\n")

    print(f"\n✓ Upload complete!")
    print(f"  Video URL: {video_url}")
    print(f"  Status: {privacy}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
