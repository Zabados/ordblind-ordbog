#!/usr/bin/env python3
"""
fill_examples_news.py — Fill TODO example sentences using the Leipzig Danish news corpus.

Finds matching sentences from dan_news_2020_1M-sentences.txt (inside the
downloaded tar.gz), then auto-translates the Danish sentence to English via
the free MyMemory API (https://mymemory.translated.net).

Usage:
    python scripts/fill_examples_news.py [--dry-run] [--no-translate]

Options:
    --dry-run       Show what would change without writing files.
    --no-translate  Skip translation; set english field to TODO.

MyMemory free tier: 1,000 words/day without a key.
With --email flag you can add: --email you@example.com  (raises limit to 10K/day)
"""

from __future__ import annotations

import argparse
import re
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "entries" / "da-en"
TARBALL     = ROOT / "data" / "dan_news_2020_1M.tar.gz"
SENTENCES_MEMBER = "dan_news_2020_1M/dan_news_2020_1M-sentences.txt"

MAX_DA_CHARS = 110   # slightly tighter than Tatoeba — news sentences can be long
TODO_BLOCK = (
    "  - danish: TODO\n"
    "    english: TODO\n"
    "    source: manual\n"
    "    source_id: SKIP"
)

_DA_ALPHA   = "a-zA-ZæøåÆØÅ"
_WB_START   = f"(?<![{_DA_ALPHA}0-9])"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"


# ---------------------------------------------------------------------------
# Load corpus
# ---------------------------------------------------------------------------

def load_sentences() -> list[str]:
    """Read Danish sentences from the Leipzig tar.gz, pre-filtered to MAX_DA_CHARS.

    Returns a list of sentence strings sorted shortest-first.
    """
    print(f"Loading Leipzig sentences from {TARBALL.name} …", flush=True)
    sentences: list[str] = []
    with tarfile.open(TARBALL, "r:gz") as tf:
        fobj = tf.extractfile(SENTENCES_MEMBER)
        assert fobj is not None, f"Member not found: {SENTENCES_MEMBER}"
        for raw in fobj:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            parts = line.split("\t", 1)
            if len(parts) == 2:
                sent = parts[1]
                if len(sent) <= MAX_DA_CHARS:
                    sentences.append(sent)
    # Sort shortest-first so we always find the most compact example
    sentences.sort(key=len)
    print(f"  {len(sentences):,} sentences ≤{MAX_DA_CHARS} chars loaded", flush=True)
    return sentences


# ---------------------------------------------------------------------------
# Search — single-pass, all headwords at once
# ---------------------------------------------------------------------------

