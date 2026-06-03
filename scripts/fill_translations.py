"""
fill_translations.py
---------------------
Fills primary_translation: TODO fields by fetching definitions from
English Wiktionary, matched to the POS already recorded in each entry.

For each entry with primary_translation: TODO:
  1. Read headword and pos from the file
  2. Fetch wikitext from Wiktionary API
  3. Find ==Danish== section → matching POS header
  4. Extract clean English definition lines
  5. First definition → primary_translation
     Further definitions → secondary_translations (if currently SKIP)
  6. Write back only when at least one definition was found

Writes skipped/failed words to fill_translations_skipped.txt.

Usage:
    python scripts/fill_translations.py [--dry-run] [--throttle 1.2]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT       = Path(__file__).resolve().parent.parent
ENTRIES    = ROOT / "entries" / "da-en"
SKIPPED    = ROOT / "fill_translations_skipped.txt"
UA         = "DanishDyslexiaOrdbog/0.1 (fill-translations; educational use)"
WIKT_API   = "https://en.wiktionary.org/w/api.php"

MAX_SECONDARY = 3   # max secondary translations to fill
MAX_DEF_LEN   = 90  # truncate very long single definitions

# Our POS name → Wiktionary section header variants
POS_HEADERS: dict[str, list[str]] = {
    "noun":         ["Noun"],
    "verb":         ["Verb"],
    "adjective":    ["Adjective"],
    "adverb":       ["Adverb", "Particle"],
    "pronoun":      ["Pronoun", "Determiner"],
    "preposition":  ["Preposition"],
    "conjunction":  ["Conjunction"],
    "interjection": ["Interjection"],
    "phrase":       ["Phrase", "Idiom"],
}

# Verbs where we intentionally skip "to " prefix (modals, special forms)
MODAL_STEMS = {
    "burde", "skulle", "ville", "kunne", "måtte", "turde",
    "pleje", "orke",
}


# ── Wiktionary helpers ────────────────────────────────────────────────────────

def fetch_wikitext(word: str) -> str | None:
    params = {
        "action":       "query",
        "titles":       word,
        "prop":         "revisions",
        "rvprop":       "content",
        "rvslots":      "main",
        "format":       "json",
        "formatversion":"2",
    }
    try:
        r = requests.get(WIKT_API, params=params,
                         headers={"User-Agent": UA}, timeout=12)
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


def danish_section(wikitext: str) -> str | None:
    """Return the ==Danish== sub-section, or None."""
    m = re.search(r"==Danish==", wikitext)
    if not m:
        return None
    tail = wikitext[m.start():]
    cut = re.search(r"\n==[^=]", tail[10:])
    return tail if not cut else tail[:10 + cut.start()]


def pos_section(da_sec: str, target_pos: str) -> str | None:
    """Return the sub-section for a specific POS, or None."""
    candidates = POS_HEADERS.get(target_pos, [target_pos.capitalize()])
    for hdr in candidates:
        pat = rf"===+\s*{re.escape(hdr)}\s*===+"
        m = re.search(pat, da_sec)
        if not m:
            continue
        tail = da_sec[m.start():]
        # End at the next ===+ heading
        nxt = re.search(r"\n===+[^=]", tail[10:])
        return tail if not nxt else tail[:10 + nxt.start()]
    return None


def clean_wikitext(text: str) -> str:
    """Strip wikitext markup; return plain English text."""
    # Remove {{lb|da|...}} / {{label|...}} language-label templates
    text = re.sub(r"\{\{(?:lb|label|tag|tagg?)\|[^}]*\}\}", "", text, flags=re.I)
    # {{l|en|word|...}} or {{link|en|word}} → word
    text = re.sub(r"\{\{l\|[a-z-]+\|([^|}]+)(?:\|[^}]*)?\}\}", r"\1", text)
    text = re.sub(r"\{\{link\|[a-z-]+\|([^|}]+)(?:\|[^}]*)?\}\}", r"\1", text)
    # {{m|en|word|...}} → word
    text = re.sub(r"\{\{m\|[a-z-]+\|([^|}]+)(?:\|[^}]*)?\}\}", r"\1", text)
    # {{gloss|text}} → (text)
    text = re.sub(r"\{\{gloss\|([^}]+)\}\}", r"(\1)", text)
    # {{sense|...}} → (...)
    text = re.sub(r"\{\{sense\|([^}]+)\}\}", r"(\1)", text)
    # Remaining {{...}} templates — try to extract first pipe arg or remove
    def _tpl(m: re.Match) -> str:
        inner = m.group(1)
        parts = inner.split("|")
        name = parts[0].strip().lower()
        # Templates that should just vanish
        if name in ("rfdef", "rfquote", "rfc", "attention", "attention2",
                    "synonym", "antonym", "hypo", "hyper", "meronym",
                    "holonym", "cot", "col", "der", "rel", "see"):
            return ""
        # Use last pipe segment as display text if it looks like a word
        if len(parts) > 1:
            last = parts[-1].strip()
            if last and not "=" in last:
                return last
        return ""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{([^{}]+)\}\}", _tpl, text)
    # [[word|display]] → display, [[word]] → word
    text = re.sub(r"\[\[[^\[\]|]*\|([^\[\]|]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\[\]|]+)\]\]", r"\1", text)
    # '''bold''' / ''italic''
    text = re.sub(r"'{2,3}", "", text)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip().strip(";,.")
    # Lower-case first letter (definitions are lowercase in our schema)
    if text and text[0].isupper() and len(text) > 1 and text[1].islower():
        text = text[0].lower() + text[1:]
    return text


def extract_definitions(pos_sec: str) -> list[str]:
    """Return clean English definitions from a POS section."""
    defs: list[str] = []
    for m in re.finditer(r"^#(?!#)(?!:)(?!\*)[ \t]*(.*)", pos_sec, re.MULTILINE):
        raw = m.group(1).strip()
        if not raw:
            continue
        cleaned = clean_wikitext(raw)
        if not cleaned or len(cleaned) < 2:
            continue
        # Skip meta-lines like "{{rfdef}}" that cleaned to empty
        if cleaned.startswith("{{"):
            continue
        # Truncate very long definitions
        if len(cleaned) > MAX_DEF_LEN:
            # Cut at last word boundary before limit
            cut = cleaned[:MAX_DEF_LEN].rsplit(" ", 1)[0]
            cleaned = cut.rstrip(",;")
        defs.append(cleaned)
    return defs


# ── Entry helpers ─────────────────────────────────────────────────────────────

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def set_field(text: str, field: str, value: str) -> str:
    return re.sub(
        rf"^(\s*{re.escape(field)}:\s*)(.+)$",
        lambda m: m.group(1) + value,
        text, flags=re.MULTILINE,
    )


def set_secondary_translations(text: str, secondaries: list[str]) -> str:
    """Replace the secondary_translations block."""
    new_lines = "\n".join(f"  - {s}" for s in secondaries)
    # Replace the whole secondary block (between "secondary_translations:" and next blank/```)
    return re.sub(
        r"(secondary_translations:)[^\n]*(\n(?:[ \t]+-[^\n]*\n?)*)",
        lambda m: f"secondary_translations:\n{new_lines}\n",
        text, count=1,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def process(path: Path, dry_run: bool, throttle: float,
            skipped_fh) -> str:
    """Process one entry file. Returns 'filled' | 'skipped' | 'error'."""
    text = path.read_text(encoding="utf-8")
    headword = read_field(text, "headword")
    pos      = read_field(text, "pos")
    primary  = read_field(text, "primary_translation")

    if primary not in ("TODO", ""):
        return "skipped"

    if not headword or headword in ("TODO", "SKIP"):
        skipped_fh.write(f"{path.name}: no headword\n")
        return "skipped"

    # Throttle before network call
    time.sleep(throttle)

    wikitext = fetch_wikitext(headword)
    if not wikitext:
        skipped_fh.write(f"{path.name}: not on Wiktionary ({headword!r})\n")
        return "skipped"

    da_sec = danish_section(wikitext)
    if not da_sec:
        skipped_fh.write(f"{path.name}: no Danish section ({headword!r})\n")
        return "skipped"

    p_sec = pos_section(da_sec, pos) if pos and pos != "TODO" else None
    if not p_sec:
        # Fallback: try any POS section
        for pos_name in POS_HEADERS:
            p_sec = pos_section(da_sec, pos_name)
            if p_sec:
                break
    if not p_sec:
        skipped_fh.write(f"{path.name}: POS section {pos!r} not found ({headword!r})\n")
        return "skipped"

    defs = extract_definitions(p_sec)
    if not defs:
        skipped_fh.write(f"{path.name}: no definitions extracted ({headword!r})\n")
        return "skipped"

    primary_def = defs[0]
    # For verbs: ensure "to " prefix
    is_modal = headword.lower().rstrip("e") in MODAL_STEMS or headword.lower() in MODAL_STEMS
    if pos == "verb" and not is_modal:
        if not primary_def.lower().startswith("to "):
            primary_def = "to " + primary_def

    new_text = set_field(text, "primary_translation", primary_def)

    # Fill secondaries only if current value is SKIP
    sec_match = re.search(r"secondary_translations:(.*?)```", text, re.DOTALL)
    current_sec = sec_match.group(1).strip() if sec_match else ""
    sec_items = [l.strip().lstrip("- ").strip()
                 for l in current_sec.splitlines()
                 if l.strip().startswith("- ")]
    sec_is_skip = not sec_items or all(s in ("SKIP", "TODO") for s in sec_items)

    if sec_is_skip and len(defs) > 1:
        extra = defs[1: 1 + MAX_SECONDARY]
        if pos == "verb" and not is_modal:
            extra = [
                ("to " + d if not d.lower().startswith("to ") else d)
                for d in extra
            ]
        new_text = set_secondary_translations(new_text, extra)

    if dry_run:
        print(f"[DRY-RUN] {path.name}: {primary_def!r}")
        return "filled"

    path.write_text(new_text, encoding="utf-8")
    print(f"  filled  {path.name}: {primary_def!r}")
    return "filled"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--throttle", type=float, default=1.2,
                    help="Seconds between Wiktionary requests (default 1.2)")
    ap.add_argument("--only", metavar="STEM",
                    help="Process only this filename stem for testing")
    args = ap.parse_args()

    paths = sorted(ENTRIES.glob("*.md"))
    if args.only:
        paths = [p for p in paths if args.only in p.stem]

    filled = skipped = errors = 0

    with SKIPPED.open("w", encoding="utf-8") as sfh:
        for path in paths:
            try:
                result = process(path, args.dry_run, args.throttle, sfh)
            except Exception as exc:
                print(f"ERROR {path.name}: {exc}", file=sys.stderr)
                sfh.write(f"{path.name}: EXCEPTION {exc}\n")
                errors += 1
                continue
            if result == "filled":
                filled += 1
            else:
                skipped += 1

    print(f"\nDone — filled={filled}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    main()
