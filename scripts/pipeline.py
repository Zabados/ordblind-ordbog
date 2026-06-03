"""
Step 2 — Run the Ordbog entry pipeline.

Reads wordlist.txt, fetches Wiktionary data, matches Tatoeba example
sentences, looks up Leipzig frequency ranks, and writes one .md entry
file per word into entries/da-en/ (or entries/en-da/).

Run after download_data.py and make_wordlist.py:
    python scripts/pipeline.py --limit 50        # test run — 50 words
    python scripts/pipeline.py                   # full run

Options:
  --wordlist PATH    Word list file (default: wordlist.txt)
  --direction        DA→EN or EN→DA (default: DA→EN)
  --output PATH      Output directory (default: entries/da-en)
  --limit N          Process only the first N words
"""

import argparse
import re
import time
from datetime import date
from pathlib import Path

import mwparserfromhell
import pyphen
import pandas as pd
import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Stage 2 — Wiktionary
# ---------------------------------------------------------------------------

WIKTIONARY_URL = "https://en.wiktionary.org/w/api.php"
USER_AGENT = "DanishDyslexiaOrdbog/0.1 (educational project; github.com/ordbog)"


def fetch_wiktionary(word: str, retries: int = 3) -> str | None:
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json",
        "redirects": True,
    }
    for attempt in range(retries):
        try:
            r = requests.get(
                WIKTIONARY_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None
            data = r.json()
            if "error" in data:
                return None
            return data["parse"]["wikitext"]["*"]
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None



def extract_danish_section(wikitext: str) -> str | None:
    # Language sections use ==Language== (level 2 headings).
    # Stop at the next level-2 heading (== but not ===).
    match = re.search(r"(==Danish==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    return match.group(1) if match else None


_VALID_POS = {
    "noun", "verb", "adjective", "adverb", "pronoun",
    "preposition", "conjunction", "interjection", "phrase",
}


def parse_entry(wikitext: str) -> dict:
    entry: dict = {
        "pos": None,
        "gender": None,
        "ipa": None,
        "primary_translation": None,
        "secondary_translations": [],
    }

    parsed = mwparserfromhell.parse(wikitext)

    # Part of speech from section headers (===Noun===, ===Verb===, ...)
    for section in parsed.get_sections(levels=[3]):
        headings = section.filter_headings()
        if headings:
            pos_raw = headings[0].title.strip_code().strip().lower()
            if pos_raw in _VALID_POS:
                entry["pos"] = pos_raw
                break  # take the first POS found

    # IPA pronunciation — {{IPA|da|/ipa/}} or {{IPA|/ipa/}}
    for template in parsed.filter_templates():
        if template.name.strip() == "IPA":
            try:
                params = template.params
                # Skip leading language-code parameter (e.g. "da", "en")
                for p in params:
                    val = str(p.value).strip()
                    if val.startswith("/") or val.startswith("["):
                        entry["ipa"] = val
                        break
            except (IndexError, AttributeError):
                pass
            break

    # Noun gender from {{da-noun|en|...}} or {{da-noun|et|...}}
    for template in parsed.filter_templates():
        if template.name.strip() in ("da-noun", "da-noun-form"):
            try:
                g = str(template.params[0].value).strip()
                if g in ("en", "c"):
                    entry["gender"] = "en"
                elif g in ("et", "n"):
                    entry["gender"] = "et"
            except IndexError:
                pass
            break

    # Translations from definition lines starting with "# "
    translations: list[str] = []
    for line in wikitext.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            clean = mwparserfromhell.parse(line).strip_code().strip().lstrip("# ").strip()
            if clean and len(clean) > 1:
                translations.append(clean)

    if translations:
        entry["primary_translation"] = translations[0]
        entry["secondary_translations"] = translations[1:4]

    return entry


# ---------------------------------------------------------------------------
# Stage 3 — Tatoeba example sentences
# ---------------------------------------------------------------------------


def load_tatoeba(da_path: Path, en_path: Path, links_path: Path) -> pd.DataFrame:
    cache_path = links_path.parent / "tatoeba_da_en_pairs.parquet"

    if cache_path.exists():
        print("  Loading Tatoeba pairs from cache ...")
        return pd.read_parquet(cache_path)

    da = pd.read_csv(
        da_path, sep="\t", header=None, names=["id", "lang", "text"], quoting=3
    )
    en = pd.read_csv(
        en_path, sep="\t", header=None, names=["id", "lang", "text"], quoting=3
    )

    da_ids = set(da["id"])
    en_ids = set(en["id"])

    # links.csv covers all languages (~450 MB). Read in chunks and keep only
    # rows where one side is Danish and the other is English.
    kept: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        links_path,
        sep="\t",
        header=None,
        names=["sentence_id", "translation_id"],
        chunksize=200_000,
    ):
        mask = chunk["sentence_id"].isin(da_ids) & chunk["translation_id"].isin(en_ids)
        kept.append(chunk[mask])

    links = pd.concat(kept, ignore_index=True)

    da_links = links.merge(da[["id", "text"]], left_on="sentence_id", right_on="id")
    pairs = da_links.merge(
        en[["id", "text"]],
        left_on="translation_id",
        right_on="id",
        suffixes=("_da", "_en"),
    )
    result = pairs[["sentence_id", "text_da", "translation_id", "text_en"]]
    try:
        result.to_parquet(cache_path, index=False)
        print(f"  Tatoeba cache saved to {cache_path.name}")
    except Exception:
        pass  # parquet optional — pyarrow/fastparquet may not be installed
    return result


def find_examples(word: str, pairs: pd.DataFrame, max_results: int = 3) -> list[dict]:
    mask = pairs["text_da"].str.contains(
        rf"\b{re.escape(word)}\b", case=False, na=False
    )
    matches = pairs[mask].copy()
    matches["length"] = matches["text_da"].str.len()
    matches = matches.sort_values("length")

    results: list[dict] = []
    for _, row in matches.head(max_results).iterrows():
        results.append(
            {
                "danish": row["text_da"],
                "english": row["text_en"],
                "source": "tatoeba",
                "source_id": str(int(row["sentence_id"])),
            }
        )
    return results


# ---------------------------------------------------------------------------
# Stage 4 — Leipzig frequency
# ---------------------------------------------------------------------------


def load_leipzig_ranks(words_path: Path) -> dict[str, int]:
    df = pd.read_csv(
        words_path, sep="\t", header=None, names=["rank", "word", "frequency"],
        quoting=3, encoding="utf-8",
    )
    df["word_lower"] = df["word"].str.lower()
    # Keep the best (lowest) rank for each lowercase word
    best = df.groupby("word_lower")["rank"].min()
    return best.to_dict()


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


# ---------------------------------------------------------------------------
# Stage 5 — Phonetic approximation
# ---------------------------------------------------------------------------

_PHONETIC_RULES = [
    (r"aa", "AW"),
    (r"å", "AW"),
    (r"æ", "EH"),
    (r"ø", "UR"),
    (r"y", "EW"),
    (r"ej", "AY"),
    (r"aj", "AY"),
    (r"eg$", "AY"),
    (r"hv", "V"),
    (r"gn", "N"),
    (r"kn", "N"),
    (r"(?<=[aeiouæøå])d(?=[aeiouæøå])", "TH"),
    (r"g(?=[eiy])", "Y"),
    (r"j", "Y"),
    (r"v$", "W"),
    (r"lig$", "lee"),
    (r"else$", "el-seh"),
    (r"hed$", "heth"),
    (r"ig$", "ee"),
]


# ---------------------------------------------------------------------------
# Syllabification
# ---------------------------------------------------------------------------

_pyphen_da = pyphen.Pyphen(lang="da_DK")


def syllabify(word: str) -> str:
    result = _pyphen_da.inserted(word, hyphen="-")
    return result if result else word


# ---------------------------------------------------------------------------
# Tag inference
# ---------------------------------------------------------------------------

_TAG_KEYWORDS: dict[str, list[str]] = {
    "emotion": ["feel", "happy", "sad", "angry", "love", "fear", "worry", "mood", "grief", "joy"],
    "body": ["hand", "eye", "head", "arm", "leg", "heart", "face", "skin", "finger", "back"],
    "health": ["sick", "pain", "doctor", "medicine", "ill", "hospital", "disease", "health"],
    "food": ["eat", "food", "drink", "cook", "meal", "taste", "hunger", "bread", "meat"],
    "drink": ["drink", "water", "beer", "wine", "coffee", "tea", "juice", "thirst"],
    "home": ["house", "room", "kitchen", "garden", "door", "window", "flat", "floor", "home"],
    "nature": ["tree", "water", "animal", "plant", "forest", "sea", "sky", "river", "mountain"],
    "weather": ["rain", "wind", "snow", "sun", "cloud", "storm", "temperature", "weather"],
    "work": ["work", "job", "office", "meeting", "colleague", "task", "employ", "career"],
    "education": ["school", "learn", "study", "teach", "exam", "course", "class", "student"],
    "bureaucracy": ["form", "apply", "permit", "register", "authority", "official", "application"],
    "transport": ["car", "bus", "train", "bike", "travel", "drive", "ride", "plane", "road"],
    "time": ["day", "week", "month", "year", "hour", "minute", "morning", "evening", "time"],
    "money": ["pay", "cost", "price", "bank", "tax", "money", "afford", "wage", "salary"],
    "social": ["friend", "meet", "talk", "together", "visit", "party", "invite", "social"],
    "family": ["family", "parent", "child", "mother", "father", "sibling", "son", "daughter"],
    "culture": ["music", "art", "film", "book", "theatre", "tradition", "festival", "dance"],
    "politics": ["vote", "government", "party", "parliament", "minister", "election", "law"],
    "environment": ["climate", "nature", "pollution", "energy", "recycle", "environment"],
    "technology": ["computer", "phone", "internet", "software", "digital", "data", "app"],
}


def infer_tags(translation: str) -> str:
    """Return a YAML-formatted tag list inferred from the translation text."""
    if not translation or translation == "TODO":
        return "  - TODO"
    t = translation.lower()
    matched = [tag for tag, kws in _TAG_KEYWORDS.items() if any(k in t for k in kws)]
    if not matched:
        return "  - TODO"
    return "\n".join(f"  - {tag}" for tag in matched[:3])


# ---------------------------------------------------------------------------
# False friends
# ---------------------------------------------------------------------------

_FALSE_FRIENDS: dict[str, str] = {
    "gift": "Means poison (noun) or married (adj), NOT a present",
    "eventuelt": "Means possibly/perhaps, NOT eventually",
    "blank": "Means shiny or polished, NOT empty/blank",
    "aktuel": "Means current or relevant, NOT actual",
    "kontrollere": "Means to check or verify, NOT to control",
    "blik": "Means glance or tin/sheet metal, NOT blink",
    "chef": "Means boss or manager, NOT a chef/cook",
    "irritere": "Means to irritate or bother — stronger connotation than English",
    "fysik": "Means physics, NOT physique",
    "mærkelig": "Means strange/weird, NOT remarkable",
    "abstrakt": "Same meaning but spelling trap — Danish has no 'c'",
    "delikat": "Means delicate or tricky, NOT delicious",
    "realisere": "Means to implement/carry out, NOT to realise/understand",
    "sensibel": "Means sensitive, NOT sensible",
    "kompetent": "Means competent — same meaning, but false friend for Danish learners on spelling",
}


def is_false_friend(headword: str) -> tuple[bool, str]:
    note = _FALSE_FRIENDS.get(headword.lower(), "")
    return bool(note), note


def approximate_phonetics(word: str) -> tuple[str, bool]:
    result = word.lower()
    for pattern, replacement in _PHONETIC_RULES:
        result = re.sub(pattern, replacement, result)

    needs_review = bool(re.search(r"[aeiouæøå]d[aeiouæøå]", word.lower()))
    if result.lower() == word.lower():
        needs_review = True

    return result.upper(), needs_review


# ---------------------------------------------------------------------------
# Stage 6 — Assemble entry files
# ---------------------------------------------------------------------------

_ENTRY_TEMPLATE = """\
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
inflections: TODO
```

---

## PRONUNCIATION [REQUIRED]

```
phonetic_plain: {phonetic_plain}
ipa: {ipa}
syllables: {syllables}
stoed: TODO
```

---

## TRANSLATION [REQUIRED]

```
primary_translation: {primary_translation}
secondary_translations:
{secondary_translations}
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
tags:
{tags}
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
  flag_false_friend: {flag_false_friend}
  flag_false_friend_note: {flag_false_friend_note}
  flag_spelling_trap: false
  flag_pronunciation_trap: {flag_pronunciation_trap}
```

---

## PIPELINE METADATA

```
entry_id: {entry_id}
created: {created}
last_modified: {created}
source_wiktionary: {source_wiktionary}
source_tatoeba: {source_tatoeba}
source_leipzig: {source_leipzig}
review_status: draft
reviewed_by: SKIP
notes: {notes}
```
"""


def _fmt_secondary(translations: list[str]) -> str:
    if not translations:
        return "  - SKIP"
    return "\n".join(f"  - {t}" for t in translations)


def _fmt_examples(examples: list[dict]) -> str:
    if not examples:
        return (
            "  - danish: TODO\n"
            "    english: TODO\n"
            "    source: manual\n"
            "    source_id: SKIP"
        )
    lines: list[str] = []
    for ex in examples:
        lines += [
            f"  - danish: {ex['danish']}",
            f"    english: {ex['english']}",
            f"    source: {ex['source']}",
            f"    source_id: {ex.get('source_id', 'SKIP')}",
        ]
    return "\n".join(lines)


def build_entry(
    headword: str,
    wikt_data: dict,
    examples: list[dict],
    freq_rank: int | None,
    direction: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    phonetic, needs_review = approximate_phonetics(headword)
    freq_tier = get_frequency_tier(freq_rank)
    safe_word = re.sub(r"[^a-z0-9]", "-", headword.lower())
    lang_prefix = "da" if direction == "DA→EN" else "en"
    entry_id = f"{lang_prefix}-{safe_word}-001"

    pos = wikt_data.get("pos") or "TODO"
    if pos == "noun":
        gender = wikt_data.get("gender") or "TODO"
    else:
        gender = "SKIP"

    syllables = syllabify(headword)
    primary_translation = wikt_data.get("primary_translation") or "TODO"
    tags = infer_tags(primary_translation)
    ff_flag, ff_note = is_false_friend(headword)

    content = _ENTRY_TEMPLATE.format(
        headword=headword,
        direction=direction,
        pos=pos,
        gender=gender,
        phonetic_plain=phonetic,
        ipa=wikt_data.get("ipa") or "TODO",
        syllables=syllables,
        primary_translation=primary_translation,
        secondary_translations=_fmt_secondary(wikt_data.get("secondary_translations", [])),
        examples=_fmt_examples(examples),
        tags=tags,
        frequency_rank=freq_rank if freq_rank is not None else "TODO",
        frequency_tier=freq_tier,
        flag_false_friend=str(ff_flag).lower(),
        flag_false_friend_note=ff_note if ff_note else "SKIP",
        flag_pronunciation_trap=str(needs_review).lower(),
        entry_id=entry_id,
        created=str(date.today()),
        source_wiktionary=str(bool(wikt_data)).lower(),
        source_tatoeba=str(bool(examples)).lower(),
        source_leipzig=str(freq_rank is not None).lower(),
        notes=(
            "Phonetic approximation needs manual review."
            if needs_review
            else "SKIP"
        ),
    )

    output_path = output_dir / f"{entry_id}.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    wordlist_path: Path,
    da_sentences_path: Path,
    en_sentences_path: Path,
    links_path: Path,
    leipzig_path: Path,
    output_dir: Path,
    direction: str = "DA→EN",
    limit: int | None = None,
) -> None:
    wordlist = wordlist_path.read_text(encoding="utf-8").strip().splitlines()
    wordlist = [w.strip() for w in wordlist if w.strip()]
    if limit:
        wordlist = wordlist[:limit]

    print(f"Processing {len(wordlist)} words ({direction})")

    tatoeba_ok = (
        da_sentences_path.exists()
        and en_sentences_path.exists()
        and links_path.exists()
    )
    if tatoeba_ok:
        print("Loading Tatoeba pairs (filtering links — takes ~30 s) ...")
        pairs = load_tatoeba(da_sentences_path, en_sentences_path, links_path)
        print(f"  {len(pairs):,} Danish–English sentence pairs loaded")
    else:
        print("WARNING: Tatoeba data not found — examples will be TODO")
        pairs = pd.DataFrame(
            columns=["sentence_id", "text_da", "translation_id", "text_en"]
        )

    if leipzig_path.exists():
        print("Loading Leipzig ranks ...")
        freq_ranks = load_leipzig_ranks(leipzig_path)
    else:
        print("WARNING: Leipzig data not found — frequency will be TODO")
        freq_ranks = {}

    # Skip words that already have an entry file (makes the run resumable).
    lang_prefix = "da" if direction == "DA→EN" else "en"
    pending = []
    for word in wordlist:
        safe_word = re.sub(r"[^a-z0-9]", "-", word.lower())
        entry_file = output_dir / f"{lang_prefix}-{safe_word}-001.md"
        if not entry_file.exists():
            pending.append(word)
    if len(pending) < len(wordlist):
        print(f"  {len(wordlist) - len(pending)} entries already exist — skipping them")

    skipped: list[str] = []
    written: list[Path] = []

    # Fetch Wiktionary and write each entry immediately — safe to interrupt.
    for word in tqdm(pending, desc="Fetching & writing"):
        wikitext = fetch_wiktionary(word)
        time.sleep(0.5)
        da_section = extract_danish_section(wikitext) if wikitext else ""
        wikt_data = parse_entry(da_section) if da_section else {}
        examples = find_examples(word, pairs) if tatoeba_ok else []
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
            output_dir=output_dir,
        )
        written.append(path)

    print(f"\nDone — {len(written)} entries written, {len(skipped)} skipped.")
    if skipped:
        skipped_path = Path("skipped.txt")
        skipped_path.write_text("\n".join(skipped), encoding="utf-8")
        print("Skipped words → skipped.txt")


if __name__ == "__main__":
    ROOT = Path(__file__).parent.parent
    DATA = ROOT / "data"

    parser = argparse.ArgumentParser(description="Run the Ordbog entry pipeline.")
    parser.add_argument("--wordlist", default=str(ROOT / "wordlist.txt"))
    parser.add_argument(
        "--direction", default="DA→EN", choices=["DA→EN", "EN→DA"]
    )
    parser.add_argument("--output", default=str(ROOT / "entries" / "da-en"))
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N words (for testing)",
    )
    args = parser.parse_args()

    run_pipeline(
        wordlist_path=Path(args.wordlist),
        da_sentences_path=DATA / "dan_sentences.tsv",
        en_sentences_path=DATA / "eng_sentences.tsv",
        links_path=DATA / "links.csv",
        leipzig_path=DATA / "dan_news_2020_1M-words.txt",
        output_dir=Path(args.output),
        direction=args.direction,
        limit=args.limit,
    )
