#!/usr/bin/env python3
"""
fix_missing_core.py — Create entries for high-frequency Danish words
that are currently missing from the dictionary.

Reads data/missing_words.csv (output of find_missing_words.py), fetches
Wiktionary + Tatoeba data, and writes properly-formatted entry files.

Usage:
    python scripts/fix_missing_core.py --top 50 --dry-run
    python scripts/fix_missing_core.py --top 100 --throttle 0.5

Options:
    --top N         Process the top N words from missing_words.csv (default 50)
    --words W [W…]  Override: process these specific words only
    --dry-run       Print what would be created without writing files
    --throttle S    Seconds between Wiktionary API calls (default 0.5)
    --skip-tatoeba  Skip Tatoeba lookup (faster, entries will have TODO examples)
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT       = Path(__file__).resolve().parent.parent
ENTRIES    = ROOT / "entries" / "da-en"
MISSING    = ROOT / "data" / "missing_words.csv"
LEIPZIG    = ROOT / "data" / "dan_news_2020_1M-words.txt"
PARQUET    = ROOT / "data" / "tatoeba_da_en_pairs.parquet"
SKIPPED_F  = ROOT / "skipped.txt"

USER_AGENT = "DanishDyslexiaOrdbog/0.1 (gap-fill script; github.com/ordbog)"

TODAY = date.today().isoformat()

# ── Priority words not in the Leipzig top-3000 but known to be exam-critical ─
EXTRA_PRIORITY: list[str] = [
    "tilgængelig",   # available
]

# ── Leipzig rank → frequency tier ────────────────────────────────────────────
def freq_tier(rank: int | None) -> str:
    if rank is None:   return "TODO"
    if rank <= 500:    return "core"
    if rank <= 2000:   return "common"
    if rank <= 5000:   return "general"
    return "rare"

# ── Filename normalisation (æ/ø/å → -, lowercase) ────────────────────────────
# ── Filename normalisation (æ/ø/å → -, lowercase) ────────────────────────────
def slugify(word: str) -> str:
    s = word.lower()
    s = s.replace("æ", "-").replace("ø", "-").replace("å", "-")
    s = re.sub(r"[^a-z0-9-]", "-", s)
    return s


def next_entry_path(word: str) -> tuple[Path, str]:
    """Return the path and entry_id for the next available entry number.

    Checks existing files with the same slug. If a file already covers this
    exact headword, returns (existing_path, entry_id) with existing=True flag
    embedded as a sentinel: the caller checks whether out.exists() AND the
    headword inside already matches.
    """
    slug = slugify(word)
    for n in range(1, 20):
        num   = f"{n:03d}"
        path  = ENTRIES / f"da-{slug}-{num}.md"
        if not path.exists():
            return path, f"da-{slug}-{num}"
        # File exists — check if it covers the same headword
        hw_re = re.compile(r"^headword:\s*(.+)", re.MULTILINE)
        text  = path.read_text(encoding="utf-8", errors="ignore")
        m     = hw_re.search(text)
        if m and m.group(1).strip().lower() == word:
            return path, f"da-{slug}-{num}"   # already exists for this word
    raise RuntimeError(f"Could not find a free slot for {word!r}")

# ── Load Leipzig ranks ────────────────────────────────────────────────────────
def load_ranks() -> dict[str, int]:
    ranks: dict[str, int] = {}
    with open(LEIPZIG, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                ranks[parts[1].lower()] = int(parts[0])
            except ValueError:
                pass
    return ranks

# ── Load existing headwords ───────────────────────────────────────────────────
def existing_headwords() -> set[str]:
    hw_re = re.compile(r"^headword:\s*(.+)", re.MULTILINE)
    out: set[str] = set()
    for md in ENTRIES.glob("*.md"):
        m = hw_re.search(md.read_text(encoding="utf-8", errors="ignore"))
        if m:
            out.add(m.group(1).strip().lower())
    return out

# ── Wiktionary fetch ──────────────────────────────────────────────────────────
WIKT_BASE = "https://en.wiktionary.org/w/api.php"

def fetch_wikitext(word: str) -> str | None:
    try:
        r = requests.get(WIKT_BASE, params={
            "action": "parse", "page": word,
            "prop": "wikitext", "format": "json", "redirects": True,
        }, headers={"User-Agent": USER_AGENT}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if "error" in data:
            return None
        return data["parse"]["wikitext"]["*"]
    except Exception:
        return None

def extract_danish_section(wikitext: str) -> str | None:
    # Stop at the next top-level language section ==Foo== (exactly 2 = each side)
    # NOT at subsections like ===Verb=== (3+ = signs)
    m = re.search(r"(==Danish==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    return m.group(1) if m else None


def _strip_templates(text: str) -> str:
    """Iteratively remove {{...}} to handle nesting."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)
    return text


