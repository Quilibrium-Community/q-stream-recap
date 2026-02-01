# Q Stream Recap

Automated video transcription and recap workflow for Quilibrium streams.

## Features

- Download videos from any platform (Twitch, YouTube, Twitter/X, Vimeo, TikTok, etc.)
- Transcribe via OpenAI Whisper API (gpt-4o-transcribe)
- Generate formatted recaps using Claude
- Upload to YouTube with metadata

## Setup

### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# System dependency: ffmpeg
# Windows:
winget install ffmpeg

# Mac:
brew install ffmpeg

# Linux:
apt install ffmpeg
```

### 2. Configure API Keys

Copy the example env file and add your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. YouTube Setup (Optional)

To enable YouTube uploads:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **YouTube Data API v3**
3. Create **OAuth 2.0 credentials** (Desktop app type)
4. Download the JSON and save as `config/youtube_secrets.json`

## Usage

### Transcribe a Video

```bash
python scripts/video_transcribe.py --url "https://twitch.tv/videos/12345"
```

Options:
- `--url` - Video URL (required)
- `--bitrate` - Audio bitrate in kbps (default: 64)
- `--output-dir` - Output directory (default: ./output)

### Generate Recap (Claude Command)

After transcription, use the Claude command to generate a recap:

```
/Q:summarize-q-stream
```

The recap will be saved to `output/recaps/{video_id}_recap.md`.

### Upload to YouTube

```bash
python scripts/upload_to_youtube.py --video-id "12345"
```

Options:
- `--video-id` - Video ID from transcription (required)
- `--title` - Custom title (optional, extracted from recap)
- `--category` - YouTube category ID (default: 20 = Gaming)
- `--privacy` - public, unlisted, or private (default: unlisted)

## Configuration

Edit `config/config.yaml` to customize:

- Audio processing settings (bitrate, sample rate)
- YouTube defaults (category, privacy, tags)
- Output paths

## Project Structure

```
q-stream-recap/
├── scripts/
│   ├── video_transcribe.py   # Download + transcribe
│   ├── audio_processor.py    # FFmpeg audio processing
│   ├── upload_to_youtube.py  # YouTube upload
│   └── youtube_client.py     # YouTube API client
├── config/
│   ├── config.yaml           # Main configuration
│   └── youtube_secrets.json  # YouTube OAuth (not in git)
├── prompts/
│   └── recap_instructions.md # Recap formatting template
├── output/
│   ├── downloads/            # Downloaded videos
│   ├── audio/                # Extracted audio
│   ├── transcriptions/       # Raw transcripts + metadata
│   └── recaps/               # Generated recaps
├── .claude/commands/Q/       # Claude slash commands
├── .env                      # API keys (not in git)
└── requirements.txt
```

## Workflow

1. **Download & Transcribe**: `python scripts/video_transcribe.py --url <URL>`
2. **Generate Recap**: `/Q:summarize-q-stream` with transcript
3. **Review & Edit**: Check `output/recaps/{video_id}_recap.md`
4. **Upload**: `python scripts/upload_to_youtube.py --video-id <ID>`

## Supported Platforms

Uses yt-dlp which supports 1000+ sites including:
- Twitch (VODs and clips)
- YouTube (videos, live streams, shorts)
- Twitter/X
- Vimeo
- TikTok
- Facebook
- Instagram
- Reddit
