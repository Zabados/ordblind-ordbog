"""
dedup_examples.py
-----------------
Removes duplicate example sentences (same Danish text) from all entry files.
When duplicates exist, keeps the one with the best source priority:
  tatoeba > wiktionary > ordnet > manual > leipzig

Usage:
    python scripts/dedup_examples.py [--dry-run]
"""

import argparse
import re
from pathlib import Path

ENTRY_DIRS = [Path("entries/da-en"), Path("entries/en-da")]

SOURCE_PRIORITY = {"tatoeba": 0, "wiktionary": 1, "ordnet": 2, "manual": 3, "leipzig": 4}


def source_rank(block: str) -> int:
    m = re.search(r"source:\s*(\S+)", block)
    if m:
        return SOURCE_PRIORITY.get(m.group(1).strip(), 99)
    return 99


def dedup_file(path: Path, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8")

    # Find the examples block (ends at closing ```)
    block_m = re.search(r"(examples:\s*\n)(.*?)(\n```)", text, re.DOTALL)
    if not block_m:
        return 0

    header = block_m.group(1)
    body   = block_m.group(2)
    closer = block_m.group(3)

    # Split into individual example items on each "  - danish:" line
    items = re.split(r"(?=  - danish:)", body)
    items = [i for i in items if i.strip()]

    # Group by Danish sentence, keep best-priority item per sentence
    seen: dict[str, str] = {}
    for item in items:
        da_m = re.search(r"danish:\s*(.+)", item)
        if not da_m:
            continue
        key = da_m.group(1).strip()
        if key not in seen or source_rank(item) < source_rank(seen[key]):
            seen[key] = item

    # Rebuild in original encounter order
    deduped = []
    added: set[str] = set()
    for item in items:
        da_m = re.search(r"danish:\s*(.+)", item)
        if not da_m:
            deduped.append(item)
            continue
        key = da_m.group(1).strip()
        if key not in added:
            deduped.append(seen[key])
            added.add(key)

    removed = len(items) - len(deduped)
    if removed == 0:
        return 0

    new_body = "".join(deduped)
    new_text = text[:block_m.start()] + header + new_body + text[block_m.end():]

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total_removed = 0
    files_changed = 0
    for d in ENTRY_DIRS:
        for p in sorted(d.glob("*.md")):
            n = dedup_file(p, dry_run=args.dry_run)
            if n:
                total_removed += n
                files_changed += 1

    label = "(dry-run) " if args.dry_run else ""
    print(f"{label}Removed {total_removed} duplicate examples from {files_changed} files.")


if __name__ == "__main__":
    main()