def build_index(
    headwords: list[str],
    sentences: list[str],
) -> dict[str, str | None]:
    """Single-pass scan: find the shortest sentence for each headword.

    Uses fast Python `str.__contains__` as a pre-filter before applying
    the word-boundary regex. Stops early for each headword once a match
    is found (sentences are already sorted shortest-first).
    """
    patterns = {
        hw: re.compile(_WB_START + re.escape(hw), re.IGNORECASE)
        for hw in headwords
    }
    best: dict[str, str | None] = {hw: None for hw in headwords}
    remaining = set(headwords)

    for sent in sentences:
        if not remaining:
            break
        sent_lower = sent.lower()
        for hw in list(remaining):
            if hw.lower() in sent_lower:          # fast pre-filter
                if patterns[hw].search(sent):     # boundary check
                    best[hw] = sent
                    remaining.discard(hw)

    return best


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def translate_da_en(text: str, email: str | None = None) -> str | None:
    """Translate Danish → English via MyMemory free API.

    Returns translated string or None on error.
    """
    try:
        import requests
    except ImportError:
        return None

    params: dict = {
        "q": text,
        "langpair": "da|en",
        "mt": "1",
    }
    if email:
        params["de"] = email

    try:
        resp = requests.get(MYMEMORY_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # MyMemory returns responseStatus 200 on success
        if data.get("responseStatus") == 200:
            translation = data["responseData"]["translatedText"]
            # MyMemory sometimes returns "PLEASE SELECT TWO DISTINCT LANGUAGES"
            if translation and len(translation) > 5 and "PLEASE SELECT" not in translation:
                return translation
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# YAML helper
# ---------------------------------------------------------------------------

def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


# ---------------------------------------------------------------------------
# Process files
# ---------------------------------------------------------------------------

def process_file(
    path: Path,
    sentence_index: dict[str, str | None],
    translate: bool,
    email: str | None,
    dry_run: bool,
    throttle: float,
) -> str:
    """Returns 'filled' | 'not-found' | 'no-translation' | 'skipped'."""
    content = path.read_text(encoding="utf-8")
    if TODO_BLOCK not in content:
        return "skipped"

    m = re.search(r"^headword:\s*(.+)$", content, re.MULTILINE)
    if not m:
        return "skipped"
    headword = m.group(1).strip()
    if not headword or headword.upper() == "TODO":
        return "skipped"

    da_sent = sentence_index.get(headword)
    if da_sent is None:
        return "not-found"

    if translate:
        en_sent = translate_da_en(da_sent, email=email)
        if throttle:
            time.sleep(throttle)
        if en_sent is None:
            en_sent = "TODO"
            result = "no-translation"
        else:
            result = "filled"
    else:
        en_sent = "TODO"
        result = "filled"

    block = (
        f"  - danish: {yaml_safe(da_sent)}\n"
        f"    english: {yaml_safe(en_sent)}\n"
        f"    source: leipzig\n"
        f"    source_id: SKIP"
    )
    new_content = content.replace(TODO_BLOCK, block, 1)
    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Fill TODO examples from Leipzig news corpus")
    ap.add_argument("--dry-run",     action="store_true", help="Preview without writing")
    ap.add_argument("--no-translate", action="store_true", help="Skip MyMemory translation")
    ap.add_argument("--email",       default=None, help="Email for MyMemory (raises free limit to 10K/day)")
    ap.add_argument("--throttle",    type=float, default=0.5,
                    help="Seconds between translation requests (default 0.5)")
    args = ap.parse_args()

    # Collect all headwords that still need examples
    files = sorted(ENTRIES_DIR.glob("*.md"))
    todo: dict[str, Path] = {}  # headword -> path
    for path in files:
        content = path.read_text(encoding="utf-8")
        if TODO_BLOCK not in content:
            continue
        m = re.search(r"^headword:\s*(.+)$", content, re.MULTILINE)
        if m:
            hw = m.group(1).strip()
            if hw and hw.upper() != "TODO":
                todo[hw] = path

    print(f"{len(todo)} entries still have TODO examples", flush=True)
    if not todo:
        print("Nothing to do.")
        return

    sentences = load_sentences()

    print("Building sentence index …", flush=True)
    index = build_index(list(todo.keys()), sentences)
    found = sum(1 for v in index.values() if v is not None)
    print(f"  Matched {found}/{len(todo)} headwords", flush=True)

    counts: dict[str, int] = {
        "filled": 0, "not-found": 0,
        "no-translation": 0, "skipped": 0,
    }
    not_found: list[str] = []

    for hw, path in todo.items():
        # Re-read in case a previous fill already updated the file
        content = path.read_text(encoding="utf-8")
        if TODO_BLOCK not in content:
            counts["skipped"] += 1
            continue
        da_sent = index.get(hw)
        if da_sent is None:
            counts["not-found"] += 1
            not_found.append(hw)
            continue

        if not args.no_translate:
            en_sent = translate_da_en(da_sent, email=args.email)
            if args.throttle:
                time.sleep(args.throttle)
            if en_sent is None:
                en_sent = "TODO"
                counts["no-translation"] += 1
            else:
                counts["filled"] += 1
        else:
            en_sent = "TODO"
            counts["filled"] += 1

        block = (
            f"  - danish: {yaml_safe(da_sent)}\n"
            f"    english: {yaml_safe(en_sent)}\n"
            f"    source: leipzig\n"
            f"    source_id: SKIP"
        )
        new_content = content.replace(TODO_BLOCK, block, 1)
        if not args.dry_run:
            path.write_text(new_content, encoding="utf-8")

    mode = " [DRY RUN]" if args.dry_run else ""
    print(f"\nResults{mode}:")
    print(f"  Filled:          {counts['filled']:>4}")
    print(f"  No translation:  {counts['no-translation']:>4}")
    print(f"  Not found:       {counts['not-found']:>4}  (word not in Leipzig news corpus)")
    print(f"  Skipped:         {counts['skipped']:>4}  (already had examples)")

    if not_found:
        print(f"\nWords not found in Leipzig corpus ({len(not_found)}):")
        for hw in not_found[:40]:
            print(f"  {hw}")
        if len(not_found) > 40:
            print(f"  … and {len(not_found) - 40} more")


if __name__ == "__main__":
    main()
