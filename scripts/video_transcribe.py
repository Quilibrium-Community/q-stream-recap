"""
Video transcription script.
Downloads video from any supported platform, extracts audio, and transcribes via OpenAI Whisper API.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

from audio_processor import AudioProcessor


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        # Look for config relative to script location
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / "config" / "config.yaml"

    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_platform_and_id(url: str) -> Tuple[str, str]:
    """
    Extract platform name and video ID from URL.

    Returns:
        Tuple of (platform, video_id)
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    # Platform-specific ID extraction
    if "twitch.tv" in domain:
        # https://www.twitch.tv/videos/12345
        match = re.search(r"/videos/(\d+)", parsed.path)
        if match:
            return "twitch", match.group(1)
        # Clip URLs
        match = re.search(r"/clip/([^/?]+)", parsed.path)
        if match:
            return "twitch", match.group(1)

    elif "youtube.com" in domain or "youtu.be" in domain:
        # https://www.youtube.com/watch?v=abc123
        # https://youtu.be/abc123
        if "youtu.be" in domain:
            video_id = parsed.path.strip("/").split("/")[0]
            return "youtube", video_id
        match = re.search(r"(?:^|&)v=([^&]+)", parsed.query)
        if match:
            return "youtube", match.group(1)

    elif "twitter.com" in domain or "x.com" in domain:
        # https://twitter.com/user/status/12345
        # https://x.com/user/status/12345
        match = re.search(r"/status/(\d+)", parsed.path)
        if match:
            return "twitter", match.group(1)

    elif "vimeo.com" in domain:
        match = re.search(r"/(\d+)", parsed.path)
        if match:
            return "vimeo", match.group(1)

    elif "tiktok.com" in domain:
        match = re.search(r"/video/(\d+)", parsed.path)
        if match:
            return "tiktok", match.group(1)

    # Fallback: use domain as platform and hash of URL as ID
    import hashlib
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    platform = domain.split(".")[0]
    return platform, url_hash


