#!/usr/bin/env python3
"""
Check that a tweet text fits in X's 280-character limit.

X does not count characters one by one:
- every URL counts as 23, whatever its real length
- emoji and most non-Latin characters count as 2
- the rest counts as 1

Usage:
    python scripts/check_tweet.py output/recaps/<prefix>_recap_tweet.md

Exit code 0 when it fits, 1 when it is too long.
"""

import re
import sys
from pathlib import Path

LIMIT = 280
URL_WEIGHT = 23
URL_RE = re.compile(r"https?://\S+")

# Code point ranges that X counts as weight 1 (Latin and common punctuation).
LIGHT_RANGES = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]


def char_weight(ch: str) -> int:
    cp = ord(ch)
    return 1 if any(lo <= cp <= hi for lo, hi in LIGHT_RANGES) else 2


def tweet_length(text: str) -> int:
    urls = URL_RE.findall(text)
    without_urls = URL_RE.sub("", text)
    return sum(char_weight(c) for c in without_urls) + URL_WEIGHT * len(urls)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().split("\n\n")[0], file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8").strip()
    n = tweet_length(text)
    status = "OK" if n <= LIMIT else "TOO LONG"
    print(f"{status}: {n}/{LIMIT} characters")
    return 0 if n <= LIMIT else 1


if __name__ == "__main__":
    sys.exit(main())
