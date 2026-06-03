# Dictionary Pipeline Guide
# Dyslexia-Friendly Danish–English / English–Danish Ordbog
# Version: 0.1

---

## Overview

This guide describes how to build a pipeline that automatically fetches,
cleans, and structures dictionary entries conforming to `entry_template.md`.

The pipeline has five stages:

1. Build a word list
2. Fetch data from Wiktionary
3. Fetch example sentences from Tatoeba
4. Fetch frequency data from Leipzig
5. Assemble and write entry files

All sources used are open and freely available. No API keys are required
for the core pipeline. Python 3.10+ is assumed throughout.

---

## Dependencies

```bash
pip install requests beautifulsoup4 mwparserfromhell pandas pyyaml tqdm
```

| Package | Purpose |
|---|---|
| requests | HTTP fetching |
| beautifulsoup4 | HTML parsing for fallback scraping |
| mwparserfromhell | Parsing Wiktionary wikitext |
| pandas | Handling Leipzig and Tatoeba TSV data |
| pyyaml | Reading and writing YAML blocks in markdown |
| tqdm | Progress bars for bulk runs |

---

## Stage 1 — Build Your Word List

Before fetching anything you need a list of headwords. There are three
approaches, which you can combine.

### Option A — PD3 Exam Vocabulary

The PD3 exam has a known vocabulary scope of roughly B2–C1. No official
list is published, but the following sources approximate it well:

- **DSL's Nudansk Ordbog frequency list** — top 5,000 Danish words by
  frequency, available as a downloadable CSV from:
  `https://ordnet.dk/korpusdk/statistik`

- **CEFR B2–C1 Danish word lists** compiled by language researchers are
  occasionally published as open datasets on GitHub. Search:
  `site:github.com danish B2 wordlist`

- **Your own PD3 study materials** — scan your module texts and glossaries.
  These are the words most likely to appear in your specific exam context.

### Option B — Leipzig Frequency List (Recommended Starting Point)

The Leipzig Corpora Collection provides open Danish frequency data:

```
https://wortschatz.uni-leipzig.de/en/download/Danish
```

Download the `dan_news_2020_10K-sentences.tar.gz` or similar. Extract the
`words` file — it contains ranked word forms with frequency counts.

```python
import pandas as pd

# Leipzig words file has columns: rank, word, frequency
df = pd.read_csv('dan_news_2020_1M-words.txt', sep='\t',
                 header=None, names=['rank', 'word', 'frequency'])

# Filter to your target range — core + common tier
wordlist = df[df['rank'] <= 3000]['word'].tolist()
```

### Option C — Manual Curation

For a PD3-focused first edition, a curated list of 800–1,200 words is
more useful than an exhaustive frequency list. Start with the Leipzig top
3,000, then filter out:

- Proper nouns (will appear capitalised in the frequency data)
- Numbers and punctuation
- Words you already know well
- Highly technical or domain-specific words outside PD3 scope

Save your final word list as `wordlist.txt`, one word per line.

---

## Stage 2 — Fetch from Wiktionary

Wiktionary is the primary data source for grammar, gender, inflections,
IPA, and translations.

### Option A — Wiktionary API (Recommended for Small Lists)

The Wiktionary API returns parsed entry data for a single word. It is
rate-limit friendly for lists under ~2,000 words if you add a small delay.

```python
import requests
import time

BASE_URL = "https://en.wiktionary.org/w/api.php"

def fetch_wiktionary(word: str) -> dict | None:
    """
    Fetch the raw wikitext for a Danish word from English Wiktionary.
    English Wiktionary has better structured Danish entries than Danish
    Wiktionary for our purposes.
    """
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json",
        "redirects": True
    }
    response = requests.get(BASE_URL, params=params, headers={
        "User-Agent": "DanishDyslexiaOrdbog/0.1 (jordan@example.com)"
    })
    if response.status_code != 200:
        return None
    data = response.json()
    if "error" in data:
        return None
    return data["parse"]["wikitext"]["*"]


def fetch_all_words(wordlist: list[str], delay: float = 0.5) -> dict:
    """Fetch wikitext for all words with a polite delay between requests."""
    results = {}
    for word in tqdm(wordlist):
        wikitext = fetch_wiktionary(word)
        if wikitext:
            results[word] = wikitext
        time.sleep(delay)
    return results
```

