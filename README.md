# Q Stream Recap

Automated video transcription and recap workflow for Quilibrium streams. Downloads videos from any platform, transcribes via OpenAI Whisper, generates formatted recaps, and uploads to the Quilibrium YouTube channel.

Designed to run through AI coding agents using workflow prompts. Works with [Claude Code](https://claude.ai/code), [OpenCode](https://opencode.ai), or any AI agent that can execute shell commands and follow markdown instructions.


## How It Works

The workflow has two independent parts:

1. **Transcribe + Recap** (anyone can do this)
   - Download video from Twitch, YouTube, Twitter/X, etc.
   - Transcribe audio via OpenAI Whisper API
   - Generate a formatted recap using Claude
   - Verify accuracy against the transcript
   - Output: full recap + short version for Discord/Telegram

2. **Upload to YouTube** (requires Quilibrium channel access)
   - Upload the video to the Quilibrium YouTube channel
   - Auto-generate title, description, thumbnail, and tags
   - Requires editor/manager access to the channel


## Quick Start

### With Claude Code

Once set up, the entire workflow is two slash commands in chat:

```
/Q:video-recap https://www.twitch.tv/videos/XXXXXXX
```
This downloads, transcribes, generates the recap, verifies it, and asks for your approval.

```
/Q:youtube-upload
```
This generates a title, asks for approval, uploads the video, sets the thumbnail, and offers to clean up temporary files.

### With Other AI Agents (OpenCode, etc.)

The workflow prompts are plain markdown files in `.claude/commands/Q/`. You can feed them to any AI agent:

1. Open `.claude/commands/Q/video-recap.md` and paste it as instructions to your agent along with the video URL
2. The agent will follow the step-by-step workflow using the Python scripts
3. For YouTube upload, use `.claude/commands/Q/youtube-upload.md`

### Manual (No AI Agent)

You can also run the scripts directly:

```bash
# Step 1: Download and transcribe
python scripts/video_transcribe.py --url "https://www.twitch.tv/videos/XXXXXXX"

# Step 2: Write the recap manually or with any LLM using the transcript in output/transcriptions/

# Step 3: Upload to YouTube (optional)
python scripts/upload_to_youtube.py --title "Your Title Here"
```


## Setup

### 1. Prerequisites

- [Python 3.10+](https://python.org)
- [ffmpeg](https://ffmpeg.org) in PATH
- An [OpenAI API key](https://platform.openai.com/api-keys) (for Whisper transcription)
- An AI coding agent (optional but recommended): [Claude Code](https://claude.ai/code), [OpenCode](https://opencode.ai), or similar

### 2. Install Dependencies

```bash
git clone https://github.com/QuilibriumNetwork/q-stream-recap.git
cd q-stream-recap
pip install -r requirements.txt
```

Install ffmpeg if you don't have it:
```bash
# Windows
winget install ffmpeg

# Mac
brew install ffmpeg

# Linux
apt install ffmpeg
```

### 3. Configure OpenAI API Key

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-...
```

This is all you need to transcribe videos and generate recaps.

### 4. YouTube Upload Setup (Optional)

This step is only needed if you want to upload videos to the Quilibrium YouTube channel. You need to be an **editor or manager** of the channel.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable **YouTube Data API v3** in the Library
4. Go to **OAuth consent screen** and configure it:
   - Set to **Production** (not Testing, otherwise tokens expire after 7 days)
   - Add the YouTube scopes
5. Create **OAuth 2.0 credentials** (Application type: Desktop app)
6. Download the JSON and save as `config/youtube_secrets.json`
7. Run authentication once via Claude Code or directly:
   ```bash
   python scripts/upload_to_youtube.py --auth-only
   ```
   This opens a browser for Google consent. Sign in with the account that has access to the Quilibrium YouTube channel. The token is saved locally and all future uploads are fully automatic.


## Contributing

Contributions are welcome! You can help by:

- **Improving recaps**: Submit PRs with corrections to existing recaps in `output/recaps/`
- **Adding features**: Improve the transcription or upload scripts
- **Translating recaps**: Add translations of existing recaps

You don't need YouTube channel access to contribute. The transcription and recap generation only requires an OpenAI API key.


## Configuration

Edit `config/config.yaml` to customize:

- OpenAI model selection (`gpt-4o-transcribe` or `whisper-1`)
- Audio processing settings (bitrate, sample rate, chunk size)
- YouTube defaults (category, privacy, tags, thumbnail)
- Output paths


## Project Structure

```
q-stream-recap/
├── scripts/
│   ├── video_transcribe.py    # Download + transcribe pipeline
│   ├── audio_processor.py     # FFmpeg audio extraction/chunking
│   ├── upload_to_youtube.py   # YouTube upload with OAuth
│   └── youtube_client.py      # YouTube API client
├── config/
│   ├── config.yaml            # Main configuration
│   ├── youtube_secrets.json   # YouTube OAuth secrets (not in git)
│   └── .youtube_token.json    # Cached OAuth token (not in git)
├── output/
│   ├── downloads/             # Downloaded MP4 files (not in git)
│   ├── audio/                 # Extracted audio + chunks (not in git)
│   ├── transcriptions/        # Transcripts + metadata
│   └── recaps/                # Full + short recaps
├── .claude/commands/Q/        # Workflow prompts (work with any AI agent)
├── .env                       # API keys (not in git)
└── requirements.txt
```


## Supported Platforms

Uses yt-dlp which supports 1000+ sites including:
- Twitch (VODs and clips)
- YouTube
- Twitter/X
- Vimeo
- TikTok
- Facebook, Instagram, Reddit, and more


## Recap Format

Recaps follow a specific format for the Quilibrium community:
- Greeting: "Hey Q fam!" with speaker attribution
- Bullet points use "⦿"
- Section titles use "✅"
- Main title uses "✨"
- Tone: informative, third person, non-technical focus
- Project name is always "Quilibrium" (transcription misspellings are auto-corrected)

A short version is also generated for Discord/Telegram sharing.
