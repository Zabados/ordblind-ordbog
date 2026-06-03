"""
fix_pos_remaining.py
--------------------
Second-pass POS fixer for the ~226 entries where fix_pos_ordnet.py returned not_found.
Tries two strategies in order:

  1. Ordnet.dk — looser parser: scans the full page for ordklasse keywords,
     not just adjacent to the headword. Takes the first hit.
  2. Primary-translation heuristic — checks primary_translation field:
       • starts with "to " → verb
       • "(en " or "(et " in translation → noun + gender
       • otherwise → mark as SKIP so it surfaces in audit

Usage:
    python scripts/fix_pos_remaining.py [--throttle SECONDS] [--dry-run]
"""

import argparse
import re
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "ordbog-dict-pipeline/1.0 (educational DA-EN dictionary; "
                  "contact: ordbog@example.com)"
}
BASE_URL = "https://ordnet.dk/ddo/ordbog"
ENTRIES_DIR = Path("entries/da-en")

POS_MAP = {
    "substantiv":  "noun",
    "verbum":      "verb",
    "adjektiv":    "adjective",
    "adverbium":   "adverb",
    "pronomen":    "pronoun",
    "præposition": "preposition",
    "konjunktion": "conjunction",
    "interjektion":"interjection",
    "udråbsord":   "interjection",
    "partikel":    "adverb",
}
GENDER_MAP = {
    "fælleskøn":           "en",
    "fælles- og intetkøn": "en",
    "intetkøn":            "et",
}

# Rough heuristic suffixes → noun
NOUN_SUFFIXES = (
    "-tion", "-sion", "-ling", "-ning", "-else", "-hed",
    "-skab", "-ighed", "-dom", "-eri",
)
# Rough verb suffixes
VERB_SUFFIXES = ("-ere",)


# ── Ordnet.dk with loose parser ─────────────────────────────────────────────

def fetch_ordnet(word: str) -> str | None:
    try:
        r = requests.get(BASE_URL, params={"query": word},
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def parse_loose(html: str) -> tuple[str | None, str | None]:
    """
    Scan the whole page text for the first ordklasse keyword.
    Also grab the first gender keyword if present nearby.
    Returns (pos, gender).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Try dedicated CSS classes first (ordnet uses class="bord" or similar)
    for cls in ("bord", "ordkl", "artikel-ordklasse"):
        tag = soup.find(class_=cls)
        if tag:
            raw = tag.get_text(" ", strip=True).lower()
            for dk, en in POS_MAP.items():
                if dk in raw:
                    # look for gender in same tag
                    gender = None
                    for dk_g, en_g in GENDER_MAP.items():
                        if dk_g in raw:
                            gender = en_g
                            break
                    return en, gender

    # Fall back: search full page text
    text = soup.get_text(" ", strip=True)
    lower = text.lower()

    found_pos    = None
    found_pos_idx = len(lower)
    for dk, en in POS_MAP.items():
        idx = lower.find(dk)
        if idx != -1 and idx < found_pos_idx:
            found_pos_idx = idx
            found_pos = en

    if found_pos is None:
        return None, None

    # Check for gender within 80 chars after first pos keyword
    window = lower[found_pos_idx: found_pos_idx + 80]
    gender = None
    for dk_g, en_g in GENDER_MAP.items():
        if dk_g in window:
            gender = en_g
            break

    return found_pos, gender


# ── Translation heuristics ──────────────────────────────────────────────────

def guess_from_translation(primary: str, headword: str) -> tuple[str | None, str | None]:
    """Infer pos (and optionally gender) from the primary_translation text."""
    t = primary.strip().lower()

    # Verb: translation starts with 'to '
    if t.startswith("to "):
        return "verb", None

    # Noun with explicit article in parens: "(en X)" or "(et X)"
    m = re.search(r'\(e[nt]\s+\w', t)
    if m:
        art = m.group(0)[1:3]   # 'en' or 'et'
        gender = "en" if art == "en" else "et"
        return "noun", gender

    # Suffix-based noun (Danish headword ends in noun suffix)
    hw_lower = headword.lower()
    for suf in NOUN_SUFFIXES:
        if hw_lower.endswith(suf.lstrip("-")):
            return "noun", None

    # Suffix-based verb
    for suf in VERB_SUFFIXES:
        if hw_lower.endswith(suf.lstrip("-")):
            return "verb", None

    return None, None


# ── File patching ────────────────────────────────────────────────────────────

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def patch_field(text: str, field: str, value: str) -> str:
    return re.sub(
        rf'^(\s*{re.escape(field)}:\s*)TODO\s*$',
        rf'\g<1>{value}',
        text, flags=re.MULTILINE,
    )


# ── Main processing ──────────────────────────────────────────────────────────

def process_file(path: Path, dry_run: bool, throttle: float) -> str:
    text = path.read_text(encoding="utf-8")

    if not re.search(r"^\s*pos:\s*TODO", text, re.MULTILINE):
        return "skipped"

    headword  = read_field(text, "headword")
    primary   = read_field(text, "primary_translation")
    if not headword:
        return "no_headword"

    # Strategy 1: ordnet.dk loose parse
    html = fetch_ordnet(headword)
    time.sleep(throttle)
    pos, gender = (None, None)
    source = "ordnet"
    if html:
        pos, gender = parse_loose(html)

    # Strategy 2: translation heuristic
    if pos is None:
        pos, gender = guess_from_translation(primary, headword)
        source = "heuristic"

    if pos is None:
        return "not_found"

    new_text = text
    new_text = patch_field(new_text, "pos", pos)
    if pos != "noun":
        new_text = patch_field(new_text, "gender", "SKIP")
    elif gender:
        new_text = patch_field(new_text, "gender", gender)

    if new_text == text:
        return "no_change"

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")

    return f"fixed:{source}"


def main():
    parser = argparse.ArgumentParser(description="Second-pass POS fixer")
    parser.add_argument("--throttle", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not ENTRIES_DIR.exists():
        print(f"ERROR: {ENTRIES_DIR} not found.", file=sys.stderr)
        sys.exit(1)

    todo_files = [
        f for f in sorted(ENTRIES_DIR.glob("*.md"))
        if re.search(r"^\s*pos:\s*TODO",
                     f.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    print(f"Files with pos:TODO: {len(todo_files)}")
    if args.dry_run:
        print("[DRY RUN]\n")

    counts: dict[str, int] = {}
    for path in todo_files:
        result = process_file(path, dry_run=args.dry_run, throttle=args.throttle)
        counts[result] = counts.get(result, 0) + 1

    print("\nResults:")
    for k, v in sorted(counts.items()):
        print(f"  {k:20s} {v}")

    remaining = sum(1 for f in ENTRIES_DIR.glob("*.md")
                    if re.search(r"^\s*pos:\s*TODO",
                                 f.read_text(encoding="utf-8"), re.MULTILINE))
    print(f"\nRemaining pos:TODO after run: {remaining}")


if __name__ == "__main__":
    main()