**Important:** Always include a descriptive `User-Agent` header with contact
information. Wiktionary's API terms require this and it prevents your
requests being blocked.

### Option B — Wiktionary Data Dump (Recommended for Full Runs)

For bulk processing, download the full English Wiktionary dump rather than
hitting the API repeatedly. This is a single download and then all
processing is local.

Download from:
```
https://dumps.wikimedia.org/enwiktionary/latest/
```

File to download: `enwiktionary-latest-pages-articles.xml.bz2`
(approximately 900MB compressed)

```python
import bz2
import xml.etree.ElementTree as ET

def stream_wiktionary_dump(dump_path: str, target_words: set[str]):
    """
    Stream through the Wiktionary XML dump and extract pages
    matching our target word list.
    """
    results = {}
    with bz2.open(dump_path, 'rb') as f:
        for event, elem in ET.iterparse(f, events=['end']):
            if elem.tag.endswith('}page'):
                title = elem.findtext('.//{*}title', '')
                if title.lower() in target_words:
                    text = elem.findtext('.//{*}text', '')
                    results[title] = text
                elem.clear()  # Free memory
    return results
```

### Parsing Wikitext for Danish Entries

Wiktionary entries contain multiple language sections. We need only the
Danish section.

```python
import mwparserfromhell
import re

def extract_danish_section(wikitext: str) -> str | None:
    """Extract only the Danish language section from a Wiktionary entry."""
    # Language sections are marked with == Language ==
    pattern = r'(==Danish==.*?)(?===\w|\Z)'
    match = re.search(pattern, wikitext, re.DOTALL)
    if not match:
        return None
    return match.group(1)


def parse_entry(wikitext: str) -> dict:
    """
    Parse a Danish Wiktionary section into structured fields.
    Returns a dict matching the entry_template.md schema.
    """
    entry = {
        "pos": None,
        "gender": None,
        "ipa": None,
        "inflections": {},
        "primary_translation": None,
        "secondary_translations": [],
        "review_status": "draft"
    }

    parsed = mwparserfromhell.parse(wikitext)

    # Extract part of speech from section headers
    # Wiktionary uses ===Noun===, ===Verb=== etc.
    for section in parsed.get_sections(levels=[3]):
        heading = section.filter_headings()
        if heading:
            pos_raw = heading[0].title.strip_code().strip().lower()
            if pos_raw in ['noun', 'verb', 'adjective', 'adverb',
                           'preposition', 'conjunction', 'interjection',
                           'pronoun', 'phrase']:
                entry["pos"] = pos_raw

    # Extract IPA pronunciation
    for template in parsed.filter_templates():
        if template.name.strip() == "IPA":
            try:
                entry["ipa"] = str(template.params[0].value).strip()
            except IndexError:
                pass

    # Extract gender from noun templates
    # Wiktionary uses {{da-noun|en|...}} or {{da-noun|et|...}}
    for template in parsed.filter_templates():
        name = template.name.strip()
        if name in ['da-noun', 'da-noun-form']:
            try:
                gender_raw = str(template.params[0].value).strip()
                if gender_raw in ['en', 'et', 'c', 'n']:
                    # c = common (en), n = neuter (et)
                    entry["gender"] = 'en' if gender_raw in ['en', 'c'] else 'et'
            except IndexError:
                pass

    # Extract English translations from definition lines
    # Wiktionary definitions start with # and may contain {{l|en|word}} links
    translations = []
    for line in wikitext.split('\n'):
        if line.startswith('# ') and not line.startswith('## '):
            # Clean wikitext markup from the definition
            clean = mwparserfromhell.parse(line).strip_code().strip()
            clean = clean.lstrip('# ').strip()
            if clean and len(clean) > 1:
                translations.append(clean)

    if translations:
        entry["primary_translation"] = translations[0]
        entry["secondary_translations"] = translations[1:4]  # Max 3 extras

    return entry
```

---

## Stage 3 — Fetch Example Sentences from Tatoeba

Tatoeba provides open Danish-English sentence pairs under CC-BY 2.0.

### Download the Sentence Files

