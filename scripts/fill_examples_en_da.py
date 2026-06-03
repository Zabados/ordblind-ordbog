#!/usr/bin/env python3
"""
fill_examples_en_da.py — Fill TODO example sentences in en-da entries from Tatoeba.

For each entries/en-da/*.md that contains "danish: TODO", searches Tatoeba
for the PRIMARY DANISH TRANSLATION (not the English headword).

Usage:
    python scripts/fill_examples_en_da.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "entries" / "en-da"
PARQUET_PATH = ROOT / "data" / "tatoeba_da_en_pairs.parquet"

MAX_DA_CHARS = 120
MAX_EXAMPLES = 2

TODO_BLOCK = (
    "  - danish: TODO\n"
    "    english: TODO\n"
    "    source: manual\n"
    "    source_id: SKIP"
)

_DA_ALPHA = "a-zA-ZæøåÆØÅ"
_WB_START = f"(?<![{_DA_ALPHA}0-9])"
_WB_END   = f"(?![{_DA_ALPHA}0-9])"


def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_block(rows: list[tuple[int, str, str]]) -> str:
    parts = []
    for da_id, da_text, en_text in rows:
        parts.append(f"  - danish: {yaml_safe(da_text)}")
        parts.append(f"    english: {yaml_safe(en_text)}")
        parts.append(f"    source: tatoeba")
        parts.append(f"    source_id: {da_id}")
    return "\n".join(parts)


def _strip_gender(s: str) -> str:
    """Strip trailing ' (en)' / ' (et)' from a translation string."""
    return re.sub(r'\s+\((en|et)\)\s*$', '', s, flags=re.IGNORECASE).strip()


def find_examples(
    search_word: str,
    text_da: "pd.Series",
    sent_id: "pd.Series",
    text_en: "pd.Series",
) -> list[tuple[int, str, str]]:
    if not search_word or len(search_word) < 2:
        return []
    hw_escaped = re.escape(search_word)
    pattern = re.compile(_WB_START + hw_escaped, re.IGNORECASE)

    mask = text_da.str.contains(pattern, regex=True, na=False)
    if not mask.any():
        return []

    mask = mask & (text_da.str.len() <= MAX_DA_CHARS)
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
    content = path.read_text(encoding="utf-8")
    if TODO_BLOCK not in content:
        return "skipped"

    # Use primary_translation as the Danish search term
    m = re.search(r"^primary_translation:\s*(.+)$", content, re.MULTILINE)
    if not m:
        return "skipped"
    primary = _strip_gender(m.group(1).strip())
    if not primary or primary.upper() in ("TODO", "SKIP"):
        return "skipped"

    # Multi-word primaries like "i stand til" — search for the first content word
    search_word = primary.split()[0] if " " in primary else primary

    rows = find_examples(search_word, text_da, sent_id, text_en)
    if not rows:
        return "not-found"

    new_block = build_block(rows)
    new_content = content.replace(TODO_BLOCK, new_block, 1)

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return "filled"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fill TODO examples in EN->DA entries from Tatoeba"
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing files")
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

    paths = sorted(ENTRIES_DIR.glob("*.md"))
    filled = not_found = skipped = 0

    for path in paths:
        result = process_file(path, text_da, sent_id, text_en, args.dry_run)
        if result == "filled":
            filled += 1
            if args.dry_run:
                m = re.search(r"^primary_translation:\s*(.+)$",
                              path.read_text(encoding="utf-8"), re.MULTILINE)
                print(f"  [would fill] {path.name}  ({m.group(1).strip() if m else '?'})")
        elif result == "not-found":
            not_found += 1

    action = "Would fill" if args.dry_run else "Filled"
    print(f"\n{action}:     {filled}")
    print(f"Not found:  {not_found}")
    print(f"Skipped:    {skipped}  (already had examples or no primary)")


if __name__ == "__main__":
    main()
