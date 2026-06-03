"""
fix_en_da_missing.py
--------------------
Create EN->DA entries for content words that were missed by both the
DA->EN reverse lookup and the Wiktionary gap-fill.

Uses hardcoded translations for well-known words.
Writes to entries/en-da/ using the same format as other scripts.
Run:
    python scripts/fix_en_da_missing.py
    python scripts/fix_en_da_missing.py --dry-run
"""

import argparse
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "entries" / "en-da"

# (en_word, pos, da_primary, [secondaries], tags)
MANUAL_ENTRIES = [
    # Core vocabulary
    ("son",        "noun",      "søn",          ["dreng"],                     ["family"]),
    ("blood",      "noun",      "blod",          [],                            ["body", "health"]),
    ("brother",    "noun",      "bror",          ["broder"],                    ["family"]),
    ("star",       "noun",      "stjerne",       [],                            ["nature"]),
    ("river",      "noun",      "flod",          ["å"],                         ["nature"]),
    ("sky",        "noun",      "himmel",        [],                            ["nature", "weather"]),
    ("cloud",      "noun",      "sky",           [],                            ["nature", "weather"]),
    ("leg",        "noun",      "ben",           [],                            ["body"]),
    ("shoulder",   "noun",      "skulder",       [],                            ["body"]),
    ("god",        "noun",      "gud",           [],                            ["culture"]),
    ("sin",        "noun",      "synd",          [],                            ["culture"]),
    ("king",       "noun",      "konge",         [],                            ["culture", "politics"]),
    ("sex",        "noun",      "køn",           ["sex"],                       ["social"]),
    ("rate",       "noun",      "sats",          ["rate", "hastighed"],         ["money", "work"]),
    ("college",    "noun",      "college",       ["højskole"],                  ["education"]),
    ("labor",      "noun",      "arbejde",       ["arbejdskraft"],              ["work"]),
    ("pattern",    "noun",      "mønster",       [],                            ["work"]),
    ("performance","noun",      "præstation",    ["optræden", "forestilling"],  ["work", "culture"]),
    ("measurement","noun",      "måling",        ["mål"],                       ["work"]),
    ("issue",      "noun",      "emne",          ["sag", "udgave"],             ["work", "politics"]),
    ("trouble",    "noun",      "problem",       ["besvær"],                    ["social"]),
    ("fellow",     "noun",      "fyr",           ["kammerat"],                  ["social"]),
    ("neighbor",   "noun",      "nabo",          [],                            ["social", "home"]),
    ("combination","noun",      "kombination",   ["forening"],                  ["work"]),
    ("consideration","noun",    "overvejelse",   ["hensyn"],                    ["work"]),
    ("ideal",      "noun",      "ideal",         [],                            ["social"]),
    ("publication","noun",      "udgivelse",     ["publikation"],               ["education", "work"]),
    ("completion", "noun",      "afslutning",    ["fuldførelse"],               ["work"]),
    ("maximum",    "noun",      "maksimum",      [],                            ["work"]),
    ("sum",        "noun",      "sum",           ["beløb"],                     ["money"]),
    ("pace",       "noun",      "tempo",         ["skridt"],                    ["work"]),
    ("sample",     "noun",      "prøve",         ["eksempel"],                  ["work", "education"]),
    ("troop",      "noun",      "troppe",        ["soldat"],                    ["politics"]),
    ("railroad",   "noun",      "jernbane",      [],                            ["transport"]),
    ("wagon",      "noun",      "vogn",          [],                            ["transport"]),
    ("sponsor",    "noun",      "sponsor",       [],                            ["work", "social"]),
    ("appeal",     "noun",      "appel",         ["tiltrækningskraft"],         ["social", "politics"]),
    ("intellectual","noun",     "intellektuel",  [],                            ["education"]),

    # Adjectives
    ("best",       "adjective", "bedst",         ["bedste"],                    ["TODO"]),
    ("entire",     "adjective", "hel",           ["fuldstændig"],               ["TODO"]),
    ("ready",      "adjective", "klar",          ["parat"],                     ["TODO"]),
    ("particular", "adjective", "bestemt",       ["særlig"],                    ["TODO"]),
    ("liberal",    "adjective", "liberal",       ["frisindet"],                 ["politics"]),
    ("practical",  "adjective", "praktisk",      [],                            ["work"]),
    ("substantial","adjective", "betydelig",     ["væsentlig"],                 ["TODO"]),
    ("capable",    "adjective", "i stand til",   ["dygtig", "kompetent"],       ["work"]),
    ("dominant",   "adjective", "dominerende",   ["fremherskende"],             ["TODO"]),
    ("willing",    "adjective", "villig",        ["parat"],                     ["TODO"]),
    ("initial",    "adjective", "første",        ["indledende"],                ["TODO"]),
    ("ideal",      "adjective", "ideel",         [],                            ["TODO"]),  # also noun above
    ("junior",     "adjective", "junior",        ["yngre"],                     ["work", "education"]),

    # Verbs
    ("fill",       "verb",      "fylde",         ["udfylde"],                   ["TODO"]),
    ("join",       "verb",      "slutte sig til",["tilslutte", "forbinde"],     ["social"]),
    ("attend",     "verb",      "deltage",       ["overværre"],                 ["work", "education"]),
    ("paint",      "verb",      "male",          [],                            ["culture", "home"]),
    ("operate",    "verb",      "betjene",       ["operere", "drive"],          ["work", "health"]),
    ("determine",  "verb",      "bestemme",      ["fastslå"],                   ["work"]),
    ("relate",     "verb",      "relatere",      ["fortælle"],                  ["social"]),
    ("grant",      "verb",      "bevilge",       ["tilstå"],                    ["work", "politics"]),
    ("extend",     "verb",      "udvide",        ["forlænge", "strække"],       ["work"]),
    ("vary",       "verb",      "variere",       ["skifte"],                    ["work"]),
    ("recall",     "verb",      "huske",         ["trække tilbage"],            ["TODO"]),
    ("identify",   "verb",      "identificere",  ["genkende"],                  ["work"]),
    ("oppose",     "verb",      "modstå",        ["modsætte sig"],              ["politics", "social"]),
    ("distinguish","verb",      "skelne",        ["udmærke"],                   ["TODO"]),
    ("eliminate",  "verb",      "eliminere",     ["udelukke"],                  ["work"]),
    ("escape",     "verb",      "flygte",        ["undslippe"],                 ["TODO"]),
    ("display",    "verb",      "vise",          ["fremvise"],                  ["work"]),
    ("climb",      "verb",      "klatre",        ["stige"],                     ["nature"]),
    ("settle",     "verb",      "slå sig ned",   ["afgøre", "ordne"],           ["social", "home"]),
    ("urge",       "verb",      "opfordre",      ["tilskynde"],                 ["social"]),
    ("lean",       "verb",      "læne sig",      [],                            ["body"]),
    ("tend",       "verb",      "have tendens til",["passe"],                   ["TODO"]),
    ("illustrate", "verb",      "illustrere",    [],                            ["education"]),
    ("entitle",    "verb",      "berettige",     ["give ret til"],              ["work", "education"]),
    ("rid",        "verb",      "befri",         ["kvitte sig med"],            ["TODO"]),
    ("strip",      "verb",      "afmontere",     ["strippe"],                   ["TODO"]),
    ("mount",      "verb",      "stige op",      ["montere"],                   ["TODO"]),
    ("appeal",     "verb",      "appellere",     ["tiltale"],                   ["social", "politics"]),

    # Adverb
    ("less",       "adverb",    "mindre",        ["færre"],                     ["TODO"]),
    ("forth",      "adverb",    "frem",          ["fremad"],                    ["TODO"]),

    # Misc
    ("anything",   "pronoun",   "noget",         ["hvad som helst"],            ["TODO"]),
    ("chief",      "noun",      "chef",          ["leder"],                     ["work"]),
    ("executive",  "noun",      "direktør",      ["leder"],                     ["work"]),
]