def download_video(url: str, output_dir: str, retries: int = 3, cookies_file: str = None) -> Tuple[str, dict]:
    """
    Download video using yt-dlp.

    Returns:
        Tuple of (file_path, info_dict)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Output template
    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    # Use python -m yt_dlp for cross-platform compatibility
    yt_dlp_cmd = [sys.executable, "-m", "yt_dlp"]

    # Add cookies file if provided and exists
    cookies_args = []
    if cookies_file and os.path.exists(cookies_file):
        cookies_args = ["--cookies", cookies_file]

    for attempt in range(retries):
        try:
            # First, get video info
            info_cmd = yt_dlp_cmd + cookies_args + [
                "--dump-json",
                "--no-download",
                url,
            ]
            result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            # Download the video (need MP4 for YouTube upload later)
            download_cmd = yt_dlp_cmd + cookies_args + [
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", output_template,
                "--no-playlist",
                url,
            ]
            subprocess.run(download_cmd, capture_output=True, check=True)

            # Find the downloaded file
            video_id = info.get("id", "video")
            ext = info.get("ext", "mp4")

            # yt-dlp might download a different extension
            possible_files = list(Path(output_dir).glob(f"{video_id}.*"))
            if possible_files:
                return str(possible_files[0]), info

            # Fallback to expected path
            file_path = os.path.join(output_dir, f"{video_id}.{ext}")
            if os.path.exists(file_path):
                return file_path, info

            raise FileNotFoundError(f"Downloaded file not found for {video_id}")

        except subprocess.CalledProcessError as e:
            if attempt < retries - 1:
                print(f"Download attempt {attempt + 1} failed, retrying...")
                continue
            raise RuntimeError(f"Download failed after {retries} attempts: {e.stderr}")

    raise RuntimeError("Download failed")


def transcribe_audio(
    audio_paths: list[str],
    client: OpenAI,
    model: str = "gpt-4o-transcribe",
) -> str:
    """
    Transcribe audio file(s) using OpenAI Whisper API.

    Args:
        audio_paths: List of audio file paths (chunks)
        client: OpenAI client instance
        model: Whisper model to use

    Returns:
        Combined transcription text
    """
    transcriptions = []

    for i, audio_path in enumerate(tqdm(audio_paths, desc="Transcribing")):
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                response_format="text",
            )
            transcriptions.append(response)

    return "\n".join(transcriptions)


def save_metadata(
    output_path: str,
    video_id: str,
    platform: str,
    url: str,
    video_path: str,
    audio_path: str,
    transcript_path: str,
    chunks: int,
    duration: float,
    info: dict = None,
) -> dict:
    """Save video metadata to JSON file."""
    metadata = {
        "video_id": video_id,
        "platform": platform,
        "url": url,
        "title": info.get("title", "") if info else "",
        "mp4_path": video_path,
        "audio_path": audio_path,
        "transcript_path": transcript_path,
        "chunks": chunks,
        "duration_seconds": round(duration, 2),
        "download_date": datetime.now(timezone.utc).isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download and transcribe video from any supported platform"
    )
    parser.add_argument("--url", required=True, help="Video URL")
    parser.add_argument("--bitrate", type=int, help="Audio bitrate in kbps")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Load config
    config = load_config(args.config)

    # Override config with CLI args
    bitrate = args.bitrate or config["audio"]["bitrate"]
    base_output_dir = args.output_dir or "output"

    # Setup paths
    script_dir = Path(__file__).parent.parent
    downloads_dir = script_dir / config["paths"]["downloads"]
    audio_dir = script_dir / config["paths"]["audio"]
    transcripts_dir = script_dir / config["paths"]["transcriptions"]

    # Extract platform and video ID
    platform, video_id = extract_platform_and_id(args.url)
    print(f"Platform: {platform}")
    print(f"Video ID: {video_id}")

    # Create date prefix for all output files (YYYY-MM-DD)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    file_prefix = f"{date_prefix}_{video_id}"
    print(f"File prefix: {file_prefix}")

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set in environment")
        print("Please set it in your .env file")
        return 1

    # Check for ffmpeg
    audio_processor = AudioProcessor(
        bitrate=bitrate,
        sample_rate=config["audio"]["sample_rate"],
        channels=config["audio"]["channels"],
        max_chunk_size_mb=config["audio"]["max_chunk_size_mb"],
    )
    if not audio_processor.check_ffmpeg():
        print("Error: ffmpeg not found in PATH")
        print("Please install ffmpeg:")
        print("  Windows: winget install ffmpeg")
        print("  Mac: brew install ffmpeg")
        print("  Linux: apt install ffmpeg")
        return 1

    # Get cookies file path if configured
    cookies_file = config["download"].get("cookies_file")
    if cookies_file:
        cookies_file = str(script_dir / cookies_file)

    # Download video
    print(f"\n1. Downloading video...")
    try:
        video_path_original, info = download_video(
            args.url,
            str(downloads_dir),
            retries=config["download"]["retries"],
            cookies_file=cookies_file,
        )
        # Rename to include date prefix
        video_ext = Path(video_path_original).suffix
        video_path = downloads_dir / f"{file_prefix}{video_ext}"
        if str(video_path_original) != str(video_path):
            Path(video_path_original).rename(video_path)
        print(f"   Downloaded: {video_path}")
    except Exception as e:
        print(f"Error downloading video: {e}")
        return 1

    # Process audio
    print(f"\n2. Processing audio...")
    try:
        audio_path, chunk_paths, duration = audio_processor.process_video(
            str(video_path),
            str(audio_dir),
            file_prefix,
        )
        print(f"   Audio: {audio_path}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Chunks: {len(chunk_paths)}")
    except Exception as e:
        print(f"Error processing audio: {e}")
        return 1

    # Transcribe
    print(f"\n3. Transcribing...")
    try:
        client = OpenAI(api_key=api_key)
        transcript = transcribe_audio(
            chunk_paths,
            client,
            model=config["openai"]["model"],
        )
    except Exception as e:
        print(f"Error transcribing: {e}")
        return 1

    # Save transcript
    os.makedirs(transcripts_dir, exist_ok=True)
    transcript_path = transcripts_dir / f"{file_prefix}_transcript.txt"
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"\n4. Transcript saved: {transcript_path}")

    # Save metadata
    meta_path = transcripts_dir / f"{file_prefix}_meta.json"
    metadata = save_metadata(
        str(meta_path),
        video_id=file_prefix,  # Use file_prefix as the ID for consistency
        platform=platform,
        url=args.url,
        video_path=str(video_path),
        audio_path=str(audio_path),
        transcript_path=str(transcript_path),
        chunks=len(chunk_paths),
        duration=duration,
        info=info,
    )
    print(f"   Metadata saved: {meta_path}")

    print(f"\n✓ Complete!")
    print(f"  File prefix: {file_prefix}")
    print(f"  Transcript: {transcript_path}")
    print(f"  Ready for recap generation.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
