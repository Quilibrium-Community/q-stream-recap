# PRD: Video Transcription & Recap Workflow

## Overview
Automated system to download videos from various platforms (Twitch, YouTube, Twitter/X, etc.), transcribe them via OpenAI Whisper API, generate formatted recaps using Claude, verify accuracy, and optionally upload to YouTube.

## Technical Stack
- Python 3.10+
- Claude Code CLI (slash commands)
- yt-dlp (multi-platform video downloads)
- ffmpeg (audio processing)
- OpenAI Whisper API (transcription)
- YouTube Data API v3 (uploads)

## Project Structure
```
video-recap-workflow/
├── .claude/
│   └── commands/
│       ├── video-recap.json
│       └── youtube-upload.json
├── scripts/
│   ├── video_transcribe.py
│   ├── upload_to_youtube.py
│   ├── audio_processor.py
│   └── youtube_client.py
├── prompts/
│   └── recap_instructions.md
├── output/
│   ├── downloads/
│   ├── audio/
│   ├── transcriptions/
│   └── recaps/
├── config/
│   ├── config.yaml
│   └── youtube_secrets.json
├── requirements.txt
└── README.md
```

## Script 1: video_transcribe.py

### Purpose
Download video from any supported platform, optimize audio, transcribe, save metadata.

### Inputs
- `--url`: Video URL (required) - supports Twitch, YouTube, Twitter/X, Vimeo, etc.
- `--bitrate`: Audio bitrate in kbps (default: 64)
- `--output-dir`: Output directory (default: ./output)

### Process
1. **Download** via yt-dlp
   - Try direct audio extraction (best audio format)
   - Fallback to MP4 if audio-only unavailable
   - Save to `output/downloads/`
   - Extract video ID from URL (platform-agnostic)

2. **Audio optimization** (if MP4 downloaded)
   - Extract audio with ffmpeg
   - Convert to MP3 mono at specified bitrate (default 64kbps)
   - Target sample rate: 16kHz (optimal for speech)
   - Save to `output/audio/`

3. **File size check**
   - If audio <25MB: keep as single file
   - If audio ≥25MB: chunk into segments <25MB each
   - Name chunks: `{video_id}_chunk_001.mp3`, etc.

4. **Transcribe** via OpenAI Whisper API
   - Use `whisper-1` or `gpt-4o-transcribe` model
   - Process each chunk sequentially
   - Concatenate transcriptions
   - Save raw transcription to `output/transcriptions/{video_id}_transcript.txt`

5. **Save metadata** to `output/transcriptions/{video_id}_meta.json`
   ```json
   {
     "video_id": "12345",
     "platform": "twitch",
     "url": "https://twitch.tv/videos/12345",
     "mp4_path": "output/downloads/video.mp4",
     "audio_path": "output/audio/video.mp3",
     "transcript_path": "output/transcriptions/12345_transcript.txt",
     "chunks": 3,
     "duration_seconds": 3600,
     "download_date": "2026-02-01T10:30:00Z"
   }
   ```

### Output
- Raw transcription file
- Metadata JSON
- Preserved MP4 for YouTube upload
- Exit with success status

### Error Handling
- Invalid URL: exit with error message
- Unsupported platform: notify user
- Download failure: retry 3 times, then exit
- API errors: log details, exit gracefully
- Chunking errors: verify ffmpeg installation

## Slash Command 1: Q/summarize-q-stream.md

### Configuration
File: `.claude/commands/video-recap.json`

### Trigger
```bash
/video-recap <video_url>
```

### Instructions for Claude

1. **Execute script**
   ```bash
   python scripts/video_transcribe.py --url <video_url>
   ```

2. **Wait for completion**, then read:
   - `output/transcriptions/{video_id}_transcript.txt`
   - `prompts/recap_instructions.md`

3. **Generate recap**
   - Apply instructions from `recap_instructions.md`
   - Create structured recap
   - Save to `output/recaps/{video_id}_recap.md`

4. **Launch verification agent**
   - Read raw transcription
   - Read generated recap
   - Compare for:
     - Factual accuracy
     - Missing key points
     - Incorrect timestamps
     - Formatting errors
   - Make corrections directly in recap file

5. **Present final recap**
   - Display recap content
   - Show verification summary
   - Indicate location: `output/recaps/{video_id}_recap.md`
   - Prompt: "Ready for YouTube upload? Run `/youtube-upload {video_id}`"

### Success Criteria
- Transcription completed without errors
- Recap follows all formatting rules
- Verification agent found 0 errors OR corrected all errors
- All files saved to correct locations

## Script 2: upload_to_youtube.py

### Purpose
Upload MP4 to YouTube with title/description from recap.

### Inputs
- `--video-id`: Video ID (required)
- `--title`: Custom title (optional, defaults from recap)
- `--category`: YouTube category ID (default: 20 = Gaming)
- `--privacy`: Privacy status (default: "unlisted")

### Process
1. **Load metadata**
   - Read `output/transcriptions/{video_id}_meta.json`
   - Read `output/recaps/{video_id}_recap.md`

2. **Authenticate YouTube API**
   - Load `config/youtube_secrets.json`
   - OAuth 2.0 flow (browser-based first time)
   - Cache credentials