```
https://downloads.tatoeba.org/exports/sentences.tar.bz2
https://downloads.tatoeba.org/exports/links.tar.bz2
```

The `sentences` file contains all sentences in all languages with their
Tatoeba sentence ID and language code.

The `links` file maps sentence IDs to their translations.

```python
import pandas as pd

def load_tatoeba(sentences_path: str, links_path: str):
    """
    Load Tatoeba sentence pairs into a searchable DataFrame.
    Returns a DataFrame of Danish sentences with their English translations.
    """
    # Load all sentences
    sentences = pd.read_csv(
        sentences_path, sep='\t', header=None,
        names=['id', 'lang', 'text'],
        quoting=3  # QUOTE_NONE — sentences may contain quotes
    )

    # Filter to Danish and English only
    da = sentences[sentences['lang'] == 'dan'].copy()
    en = sentences[sentences['lang'] == 'eng'].copy()

    # Load translation links
    links = pd.read_csv(
        links_path, sep='\t', header=None,
        names=['sentence_id', 'translation_id']
    )

    # Join: Danish sentence -> link -> English translation
    da_links = links.merge(da[['id', 'text']], left_on='sentence_id', right_on='id')
    pairs = da_links.merge(en[['id', 'text']], left_on='translation_id', right_on='id',
                           suffixes=('_da', '_en'))

    return pairs[['sentence_id', 'text_da', 'translation_id', 'text_en']]


def find_examples(word: str, pairs: pd.DataFrame,
                  max_results: int = 5) -> list[dict]:
    """
    Find example sentences containing the target word.
    Prefers shorter, simpler sentences.
    """
    # Case-insensitive word boundary match
    mask = pairs['text_da'].str.contains(
        rf'\b{re.escape(word)}\b', case=False, na=False
    )
    matches = pairs[mask].copy()

    # Score by sentence length — prefer shorter sentences
    matches['length'] = matches['text_da'].str.len()
    matches = matches.sort_values('length')

    results = []
    for _, row in matches.head(max_results).iterrows():
        results.append({
            "danish": row['text_da'],
            "english": row['text_en'],
            "source": "tatoeba",
            "source_id": str(int(row['sentence_id']))
        })
    return results
```

**Note on licensing:** Tatoeba sentences are CC-BY 2.0. Attribution to
Tatoeba is required if you publish. A single line in the dictionary
acknowledgements section is sufficient.

---

## Stage 4 — Frequency Data from Leipzig

```python
def load_leipzig_ranks(words_path: str) -> dict[str, int]:
    """
    Load word frequency ranks from the Leipzig words file.
    Returns a dict mapping word -> rank (1 = most frequent).
    """
    df = pd.read_csv(words_path, sep='\t', header=None,
                     names=['rank', 'word', 'frequency'])
    return dict(zip(df['word'].str.lower(), df['rank']))


def get_frequency_tier(rank: int | None) -> str:
    if rank is None:
        return "TODO"
    if rank <= 500:
        return "core"
    if rank <= 2000:
        return "common"
    if rank <= 5000:
        return "general"
    return "rare"
```

---

## Stage 5 — Generate Phonetic Approximations

IPA is great but not enough on its own for a dyslexic learner. We also
need the plain-English phonetic approximation (e.g. `HOO-yeh` for *hygge*).

Danish phonology is complex enough that fully automatic approximation is
unreliable. The approach here is a rule-based approximation that covers
the most common patterns, flagging unusual cases for manual review.

