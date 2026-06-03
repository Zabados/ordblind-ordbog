"""
fix_pos_ordnet.py
-----------------
Fills pos:TODO and gender:TODO fields by scraping Den Danske Ordbog (ordnet.dk).
Handles Danish headwords with special characters (ø, å, æ etc.) correctly.

Usage:
    python scripts/fix_pos_ordnet.py [--throttle SECONDS] [--dry-run]
"""

import argparse
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "ordbog-dict-pipeline/1.0 (educational DA-EN dictionary; contact: ordbog@example.com)"
}
BASE_URL = "https://ordnet.dk/ddo/ordbog"

ENTRY_DIRS = [Path("entries/da-en")]   # Only DA entries; EN entries use English Wiktionary

POS_MAP = {
    "substantiv":   "noun",
    "verbum":       "verb",
    "adjektiv":     "adjective",
    "adverbium":    "adverb",
    "pronomen":     "pronoun",
    "præposition":  "preposition",
    "konjunktion":  "conjunction",
    "interjektion": "interjection",
    "udråbsord":    "interjection",
    "talord":       "adjective",
    "partikel":     "adverb",
    "forkortelse":  None,   # skip abbreviations
    "forkortet":    None,
}

GENDER_MAP = {
    "fælleskøn":           "en",
    "fælles- og intetkøn": "en",   # both genders → use common
    "intetkøn":            "et",
}


def fetch_ordnet(word: str) -> str | None:
    """Fetch ordnet.dk page text for a word. Returns page text or None."""
    try:
        r = requests.get(BASE_URL, params={"query": word}, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def parse_pos_gender(html: str, word: str) -> tuple[str | None, str | None]:
    """
    Parse POS and gender from ordnet.dk HTML.
    Returns (pos, gender) — either may be None if not found/applicable.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    # The article starts with: WORD  ordklasse [, køn]
    # e.g. "ansvar substantiv , intetkøn"
    # Try to find the pattern near the headword
    pattern = re.compile(
        r'\b' + re.escape(word) + r'\b'
        r'[\s\u00a0]+'
        r'(' + '|'.join(POS_MAP.keys()) + r')'
        r'(?:[\s,]+(' + '|'.join(re.escape(k) for k in GENDER_MAP.keys()) + r'))?',
        re.IGNORECASE
    )
    m = pattern.search(text)
    if not m:
        return None, None

    raw_pos = m.group(1).lower()
    raw_gender = m.group(2).lower() if m.group(2) else None

    pos    = POS_MAP.get(raw_pos)
    gender = GENDER_MAP.get(raw_gender) if raw_gender else None

    return pos, gender


def patch_field(content: str, field: str, value: str) -> str:
    """Replace `field: TODO` with `field: value`."""
    return re.sub(
        rf'^({re.escape(field)}:\s*)TODO\s*$',
        rf'\g<1>{value}',
        content,
        flags=re.MULTILINE,
    )


def process_entry(path: Path, dry_run: bool, throttle: float) -> str:
    """Process one entry file. Returns outcome label."""
    text = path.read_text(encoding="utf-8")

    needs_pos    = bool(re.search(r'^pos:\s*TODO', text, re.MULTILINE))
    needs_gender = bool(re.search(r'^gender:\s*TODO', text, re.MULTILINE))

    if not needs_pos and not needs_gender:
        return "skipped"

    # Get headword
    hw_m = re.search(r'^headword:\s*(.+)', text, re.MULTILINE)
    if not hw_m:
        return "no_headword"
    word = hw_m.group(1).strip()

    html = fetch_ordnet(word)
    time.sleep(throttle)

    if not html:
        return "fetch_error"

    pos, gender = parse_pos_gender(html, word)

    if pos is None and gender is None:
        return "not_found"

    if pos is None:
        # ordnet returned gender but no parseable POS
        pass

    changed = False
    new_text = text

    if needs_pos and pos:
        new_text = patch_field(new_text, "pos", pos)
        # If pos is not noun, gender should be SKIP
        if pos != "noun":
            new_text = patch_field(new_text, "gender", "SKIP")
        changed = True

    if needs_gender and gender and pos == "noun":
        new_text = patch_field(new_text, "gender", gender)
        changed = True
    elif needs_gender and pos and pos != "noun":
        new_text = patch_field(new_text, "gender", "SKIP")
        changed = True

    if not changed:
        return "no_change"

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")

    fixed_pos    = needs_pos and pos
    fixed_gender = needs_gender and (gender or (pos and pos != "noun"))
    if fixed_pos and fixed_gender:
        return "fixed_both"
    if fixed_pos:
        return "fixed_pos"
    if fixed_gender:
        return "fixed_gender"
    return "no_change"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--throttle", type=float, default=0.3,
                        help="Seconds between requests (default 0.3)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Collect files needing work
    todo_files = []
    for d in ENTRY_DIRS:
        for p in sorted(d.glob("*.md")):
            t = p.read_text(encoding="utf-8")
            if re.search(r'^pos:\s*TODO', t, re.MULTILINE) or \
               re.search(r'^gender:\s*TODO', t, re.MULTILINE):
                todo_files.append(p)

    print(f"{len(todo_files)} entries need fixing")
    if args.dry_run:
        print("(dry-run)")

    from collections import Counter
    results: Counter = Counter()

    for i, path in enumerate(todo_files, 1):
        outcome = process_entry(path, dry_run=args.dry_run, throttle=args.throttle)
        results[outcome] += 1
        if i % 50 == 0 or i == len(todo_files):
            print(f"  {i}/{len(todo_files)} …")

    print("\nResults:")
    for k, v in sorted(results.items()):
        print(f"  {k:20s} {v}")


if __name__ == "__main__":
    main()