def _ascii_slug(word: str) -> str:
    s = unicodedata.normalize("NFKD", word)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s


def write_entry(en_word: str, pos: str, da_primary: str,
                secondaries: list, tags: list) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _ascii_slug(en_word)
    fpath = OUT_DIR / f"en-{slug}-001.md"

    gender = "SKIP"
    sec_block = "\n".join(f"  - {s}" for s in secondaries[:3]) if secondaries else "  - TODO"
    tags_block = "\n".join(f"  - {t}" for t in tags) if tags else "  - TODO"

    content = f"""# {en_word}

```
headword: {en_word}
direction: EN->DA
```

```
pos: {pos}
gender: {gender}
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
notes: manually added
```
"""
    fpath.write_text(content, encoding="utf-8")
    return fpath


def main():
    parser = argparse.ArgumentParser(description="Create missing EN->DA entries manually")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip words that already have an entry file")
    args = parser.parse_args()

    written = skipped = 0
    # Deduplicate: if a word appears twice (e.g. ideal as noun and adj), first wins
    seen = set()
    for en_word, pos, da_primary, secondaries, tags in MANUAL_ENTRIES:
        slug = _ascii_slug(en_word)
        fpath = OUT_DIR / f"en-{slug}-001.md"

        if en_word in seen:
            continue  # skip duplicate headword
        seen.add(en_word)

        if args.skip_existing and fpath.exists():
            skipped += 1
            continue

        if args.dry_run:
            print(f"  {en_word:20} -> {da_primary}  ({pos})")
            written += 1
        else:
            write_entry(en_word, pos, da_primary, secondaries, tags)
            print(f"  {en_word:20} -> en-{slug}-001.md")
            written += 1

    print(f"\n{'Would write' if args.dry_run else 'Written'}: {written}  |  Skipped: {skipped}")


if __name__ == "__main__":
    main()