```python
# Danish-to-plain-English phonetic rules
# These cover the most frequent patterns. Edge cases need manual review.

PHONETIC_RULES = [
    # Vowels
    (r'aa', 'AW'),
    (r'å', 'AW'),
    (r'æ', 'EH'),
    (r'ø', 'UR'),   # approximate — no English equivalent
    (r'y', 'EW'),   # approximate
    (r'ej', 'AY'),
    (r'aj', 'AY'),
    (r'eg$', 'AY'), # word-final -eg
    (r'ig$', 'EE'), # word-final -ig

    # Consonants
    (r'hv', 'V'),   # hv- is pronounced as V
    (r'gn', 'N'),   # gn- drops the g
    (r'kn', 'N'),   # kn- drops the k (unlike English)
    (r'(?<=\w)d(?=\w)', 'TH'),  # soft-d between vowels → TH (approximate)
    (r'g(?=[eiy])', 'Y'),       # g before front vowels → Y sound
    (r'j', 'Y'),
    (r'v$', 'W'),   # word-final v often softens

    # Common endings
    (r'lig$', 'lee'),
    (r'else$', 'el-seh'),
    (r'hed$', 'heth'),
    (r'ig$', 'ee'),
]

def approximate_phonetics(word: str) -> tuple[str, bool]:
    """
    Generate a plain-English phonetic approximation.
    Returns (approximation, needs_manual_review).
    Flags words with soft-d, stød, or uncommon patterns for review.
    """
    result = word.lower()
    needs_review = False

    for pattern, replacement in PHONETIC_RULES:
        result = re.sub(pattern, replacement, result)

    # Flag for manual review if:
    # - Contains d between vowels (soft-d candidate)
    # - Contains stød markers (ˀ in IPA)
    # - Is unchanged after rules (likely an edge case)
    if re.search(r'[aeiouæøå]d[aeiouæøå]', word.lower()):
        needs_review = True
    if result.lower() == word.lower():
        needs_review = True

    return result.upper(), needs_review
```

---

## Stage 6 — Assemble Entry Files

```python
import yaml
from pathlib import Path
from datetime import date

TEMPLATE = """\
---

## HEADWORD [REQUIRED]

```
headword: {headword}
direction: {direction}
```

---

## GRAMMAR [REQUIRED]

```
pos: {pos}
gender: {gender}
```

### Inflections [OPTIONAL]

```
inflections: {inflections}
```

---

## PRONUNCIATION [REQUIRED]

```
phonetic_plain: {phonetic_plain}
ipa: {ipa}
syllables: TODO
stoed: {stoed}
```

---

## TRANSLATION [REQUIRED]

```
primary_translation: {primary_translation}
secondary_translations:
{secondary_translations}
```

---

## REGISTER [NOT FILLED — FUTURE OPTION]

This field was intentionally left unfilled (all entries remain `TODO`). It is not
rendered in `dictionary.html` and was not part of the pipeline.

It could in theory be populated from ordnet.dk, where register labels appear as
inline text (*hverdagssprog*, *formelt*, *slang*, *forældet*, etc.) in the article
body — but most neutral words carry no label, so ~90% of entries would be `neutral`
by default. A scraper + heuristic approach is feasible if this becomes a priority.

```
register: TODO
domain: TODO
formality: TODO
```

---

## EXAMPLE SENTENCES [REQUIRED]

```yaml
examples:
{examples}
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
tags: TODO
```

---

## FREQUENCY [REQUIRED]

```
frequency_rank: {frequency_rank}
frequency_tier: {frequency_tier}
```

---

## LAYOUT HINTS [MANUAL]

```
layout:
  print_emphasis: normal
  flag_false_friend: false
  flag_spelling_trap: false
  flag_pronunciation_trap: {flag_pronunciation_trap}
