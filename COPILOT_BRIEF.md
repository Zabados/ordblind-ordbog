# Project Brief: Dyslexia-Friendly Danish–English Ordbog
# For: GitHub Copilot / Claude Code
# Status: Pipeline exists and has run. Entries are being generated. Next phase is diagnosis, improvement, and tooling for editorial review.

---

## What This Project Is

A self-published, dyslexia-friendly bilingual dictionary: Danish→English and
English→Danish. The end goal is a physical hardback book (A4, full colour,
lay-flat sewn binding) usable in Danish language exams (PD2/PD3) and English
school exams in Denmark.

The primary author is a dyslexic PD3 student. The design decisions throughout
— layout, typography, colour coding, phonetic approximations, fuzzy-finding
aids — are all driven by dyslexia accessibility first.

This is not a web app. The pipeline produces structured markdown entry files
which will eventually be typeset into a printed book. All tooling should
serve that goal.

---

## Repository Structure

```
ordbog/
├── COPILOT_BRIEF.md          ← this file
├── entry_template.md         ← schema for a single dictionary entry
├── pipeline_guide.md         ← full technical documentation of the pipeline
├── wordlist.txt              ← input word list (Danish, top ~3000 by frequency)
├── skipped.txt               ← words the pipeline could not process
├── scripts/
│   ├── download_data.py      ← Step 0: downloads Tatoeba + Leipzig data
│   ├── make_wordlist.py      ← Step 1: generates wordlist.txt from Leipzig
│   └── pipeline.py           ← Step 2: generates entry .md files
└── data/
│   ├── dan_sentences.tsv     ← Tatoeba Danish sentences (downloaded)
│   ├── eng_sentences.tsv     ← Tatoeba English sentences (downloaded)
│   ├── links.csv             ← Tatoeba translation links (downloaded)
│   └── dan_news_2020_1M-words.txt  ← Leipzig frequency data (manual download)
└── entries/
    ├── da-en/                ← DA→EN entry files (one .md per word)
    └── en-da/                ← EN→DA entry files (not yet generated)
```

---

## Entry File Schema

Every entry file follows the schema defined in `entry_template.md`.
Key fields are:

| Field | Status | Notes |
|---|---|---|
| `headword` | auto | The Danish (or English) word |
| `direction` | auto | DA→EN or EN→DA |
| `pos` | auto | Part of speech from Wiktionary |
| `gender` | auto | en / et / SKIP — from Wiktionary da-noun template |
| `ipa` | auto | IPA from Wiktionary, often missing |
| `phonetic_plain` | auto | Rule-based plain-English approximation, unreliable |
| `syllables` | TODO | Not yet implemented — needs manual or tool |
| `stoed` | TODO | Stød marker — not yet implemented |
| `primary_translation` | auto | From Wiktionary definition lines |
| `secondary_translations` | auto | Up to 3 extras from Wiktionary |
| `examples` | auto | From Tatoeba DA–EN sentence pairs |
| `frequency_rank` | auto | From Leipzig frequency data |
| `frequency_tier` | auto | core / common / general / rare |
| `register` | TODO | Manual |
| `domain` | TODO | Manual |
| `tags` | TODO | Thematic tags — manual or keyword inference |
| `memory_hook` | TODO | Manual — author expertise |
| `flag_false_friend` | TODO | Manual — critical for this dictionary |
| `flag_spelling_trap` | TODO | Manual |
| `flag_pronunciation_trap` | auto | Set true when phonetic rules fire |
| `review_status` | auto | Starts as `draft` |

Fields left as `TODO` after the pipeline runs need either tooling or
manual editorial work. See the Editorial Passes section below.

---

## Pipeline: What Each Script Does

### `download_data.py`
Downloads Tatoeba per-language sentence files and links. Leipzig must be
downloaded manually (instructions printed at end of script).

Run once:
```bash
python scripts/download_data.py
```