3. **Prepare upload**
   - Title: Extract from recap or use custom
   - Description: Full recap content
   - Tags: Extract from recap or defaults
   - Thumbnail: Optional cover image path

4. **Upload with progress**
   - Use resumable upload
   - Show progress bar
   - Handle interruptions (resume capability)

5. **Return YouTube URL**
   - Save to `output/transcriptions/{video_id}_meta.json`
   - Print: "Uploaded: https://youtube.com/watch?v=..."

### Output
- YouTube video URL
- Updated metadata JSON

### Error Handling
- Missing video file: clear error message
- API quota exceeded: inform user, save progress
- Network interruption: auto-resume upload
- Authentication failure: re-run OAuth flow

## Slash Command 2: /youtube-upload

### Configuration
File: `.claude/commands/youtube-upload.json`

### Trigger
```bash
/youtube-upload <video_id>
```

### Instructions for Claude

1. **Verify prerequisites**
   - Check if `output/transcriptions/{video_id}_meta.json` exists
   - Check if MP4 file exists at saved path
   - Check if recap exists

2. **Execute upload**
   ```bash
   python scripts/upload_to_youtube.py --video-id <video_id>
   ```

3. **Monitor progress**
   - Show upload progress to user
   - Estimated time remaining

4. **On completion**
   - Display YouTube URL
   - Save URL to recap file (as footer)
   - Confirm: "Upload complete! Video is live/unlisted at: [URL]"

## Configuration Files

### config.yaml
```yaml
openai:
  api_key: ${OPENAI_API_KEY}
  model: "gpt-4o-transcribe"
  
audio:
  bitrate: 64  # kbps
  sample_rate: 16000  # Hz
  channels: 1  # mono
  max_chunk_size_mb: 24  # under 25MB limit
  
youtube:
  default_category: 20  # Gaming
  default_privacy: "unlisted"
  default_tags: ["Stream", "Recap", "Transcription"]
  
paths:
  downloads: "output/downloads"
  audio: "output/audio"
  transcriptions: "output/transcriptions"
  recaps: "output/recaps"
```

### YouTube API Setup
Google Cloud Console requirements:
1. Create project
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `youtube_secrets.json` to `config/`
5. Add scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`

## Dependencies (requirements.txt)
```
yt-dlp>=2024.1.0
openai>=1.12.0
google-api-python-client>=2.115.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
pyyaml>=6.0
tqdm>=4.66.0
```

System dependencies:
- ffmpeg (must be in PATH)

## Recap Instructions Template

File: `prompts/recap_instructions.md`

**User to provide:**
- Formatting rules
- Section structure
- Tone/style guidelines
- What to include/exclude
- Example outputs

## User Flow

### Main Workflow
```
User: /video-recap https://twitch.tv/videos/12345

Claude:
1. Downloading video...
2. Converting to audio...
3. Transcribing (chunk 1/3)...
4. Transcribing (chunk 2/3)...
5. Transcribing (chunk 3/3)...
6. Generating recap...
7. Verifying accuracy...
8. Corrections made: 2 timestamps fixed
9. ✓ Complete!

Recap saved: output/recaps/12345_recap.md
Ready for YouTube? Run: /youtube-upload 12345
```

### Upload Workflow
```
User: /youtube-upload 12345

Claude:
1. Loading video metadata...
2. Authenticating with YouTube...
3. Uploading video (3.2 GB)...
   [████████████████░░░░] 82% - 5 min remaining
4. Processing on YouTube...
5. ✓ Upload complete!

Video URL: https://youtube.com/watch?v=abc123xyz
Status: Unlisted
```

## Supported Platforms

yt-dlp supports 1000+ sites including:
- Twitch (VODs and clips)
- YouTube (videos, live streams, shorts)
- Twitter/X (video posts)
- Vimeo
- Facebook
- Instagram (Reels, IGTV)
- TikTok
- Reddit (video posts)
- And many more...

## Success Criteria

### Script 1 Success
- ✅ Downloads from any yt-dlp supported platform
- ✅ Handles videos 10 min - 10 hours
- ✅ Transcription accuracy >95%
- ✅ Properly chunks files >25MB
- ✅ Completes in <10 min for 1hr video (excluding download)

### Slash Command Success
- ✅ Claude generates well-formatted recap
- ✅ Verification catches >90% of errors
- ✅ Final output matches user's prompt requirements
- ✅ All files saved to correct locations

### Script 2 Success
- ✅ Successfully authenticates with YouTube
- ✅ Uploads files up to 10GB
- ✅ Handles network interruptions
- ✅ Sets correct metadata from recap

## Future Enhancements (Optional)
- Batch processing multiple URLs
- Custom thumbnail generation
- Automatic chapter markers from recap
- Platform-specific optimizations
- Webhook notifications on completion
- Web UI for monitoring

## Security Notes
- Never commit `youtube_secrets.json`
- Never commit `.env` with API keys
- Add to `.gitignore`:
  ```
  config/youtube_secrets.json
  config/.youtube_token.json
  .env
  output/downloads/
  output/audio/
  ```