```

---

## PIPELINE METADATA [AUTO-POPULATED]

```
entry_id: {entry_id}
created: {created}
last_modified: {created}
source_wiktionary: {source_wiktionary}
source_tatoeba: {source_tatoeba}
source_leipzig: {source_leipzig}
review_status: draft
reviewed_by: TODO
notes: {notes}
```
"""


def format_secondary_translations(translations: list[str]) -> str:
    if not translations:
        return "  - SKIP"
    return '\n'.join(f"  - {t}" for t in translations)


def format_examples(examples: list[dict]) -> str:
    if not examples:
        return "  - danish: TODO\n    english: TODO\n    source: manual\n    source_id: SKIP"
    lines = []
    for ex in examples:
        lines.append(f"  - danish: {ex['danish']}")
        lines.append(f"    english: {ex['english']}")
        lines.append(f"    source: {ex['source']}")
        lines.append(f"    source_id: {ex.get('source_id', 'SKIP')}")
    return '\n'.join(lines)


def build_entry(
    headword: str,
    wikt_data: dict,
    examples: list[dict],
    freq_rank: int | None,
    direction: str = "DA→EN",
    output_dir: Path = Path("entries")
) -> Path:
    """
    Assemble a complete entry file from pipeline data.
    Returns the path of the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    phonetic, needs_review = approximate_phonetics(headword)

    freq_tier = get_frequency_tier(freq_rank)

    # Build safe entry ID
    safe_word = re.sub(r'[^a-z0-9]', '-', headword.lower())
    lang_prefix = 'da' if direction == 'DA→EN' else 'en'
    entry_id = f"{lang_prefix}-{safe_word}-001"

    content = TEMPLATE.format(
        headword=headword,
        direction=direction,
        pos=wikt_data.get('pos') or 'TODO',
        gender=wikt_data.get('gender') or 'SKIP',
        inflections='TODO',
        phonetic_plain=phonetic,
        ipa=wikt_data.get('ipa') or 'TODO',
        stoed='TODO',
        primary_translation=wikt_data.get('primary_translation') or 'TODO',
        secondary_translations=format_secondary_translations(
            wikt_data.get('secondary_translations', [])
        ),
        examples=format_examples(examples),
        frequency_rank=freq_rank or 'TODO',
        frequency_tier=freq_tier,
        flag_pronunciation_trap=str(needs_review).lower(),
        entry_id=entry_id,
        created=str(date.today()),
        source_wiktionary=str(bool(wikt_data)).lower(),
        source_tatoeba=str(bool(examples)).lower(),
        source_leipzig=str(freq_rank is not None).lower(),
        notes='Phonetic approximation needs manual review.' if needs_review else 'SKIP'
    )

    output_path = output_dir / f"{entry_id}.md"
    output_path.write_text(content, encoding='utf-8')
    return output_path
```

---

## Putting It All Together

```python
from pathlib import Path
from tqdm import tqdm

def run_pipeline(
    wordlist_path: str,
    tatoeba_sentences_path: str,
    tatoeba_links_path: str,
    leipzig_words_path: str,
    output_dir: str = "entries",
    direction: str = "DA→EN",
    use_api: bool = True,          # False = use local dump
    wiktionary_dump_path: str = None
):
    print("Loading word list...")
    wordlist = Path(wordlist_path).read_text().strip().splitlines()
    wordlist = [w.strip() for w in wordlist if w.strip()]

    print("Loading Tatoeba pairs...")
    pairs = load_tatoeba(tatoeba_sentences_path, tatoeba_links_path)

    print("Loading Leipzig frequency data...")
    freq_ranks = load_leipzig_ranks(leipzig_words_path)

    print("Loading Wiktionary data...")
    if use_api:
        wikt_raw = fetch_all_words(wordlist)
    else:
        wikt_raw = stream_wiktionary_dump(wiktionary_dump_path, set(wordlist))

    print(f"Processing {len(wordlist)} words...")
    skipped = []
    written = []

    for word in tqdm(wordlist):
        wikitext = wikt_raw.get(word, '')
        da_section = extract_danish_section(wikitext) if wikitext else ''
        wikt_data = parse_entry(da_section) if da_section else {}

        examples = find_examples(word, pairs, max_results=3)
        freq_rank = freq_ranks.get(word.lower())

        if not wikt_data and not examples:
            skipped.append(word)
            continue

        path = build_entry(
            headword=word,
            wikt_data=wikt_data,
            examples=examples,
            freq_rank=freq_rank,
            direction=direction,
            output_dir=Path(output_dir)
        )
        written.append(path)

    print(f"\nDone. {len(written)} entries written, {len(skipped)} skipped.")
    if skipped:
        Path("skipped.txt").write_text('\n'.join(skipped))
        print(f"Skipped words saved to skipped.txt for manual handling.")


# Example invocation
if __name__ == "__main__":
    run_pipeline(
        wordlist_path="wordlist.txt",
        tatoeba_sentences_path="data/sentences.csv",
        tatoeba_links_path="data/links.csv",
        leipzig_words_path="data/dan_news_2020_1M-words.txt",
        output_dir="entries/da-en",
        direction="DA→EN",
        use_api=True
    )
```

---

## After the Pipeline — Editorial Passes

The pipeline produces `draft` status entries. Before typesetting, each
entry needs at least one editorial pass. Work through them in priority
order:

### Pass 1 — Completeness Check (can be scripted)
Flag any entry where required fields are still `TODO`. Run:

