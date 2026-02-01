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
    parser.add_argument("--video-id", required=True, help="Video ID from transcription")
    parser.add_argument("--title", help="Custom title (overrides recap title)")
    parser.add_argument("--category", help="YouTube category ID")
    parser.add_argument("--privacy", help="Privacy status: public, unlisted, private")
    parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Setup paths
    script_dir = Path(__file__).parent.parent
    transcripts_dir = script_dir / config["paths"]["transcriptions"]
    recaps_dir = script_dir / config["paths"]["recaps"]
    secrets_path = script_dir / "config" / "youtube_secrets.json"

    # Load metadata
    meta_path = transcripts_dir / f"{args.video_id}_meta.json"
    if not meta_path.exists():
        print(f"Error: Metadata not found: {meta_path}")
        print("Run video_transcribe.py first to download and transcribe the video.")
        return 1

    metadata = load_metadata(str(meta_path))
    print(f"Loaded metadata for: {metadata.get('title', args.video_id)}")

    # Check video file exists
    video_path = metadata.get("mp4_path")
    if not video_path or not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return 1

    # Load recap for description
    recap_path = recaps_dir / f"{args.video_id}_recap.md"
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

    print(f"\nUpload details:")
    print(f"  Title: {title}")
    print(f"  Privacy: {privacy}")
    print(f"  Category: {category}")
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