### `make_wordlist.py`
Reads the Leipzig frequency file and outputs `wordlist.txt` — one Danish
word per line, filtered to remove proper nouns and noise, defaulting to
top 3000 words.

```bash
python scripts/make_wordlist.py           # top 3000
python scripts/make_wordlist.py --top 500
python scripts/make_wordlist.py --test    # first 50 only
```

### `pipeline.py`
The main entry generator. For each word in `wordlist.txt` it:
1. Fetches wikitext from English Wiktionary API (0.5s delay per word)
2. Extracts the Danish language section
3. Parses: POS, gender, IPA, translations
4. Finds example sentences from Tatoeba DA–EN pairs
5. Looks up Leipzig frequency rank
6. Generates a plain-English phonetic approximation (rule-based, unreliable)
7. Writes one `.md` file per word to `entries/da-en/`

The run is resumable — it skips words that already have an entry file.
Words where both Wiktionary and Tatoeba returned nothing go to `skipped.txt`.

```bash
python scripts/pipeline.py --limit 50    # test run
python scripts/pipeline.py               # full run
python scripts/pipeline.py --direction EN→DA --output entries/en-da
```

---

## Known Gaps and Problems

These are the things that need fixing or building next, roughly in priority order.

### 1. Diagnosis: What Is Missing From Existing Entries?

After the first run many entries will have `TODO` fields. We need a
diagnostic script that scans all entry files and reports:

- How many entries exist total
- How many have `TODO` in each required field
- How many are in `skipped.txt` and why (no Wiktionary data? no Tatoeba?)
- Which words have no translation at all
- Which words have no examples at all

This should output a clean summary report, e.g. `reports/audit.md`.

### 2. Wiktionary Coverage Gaps

The Wiktionary API returns nothing for:
- Words not yet in English Wiktionary's Danish section
- Words where the Danish section exists but uses non-standard templates
- Inflected forms rather than lemmas (the wordlist may contain inflections)

Possible fixes:
- Also try Danish Wiktionary (`da.wiktionary.org`) as a fallback
- Lemmatise the wordlist before running — use a Danish NLP library
  (`dacy`, `spacy` with `da_core_news_sm`) to convert inflected forms to
  their dictionary lemma before lookup
- For words still missing: scrape ordnet.dk (Den Danske Ordbog) carefully
  — it is public-facing but has no open API, so crawl politely with delays

### 3. Lemmatisation of the Wordlist

The Leipzig frequency list contains inflected word forms (e.g. `børnene`,
`gik`, `større`) not just lemmas. Wiktionary entries exist for lemmas
(`barn`, `gå`, `stor`). Many Wiktionary misses will be because the
pipeline looked up an inflected form.

Fix: add a lemmatisation step to `make_wordlist.py` using spaCy:

```bash
pip install spacy
python -m spacy download da_core_news_sm
```

```python
import spacy
nlp = spacy.load("da_core_news_sm")

def lemmatise(word: str) -> str:
    doc = nlp(word)
    return doc[0].lemma_ if doc else word
```

Apply this to each word before Wiktionary lookup. Deduplicate the list
after lemmatisation.

### 4. Phonetic Approximations Are Unreliable

The current rule-based system in `pipeline.py` (`approximate_phonetics()`)
covers common patterns but fails on:
- Soft-d (blødt d) — context-dependent, not just between vowels
- Stød — cannot be inferred from spelling alone
- Many vowel combinations
- Loanwords with different phonology

Options:
- Extend the rules — a comprehensive Danish grapheme-to-phoneme ruleset
  exists in linguistic literature
- Use eSpeak-NG (open source TTS) to generate IPA programmatically:
  ```bash
  espeak-ng -v da --ipa "hygge"
  ```
  This can be called from Python via `subprocess` and gives reliable IPA,
  which can then be used as a better base for the plain-English approximation
- Keep the current system but improve the `flag_pronunciation_trap` logic
  so more edge cases are flagged for manual review

