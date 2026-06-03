#!/usr/bin/env python3
"""
fill_examples.py — Populate TODO example sentences in da-en entries from Tatoeba.

Usage:
    python scripts/fill_examples.py [--dry-run]

Reads data/tatoeba_da_en_pairs.parquet (columns: sentence_id, text_da, translation_id, text_en).
For each entries/da-en/*.md that contains "danish: TODO", searches Tatoeba for the headword
and replaces the placeholder block with real sentence pairs.
Writes updated files in-place.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "entries" / "da-en"
PARQUET_PATH = ROOT / "data" / "tatoeba_da_en_pairs.parquet"

MAX_DA_CHARS = 120   # discard Danish sentences longer than this
MAX_EXAMPLES = 2     # how many examples to inject per entry

# Exact placeholder block as written by the pipeline
TODO_BLOCK = (
    "  - danish: TODO\n"
    "    english: TODO\n"
    "    source: manual\n"
    "    source_id: SKIP"
)

# Danish-aware "word boundary" — exclude alphanumeric and Danish letters on either side
_DA_ALPHA = "a-zA-ZæøåÆØÅ"
_WB_START = f"(?<![{_DA_ALPHA}0-9])"
_WB_END   = f"(?![{_DA_ALPHA}0-9])"


def yaml_safe(text: str) -> str:
    """Return text safe for a YAML plain scalar on a single line.

    If the text contains characters that need quoting, wraps in double quotes.
    """
    text = text.strip()
    # Characters that require YAML quoting when starting a plain scalar or mid-value
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_block(rows: list[tuple[int, str, str]]) -> str:
    """Build YAML example block lines from a list of (da_id, da_text, en_text)."""
    parts = []
    for da_id, da_text, en_text in rows:
        parts.append(f"  - danish: {yaml_safe(da_text)}")
        parts.append(f"    english: {yaml_safe(en_text)}")
        parts.append(f"    source: tatoeba")
        parts.append(f"    source_id: {da_id}")
    return "\n".join(parts)


def find_examples(
    headword: str,
    text_da: "pd.Series",
    sent_id: "pd.Series",
    text_en: "pd.Series",
) -> list[tuple[int, str, str]]:
    """Return up to MAX_EXAMPLES (da_id, da_text, en_text) tuples.

    Uses a start-only word boundary so that inflected forms (dage, åbningen, …)
    and end-compounds are matched, while the headword cannot appear as a suffix
    of another word (e.g. 'dag' won't match inside 'adgang').
    """
    hw_escaped = re.escape(headword)
    pattern = re.compile(_WB_START + hw_escaped, re.IGNORECASE)

    mask = text_da.str.contains(pattern, regex=True, na=False)
    if not mask.any():
        return []

    # Length filter
    lengths = text_da.str.len()
    mask = mask & (lengths <= MAX_DA_CHARS)
    if not mask.any():
        return []

    candidates = sorted(
        zip(sent_id[mask], text_da[mask], text_en[mask]),
        key=lambda t: len(t[1]),
    )

    seen_ids: set[int] = set()
    result: list[tuple[int, str, str]] = []
    for sid, da, en in candidates:
        sid_int = int(sid)
        if sid_int in seen_ids:
            continue
        seen_ids.add(sid_int)
        result.append((sid_int, str(da), str(en)))
        if len(result) >= MAX_EXAMPLES:
            break
    return result


def process_file(
    path: Path,
    text_da: "pd.Series",
    sent_id: "pd.Series",
    text_en: "pd.Series",
    dry_run: bool,
) -> str:
    """Process one entry file. Returns 'filled' | 'not-found' | 'skipped'."""
    content = path.read_text(encoding="utf-8")
    if TODO_BLOCK not in content:
        return "skipped"

    # Extract headword
    m = re.search(r"^headword:\s*(.+)$", content, re.MULTILINE)
    if not m:
        return "skipped"
    headword = m.group(1).strip()
    if not headword or headword.upper() == "TODO":
        return "skipped"

    rows = find_examples(headword, text_da, sent_id, text_en)
    if not rows:
        return "not-found"

    new_block = build_block(rows)
    new_content = content.replace(TODO_BLOCK, new_block, 1)

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return "filled"


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill TODO example sentences from Tatoeba")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing any files")
    args = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas is required — run: pip install pandas pyarrow")

    print("Loading Tatoeba pairs …", flush=True)
    df = pd.read_parquet(PARQUET_PATH)
    print(f"  {len(df):,} DA–EN pairs loaded", flush=True)

    text_da = df["text_da"]
    sent_id = df["sentence_id"]
    text_en = df["text_en"]

    files = sorted(ENTRIES_DIR.glob("*.md"))
    counts: dict[str, int] = {"filled": 0, "not-found": 0, "skipped": 0}
    not_found_words: list[str] = []

    for path in files:
        result = process_file(path, text_da, sent_id, text_en, dry_run=args.dry_run)
        counts[result] += 1
        if result == "not-found":
            content = path.read_text(encoding="utf-8")
            m = re.search(r"^headword:\s*(.+)$", content, re.MULTILINE)
            hw = m.group(1).strip() if m else path.stem
            not_found_words.append(hw)

    mode = " [DRY RUN — no files written]" if args.dry_run else ""
    print(f"\nResults{mode}:")
    print(f"  Filled:     {counts['filled']:>4}")
    print(f"  Not found:  {counts['not-found']:>4}  (Tatoeba has no match)")
    print(f"  Skipped:    {counts['skipped']:>4}  (already filled or no headword)")

    if not_found_words:
        print(f"\nWords with no Tatoeba match ({len(not_found_words)}):")
        for hw in not_found_words[:60]:
            print(f"  {hw}")
        if len(not_found_words) > 60:
            print(f"  … and {len(not_found_words) - 60} more")


if __name__ == "__main__":
    main()
