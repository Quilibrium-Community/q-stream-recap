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

### Quilibrium Glossary

These terms frequently appear in Quilibrium content. Use this reference to correct transcription errors:

| Term | Description | Common Misspellings |
|------|-------------|---------------------|
| **Quilibrium** | The project name | Equilibrium, Calibrium, Quillibrium |
| **QUIL** | Native token | Quill, Kill, Kwil |
| **wQUIL** | Wrapped QUIL (ERC-20) | w-Quil, wrapped Quil |
| **QStorage** | Decentralized storage service | Q Storage, Queue Storage |
| **QQ** | SQS-style queue service | Q-Q, Cue Cue |
| **QPing** | SNS-style notification service | Q Ping, Cuping |
| **QKMS** | Quilibrium Key Management Service | Q-KMS, QK MS |
| **Quorum** | Consensus mechanism | Quorom, Corum |
| **QNS** | Quilibrium Name Service | Q-NS, QNess |
| **Quark** | SDK for tokenizable 3D assets/game integration | Cork, Quart, Clark |
| **QConsole** | Web console/dashboard for Q services | Q Console, Cue Console |
| **HyperSnap** | Farcaster protocol fork | Hyper Snap, Hypersnap |
| **Klearu** | MPC machine learning framework and runtime | Claro, Clairo, Clear-o |
| **MetaVM** | Zero-knowledge RISC-V VM | Meta VM, Meta-VM |
| **MegaRPC** | Privacy-preserving RPC service | Mega RPC, mega RPC |
| **Ferret** | MPC garbled circuit library | Feret, Farret |
| **QClient** | Quilibrium client tool | Q Client, Cue Client |
| **Neynar** | Farcaster API/infrastructure company | Nadar, Nader, Naynar |
| **Merkle** (Manufactory) | Original Farcaster development company | Merkel, Merkyl |
| **Q Inc.** / **Quilibrium, Inc.** | The company | QInk, Q Ink, Quink |
| **a16z** | Andreessen Horowitz (VC firm) | 16Zs, A16Z, a16Zs |
| **Cassandra Heart** | Founder (@cass_on_mars) | Sandra Heart |

When writing the recap, always use the correct spelling from this glossary.

Save the recap to: `output/recaps/{file_prefix}_recap.md`

## Step 4: Verification Agent

Launch a verification agent to compare the recap against the raw transcript.

### Part A: Transcript Consistency Check

The agent must check for:
1. **Factual accuracy** - Are all claims in the recap supported by the transcript?
2. **Completeness** - Are any major topics or announcements missing?
3. **Correct attributions** - Are quotes and statements attributed correctly?
4. **No hallucinations** - Is there anything in the recap not in the transcript?

### Part B: Transcription Error Detection

**Important context**: The recap is derived from an audio transcription of a video. Speech-to-text can mishear uncommon words, technical terms, and proper nouns.

The agent must identify and verify:
1. **Technical terminology** - Programming languages, frameworks, protocols, algorithms
2. **Company/product names** - Especially lesser-known projects, startups, crypto projects
3. **People's names** - Contributors, developers, public figures mentioned
4. **Mathematical formulas or numbers** - Statistics, percentages, token amounts, dates
5. **Code snippets or commands** - Syntax that may have been misheard
6. **Acronyms and abbreviations** - Industry-specific terms

For each suspicious or technical term found:
- Use web search to verify correct spelling and context
- Cross-reference with your own knowledge
- Check if the transcribed term makes sense in context (e.g., "equilibrium" should likely be "Quilibrium")

Common transcription errors to watch for:
- Homophones (their/there, affect/effect)
- Technical terms phonetically similar to common words
- Project names that sound like regular words
- Numbers that could be misheard (15 vs 50, million vs billion)

### Corrections

If errors are found:
- Correct them directly in the recap file
- Note what was corrected and why (transcription error vs recap error)

## Step 5: Present for Human Verification

Display to the user:
1. The final recap content
2. A summary of any corrections made during verification
3. The file location: `output/recaps/{file_prefix}_recap.md`
4. Next steps: "Ready for YouTube upload? Run `/Q:youtube-upload`"

Wait for user approval before proceeding to Step 6.

## Step 6: Generate Short Version

After the user approves the full recap, create a shorter version for Discord/Telegram channels.

### Short Version Format:

```
Hey @everyone,
Here is a summary of the latest live stream.

✨ [TITLE]
[Short description - same as full recap]


✅ Key topics:
⦿ [Topic 1]
⦿ [Topic 2]
⦿ [Topic 3]
⦿ [Topic 4]


👉 Read the full summary:

▶️ Watch it on YouTube (English captions):
▶️ Watch it on X:
```

### Differences from Full Recap:
- Opening: "Hey @everyone," instead of "Hey Q fam! Here is a summary of the latest live stream with @cass_on_mars (@QuilibriumInc founder)."
- Remove all detailed section content (everything after "Key topics")
- Add "👉 Read the full summary:" placeholder before the video links
- Move YouTube/X links to the end

Save the short version to: `output/recaps/{file_prefix}_recap_short.md`

Display both file locations to the user:
- Full recap: `output/recaps/{file_prefix}_recap.md`
- Short version: `output/recaps/{file_prefix}_recap_short.md`
