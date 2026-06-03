# Ordbog — AI Agent Instructions

Dyslexia-friendly Danish–English / English–Danish dictionary project targeting PD3 exam vocabulary (B2–C1).

## Key Files

| File | Purpose |
|---|---|
| [entry_template.md](entry_template.md) | **Authoritative schema** — every entry field, its allowed values, and comments. Read this before creating or editing any entry. |
| [pipeline_guide.md](pipeline_guide.md) | Full pipeline implementation (Python 3.10+) from word list → Wiktionary → Tatoeba → Leipzig → entry files. |

## Project Structure

```
ordbog/
├── wordlist.txt
├── data/
│   ├── sentences.csv            # Tatoeba sentences (downloaded)
│   ├── links.csv                # Tatoeba translation links
│   └── dan_news_2020_1M-words.txt  # Leipzig frequency data
└── entries/
    ├── da-en/                   # DA→EN entry files
    └── en-da/                   # EN→DA entry files
```

## Entry File Conventions

- **Filename**: `{lang}-{headword}-001.md` — e.g. `da-hygge-001.md`, `en-cosy-001.md`
- **Non-applicable field**: use `SKIP` (never blank or `null`)
- **Applicable but unpopulated field**: use `TODO`
- **Never delete any field** — the pipeline checks for presence of all fields
- **MANUAL fields** (`layout`) must not be auto-populated; leave as `TODO` or preserve existing human-written content

## Field Sentinel Values

| Value | Meaning |
|---|---|
| `TODO` | Field is applicable but not yet populated — must be resolved before `review_status: approved` |
| `SKIP` | Field is not applicable for this entry (e.g. gender for a verb) |

## Controlled Vocabularies

- **pos**: `noun | verb | adjective | adverb | pronoun | preposition | conjunction | interjection | phrase`
- **gender** (nouns only): `en | et | SKIP`
- **register**: `neutral | colloquial | formal | slang | archaic | technical | literary`
- **formality**: `informal | neutral | formal`
- **review_status**: `draft | reviewed | approved | flagged`
- **frequency_tier**: `core` (top 500) | `common` (501–2000) | `general` (2001–5000) | `rare` (5000+)
- **tags** (1–3 per entry): `emotion | body | health | food | drink | home | nature | weather | work | education | bureaucracy | transport | time | money | social | family | culture | politics | environment | technology`
- **example source**: `tatoeba | wiktionary | manual | ordnet`

## Pipeline Dependencies

```bash
pip install requests beautifulsoup4 mwparserfromhell pandas pyyaml tqdm
```

Python 3.10+ required (uses `dict | None` union syntax).

## Data Sources

| Source | What it provides | Notes |
|---|---|---|
| English Wiktionary API | pos, gender, IPA, inflections, translations | Use `en.wiktionary.org`, not Danish Wiktionary |
| Wiktionary dump | Same, for bulk runs | `enwiktionary-latest-pages-articles.xml.bz2` |
| Tatoeba | Example sentence pairs (DA + EN) | CC-BY 2.0 — attribution required |
| Leipzig Corpora | Frequency rank | CC-BY — attribution required |

Always include a descriptive `User-Agent` header on Wiktionary API calls (required by their terms).

## Editorial Passes (Post-Pipeline)

Entries are written with `review_status: draft`. Before approving:
1. **Completeness** — flag entries with remaining `TODO` fields (scriptable)
2. **Pronunciation** — manually verify all `flag_pronunciation_trap: true` entries (soft-d, stød, ø/y/æ)
3. **Memory hooks** — write for the 200 most-frequent entries only (human expertise required)
4. **False friends** — see the false-friends table in [pipeline_guide.md](pipeline_guide.md)
5. **Tags** — keyword-infer then manually confirm

## Common Pitfalls

- ~15–20% of words are missing from Wiktionary — add to `skipped.txt` for manual handling
- Gender is unparsed for ~10% of nouns — cross-reference `ordnet.dk`
- IPA missing for ~25% of entries — cross-reference `forvo.com`
- Phonetic approximation rules cover common patterns only; edge cases are flagged `flag_pronunciation_trap: true`
