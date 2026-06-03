"""
Step 1 — Generate wordlist.txt from the Leipzig frequency data.

Run after downloading Leipzig data:
    python scripts/make_wordlist.py          # top 3000 words
    python scripts/make_wordlist.py --test   # first 50 words only
    python scripts/make_wordlist.py --top 500
    python scripts/make_wordlist.py --no-lemma  # skip lemmatisation (faster)

The output is written to wordlist.txt in the project root.
Requires: pip install spacy && python -m spacy download da_core_news_sm
"""

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
LEIPZIG_FILE = DATA_DIR / "dan_news_2020_1M-words.txt"
OUTPUT = ROOT / "wordlist.txt"


def is_proper_noun(word: str) -> bool:
    """Words starting with a capital letter in the frequency list are proper nouns."""
    return bool(word) and word[0].isupper()


# Common Danish function words to exclude from the generated wordlist.
# These are grammatical particles that don't make useful dictionary entries.
_FUNCTION_WORDS = {
    "og", "i", "det", "at", "en", "er", "til", "på", "de", "med",
    "han", "af", "for", "ikke", "der", "var", "den", "jeg", "sig",
    "men", "et", "har", "om", "vi", "min", "havde", "ham", "hun",
    "nu", "over", "da", "fra", "du", "ud", "sin", "dem", "os",
    "op", "man", "hans", "hvor", "eller", "hvad", "vil", "jeg",
    "også", "efter", "kan", "selv", "her", "alle", "under", "når",
    "meget", "jo", "ind", "end", "så", "som", "men", "bli", "kan",
    "ned", "om", "alt", "blev", "disse", "dette", "hvilke", "som",
    "skulle", "kunne", "ville", "have", "blive", "være",
}


def is_noise(word: str) -> bool:
    """Filter out numbers, punctuation-only tokens, and very short tokens."""
    return bool(re.fullmatch(r"[\d\W]+", word)) or len(word) < 3


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate wordlist.txt from Leipzig data.")
    parser.add_argument("--top", type=int, default=3000, help="Top N words (default: 3000)")
    parser.add_argument("--test", action="store_true", help="Output first 50 words only")
    parser.add_argument("--no-lemma", action="store_true", help="Skip lemmatisation")
    args = parser.parse_args()

    if not LEIPZIG_FILE.exists():
        print(f"ERROR: {LEIPZIG_FILE} not found.")
        print("Download Leipzig data first — see scripts/download_data.py for instructions.")
        raise SystemExit(1)

    df = pd.read_csv(
        LEIPZIG_FILE, sep="\t", header=None, names=["rank", "word", "frequency"],
        quoting=3, encoding="utf-8",
    )
    df = df.dropna(subset=["word"])
    df["word"] = df["word"].astype(str)

    filtered = df[
        ~df["word"].apply(is_proper_noun) & ~df["word"].apply(is_noise)
    ]
    # Exclude function words (filter by lowercase match)
    filtered = filtered[~filtered["word"].str.lower().isin(_FUNCTION_WORDS)]
    filtered = filtered.head(args.top)

    words = filtered["word"].tolist()

    if args.test:
        words = words[:50]

    if not args.no_lemma:
        print("Lemmatising with spaCy da_core_news_sm ...")
        try:
            import spacy
            nlp = spacy.load("da_core_news_sm", disable=["parser", "ner"])
            # Process in batches for speed
            lemmas = []
            seen = set()
            for doc in nlp.pipe(words, batch_size=256):
                lemma = doc[0].lemma_ if doc else words[lemmas.__len__()]
                # Fall back to original if spaCy returns empty or punctuation
                if not lemma or not lemma.isalpha():
                    lemma = words[len(lemmas)]
                if lemma.lower() not in seen and lemma.lower() not in _FUNCTION_WORDS:
                    seen.add(lemma.lower())
                    lemmas.append(lemma.lower())
            words = lemmas
            print(f"  {len(words)} unique lemmas after deduplication")
        except Exception as e:
            print(f"WARNING: Lemmatisation failed ({e}) — using raw forms")

    OUTPUT.write_text("\n".join(words), encoding="utf-8")
    print(f"Written {len(words)} words to {OUTPUT}")
    print("Next step:  python scripts/pipeline.py --limit 50")


if __name__ == "__main__":
    main()