### 5. Syllabification

The `syllables` field is `TODO` for all entries. Syllabification matters
for the printed layout (visual word chunking for dyslexic readers).

The `pyphen` library supports Danish:
```bash
pip install pyphen
```
```python
import pyphen
dic = pyphen.Pyphen(lang='da_DK')
dic.inserted('hygge')  # → 'hyg-ge'
```

Add this to `pipeline.py` and populate the `syllables` field automatically.

### 6. Thematic Tags (Semi-Automatic)

The `tags` field is `TODO` for all entries. Tags drive the thematic index
section of the printed book — a critical second retrieval route for users
who can't find a word alphabetically.

A keyword-inference approach using the primary translation:

```python
TAG_KEYWORDS = {
    'emotion': ['feel', 'happy', 'sad', 'angry', 'love', 'fear', 'worry', 'mood'],
    'body': ['hand', 'eye', 'head', 'arm', 'leg', 'heart', 'face', 'skin'],
    'health': ['sick', 'pain', 'doctor', 'medicine', 'ill', 'hospital'],
    'food': ['eat', 'food', 'drink', 'cook', 'meal', 'taste', 'hunger'],
    'home': ['house', 'room', 'kitchen', 'garden', 'door', 'window', 'flat'],
    'nature': ['tree', 'water', 'animal', 'plant', 'forest', 'sea', 'sky'],
    'weather': ['rain', 'wind', 'snow', 'sun', 'cloud', 'storm', 'temperature'],
    'work': ['work', 'job', 'office', 'meeting', 'colleague', 'task', 'employ'],
    'education': ['school', 'learn', 'study', 'teach', 'exam', 'course', 'class'],
    'bureaucracy': ['form', 'apply', 'permit', 'register', 'authority', 'official'],
    'transport': ['car', 'bus', 'train', 'bike', 'travel', 'drive', 'ride'],
    'time': ['day', 'week', 'month', 'year', 'hour', 'minute', 'morning'],
    'money': ['pay', 'cost', 'price', 'bank', 'tax', 'money', 'afford'],
    'social': ['friend', 'meet', 'talk', 'together', 'visit', 'party', 'invite'],
    'family': ['family', 'parent', 'child', 'mother', 'father', 'sibling'],
    'culture': ['music', 'art', 'film', 'book', 'theatre', 'tradition'],
    'environment': ['climate', 'nature', 'pollution', 'energy', 'recycle'],
}

def suggest_tags(translation: str) -> list[str]:
    t = translation.lower()
    return [tag for tag, kws in TAG_KEYWORDS.items() if any(k in t for k in kws)] or ['TODO']
```

This gets you a first pass. All entries still need a human check before
`review_status` is changed from `draft` to `reviewed`.

### 7. False Friend Detection

This is one of the most valuable features of this dictionary for the target
audience. Words that look like English but mean something different in Danish
are especially dangerous for dyslexic readers who lean on visual word shape.

A seed list to start with (expand this):

```python
FALSE_FRIENDS = {
    'gift': 'Means poison (noun) or married (adjective), not a present',
    'eventuelt': 'Means possibly/perhaps, not eventually',
    'blank': 'Means shiny or polished, not empty',
    'aktuel': 'Means current or relevant, not actual',
    'kontrollere': 'Means to check or verify, not to control',
    'blik': 'Means glance or tin/sheet metal, not blink',
    'chef': 'Means boss or manager, not a cook',
    'irritere': 'Means to irritate or bother, same root but stronger',
    'melon': 'Same meaning, but watch out for der/det gender',
    'abstrakt': 'Same meaning but false-friend trap on spelling',
    'fysik': 'Means physics, not physique',
    'mærkelig': 'Means strange/weird, not remarkable',
}
```

Add a post-processing step that checks each headword against this dict,
sets `flag_false_friend: true`, and appends a note to the translation field.