def _strip_wikilinks(text: str) -> str:
    """Replace [[target|label]] → label, [[target]] → target."""
    return re.sub(r'\[\[(?:[^\[\]|]*\|)?([^\[\]|]+)\]\]', r'\1', text)

_DA_POS = {"noun", "verb", "adjective", "adverb", "pronoun",
           "preposition", "conjunction", "interjection", "phrase"}

def parse_danish(section: str, word: str) -> dict:
    """Return a dict with keys: pos, gender, ipa, primary, secondaries."""
    d: dict = {"pos": "TODO", "gender": "SKIP", "ipa": "TODO",
               "primary": "TODO", "secondaries": []}

    # POS from ===Noun=== style headers
    for m in re.finditer(r"===([A-Za-z ]+)===", section):
        p = m.group(1).strip().lower()
        if p in _DA_POS:
            d["pos"] = p
            break

    # Gender from {{da-noun|en|…}} or {{da-noun|et|…}}
    m = re.search(r"\{\{da-noun\|([a-z]+)", section)
    if m:
        g = m.group(1)
        if g in ("en", "c"):
            d["gender"] = "en"
        elif g in ("et", "n"):
            d["gender"] = "et"

    # If no gender template found, set TODO for nouns
    if d["pos"] == "noun" and d["gender"] == "SKIP":
        d["gender"] = "TODO"

    # For non-nouns, gender stays SKIP
    if d["pos"] not in ("noun", "TODO"):
        d["gender"] = "SKIP"

    # IPA from {{IPA|da|/…/}}
    m = re.search(r"\{\{IPA\|da\|([^}|]+)", section)
    if m:
        d["ipa"] = m.group(1).strip().strip("|").strip()
    else:
        # Fallback: {{IPA|/…/}}
        m = re.search(r"\{\{IPA\|(/[^/}]+/)", section)
        if m:
            d["ipa"] = m.group(1).strip()

    # Translations: definition lines starting with "# " (not "## ")
    translations: list[str] = []
    for line in section.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            clean = _strip_templates(line)
            clean = _strip_wikilinks(clean)
            clean = re.sub(r"'''?([^']+)'''?", r"\1", clean)
            clean = clean.lstrip("# ").strip()
            # Discard lines that are empty or still contain markup
            if clean and len(clean) > 2 and '{' not in clean:
                translations.append(clean)

    if translations:
        d["primary"]     = translations[0]
        d["secondaries"] = translations[1:4]

    return d

# ── Tatoeba lookup ────────────────────────────────────────────────────────────
_DA_ALPHA = "a-zA-ZæøåÆØÅ"
_WB_START = f"(?<![{_DA_ALPHA}0-9])"
MAX_DA_CHARS  = 120
MAX_EXAMPLES  = 2

def load_tatoeba():
    try:
        import pandas as pd
        df = pd.read_parquet(PARQUET)
        return df["sentence_id"], df["text_da"], df["text_en"]
    except Exception as e:
        print(f"  Warning: could not load Tatoeba — {e}", file=sys.stderr)
        return None, None, None

def find_examples(word: str, sent_id, text_da, text_en) -> list[tuple[int, str, str]]:
    if text_da is None:
        return []
    pattern = re.compile(_WB_START + re.escape(word), re.IGNORECASE)
    mask = text_da.str.contains(pattern, regex=True, na=False)
    mask = mask & (text_da.str.len() <= MAX_DA_CHARS)
    if not mask.any():
        return []
    candidates = sorted(
        zip(sent_id[mask], text_da[mask], text_en[mask]),
        key=lambda t: len(t[1]),
    )
    return [(int(s), str(d), str(e)) for s, d, e in candidates[:MAX_EXAMPLES]]

