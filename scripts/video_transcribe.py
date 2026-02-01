"""
Video transcription script.
Downloads video from any supported platform, extracts audio, and transcribes via OpenAI Whisper API.

Supports resuming from any step via --from-step flag:
  download   - Start from beginning (download video)
  audio      - Skip download, start from audio extraction
  chunk      - Skip download and audio extraction, start from chunking
  transcribe - Skip to transcription only
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

from audio_processor import AudioProcessor


# Pipeline steps in order
STEPS = ["download", "audio", "chunk", "transcribe"]


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
    parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
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


def find_existing_file(directory: Path, video_id: str, extension: str, pattern: str = None) -> Optional[Path]:
    """
    Find the most recent existing file for a video ID.

    Files are named with date prefix: YYYY-MM-DD_<video_id>.<ext>
    Returns the most recent one if multiple exist.
    """
    if pattern:
        # Use custom pattern (e.g., for chunks)
        files = list(directory.glob(pattern))
    else:
        # Match files ending with video_id and extension
        files = list(directory.glob(f"*_{video_id}{extension}"))

    if not files:
        return None

    # Sort by filename (date prefix means alphabetical = chronological)
    files.sort(reverse=True)
    return files[0]


def find_existing_chunks(directory: Path, video_id: str) -> List[Path]:
    """
    Find existing audio chunks for a video ID.
    Returns sorted list of chunk files.
    """
    # Match pattern: *_<video_id>_chunk_*.mp3
    chunks = list(directory.glob(f"*_{video_id}_chunk_*.mp3"))
    chunks.sort()
    return chunks


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
        description="Download and transcribe video from any supported platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline from URL
  python video_transcribe.py --url "https://twitch.tv/videos/12345"

  # Resume from audio extraction (video already downloaded)
  python video_transcribe.py --url "https://twitch.tv/videos/12345" --from-step audio

  # Resume from chunking (audio already extracted)
  python video_transcribe.py --url "https://twitch.tv/videos/12345" --from-step chunk

  # Resume from transcription (chunks already created)
  python video_transcribe.py --url "https://twitch.tv/videos/12345" --from-step transcribe
"""
    )
    parser.add_argument("--url", required=True, help="Video URL")
    parser.add_argument("--bitrate", type=int, help="Audio bitrate in kbps")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument(
        "--from-step",
        choices=STEPS,
        default="download",
        help="Start from this step (default: download). Use to resume after failures."
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Load config
    config = load_config(args.config)

    # Override config with CLI args
    bitrate = args.bitrate or config["audio"]["bitrate"]

    # Setup paths
    script_dir = Path(__file__).parent.parent
    downloads_dir = script_dir / config["paths"]["downloads"]
    audio_dir = script_dir / config["paths"]["audio"]
    transcripts_dir = script_dir / config["paths"]["transcriptions"]

    # Extract platform and video ID
    platform, video_id = extract_platform_and_id(args.url)
    print(f"Platform: {platform}")
    print(f"Video ID: {video_id}")

    # Determine start step
    start_step_idx = STEPS.index(args.from_step)
    if args.from_step != "download":
        print(f"Resuming from step: {args.from_step}")

    # Check for OpenAI API key (needed for transcribe step)
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
        max_chunk_duration_sec=config["audio"].get("max_chunk_duration_sec", 1300),
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

    # Initialize variables that may be set by skipped steps
    video_path = None
    audio_path = None
    chunk_paths = None
    duration = None
    info = None
    file_prefix = None

    # --- STEP 1: Download ---
    if start_step_idx <= STEPS.index("download"):
        # Create date prefix for all output files (YYYY-MM-DD)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        file_prefix = f"{date_prefix}_{video_id}"
        print(f"File prefix: {file_prefix}")

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
    else:
        # Find existing video file
        print(f"\n1. Skipping download (--from-step={args.from_step})")
        existing_video = find_existing_file(downloads_dir, video_id, ".mp4")
        if not existing_video:
            print(f"   Error: No existing video found for video ID '{video_id}' in {downloads_dir}")
            print(f"   Run without --from-step to download first.")
            return 1
        video_path = existing_video
        # Extract file_prefix from existing filename
        file_prefix = existing_video.stem
        print(f"   Using existing: {video_path}")
        print(f"   File prefix: {file_prefix}")

    # --- STEP 2: Audio extraction ---
    if start_step_idx <= STEPS.index("audio"):
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
    else:
        # Find existing audio file
        print(f"\n2. Skipping audio extraction (--from-step={args.from_step})")
        existing_audio = find_existing_file(audio_dir, video_id, ".mp3")
        if not existing_audio:
            print(f"   Error: No existing audio found for video ID '{video_id}' in {audio_dir}")
            print(f"   Run with --from-step=audio to extract audio first.")
            return 1
        audio_path = str(existing_audio)
        # Get duration from existing audio
        duration = audio_processor.get_duration(audio_path)
        # Extract file_prefix from audio filename if not already set
        if not file_prefix:
            file_prefix = existing_audio.stem
        print(f"   Using existing: {audio_path}")
        print(f"   Duration: {duration:.1f} seconds")

    # --- STEP 3: Chunking ---
    if start_step_idx <= STEPS.index("chunk"):
        # Chunking is part of audio processing, but can be done separately
        if chunk_paths is None:
            print(f"\n3. Creating audio chunks...")
            try:
                chunk_paths = audio_processor.chunk_audio(
                    audio_path,
                    str(audio_dir),
                    file_prefix,
                )
                print(f"   Chunks: {len(chunk_paths)}")
                for chunk in chunk_paths:
                    size = audio_processor.get_file_size_mb(chunk)
                    print(f"     - {Path(chunk).name}: {size:.1f} MB")
            except Exception as e:
                print(f"Error chunking audio: {e}")
                return 1
        else:
            print(f"\n3. Audio chunks already created: {len(chunk_paths)}")
    else:
        # Find existing chunks
        print(f"\n3. Skipping chunking (--from-step={args.from_step})")
        existing_chunks = find_existing_chunks(audio_dir, video_id)
        if existing_chunks:
            chunk_paths = [str(c) for c in existing_chunks]
            print(f"   Using existing chunks: {len(chunk_paths)}")
        else:
            # No chunks found - use the main audio file if it's small enough
            if audio_path and audio_processor.get_file_size_mb(audio_path) < audio_processor.max_chunk_size_mb:
                chunk_paths = [audio_path]
                print(f"   Using main audio file (no chunking needed)")
            else:
                print(f"   Error: No existing chunks found for video ID '{video_id}' in {audio_dir}")
                print(f"   Run with --from-step=chunk to create chunks first.")
                return 1

    # --- STEP 4: Transcribe ---
    print(f"\n4. Transcribing...")
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
    print(f"\n5. Transcript saved: {transcript_path}")

    # Save metadata
    meta_path = transcripts_dir / f"{file_prefix}_meta.json"
    metadata = save_metadata(
        str(meta_path),
        video_id=file_prefix,  # Use file_prefix as the ID for consistency
        platform=platform,
        url=args.url,
        video_path=str(video_path) if video_path else "",
        audio_path=str(audio_path) if audio_path else "",
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