### 8. EN→DA Direction

The pipeline currently only runs DA→EN. The EN→DA direction is important
for Danish children learning English (the larger market segment).

For EN→DA:
- The wordlist should be English words (use a similar frequency list —
  Leipzig has English corpora, or use the BNC frequency list)
- Wiktionary lookup should target the English headword and find the Danish
  translation in the definition
- Gender must be included with every Danish translation: `hygge (en)`
- The phonetic approximation runs on the *Danish* translation, not the
  English headword

The pipeline already accepts `--direction EN→DA` but the Wiktionary parsing
logic needs extending for this case.

---

## Editorial Passes Required After Pipeline

These cannot be automated. They need the author — a Danish language learner
with dyslexia who knows what is confusing:

| Pass | What to do |
|---|---|
| Pronunciation review | Check all entries flagged `flag_pronunciation_trap: true`. Correct `phonetic_plain`. Mark `stoed: true/false`. |
| Memory hooks | Write one-sentence mnemonics for the 500 most frequent entries. |
| False friends | Review and expand the false friends list. |
| Example sentences | Replace any Tatoeba sentences that are too long, too complex, or unnatural. |
| Thematic tags | Verify auto-suggested tags. Add missing ones. |
| Spelling traps | Flag words dyslexic learners commonly misspell. |

---

## Typesetting (Future Phase)

Once entries are complete and reviewed, the markdown files need converting
to a print-ready layout. The planned approach:

- Python script reads all entry `.md` files in frequency order
- Outputs a single structured document
- Pandoc converts to LaTeX with a custom template
- LaTeX handles the multi-column dictionary layout, colour coding,
  thumb index, and section headers

Key typesetting requirements:
- Font: OpenDyslexic or Atkinson Hyperlegible
- Background: cream/ivory (#FAF6F0), not white
- Gender colour coding: warm terracotta for `en` words, slate blue for `et`
- Thumb index: coloured edge bands per letter section, visible when closed
- Page size: A4
- Binding: sewn hardback (requires short-run printer — not POD)
- False friend entries get a distinct visual flag (icon + colour band)
- Pronunciation traps get a distinct visual flag

Typesetting tooling does not yet exist. It is a future phase.

---

## Immediate Next Steps (Priority Order)

1. **Run the diagnostic script** (needs building) — understand what is
   actually in the existing entries before doing anything else
2. **Add lemmatisation** to `make_wordlist.py` and re-run on the skipped words
3. **Add syllabification** to `pipeline.py` using `pyphen`
4. **Add eSpeak-NG IPA generation** as a fallback where Wiktionary IPA is missing
5. **Add tag inference** to the pipeline
6. **Build the false friends post-processor**
7. **Re-run pipeline** on the skipped word list with improved tooling
8. **Begin editorial passes** — pronunciation review first

---

## Design Principles (Do Not Compromise These)

These are not preferences — they are the core purpose of the project:

- **Dyslexia-first**: every decision serves a reader with dyslexia under
  exam pressure. Speed of retrieval and clarity of layout matter more than
  completeness.
- **Phonetics are essential**: a bilingual dictionary without reliable
  pronunciation guidance is half a dictionary for this audience.
  Danish spelling-to-sound correspondence is particularly opaque.
- **Multiple retrieval routes**: alphabetical lookup, phonetic sound index,
  thematic groupings, and misspelling redirects all exist in the final book.
  A reader who can't find a word one way must be able to find it another way.
- **False friends are a priority feature**, not an optional extra.
- **No walls of text**: every entry must be scannable in under 5 seconds.

---

## Licensing and Attribution

The pipeline draws on three open sources. Attribution is required in the
printed dictionary:

- **Wiktionary** — CC-BY-SA 4.0
- **Tatoeba** — CC-BY 2.0 (tatoeba.org)
- **Leipzig Corpora Collection** — CC-BY

---
<!-- END OF BRIEF -->