# ── YAML helpers ──────────────────────────────────────────────────────────────
def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}',
                                          '[', ']', '&', '*', '!', '|',
                                          '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(("-", ".", ",", "%")):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text

def format_secondaries(secs: list[str]) -> str:
    if not secs:
        return "\n  - SKIP"
    return "".join(f"\n  - {yaml_safe(s)}" for s in secs)

def format_examples(examples: list[tuple[int, str, str]]) -> str:
    if not examples:
        return (
            "  - danish: TODO\n"
            "    english: TODO\n"
            "    source: manual\n"
            "    source_id: SKIP"
        )
    parts = []
    for sid, da, en in examples:
        parts.append(
            f"  - danish: {yaml_safe(da)}\n"
            f"    english: {yaml_safe(en)}\n"
            f"    source: tatoeba\n"
            f"    source_id: {sid}"
        )
    return "\n".join(parts)

# ── Entry file builder ────────────────────────────────────────────────────────
def build_entry(word: str, entry_id: str, parsed: dict, examples: list,
                rank: int | None) -> str:
    slug     = entry_id.split("-")[1]   # da-{slug}-NNN → slug
    tier     = freq_tier(rank)
    rank_str = str(rank) if rank else "TODO"
    gender   = parsed["gender"]
    pos      = parsed["pos"]

    # Inflection stub depends on POS
    if pos == "verb":
        inflections_block = (
            "inflections:\n"
            "  infinitive: TODO\n"
            "  present: TODO\n"
            "  past: TODO\n"
            "  past_participle: TODO"
        )
    elif pos == "noun":
        inflections_block = (
            "inflections:\n"
            "  indefinite_singular: TODO\n"
            "  definite_singular: TODO\n"
            "  indefinite_plural: TODO\n"
            "  definite_plural: TODO"
        )
    elif pos == "adjective":
        inflections_block = (
            "inflections:\n"
            "  base: TODO\n"
            "  comparative: TODO\n"
            "  superlative: TODO\n"
            "  neuter: TODO\n"
            "  plural: TODO"
        )
    else:
        inflections_block = "inflections: TODO"

    return f"""\
---

## HEADWORD [REQUIRED]

```
headword: {word}
direction: DA\u2192EN
```

---

## GRAMMAR [REQUIRED]

```
pos: {pos}
gender: {gender}
```

### Inflections [OPTIONAL]

```
{inflections_block}
```

---

## PRONUNCIATION [REQUIRED]

```
phonetic_plain: TODO
ipa: {parsed["ipa"]}
syllables: TODO
stoed: TODO
```

---

## TRANSLATION [REQUIRED]

```
primary_translation: {yaml_safe(parsed["primary"]) if parsed["primary"] != "TODO" else "TODO"}
secondary_translations:{format_secondaries(parsed["secondaries"])}
```

---

## REGISTER [OPTIONAL]

```
register: TODO
domain: TODO
formality: TODO
```

---

## EXAMPLE SENTENCES [REQUIRED]

```yaml
examples:
{format_examples(examples)}
```

---

## MEMORY HOOK [MANUAL]

```
memory_hook: TODO
```

---

## RELATED WORDS [OPTIONAL]

```
related: TODO
```

---

## THEMATIC TAGS [REQUIRED]

```
tags:
  - TODO
```

---

## FREQUENCY [REQUIRED]

```
frequency_rank: {rank_str}
frequency_tier: {tier}
```

---

## LAYOUT HINTS [MANUAL]

```
layout:
  print_emphasis: normal
  flag_false_friend: false
  flag_false_friend_note: SKIP
  flag_spelling_trap: false
  flag_pronunciation_trap: false
```

---

## PIPELINE METADATA

```
entry_id: da-{slug}-001
created: {TODAY}
last_modified: {TODAY}
source_wiktionary: true
source_tatoeba: {"true" if examples else "false"}
source_leipzig: {"true" if rank else "false"}
review_status: draft
reviewed_by: SKIP
notes: Auto-generated from gap analysis. Needs manual review.
```
"""

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="Create entries for missing high-frequency words")
    ap.add_argument("--top",          type=int,   default=50,
                    help="Process top N words from missing_words.csv (default 50)")
    ap.add_argument("--words",        nargs="+",  metavar="W",
                    help="Process these specific words instead of reading CSV")
    ap.add_argument("--dry-run",      action="store_true",
                    help="Print actions without writing files")
    ap.add_argument("--throttle",     type=float, default=0.5,
                    help="Seconds between Wiktionary calls (default 0.5)")
    ap.add_argument("--skip-tatoeba", action="store_true",
                    help="Skip Tatoeba lookup")
    args = ap.parse_args()

    # ── Build word list ──
    if args.words:
        words = [(None, w) for w in args.words]
    else:
        if not MISSING.exists():
            sys.exit("data/missing_words.csv not found — run find_missing_words.py first")
        with open(MISSING, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        # Priority words first (if present in CSV), then top-N by rank
        csv_words = {r["word"]: int(r["rank"]) for r in rows}
        priority = [(csv_words.get(w), w) for w in EXTRA_PRIORITY
                    if w not in csv_words]   # only if not already in CSV
        regular  = [(int(r["rank"]), r["word"]) for r in rows]
        combined = priority + regular
        words    = combined[: args.top]

    # ── Load supporting data ──
    print("Loading Leipzig ranks …")
    ranks = load_ranks()

    if not args.skip_tatoeba:
        print("Loading Tatoeba …")
        sent_id, text_da, text_en = load_tatoeba()
    else:
        sent_id = text_da = text_en = None

    print("Loading existing headwords …")
    known = existing_headwords()

    # ── Process each word ──
    counts = {"created": 0, "skipped_exists": 0,
              "skipped_no_wikt": 0, "skipped_no_danish": 0, "dry_run": 0}
    skipped_words: list[str] = []

    for _rank, word in words:
        word = word.strip().lower()
        if not word:
            continue

        if word in known:
            counts["skipped_exists"] += 1
            continue

        try:
            out_path, entry_id = next_entry_path(word)
        except RuntimeError as e:
            print(f"  {word} … {e}")
            continue

        # If the returned path exists, the headword is already covered
        if out_path.exists():
            counts["skipped_exists"] += 1
            continue

        rank = ranks.get(word) or ranks.get(word.capitalize())

        # ── Wiktionary ──
        print(f"  {word} … ", end="", flush=True)
        wikitext = fetch_wikitext(word)
        time.sleep(args.throttle)

        if not wikitext:
            print("no Wiktionary page")
            counts["skipped_no_wikt"] += 1
            skipped_words.append(word)
            continue

        section = extract_danish_section(wikitext)
        if not section:
            print("no Danish section")
            counts["skipped_no_danish"] += 1
            skipped_words.append(word)
            continue

        parsed = parse_danish(section, word)

        # ── Tatoeba ──
        if text_da is not None:
            examples = find_examples(word, sent_id, text_da, text_en)
        else:
            examples = []

        # ── Write ──
        entry_text = build_entry(word, entry_id, parsed, examples, rank)

        if args.dry_run:
            print(f"DRY-RUN → {out_path.name}  "
                  f"pos={parsed['pos']}  gender={parsed['gender']}  "
                  f"ipa={parsed['ipa']}  "
                  f"primary={parsed['primary']!r}  "
                  f"examples={len(examples)}")
            counts["dry_run"] += 1
        else:
            out_path.write_text(entry_text, encoding="utf-8")
            print(f"written  → {out_path.name}  "
                  f"pos={parsed['pos']}  ipa={parsed['ipa']}  "
                  f"examples={len(examples)}")
            counts["created"] += 1

    # ── Summary ──
    print()
    print("── Summary ─────────────────────────────────────────")
    if args.dry_run:
        print(f"  Would create:   {counts['dry_run']}")
    else:
        print(f"  Created:        {counts['created']}")
    print(f"  Already exists: {counts['skipped_exists']}")
    print(f"  No Wiktionary:  {counts['skipped_no_wikt']}")
    print(f"  No DA section:  {counts['skipped_no_danish']}")

    # Append to skipped.txt
    if skipped_words and not args.dry_run:
        with open(SKIPPED_F, "a", encoding="utf-8") as fh:
            for w in skipped_words:
                fh.write(w + "\n")
        print(f"  → {len(skipped_words)} words appended to skipped.txt")


if __name__ == "__main__":
    main()
