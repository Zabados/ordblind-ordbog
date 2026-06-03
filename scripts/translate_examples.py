"""
translate_examples.py
---------------------
Fills `english: TODO` in example sentences that have `source: leipzig`.
Uses the free MyMemory translation API (no key required, 1000 req/day).

Usage:
    python scripts/translate_examples.py [--throttle SECONDS] [--dry-run]
"""

import argparse
import re
import time
from pathlib import Path

import requests

API_URL = "https://api.mymemory.translated.net/get"
HEADERS = {"User-Agent": "ordbog-dict-pipeline/1.0 (educational; contact: ordbog@example.com)"}

ENTRY_DIRS = [Path("entries/da-en"), Path("entries/en-da")]


def translate(text: str, throttle: float) -> str | None:
    """Call MyMemory and return the English translation, or None on failure."""
    try:
        r = requests.get(
            API_URL,
            params={"q": text, "langpair": "da|en"},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        translated = data.get("responseData", {}).get("translatedText", "")
        status = data.get("responseStatus", 0)
        if status == 200 and translated:
            return translated.strip()
        return None
    except Exception:
        return None
    finally:
        time.sleep(throttle)


def process_file(path: Path, dry_run: bool, throttle: float) -> int:
    """Translate all `english: TODO` in Leipzig examples. Returns count filled."""
    text = path.read_text(encoding="utf-8")
    if "english: TODO" not in text:
        return 0

    # Find examples block and only translate Leipzig ones
    filled = 0

    def replace_todo(m: re.Match) -> str:
        nonlocal filled
        block = m.group(0)
        # Only touch Leipzig-sourced examples
        if "source: leipzig" not in block:
            return block
        # Extract danish sentence
        da_match = re.search(r"danish:\s*(.+)", block)
        if not da_match:
            return block
        danish_text = da_match.group(1).strip()
        translation = translate(danish_text, throttle)
        if not translation:
            return block
        filled += 1
        return block.replace("english: TODO", f"english: {translation}", 1)

    # Match each example item (from "- danish:" to next "- danish:" or end of examples block)
    new_text = re.sub(
        r"- danish:.*?(?=\n\s*- danish:|\nexamples:|\n```|\Z)",
        replace_todo,
        text,
        flags=re.DOTALL,
    )

    if filled > 0 and not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return filled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--throttle", type=float, default=0.5,
                        help="Seconds between API calls (default 0.5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be translated without writing files")
    args = parser.parse_args()

    # Collect files that need work
    todo_files = []
    for d in ENTRY_DIRS:
        for p in sorted(d.glob("*.md")):
            t = p.read_text(encoding="utf-8")
            if "english: TODO" in t and "source: leipzig" in t:
                todo_files.append(p)

    print(f"{len(todo_files)} entries with untranslated Leipzig examples")
    if args.dry_run:
        print("(dry-run — no files will be written)")

    total_filled = 0
    for i, path in enumerate(todo_files, 1):
        n = process_file(path, dry_run=args.dry_run, throttle=args.throttle)
        total_filled += n
        if i % 20 == 0 or i == len(todo_files):
            print(f"  {i}/{len(todo_files)} …  ({total_filled} translated so far)")

    print(f"\nDone. Translated {total_filled} example sentences.")


if __name__ == "__main__":
    main()
