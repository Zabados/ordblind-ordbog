"""
build_en_da_entries.py
----------------------
Build EN->DA dictionary entry files from English Wiktionary translations.

For each English word in data/en_wordlist.txt:
  1. Fetch English Wiktionary wikitext
  2. Extract pos, IPA, and Danish translation(s)
  3. Write entries/en-da/en-{word}-001.md

Run:
    python scripts/build_en_da_entries.py --sample 20   # first 20 words only
    python scripts/build_en_da_entries.py --word say     # single word
    python scripts/build_en_da_entries.py                # full list (slow)
    python scripts/build_en_da_entries.py --skip-existing  # skip already-created

Uses a 0.5 s delay between requests per Wiktionary policy (User-Agent required).
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
WORDLIST = ROOT / "data" / "en_wordlist.txt"
OUT_DIR = ROOT / "entries" / "en-da"
SKIP_LOG = ROOT / "data" / "en_da_skipped.txt"

USER_AGENT = "OrdbogDictionaryBot/1.0 (educational-project; contact@example.com)"
API_URL = "https://en.wiktionary.org/w/api.php"
DELAY = 2.0  # seconds between API calls (Wiktionary rate limit tolerance)


# ── Wiktionary fetching ─────────────────────────────────────────────────────

def fetch_wikitext(word: str) -> Optional[str]:
    """Fetch wikitext for a Wiktionary page, or None on failure.
    Retries up to 3 times with exponential backoff on 429/503."""
    import urllib.error
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            if "error" in data:
                return None
            return data["parse"]["wikitext"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 3:
                wait = 3.0 * (2 ** attempt)  # 3, 6, 12 seconds
                time.sleep(wait)
                continue
            return None
        except Exception:
            return None
    return None


# ── Wikitext parsing ────────────────────────────────────────────────────────

def extract_english_section(wikitext: str) -> Optional[str]:
    """Return only the ==English== section, or None."""
    m = re.search(r"==English==\n(.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    return m.group(1) if m else None


_POS_HEADERS = {
    "noun": "noun",
    "verb": "verb",
    "adjective": "adjective",
    "adverb": "adverb",
    "pronoun": "pronoun",
    "preposition": "preposition",
    "conjunction": "conjunction",
    "interjection": "interjection",
    "phrase": "phrase",
    "proper noun": "noun",        # treat proper nouns as noun
    "numeral": "noun",
}


def extract_pos(en_section: str) -> str:
    """Return best POS label for the English section."""
    for line in en_section.splitlines():
        m = re.match(r"===+(.*?)=+", line)
        if m:
            h = m.group(1).strip().lower()
            if h in _POS_HEADERS:
                return _POS_HEADERS[h]
    return "TODO"


def extract_ipa(en_section: str) -> str:
    """Return first English IPA string found, or TODO."""
    # e.g. {{IPA|en|/seɪ/}} or * IPA(key): /seɪ/
    m = re.search(r"\{\{IPA\|en\|([^}]+)\}\}", en_section)
    if m:
        # take first /.../ or [...] token
        inner = m.group(1)
        tokens = re.findall(r"[/\[][^/\[\]]+[/\]]", inner)
        if tokens:
            return tokens[0]
    # plain IPA line
    m = re.search(r"IPA(?:\(key\))?:\s*([/\[][^/\[\]]+[/\]])", en_section)
    if m:
        return m.group(1)
    return "TODO"


def _gender_from_tag(tag_inner: str) -> str:
    """
    Given the inside of {{t|da|word|...}} return 'en', 'et', or 'SKIP'.
    Gender codes: c (common) -> en;  n (neuter) -> et;
                  m (masculine, rare) -> en;  f (feminine, rare) -> en
    """
    parts = [p.strip() for p in tag_inner.split("|")]
    # parts[0]=template_name, parts[1]=lang, parts[2]=word, rest=modifiers
    for p in parts[3:]:
        if p in ("c", "m", "f", "en-c", "en-m"):
            return "en"
        if p in ("n", "en-n"):
            return "et"
        if p.startswith("g="):
            g = p[2:]
            if g in ("c", "m", "f"):
                return "en"
            if g == "n":
                return "et"
    return "SKIP"  # unknown / not given


def extract_danish_translations(en_section: str, pos: str) -> list[dict]:
    """
    Return a list of {'word': str, 'gender': str, 'sense': str} dicts.
    Parses {{t+|da|...}} and {{t|da|...}} templates.
    """
    results: list[dict] = []

    # Find all translation blocks with their sense labels
    trans_blocks = re.finditer(
        r"\{\{trans-top(?:\|([^}]*))?\}\}(.*?)\{\{trans-bottom\}\}",
        en_section,
        re.DOTALL,
    )

    for block_m in trans_blocks:
        sense = (block_m.group(1) or "").strip()
        block = block_m.group(2)

        # Find all {{t...}} / {{tt...}} templates for Danish
        for tag_m in re.finditer(r"\{\{tt?\+?\|da\|([^}]+)\}\}", block):
            inner = "t|da|" + tag_m.group(1)
            parts = [p.strip() for p in tag_m.group(1).split("|")]
            da_word = parts[0].strip()
            if not da_word or not re.match(r"^[\w\- ]+$", da_word):
                continue
            gender = _gender_from_tag(inner)
            # For non-nouns from entry's pos, ignore gender
            if pos not in ("noun", "TODO"):
                gender = "SKIP"
            results.append({"word": da_word, "gender": gender, "sense": sense})

    # If no trans-top blocks found, try inline Danish: pattern
    if not results:
        for line in en_section.splitlines():
            if not line.strip().startswith("* Danish:"):
                continue
            for tag_m in re.finditer(r"\{\{tt?\+?\|da\|([^}]+)\}\}", line):
                inner = "t|da|" + tag_m.group(1)
                parts = [p.strip() for p in tag_m.group(1).split("|")]
                da_word = parts[0].strip()
                if not da_word:
                    continue
                gender = _gender_from_tag(inner)
                if pos not in ("noun", "TODO"):
                    gender = "SKIP"
                results.append({"word": da_word, "gender": gender, "sense": ""})

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[dict] = []
    for item in results:
        if item["word"] not in seen:
            seen.add(item["word"])
            unique.append(item)

    return unique


# ── Entry writing ────────────────────────────────────────────────────────────

def _ascii_slug(word: str) -> str:
    """Convert a word to a safe ASCII filename slug."""
    s = unicodedata.normalize("NFKD", word)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s


def format_translation(t: dict) -> str:
    """Format a Danish translation with optional gender."""
    if t["gender"] == "SKIP" or not t["gender"]:
        return t["word"]
    return f"{t['word']} ({t['gender']})"


def write_entry(word: str, pos: str, ipa: str, translations: list[dict]) -> Path:
    """Write an EN->DA entry file and return its path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _ascii_slug(word)
    fpath = OUT_DIR / f"en-{slug}-001.md"

    # Build primary and secondary translations
    if translations:
        primary = format_translation(translations[0])
        secondaries = [format_translation(t) for t in translations[1:4]]
    else:
        primary = "TODO"
        secondaries = []

    secondary_block = "\n".join(f"  - {s}" for s in secondaries) if secondaries else "  - TODO"

    content = f"""# {word}

```
headword: {word}
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
ipa: {ipa}
syllables: TODO
stoed: false
```

```
primary_translation: {primary}
secondary_translations:
{secondary_block}
```

```
register: neutral
domain: SKIP
formality: neutral
```

```yaml
examples:
  - danish: TODO
    english: TODO
    source: manual
    source_id: SKIP
```

```
related: TODO
```

```
tags:
  - TODO
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
notes: auto-generated from Wiktionary
```
"""
    fpath.write_text(content, encoding="utf-8")
    return fpath


