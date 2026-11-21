#!/usr/bin/env python3
"""
Convert a plain-text recap (emoji markers) into real Markdown that renders
well on github.com.

The plain recap uses single line breaks and emoji markers, which GitHub
collapses into one line when it renders a .md file. This script maps the
markers onto headings and lists and writes `<prefix>_recap_web.md` next to
the original. The original recap is never modified, because the YouTube
upload and the X/Discord posts still use the plain text.

Usage:
    python scripts/recap_to_web.py output/recaps/2026-11-21_2935918001_recap.md
"""

import argparse
import re
import sys
from pathlib import Path

# Handles that appear in recap headers. Linked to X so readers can click them.
HANDLE_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9_]{2,15})\b")


def link_handles(text: str) -> str:
    return HANDLE_RE.sub(lambda m: f"[@{m.group(1)}](https://x.com/{m.group(1)})", text)


def convert(plain: str) -> str:
    out: list[str] = []
    lines = plain.splitlines()
    i = 0

    def blank() -> None:
        if out and out[-1] != "":
            out.append("")

    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line:
            continue

        if line.startswith("✨"):
            blank()
            out.append("# " + line.lstrip("✨").strip())
            blank()
            # The next non-empty line is the short description.
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines) and not lines[i].lstrip().startswith(("▶️", "✅", "⦿")):
                out.append(f"*{lines[i].strip()}*")
                i += 1
            blank()
        elif line.startswith("✅"):
            blank()
            out.append("## " + line.lstrip("✅").strip().rstrip(":"))
            blank()
        elif line.startswith("⦿"):
            # A list item directly after a blank line keeps lists tight.
            if out and out[-1] != "" and not out[-1].startswith("- "):
                blank()
            out.append("- " + link_handles(line.lstrip("⦿").strip()))
        elif line.startswith("▶️"):
            # "▶️ Watch it on YouTube (English captions): https://..."
            label, _, url = line.partition(": ")
            label = label.rstrip(":").strip()
            url = url.strip()
            if url.startswith("http"):
                out.append(f"{label}: [{url}]({url})  ")
            else:
                # No URL yet. Dropped so the page has no dead label; the
                # caller is warned below.
                print(f"warning: no URL for '{label}', line skipped", file=sys.stderr)
        else:
            # Plain paragraph. Consecutive source lines (like the greeting)
            # get a hard break so they stay apart; a blank line in the source
            # starts a new paragraph.
            prev_is_text = (
                i >= 2
                and lines[i - 2].strip() != ""
                and not lines[i - 2].lstrip().startswith(("✨", "✅", "⦿", "▶️"))
            )
            if prev_is_text and out and out[-1] != "":
                out[-1] = out[-1].rstrip() + "  "
            else:
                blank()
            out.append(link_handles(line))

    # Paragraphs are separated by a blank line in the source; re-add them.
    return "\n".join(out).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("recap", help="Path to the plain recap (*_recap.md)")
    args = parser.parse_args()

    src = Path(args.recap)
    if not src.is_file() or not src.name.endswith("_recap.md"):
        print("error: expected an existing *_recap.md file", file=sys.stderr)
        return 1

    dst = src.with_name(src.name.replace("_recap.md", "_recap_web.md"))
    dst.write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    print(f"Web version: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
