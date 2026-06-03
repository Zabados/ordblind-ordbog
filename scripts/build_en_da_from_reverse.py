"""
build_en_da_from_reverse.py
---------------------------
Fast-path: build EN->DA entry files by reversing the curated DA->EN entries.

For each word in data/en_wordlist.txt, this script:
  1. Searches the DA->EN entries for any whose primary_translation or
     secondary_translations match that English word.
  2. Creates entries/en-da/en-{word}-001.md with the DA word(s) as translation.

This gives high-quality entries instantly (the DA->EN translations are
hand-curated). Use build_en_da_entries.py (Wiktionary) afterwards for words
not covered here.

Run:
    python scripts/build_en_da_from_reverse.py           # full wordlist
    python scripts/build_en_da_from_reverse.py --dry-run # show matches only
    python scripts/build_en_da_from_reverse.py --skip-existing
"""

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENTRIES_DA_EN = ROOT / "entries" / "da-en"
OUT_DIR = ROOT / "entries" / "en-da"
WORDLIST = ROOT / "data" / "en_wordlist.txt"


# ── Entry parsing (mirrors render_sample.py) ─────────────────────────────────

def _field(content: str, name: str) -> str:
    m = re.search(rf'^\s*{re.escape(name)}:\s*(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _list_field(content: str, name: str) -> list[str]:
    m = re.search(rf'^{re.escape(name)}:\n((?:[ \t]+-[^\n]+\n?)+)', content, re.MULTILINE)
    if not m:
        return []
    return [
        re.sub(r'^\s*-\s*', '', ln).strip()
        for ln in m.group(1).splitlines()
        if ln.strip().startswith('-')
    ]


def _parse_secondary(content: str) -> list[str]:
    """Return secondary_translations as plain English strings."""
    skip = {"TODO", "SKIP", ""}
    result = []
    for item in _list_field(content, "secondary_translations"):
        if item in skip:
            continue
        # Strip sense label if present: "to bear | carry a load" -> "to bear"
        english = item.split(" | ")[0].strip() if " | " in item else item
        result.append(english)
    return result


def _examples(content: str) -> list[dict]:
    m = re.search(r'examples:\n(.*?)(?:\n```|\Z)', content, re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    da_items = re.findall(r'danish:\s*(.+)', block)
    en_items = re.findall(r'english:\s*(.+)', block)
    result = []
    for d, e in zip(da_items, en_items):
        d, e = d.strip(), e.strip()
        if d and d not in {"TODO", "SKIP"}:
            en = "" if e in {"SKIP", "TODO", ""} else e
            result.append({"da": d, "en": en})
    return result[:2]


def parse_da_entry(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    return {
        "headword": _field(content, "headword"),
        "pos":       _field(content, "pos"),
        "gender":    _field(content, "gender"),
        "ipa":       _field(content, "ipa"),
        "phonetic":  _field(content, "phonetic_plain"),
        "syllables": _field(content, "syllables"),
        "primary":   _field(content, "primary_translation"),
        "secondary": _parse_secondary(content),
        "examples":  _examples(content),
        "tags":      [t for t in _list_field(content, "tags")
                      if t not in {"TODO", "SKIP", ""}],
        "tier":      _field(content, "frequency_tier"),
        "rank":      _field(content, "frequency_rank"),
    }


# ── English normalisation ────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """
    Normalise an English translation string to a clean headword for comparison.
    Mirrors render_sample._clean_en_hw but returns lowercased result.
    """
    if not text or text in {"TODO", "SKIP"}:
        return ""
    # Reject purely numeric
    if re.match(r'^\d[\d\s]*$', text.strip()):
        return ""
    # Reject suffix/compound fragments starting with hyphen
    if text.strip().startswith('-'):
        return ""
    # Take only the first clause
    text = re.split(r'[;,]', text)[0].strip()
    # Strip parenthetical notes
    text = re.sub(r'\s*\([^)]*\)', '', text).strip()
    # Strip leading unclosed paren left by comma-split
    text = re.sub(r'^\([^)]*$', '', text).strip()
    # Strip leading articles
    text = re.sub(r'^(?:a|an|the)\s+', '', text, flags=re.IGNORECASE)
    # Strip infinitive "to "
    text = re.sub(r'^to\s+', '', text, flags=re.IGNORECASE)
    return text.strip().lower()


# ── Entry writing ─────────────────────────────────────────────────────────────

def _ascii_slug(word: str) -> str:
    s = unicodedata.normalize("NFKD", word)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s


def write_entry(en_word: str, matches: list[dict]) -> Path:
    """
    Write entries/en-da/en-{word}-001.md.
    matches: list of DA entry dicts, ordered best-first.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _ascii_slug(en_word)
    fpath = OUT_DIR / f"en-{slug}-001.md"

    best = matches[0]
    da_primary = best["headword"]
    gender = best["gender"] if best["pos"] == "noun" else "SKIP"
    pos = best["pos"] if best["pos"] not in {"TODO", ""} else "TODO"

    # Build secondary translations from further matches
    secondaries: list[str] = []
    for m in matches[1:4]:
        da_w = m["headword"]
        if da_w != da_primary and da_w not in secondaries:
            secondaries.append(da_w)

    sec_block = "\n".join(f"  - {s}" for s in secondaries) if secondaries else "  - TODO"

    # Use example from best match (reversed: DA becomes DA, EN becomes EN)
    if best["examples"]:
        ex = best["examples"][0]
        ex_da = ex["da"]
        ex_en = ex["en"] or "TODO"
    else:
        ex_da = "TODO"
        ex_en = "TODO"

    tags_block = "\n".join(f"  - {t}" for t in best["tags"]) if best["tags"] else "  - TODO"

    content = f"""# {en_word}

```
headword: {en_word}
direction: EN->DA
```

```
pos: {pos}
gender: SKIP
```

```
inflections: TODO
```

```
phonetic_plain: TODO
ipa: TODO
syllables: TODO
stoed: false
```

```
primary_translation: {da_primary}
secondary_translations:
{sec_block}
```

```
register: neutral
domain: SKIP
formality: neutral
```

```yaml
examples:
  - danish: {ex_da}
    english: {ex_en}
    source: manual
    source_id: SKIP
```

```
related: TODO
```

```
tags:
{tags_block}
```

```
frequency_rank: TODO
frequency_tier: TODO
```

```
layout:
  print_emphasis: normal
  flag_false_friend: false
  flag_spelling_trap: false
  flag_pronunciation_trap: false
```

```
review_status: draft
notes: auto-generated from DA->EN reverse lookup
```
"""
    fpath.write_text(content, encoding="utf-8")
    return fpath


# ── Main ──────────────────────────────────────────────────────────────────────

def build_reverse_index(da_entries: list[dict]) -> dict[str, list[dict]]:
    """
    Build a mapping: normalised_en_word -> [list of DA entries that translate to it].
    An entry appears in the list for its primary translation and up to 2 secondaries.
    """
    index: dict[str, list[dict]] = {}

    for e in da_entries:
        if not e["headword"] or e["headword"] in {"TODO", "SKIP"}:
            continue

        primary_key = _norm(e["primary"])
        if primary_key and len(primary_key) >= 2 and _safe_index_key(e["primary"], primary_key):
            index.setdefault(primary_key, [])
            index[primary_key].insert(0, e)

        for sec in e["secondary"][:2]:
            key = _norm(sec)
            if key and len(key) >= 2 and key != primary_key and _safe_index_key(sec, key):
                index.setdefault(key, [])
                index[key].append(e)

    # Deduplicate each list while preserving order
    for key in index:
        seen: set[str] = set()
        unique = []
        for e in index[key]:
            if e["headword"] not in seen:
                seen.add(e["headword"])
                unique.append(e)
        index[key] = unique

    return index


# ── Validation ────────────────────────────────────────────────────────────────

# Short words that are frequently the first item in a comma list but are
# coincidental matches, not true single-word EN headwords in that context.
# e.g. "one, people" in da-folk → "one" is not a valid key here.
_COMMA_EXTRACT_SKIP: set[str] = {"one"}


def _safe_index_key(raw: str, normalized: str) -> bool:
    """Return False if this key looks like a false positive from a comma split."""
    if "," not in raw:
        return True  # no comma: safe
    if len(normalized) > 3:
        return True  # long enough to be meaningful
    if normalized in _COMMA_EXTRACT_SKIP:
        return False
    return True  # short but not in blocklist: allow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build EN->DA entries from DA->EN reverse lookup"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print matches without writing files")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip words that already have an entry file")
    args = parser.parse_args()

    # Load wordlist
    if not WORDLIST.exists():
        print(f"ERROR: {WORDLIST} not found. Run make_en_wordlist.py first.",
              file=sys.stderr)
        sys.exit(1)
    wordlist = [w.strip() for w in WORDLIST.read_text(encoding="utf-8").splitlines() if w.strip()]
    print(f"Wordlist: {len(wordlist)} words")

    # Load all DA->EN entries
    da_paths = sorted(ENTRIES_DA_EN.glob("*.md"))
    print(f"Loading {len(da_paths)} DA->EN entries …", end=" ", flush=True)
    da_entries = []
    for p in da_paths:
        try:
            da_entries.append(parse_da_entry(p))
        except Exception:
            pass
    print(f"{len(da_entries)} loaded")

    # Build reverse index
    print("Building reverse index …", end=" ", flush=True)
    index = build_reverse_index(da_entries)
    print(f"{len(index)} English headwords indexed")

    # Match wordlist against index
    ok = skipped = no_match = 0
    matched_words: list[str] = []

    for en_word in wordlist:
        key = en_word.lower()

        if args.skip_existing:
            slug = _ascii_slug(en_word)
            if (OUT_DIR / f"en-{slug}-001.md").exists():
                ok += 1  # already done
                continue

        matches = index.get(key, [])
        if not matches:
            no_match += 1
            continue

        if args.dry_run:
            da_words = ", ".join(m["headword"] for m in matches[:3])
            print(f"  {en_word:20} -> {da_words}")
            ok += 1
            matched_words.append(en_word)
            continue

        write_entry(en_word, matches)
        ok += 1
        matched_words.append(en_word)

    print(f"\nResults:")
    print(f"  Written:   {ok}")
    print(f"  No match:  {no_match}")
    if no_match > 0:
        no_match_words = [w for w in wordlist
                          if w.lower() not in index
                          and not (OUT_DIR / f"en-{_ascii_slug(w)}-001.md").exists()]
        print(f"\nWords without DA->EN coverage ({len(no_match_words)}):")
        for i, w in enumerate(no_match_words[:40], 1):
            print(f"  {i:3}. {w}")
        if len(no_match_words) > 40:
            print(f"  ... and {len(no_match_words) - 40} more")


if __name__ == "__main__":
    main()
