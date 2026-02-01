"""
Audio processing module for video transcription workflow.
Handles audio extraction from video files and chunking for API limits.
"""

import os
import subprocess
import math
from pathlib import Path
from typing import List, Optional, Tuple


class AudioProcessor:
    """FFmpeg wrapper for audio extraction and chunking."""

    def __init__(
        self,
        bitrate: int = 64,
        sample_rate: int = 16000,
        channels: int = 1,
        max_chunk_size_mb: float = 24,
    ):
        self.bitrate = bitrate
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_chunk_size_mb = max_chunk_size_mb

    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available in PATH."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_duration(self, file_path: str) -> float:
        """Get duration of audio/video file in seconds."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def extract_audio(
        self,
        input_path: str,
        output_path: str,
    ) -> str:
        """
        Extract and convert audio from video file.

        Args:
            input_path: Path to input video/audio file
            output_path: Path for output MP3 file

        Returns:
            Path to the output audio file
        """
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-b:a", f"{self.bitrate}k",
            "-y",  # Overwrite output
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def get_file_size_mb(self, file_path: str) -> float:
        """Get file size in megabytes."""
        return os.path.getsize(file_path) / (1024 * 1024)

    def needs_chunking(self, file_path: str) -> bool:
        """Check if file exceeds max chunk size."""
        return self.get_file_size_mb(file_path) >= self.max_chunk_size_mb

    def calculate_chunk_duration(self, file_path: str) -> Tuple[int, float]:
        """
        Calculate optimal chunk duration and count.

        Returns:
            Tuple of (number of chunks, duration per chunk in seconds)
        """
        file_size_mb = self.get_file_size_mb(file_path)
        duration = self.get_duration(file_path)

        # Calculate how many chunks we need
        num_chunks = math.ceil(file_size_mb / self.max_chunk_size_mb)

        # Duration per chunk
        chunk_duration = duration / num_chunks

        return num_chunks, chunk_duration

    def chunk_audio(
        self,
        input_path: str,
        output_dir: str,
        base_name: str,
    ) -> List[str]:
        """
        Split audio file into chunks under the size limit.

        Args:
            input_path: Path to input audio file
            output_dir: Directory for output chunks
            base_name: Base name for chunk files (e.g., video_id)

        Returns:
            List of paths to chunk files
        """
        if not self.needs_chunking(input_path):
            return [input_path]

        num_chunks, chunk_duration = self.calculate_chunk_duration(input_path)
        chunk_paths = []

        for i in range(num_chunks):
            start_time = i * chunk_duration
            chunk_name = f"{base_name}_chunk_{i+1:03d}.mp3"
            chunk_path = os.path.join(output_dir, chunk_name)

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-ss", str(start_time),
                "-t", str(chunk_duration),
                "-acodec", "libmp3lame",
                "-ar", str(self.sample_rate),
                "-ac", str(self.channels),
                "-b:a", f"{self.bitrate}k",
                "-y",
                chunk_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            chunk_paths.append(chunk_path)

        return chunk_paths

    def process_video(
        self,
        video_path: str,
        output_dir: str,
        video_id: str,
    ) -> Tuple[str, List[str], float]:
        """
        Full processing pipeline: extract audio, chunk if needed.

        Args:
            video_path: Path to input video file
            output_dir: Directory for output files
            video_id: Identifier for naming output files

        Returns:
            Tuple of (main audio path, list of chunk paths, duration in seconds)
        """
        os.makedirs(output_dir, exist_ok=True)

        # Extract audio
        audio_path = os.path.join(output_dir, f"{video_id}.mp3")
        self.extract_audio(video_path, audio_path)

        # Get duration
        duration = self.get_duration(audio_path)

        # Chunk if needed
        chunk_paths = self.chunk_audio(audio_path, output_dir, video_id)

        return audio_path, chunk_paths, duration


def main():
    """CLI for testing audio processor."""
    import argparse

    parser = argparse.ArgumentParser(description="Process audio for transcription")
    parser.add_argument("input", help="Input video/audio file")
    parser.add_argument("--output-dir", default="./output/audio", help="Output directory")
    parser.add_argument("--video-id", default="test", help="Video ID for naming")
    parser.add_argument("--bitrate", type=int, default=64, help="Audio bitrate (kbps)")

    args = parser.parse_args()

    processor = AudioProcessor(bitrate=args.bitrate)

    if not processor.check_ffmpeg():
        print("Error: ffmpeg not found in PATH")
        return 1

    audio_path, chunks, duration = processor.process_video(
        args.input,
        args.output_dir,
        args.video_id,
    )

    print(f"Audio extracted: {audio_path}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Chunks: {len(chunks)}")
    for chunk in chunks:
        size = processor.get_file_size_mb(chunk)
        print(f"  - {chunk} ({size:.1f} MB)")

    return 0


if __name__ == "__main__":
    exit(main())
