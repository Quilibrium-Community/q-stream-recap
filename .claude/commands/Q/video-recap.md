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
- Transcribe via the configured backend (Groq Whisper by default, OpenAI as fallback)
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
4. What happens next, in one line: "Reply 'approved' and I publish everything: GitHub page, tweet and chat texts, YouTube upload (unlisted)."

Then STOP and wait. If the user asks for changes, edit the plain recap, re-run the checks that apply, and ask again.

**The user's approval of the recap is the go-ahead for Steps 6 to 9.** They asked (2026-11-21) that everything be ready after the recap is approved, so do not ask again at each step. The approval covers exactly this and nothing more:
- one commit and push to `main` of the recap files listed in Step 6
- one YouTube upload of this video as **unlisted**
- one final commit and push of the short texts and metadata listed in Step 9

It does not cover posting on X, Discord or Telegram, making the video public, or committing any other file. If a step fails, stop and report the error. Do not improvise a workaround and do not retry a publish blindly: check whether it took effect first.

## Step 6: Publish the Full Recap on GitHub

X no longer allows long-form posts, so the full recap is published as a file in this public repo (`Quilibrium-Community/q-stream-recap`). GitHub renders Markdown as a formatted page, so people read it there. Every short version links to it, so it must be online before the short versions are written.

The plain recap cannot be linked directly: GitHub collapses its single line breaks and shows the emoji markers as plain text. Generate a real Markdown version first:

```bash
cd d:\GitHub\Quilibrium\q-stream-recap && python scripts/recap_to_web.py output/recaps/{file_prefix}_recap.md
```

Output: `output/recaps/{file_prefix}_recap_web.md`. The script maps the emoji markers onto headings, lists and clickable links, and never modifies the original recap. Do not hand-edit the web file: fix the plain recap and run the script again. The YouTube and X lines are empty at this point, and the script drops lines without a URL, so its warning about them is expected.

Commit and push exactly these files, and no others (stage them by name, never `git add -A`):
- `output/recaps/{file_prefix}_recap.md`
- `output/recaps/{file_prefix}_recap_web.md`
- `output/transcriptions/{file_prefix}_transcript.txt`
- `output/transcriptions/{file_prefix}_meta.json`

Commit message: short, lowercase, in the style of the repo history (for example `add recap for the 2026-11-21 livestream`). No mention of Claude or AI and no co-author line. Push to `main`. Then check the page is online:

```bash
curl -s -o /dev/null -w "%{http_code}" https://github.com/Quilibrium-Community/q-stream-recap/blob/main/output/recaps/{file_prefix}_recap_web.md
```

It must print `200`. GitHub can take a few seconds, so retry up to 5 times, 10 seconds apart. If it still fails, stop and report. Do not write the short versions with a link that does not work.

The full recap link, used by everything below:
`https://github.com/Quilibrium-Community/q-stream-recap/blob/main/output/recaps/{file_prefix}_recap_web.md`

## Step 7: Generate the Short Versions

Only after Step 6 is done and the page returns 200. Write two short versions. Both contain the GitHub link from Step 6. The YouTube link is filled in Step 8. The X watch link is not known yet: leave its line empty, the user adds it by hand.

### 7a. Tweet (super short)

For X. It must fit in a single tweet, 280 characters, with the GitHub link inside the count.

```
✨ [TITLE]

[One short hook line]

⦿ [Topic 1]
⦿ [Topic 2]
⦿ [Topic 3]

📖 Full recap: [GitHub link]
```

Rules:
- Use at most 3 topics, as short as possible. Cut topics before cutting the link.
- No hashtags, no @mentions unless they fit with room to spare.
- X counts every URL as 23 characters, and emoji as 2.

Save to `output/recaps/{file_prefix}_recap_tweet.md`, then check the length:

```bash
cd d:\GitHub\Quilibrium\q-stream-recap && python scripts/check_tweet.py output/recaps/{file_prefix}_recap_tweet.md
```

If it prints `TOO LONG`, shorten the text and check again until it prints `OK`.

### 7b. Discord and Telegram (slightly longer)

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


👉 Read the full summary: [GitHub link]

▶️ Watch it on YouTube (English captions):
▶️ Watch it on X:
```

Differences from the full recap:
- Opening: "Hey @everyone," instead of "Hey Q fam! Here is a summary of the latest live stream with @cass_on_mars (@QuilibriumInc founder)."
- Remove all detailed section content (everything after "Key topics")
- "👉 Read the full summary:" is followed by the GitHub link
- YouTube/X lines stay at the end

Keep it under 2000 characters (the Discord message limit). Save to `output/recaps/{file_prefix}_recap_short.md`. Keep this file name and format exactly: `scripts/upload_to_youtube.py` reads it to build the YouTube description, which therefore contains the short recap and the GitHub link.

## Step 8: Upload to YouTube

Follow `/Q:youtube-upload` Steps 2 and 3, with one change: do not wait for title approval. Generate the title by its rules (under 100 characters, ending with `- Live Stream with Cassandra Heart`), use it, and report it at the end. The upload is unlisted (the config default); never change it to public. Run:

```bash
cd d:\GitHub\Quilibrium\q-stream-recap && python scripts/upload_to_youtube.py --title "<title>"
```

The description comes from `_recap_short.md`, so it holds the short recap and the GitHub link. If authentication fails (expired token, browser sign-in needed), stop and tell the user. That needs them.

On success, read `youtube_url` from `output/transcriptions/{file_prefix}_meta.json` and put it on the `▶️ Watch it on YouTube (English captions):` line of `_recap_short.md`. The uploaded description is not changed by this edit, and does not need to be: the script drops the watch lines from it.

## Step 9: Hand Over

Make the final commit and push to `main`, again staging by name: `output/recaps/{file_prefix}_recap_tweet.md`, `output/recaps/{file_prefix}_recap_short.md`, `output/transcriptions/{file_prefix}_meta.json` (it now holds the YouTube URL). Same commit style as Step 6.

Then show the user, ready to copy:
1. The tweet text, with its length.
2. The Discord/Telegram text.
3. The links: GitHub page, YouTube video (unlisted), and the title that was used.

List what is still manual:
1. Post the tweet on X.
2. After the stream video is on X, add its link to the `▶️ Watch it on X:` line of `_recap_short.md` before posting on Discord and Telegram.
3. Make the YouTube video public if wanted.
