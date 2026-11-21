#!/usr/bin/env python3
"""
First, mechanical cleaning pass for a Whisper transcript.

What it does (no rewriting, no summarizing):
  1. Replaces mishearings listed as "auto" in config/glossary.yaml
     (non-words like "Klaru" or "Metavium"). Safe to do mechanically.
  2. Flags mishearings listed as "check" (real words like "quill" or
     "equilibrium") with their context, because they need a human or Claude to decide.
  3. Flags digit runs that look like mangled version numbers ("21025" = 2.1.0.25).
  4. Lists words the transcript uses that appear nowhere in the Quilibrium docs
     corpus (names, products, jargon). These are the ones to verify online.

It writes:
  <prefix>_transcript_fixed.txt   transcript with the "auto" fixes applied
  <prefix>_transcript_report.txt  everything the editor must still look at

The editorial pass (sections, pronouns, filler, frontmatter) comes after this and is
done by Claude following the Quily cleaning guide. See the /Q:video-recap skill.

Usage:
    python scripts/clean_transcript.py output/transcriptions/<prefix>_transcript.txt
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_PATH = PROJECT_ROOT / "config" / "glossary.yaml"
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

MAX_CONTEXTS = 4
CONTEXT_CHARS = 60


def load_glossary(path: Path = GLOSSARY_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["terms"]


def whisper_prompt(glossary: list[dict] | None = None) -> str:
    """Vocabulary hint for Whisper: the 'prompt: true' terms, comma separated."""
    glossary = glossary if glossary is not None else load_glossary()
    terms = [t["term"] for t in glossary if t.get("prompt")]
    return ", ".join(terms) + "."


def _variant_regex(variant: str, ignore_case: bool) -> re.Pattern:
    # Whole word, with flexible whitespace for multi-word variants.
    parts = [re.escape(p) for p in variant.split()]
    body = r"\s+".join(parts)
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(rf"(?<![\w-]){body}(?![\w-])", flags)


def apply_auto(text: str, glossary: list[dict]) -> tuple[str, Counter]:
    pairs = [(v, t["term"]) for t in glossary for v in t.get("auto", [])]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)  # longest first
    counts: Counter = Counter()
    for variant, term in pairs:
        pattern = _variant_regex(variant, ignore_case=True)
        text, n = pattern.subn(term, text)
        if n:
            counts[f"{variant} -> {term}"] += n
    return text, counts


def _context(text: str, m: re.Match) -> str:
    start, end = max(0, m.start() - CONTEXT_CHARS), min(len(text), m.end() + CONTEXT_CHARS)
    return text[start:end].replace("\n", " ").strip()


def find_check(text: str, glossary: list[dict]) -> list[tuple[str, str, int, list[str]]]:
    out = []
    for t in glossary:
        for variant in t.get("check", []):
            pattern = _variant_regex(variant, ignore_case=False)
            matches = list(pattern.finditer(text))
            if matches:
                ctx = [_context(text, m) for m in matches[:MAX_CONTEXTS]]
                out.append((variant, t["term"], len(matches), ctx))
    return out


VERSION_RE = re.compile(r"(?<![\w.])(?:21\d{2,4}|210[- ]\d{2}|2\.1\.1?\d?)(?![\w.])")


def find_version_candidates(text: str) -> list[str]:
    seen, out = set(), []
    for m in VERSION_RE.finditer(text):
        if m.group(0) in seen:
            continue
        seen.add(m.group(0))
        out.append(f"{m.group(0)!r}: ...{_context(text, m)}...")
    return out


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'’-]*")


def build_vocabulary(docs_root: Path) -> set[str]:
    vocab: set[str] = set()
    for sub in ("quilibrium-official", "custom", "transcriptions", "discord"):
        base = docs_root / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.suffix.lower() in (".md", ".txt") and p.is_file():
                try:
                    vocab.update(w.lower() for w in WORD_RE.findall(p.read_text(encoding="utf-8", errors="ignore")))
                except OSError:
                    continue
    return vocab


def find_unknown_terms(text: str, vocab: set[str], glossary: list[dict]) -> list[tuple[str, int, str]]:
    known = set(vocab)
    for t in glossary:
        known.update(w.lower() for w in WORD_RE.findall(t["term"]))
    counts: Counter = Counter()
    first_ctx: dict[str, str] = {}
    for m in WORD_RE.finditer(text):
        w = m.group(0)
        low = w.lower().strip("'’-")
        if len(low) < 4 or low in known:
            continue
        # Interesting shapes only: CamelCase / inner capitals / mid-sentence Capitalized / ALLCAPS.
        inner_caps = any(c.isupper() for c in w[1:]) and not w.isupper()
        prev = text[max(0, m.start() - 2):m.start()]
        mid_sentence_cap = w[0].isupper() and not re.search(r"[.!?]\s*$", prev) and prev.strip() != ""
        if inner_caps or mid_sentence_cap or (w.isupper() and len(w) >= 4):
            counts[w] += 1
            first_ctx.setdefault(w, _context(text, m))
    return sorted(((w, n, first_ctx[w]) for w, n in counts.items()), key=lambda x: (-x[1], x[0]))


def docs_root_from_config() -> Path | None:
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        rel = cfg.get("cleaning", {}).get("quily_docs")
    except (OSError, yaml.YAMLError):
        return None
    if not rel:
        return None
    path = (PROJECT_ROOT / rel).resolve()
    return path if path.is_dir() else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("transcript", help="Path to <prefix>_transcript.txt")
    args = parser.parse_args()

    src = Path(args.transcript)
    if not src.is_file() or not src.name.endswith("_transcript.txt"):
        print("error: expected an existing *_transcript.txt file", file=sys.stderr)
        return 1

    glossary = load_glossary()
    text = src.read_text(encoding="utf-8")

    fixed, auto_counts = apply_auto(text, glossary)
    checks = find_check(fixed, glossary)
    versions = find_version_candidates(fixed)

    docs_root = docs_root_from_config()
    unknown: list[tuple[str, int, str]] | None = None
    if docs_root:
        unknown = find_unknown_terms(fixed, build_vocabulary(docs_root), glossary)

    lines = [f"Transcript: {src.name}", ""]
    lines.append(f"1. Automatic fixes applied ({sum(auto_counts.values())} replacements)")
    lines += [f"   {n:>3}x  {k}" for k, n in auto_counts.most_common()] or ["   none"]
    lines += ["", f"2. Words to check by hand ({len(checks)} kinds). Real words that may be mishearings:"]
    for variant, term, n, ctx in checks:
        lines.append(f"   '{variant}' (maybe {term}) x{n}")
        lines += [f"       ...{c}..." for c in ctx]
    if not checks:
        lines.append("   none")
    lines += ["", f"3. Possible mangled version numbers ({len(versions)})"]
    lines += [f"   {v}" for v in versions] or ["   none"]
    if unknown is None:
        lines += ["", "4. Unknown terms: SKIPPED (set cleaning.quily_docs in config/config.yaml to the Quily docs folder)"]
    else:
        lines += ["", f"4. Terms not found in the Quilibrium docs ({len(unknown)}). Verify spelling online:"]
        lines += [f"   {w} x{n}: ...{c}..." for w, n, c in unknown] or ["   none"]

    report = "\n".join(lines) + "\n"
    fixed_path = src.with_name(src.name.replace("_transcript.txt", "_transcript_fixed.txt"))
    report_path = src.with_name(src.name.replace("_transcript.txt", "_transcript_report.txt"))
    fixed_path.write_text(fixed, encoding="utf-8", newline="\n")
    report_path.write_text(report, encoding="utf-8", newline="\n")

    print(report)
    print(f"Fixed transcript: {fixed_path}")
    print(f"Report:           {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