```python
import glob, re

for path in glob.glob("entries/**/*.md", recursive=True):
    content = open(path).read()
    todos = content.count('TODO')
    if todos > 0:
        print(f"{path}: {todos} TODO fields remaining")
```

### Pass 2 — Pronunciation Review (manual)
Work through all entries flagged `flag_pronunciation_trap: true`. These
need a human to write or verify the `phonetic_plain` field. Focus
especially on:

- Words with soft-d (blødt d)
- Words with stød
- Words where vowels behave unexpectedly (ø, y, æ)
- Words where spelling and sound are very different

### Pass 3 — Memory Hooks (manual — your expertise)
Write one-sentence memory hooks for the 200 most frequent entries. These
are the words a learner will see most — a good hook here pays the most
dividends.

### Pass 4 — False Friend Flags (manual)
Review entries where the Danish word resembles an English word. Set
`flag_false_friend: true` and add a note in the translation. Core
examples to check:

| Danish | Looks like | Actually means |
|---|---|---|
| gift | gift | poison / married |
| eventuelt | eventually | possibly |
| blank | blank | shiny, polished |
| aktuel | actual | current, relevant |
| kontrollere | control | to check, verify |
| der | there | there / who / that |
| blik | blink | glance / tin/sheet metal |

### Pass 5 — Thematic Tags (can be partially scripted)
Tags can be partially inferred from the translation text using keyword
matching, then manually reviewed.

```python
TAG_KEYWORDS = {
    'food': ['eat', 'food', 'drink', 'cook', 'meal', 'taste'],
    'emotion': ['feel', 'happy', 'sad', 'angry', 'love', 'fear', 'worry'],
    'nature': ['tree', 'water', 'animal', 'plant', 'weather', 'forest'],
    'body': ['hand', 'eye', 'head', 'arm', 'leg', 'heart', 'face'],
    'work': ['work', 'job', 'office', 'meeting', 'colleague', 'task'],
    'home': ['house', 'room', 'kitchen', 'garden', 'door', 'window'],
}

def suggest_tags(translation: str) -> list[str]:
    tags = []
    translation_lower = translation.lower()
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in translation_lower for kw in keywords):
            tags.append(tag)
    return tags or ['TODO']
```

---

## File and Folder Structure

```
ordbog/
├── wordlist.txt              # Input word list
├── pipeline_guide.md         # This file
├── entry_template.md         # Schema reference
├── skipped.txt               # Words the pipeline couldn't handle
├── data/
│   ├── sentences.csv         # Tatoeba sentences (downloaded)
│   ├── links.csv             # Tatoeba links (downloaded)
│   └── dan_news_2020_1M-words.txt  # Leipzig frequency data
└── entries/
    ├── da-en/                # DA→EN entries
    │   ├── da-hygge-001.md
    │   ├── da-hus-001.md
    │   └── ...
    └── en-da/                # EN→DA entries
        ├── en-cosy-001.md
        └── ...
```

---

## Known Limitations and Manual Interventions

| Issue | Frequency | Fix |
|---|---|---|
| Word not in Wiktionary | ~15–20% of list | Manual entry or alternative source |
| Gender not parsed | ~10% of nouns | Check ordnet.dk manually |
| IPA missing | ~25% of entries | Cross-reference forvo.com |
| Soft-d not detected | Edge cases | Manual pronunciation review pass |
| Tatoeba sentence too complex | Common | Manually replace with simpler sentence |
| False friends not flagged | Requires domain knowledge | Dedicated manual pass |

---

## License and Attribution Requirements

| Source | License | Attribution required |
|---|---|---|
| Wiktionary | CC-BY-SA 4.0 | Yes — acknowledge in dictionary front matter |
| Tatoeba | CC-BY 2.0 | Yes — acknowledge in dictionary front matter |
| Leipzig Corpora | CC-BY | Yes — acknowledge in dictionary front matter |

Suggested acknowledgement text for the printed dictionary:

> "Vocabulary data sourced in part from Wiktionary (CC-BY-SA 4.0),
> example sentences from Tatoeba (tatoeba.org, CC-BY 2.0), and frequency
> data from the Leipzig Corpora Collection (CC-BY). All sources have been
> reviewed and edited."

---
<!-- END OF PIPELINE GUIDE -->
