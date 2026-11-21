# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Q Stream Recap automates the workflow of downloading Quilibrium-related videos (streams, interviews) from various platforms, transcribing them via OpenAI Whisper, generating formatted recaps, and uploading to YouTube.

## Commands

### Transcribe a Video
```bash
python scripts/video_transcribe.py --url "https://twitch.tv/videos/12345"
```
Options: `--bitrate` (kbps, default 64), `--output-dir`, `--config`

### Upload to YouTube
```bash
python scripts/upload_to_youtube.py --video-id "12345"
```
Options: `--title`, `--category`, `--privacy` (public/unlisted/private)

### Install Dependencies
```bash
pip install -r requirements.txt
```
System requirement: `ffmpeg` must be in PATH.

## Architecture

### Pipeline Flow
1. **Download**: `video_transcribe.py` uses yt-dlp to fetch video from URL
2. **Audio Processing**: `AudioProcessor` (audio_processor.py) extracts audio via ffmpeg, chunks if >24MB
3. **Transcription**: Groq Whisper API (default) or OpenAI processes chunks sequentially
4. **Recap Generation**: Claude slash command `/Q:video-recap` generates formatted recap from transcript
5. **Upload**: `upload_to_youtube.py` authenticates via OAuth and uploads with metadata from recap

### Key Files
- `scripts/video_transcribe.py` - Main entry: download → audio → transcribe → save
- `scripts/audio_processor.py` - `AudioProcessor` class wraps ffmpeg for extraction/chunking
- `scripts/youtube_client.py` - `YouTubeClient` class handles OAuth and resumable uploads
- `scripts/upload_to_youtube.py` - Upload orchestration with auto-detection of latest video
- `config/config.yaml` - All configurable settings (bitrate, paths, YouTube defaults, cookies)

### Output Structure
```
output/
├── downloads/     # Original MP4 files
├── audio/         # Extracted MP3 + chunks
├── transcriptions/# {video_id}_transcript.txt + {video_id}_meta.json
└── recaps/        # {video_id}_recap.md, _recap_short.md (Discord/Telegram + YouTube description), _recap_tweet.md (fits one tweet), _recap_web.md (GitHub page)
```

`_recap_web.md` is real Markdown generated from the plain recap by `python scripts/recap_to_web.py <recap.md>`. It is the file linked from the short version, because X has no long posts and GitHub renders Markdown as a formatted page. Never hand-edit it; fix the plain recap and regenerate.

### Claude Slash Commands
- `/Q:video-recap <url>` - Full pipeline: download, transcribe, generate recap, verify. After the user approves the recap it also publishes the GitHub page, writes the tweet and chat texts, and uploads to YouTube (unlisted)
- `/Q:summarize-q-stream` - Generate recap from uploaded transcript
- `/Q:youtube-upload` - Upload latest video to YouTube

### Platform ID Extraction
`extract_platform_and_id()` in video_transcribe.py handles URL parsing for Twitch, YouTube, Twitter/X, Vimeo, TikTok. Fallback uses MD5 hash of URL.

## Configuration

`config/config.yaml` contains:
- OpenAI model selection (`gpt-4o-transcribe` or `whisper-1`)
- Audio settings (bitrate, sample rate, chunk size limit)
- YouTube defaults (category, privacy, tags, default thumbnail)
- Paths for all output directories
- Cookies file path for authenticated downloads

## Recap Format

Recaps follow a specific format for the Quilibrium community:
- Header: "Hey Q fam!" with speaker attribution (@cass_on_mars)
- Bullet points use "⦿"
- Section titles use "✅"
- Main title uses "✨"
- Tone: informative, third person, non-technical focus
- Project name is always "Quilibrium" (fix transcription misspellings)