# ── Main ─────────────────────────────────────────────────────────────────────

def process_word(word: str, verbose: bool = False) -> Optional[Path]:
    """Fetch Wiktionary data for word and write entry. Returns path or None."""
    wikitext = fetch_wikitext(word)
    if not wikitext:
        if verbose:
            print(f"  SKIP {word}: not found on Wiktionary")
        return None

    en_section = extract_english_section(wikitext)
    if not en_section:
        if verbose:
            print(f"  SKIP {word}: no English section")
        return None

    pos = extract_pos(en_section)
    ipa = extract_ipa(en_section)
    translations = extract_danish_translations(en_section, pos)

    if not translations:
        if verbose:
            print(f"  SKIP {word}: no Danish translations found")
        return None

    path = write_entry(word, pos, ipa, translations)
    if verbose:
        da_words = ", ".join(t["word"] for t in translations[:3])
        print(f"  OK   {word:20} pos={pos:12} DA: {da_words}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build EN->DA entries from Wiktionary")
    parser.add_argument("--sample", type=int, metavar="N",
                        help="Process only first N words from wordlist")
    parser.add_argument("--word", metavar="WORD",
                        help="Process a single word")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip words that already have an entry file")
    parser.add_argument("--delay", type=float, default=DELAY,
                        help=f"Delay between API calls in seconds (default {DELAY})")
    args = parser.parse_args()

    if args.word:
        words = [args.word]
    else:
        if not WORDLIST.exists():
            print(f"ERROR: {WORDLIST} not found. Run make_en_wordlist.py first.", file=sys.stderr)
            sys.exit(1)
        words = WORDLIST.read_text(encoding="utf-8").splitlines()
        if args.sample:
            words = words[: args.sample]

    print(f"Processing {len(words)} words …")
    ok = skipped = 0
    skipped_words: list[str] = []

    for i, word in enumerate(words, 1):
        word = word.strip()
        if not word:
            continue

        if args.skip_existing:
            slug = _ascii_slug(word)
            if (OUT_DIR / f"en-{slug}-001.md").exists():
                print(f"  [{i:4}/{len(words)}] EXIST {word}")
                continue

        print(f"  [{i:4}/{len(words)}] {word} …", end=" ", flush=True)
        path = process_word(word, verbose=False)
        if path:
            print(f"-> {path.name}")
            ok += 1
        else:
            print("SKIP (no DA translation)")
            skipped += 1
            skipped_words.append(word)

        if i < len(words):
            time.sleep(args.delay)

    # Write skipped words log
    if skipped_words:
        with open(SKIP_LOG, "a", encoding="utf-8") as f:
            for w in skipped_words:
                f.write(w + "\n")

    print(f"\nDone: {ok} entries written, {skipped} skipped.")
    print(f"Entries: {OUT_DIR}")
    if skipped_words:
        print(f"Skipped log: {SKIP_LOG}")


if __name__ == "__main__":
    main()
