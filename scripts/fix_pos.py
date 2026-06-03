"""
fix_pos.py — fill pos: TODO and gender: TODO fields using English Wiktionary API.

For each entry with pos: TODO:
  1. Fetch the Wiktionary page for the Danish headword.
  2. Find the ==Danish== section and read the first POS header (Noun, Verb, etc.)
  3. For nouns, also try to extract gender (en/et) from the head template.
  4. Write back only if confident (single unambiguous POS found).

Writes a log of skipped/ambiguous words to fix_pos_skipped.txt.
"""

from __future__ import annotations
import re
import time
import argparse
from pathlib import Path

import requests

ENTRIES_DIR_DA = Path("entries/da-en")
ENTRIES_DIR_EN = Path("entries/en-da")

WIKT_API = "https://en.wiktionary.org/w/api.php"
HEADERS = {"User-Agent": "ordbog-fix-pos/1.0 (educational dictionary project; contact: local-user)"}

# Map Wiktionary POS section names → our controlled vocabulary
POS_MAP = {
    "noun": "noun",
    "verb": "verb",
    "adjective": "adjective",
    "adverb": "adverb",
    "pronoun": "pronoun",
    "preposition": "preposition",
    "conjunction": "conjunction",
    "interjection": "interjection",
    "particle": "adverb",       # Danish particles often function as adverbs
    "numeral": "adjective",     # numerals behave like adjectives in DA
    "article": "pronoun",
    "phrase": "phrase",
    "idiom": "phrase",
}

# Gender strings that appear in Wiktionary DA noun templates
GENDER_EN_PATTERNS = [
    r"\bc\b", r"\bcommon\b", r"\bmasculine\b", r"\bfeminine\b",
    r"gender=c", r"g=c", r"g=m", r"g=f",
]
GENDER_ET_PATTERNS = [
    r"\bn\b", r"\bneuter\b",
    r"gender=n", r"g=n",
]


def fetch_wikitext(word: str) -> str | None:
    params = {
        "action": "query",
        "titles": word,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    try:
        r = requests.get(WIKT_API, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        return page["revisions"][0]["slots"]["main"]["content"]
    except Exception:
        return None


def extract_da_pos_gender(wikitext: str) -> tuple[str | None, str | None]:
    """Return (pos, gender) from the ==Danish== section. gender may be None."""
    # Find ==Danish== section
    da_match = re.search(r"==Danish==", wikitext)
    if not da_match:
        return None, None

    da_section = wikitext[da_match.start():]
    # Cut off at the next level-2 heading (another language)
    next_lang = re.search(r"\n==[^=]", da_section[10:])
    if next_lang:
        da_section = da_section[:10 + next_lang.start()]

    # Find all level-3 or level-4 POS headers
    pos_headers = re.findall(r"===+\s*([^=\n]+?)\s*===+", da_section)
    pos_found: list[str] = []
    for h in pos_headers:
        mapped = POS_MAP.get(h.strip().lower())
        if mapped:
            pos_found.append(mapped)

    if not pos_found:
        return None, None

    # Use first POS found; flag as ambiguous if multiple different POS
    pos = pos_found[0]

    # For nouns, try to extract gender
    gender = None
    if pos == "noun":
        # Look for head template lines like {{da-noun|g=c}} or {{da-noun|c|...}}
        # or gender=c / gender=n in the template
        # Check for common (en) gender
        for pat in GENDER_EN_PATTERNS:
            if re.search(pat, da_section, re.IGNORECASE):
                gender = "en"
                break
        # Check for neuter (et) gender — overrides if found more specifically
        for pat in GENDER_ET_PATTERNS:
            if re.search(pat, da_section, re.IGNORECASE):
                gender = "et"
                break
        # Try {{da-noun|n|...}} or {{da-noun|c|...}} positional
        head_tmpl = re.search(r"\{\{da-noun\|([^}]+)\}\}", da_section)
        if head_tmpl:
            args = head_tmpl.group(1).split("|")
            first = args[0].strip().lower()
            if first in ("n", "neuter"):
                gender = "et"
            elif first in ("c", "common", "m", "f"):
                gender = "en"

    return pos, gender


def patch_field(content: str, field: str, value: str) -> str:
    """Replace `field: TODO` with `field: value` in YAML block."""
    return re.sub(
        rf"^({re.escape(field)}:\s*)TODO\s*$",
        rf"\g<1>{value}",
        content,
        flags=re.MULTILINE,
    )


def process_entry(path: Path, dry_run: bool, throttle: float) -> str:
    """Returns: 'fixed_both' | 'fixed_pos' | 'fixed_gender' | 'no_change' | 'not_found' | 'skipped'"""
    content = path.read_text(encoding="utf-8")

    need_pos    = "pos: TODO" in content
    need_gender = "gender: TODO" in content

    if not need_pos and not need_gender:
        return "skipped"

    hw_match = re.search(r"^headword:\s*(.+)$", content, re.MULTILINE)
    if not hw_match:
        return "skipped"
    headword = hw_match.group(1).strip()

    wikitext = fetch_wikitext(headword)
    if throttle:
        time.sleep(throttle)

    if wikitext is None:
        return "not_found"

    pos, gender = extract_da_pos_gender(wikitext)

    changed = False
    if need_pos and pos:
        content = patch_field(content, "pos", pos)
        changed = True
    if need_gender and gender:
        content = patch_field(content, "gender", gender)
        changed = True

    if not changed:
        return "no_change"

    if not dry_run:
        path.write_text(content, encoding="utf-8")

    if need_pos and pos and need_gender and gender:
        return "fixed_both"
    if need_pos and pos:
        return "fixed_pos"
    return "fixed_gender"


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill pos/gender TODO fields from Wiktionary")
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--throttle", type=float, default=0.15,
                    help="Seconds between API requests (default 0.15)")
    ap.add_argument("--dir", choices=["da-en", "en-da", "both"], default="both")
    args = ap.parse_args()

    dirs: list[Path] = []
    if args.dir in ("da-en", "both"):
        dirs.append(ENTRIES_DIR_DA)
    if args.dir in ("en-da", "both"):
        dirs.append(ENTRIES_DIR_EN)

    files = sorted(p for d in dirs for p in d.glob("*.md"))
    todo = [
        p for p in files
        if "pos: TODO" in p.read_text(encoding="utf-8")
        or "gender: TODO" in p.read_text(encoding="utf-8")
    ]

    print(f"{len(todo)} entries need fixing", flush=True)

    counts: dict[str, int] = {
        "fixed_both": 0, "fixed_pos": 0, "fixed_gender": 0,
        "no_change": 0, "not_found": 0, "skipped": 0,
    }
    skipped: list[str] = []

    for i, path in enumerate(todo):
        result = process_entry(path, dry_run=args.dry_run, throttle=args.throttle)
        counts[result] += 1
        if result in ("no_change", "not_found"):
            hw = re.search(r"^headword:\s*(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
            skipped.append(hw.group(1).strip() if hw else path.stem)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)} …", flush=True)

    mode = " [DRY RUN]" if args.dry_run else ""
    print(f"\nResults{mode}:")
    for k, v in counts.items():
        print(f"  {k:<16} {v:>4}")

    skipped_path = Path("fix_pos_skipped.txt")
    if skipped:
        skipped_path.write_text("\n".join(skipped), encoding="utf-8")
        print(f"\nSkipped/unfixed words written to {skipped_path}  ({len(skipped)} words)")


if __name__ == "__main__":
    main()
