# Video Recap Workflow

You are orchestrating a full video transcription and recap workflow. Follow these steps exactly.

## Input
The user will provide: `$ARGUMENTS` (a video URL from Twitch, YouTube, Twitter/X, etc.)

## Step 1: Download and Transcribe

Run the transcription script:

```bash
cd d:\GitHub\Quilibrium\q-stream-recap && python scripts/video_transcribe.py --url "$ARGUMENTS"
```

Wait for completion. The script will:
- Download the video using yt-dlp
- Extract and optimize audio with ffmpeg
- Chunk audio if >25MB
- Transcribe via OpenAI Whisper API
- Save files with date prefix: `YYYY-MM-DD_<video_id>`
- Output: transcript, metadata, MP4, and audio files

If the script fails, report the error and stop.

**Important**: Note the `File prefix` output from the script (e.g., `2026-02-01_abc123`). This is used for all file names.

## Step 2: Read the Transcript

After successful transcription, read:
1. The transcript file: `output/transcriptions/{file_prefix}_transcript.txt`
2. The metadata file: `output/transcriptions/{file_prefix}_meta.json`

Extract the file_prefix from the script output.

## Step 3: Generate Recap

Create a detailed recap following this exact format:

```
Hey Q fam!
Here is a summary of the latest live stream with @cass_on_mars (@QuilibriumInc founder).

✨ [TITLE]
[Short description - 2 lines max]

▶️ Watch it on YouTube (English captions):
▶️ Watch it on X:


✅ Key topics:
⦿ [Topic 1]
⦿ [Topic 2]
⦿ [Topic 3]
⦿ [Topic 4]

✅ [Section Title 1]

[Summary content...]

✅ [Section Title 2]

[Summary content...]

[Continue for all major topics...]
```

### Formatting Rules:
- Use "⦿" for bullet points
- Use "✨" for main title only
- Use "✅" for section titles
- Always leave an empty line after titles and paragraphs
- Output as plain text (no markdown code blocks in the final output)

### Content Guidelines:
- Tone: Informative, third person (not "the speaker says...")
- Project name: "Quilibrium" (transcription may misspell it)
- Speaker: Cassandra Heart (@cass_on_mars), Quilibrium founder
- Technical content: Summarize concisely
- Non-technical content: Be more detailed and specific

Save the recap to: `output/recaps/{file_prefix}_recap.md`

## Step 4: Verification Agent

Launch a verification agent to compare the recap against the raw transcript.

The agent must check for:
1. **Factual accuracy** - Are all claims in the recap supported by the transcript?
2. **Completeness** - Are any major topics or announcements missing?
3. **Correct attributions** - Are quotes and statements attributed correctly?
4. **No hallucinations** - Is there anything in the recap not in the transcript?

If errors are found:
- Correct them directly in the recap file
- Note what was corrected

## Step 5: Present for Human Verification

Display to the user:
1. The final recap content
2. A summary of any corrections made during verification
3. The file location: `output/recaps/{file_prefix}_recap.md`
4. Next steps: "Ready for YouTube upload? Run `/Q:youtube-upload`"

Wait for user approval before considering the task complete.
