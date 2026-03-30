# YouTube Upload

Upload the transcribed video to YouTube with an AI-generated title.

## Instructions

### Step 1: Find the Recap

First, find the most recent recap file in `output/recaps/`. Read it to understand the content.

```bash
ls -t d:\GitHub\Quilibrium\q-stream-recap\output\recaps\
```

Read the recap file to understand what the stream was about.

### Step 2: Generate a YouTube Title

Based on the recap content, create a compelling YouTube title that:
- Is under 100 characters
- Captures the main topic or announcement from the stream
- **Must end with**: `- Live Stream with Cassandra Heart`
- Format: `[Main Topic] - Live Stream with Cassandra Heart`
- Examples:
  - `Dawn Phase Launch & Network Updates - Live Stream with Cassandra Heart`
  - `Node Operator Guide & Rewards Explained - Live Stream with Cassandra Heart`
  - `Mainnet Timeline & Technical Deep Dive - Live Stream with Cassandra Heart`

Present the suggested title to the user for approval before proceeding.

### Step 3: Upload to YouTube

Once the title is approved, run the upload script with the title:

```bash
cd d:\GitHub\Quilibrium\q-stream-recap && python scripts/upload_to_youtube.py --title "YOUR APPROVED TITLE HERE"
```

The script will:
1. Auto-detect the most recent MP4 in `output/downloads/`
2. Load the associated metadata and recap
3. Authenticate with YouTube (opens browser first time)
4. Upload the video with:
   - The approved title
   - Description from recap content
   - Thumbnail from `config/q-livestream-yt-cover.png`
   - Tags from config + recap
   - Privacy: unlisted (default)
5. Set the custom thumbnail

### Step 4: Report Results

After upload completes, report to the user:
- The YouTube video URL
- The title used
- The privacy status (unlisted by default)
- Confirm the thumbnail was set

The YouTube URL is also automatically saved to:
- `output/transcriptions/{video_id}_meta.json`
- Appended to `output/recaps/{video_id}_recap.md`

### Step 5: Cleanup

After a successful upload, ask the user:

> "Upload complete! Do you want me to clean up the temporary files?
> - **Audio files** (MP3 + chunks in `output/audio/`): these are intermediate files from transcription and are no longer needed.
> - **Video file** (MP4 in `output/downloads/`): keeping this allows re-uploading if needed, but it's large (~3-4GB).
>
> I can delete audio only (recommended), delete both, or keep everything."

Based on the user's response:
- **Audio only** (default/recommended): delete all files matching `{file_prefix}*` in `output/audio/`
- **Both**: delete audio files AND the MP4 in `output/downloads/`
- **Keep**: do nothing

Use bash `rm` to delete the files. Always confirm what was deleted.
