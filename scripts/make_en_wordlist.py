"""
make_en_wordlist.py
-------------------
Build a curated English wordlist for the EN-DA dictionary section.

Source: NLTK Brown corpus (written American English prose, ~1M words),
        lemmatized and POS-filtered to genuine content words.
Output: data/en_wordlist.txt  (~1500 words, frequency-ranked)

Run:
    python scripts/make_en_wordlist.py
    python scripts/make_en_wordlist.py --show-sample  # print sample bands
    python scripts/make_en_wordlist.py --target 2000  # larger list
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_FILE = ROOT / "data" / "en_wordlist.txt"

# Pure function words - no useful EN-DA dictionary value on their own
SKIP_WORDS = {
    "a", "an", "the",
    "i", "me", "my", "myself", "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "this", "that", "these", "those",
    "who", "whom", "whose", "which", "what",
    "of", "in", "on", "at", "by", "to", "up", "as", "if", "or",
    "for", "nor", "so", "yet", "but", "and",
    "into", "onto", "from", "with", "about", "above", "below",
    "between", "through", "during", "before", "after", "since",
    "under", "over", "out", "off", "down", "than", "then",
    "along", "across", "against", "within", "without", "toward",
    "towards", "upon", "via", "per", "plus", "minus", "around",
    "be", "am", "is", "are", "was", "were", "been", "being",
    "do", "does", "did", "done", "doing",
    "have", "has", "had", "having",
    "will", "would", "shall", "should", "may", "might", "must",
    "can", "could", "ought",
    "all", "any", "both", "each", "every", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "own",
    "also", "too", "very", "just", "here", "there", "where",
    "when", "how", "why", "now", "still", "already", "even",
    "never", "always", "often", "again", "really", "quite",
    "then", "else", "ever", "away",
    "www", "http", "https", "com", "org", "net", "vs", "etc",
    "ie", "eg", "re", "en", "de", "la", "le", "al",
    "mr", "mrs", "dr", "st", "co",
    "gonna", "gotta", "wanna", "yeah", "yep", "nope",
}

EXTRA_SKIP = {
    "man", "woman", "boy", "girl", "men", "women", "children",
    "american", "english", "british", "french", "german",
    "christian", "jewish", "catholic",
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    "fuck", "shit", "damn", "hell", "ass", "bitch", "crap",
    "ok", "okay", "wow", "hey", "hmm",
    # Proper-noun forms that leaked through lemmatisation
    "york", "jack", "mike", "bob", "jim", "tom", "joe", "bill",
    "harry", "sam", "frank", "henry", "paul",
    "negro",   # dated / offensive — not useful for productive writing
    "christ",  # proper noun
}


def build_from_brown(target: int = 1500) -> list:
    """Return content-word lemmas ranked by written-prose frequency (Brown corpus)."""
    try:
        import nltk
        from nltk.corpus import brown
        from nltk.stem import WordNetLemmatizer
    except ImportError:
        print("ERROR: Install nltk first: pip install nltk", file=sys.stderr)
        sys.exit(1)

    for pkg in ("brown", "wordnet", "universal_tagset", "omw-1.4"):
        nltk.download(pkg, quiet=True)

    POS_MAP = {"NOUN": "n", "VERB": "v", "ADJ": "a", "ADV": "r"}

    print("Reading Brown corpus ...", file=sys.stderr)
    tagged = brown.tagged_words(tagset="universal")
    lem = WordNetLemmatizer()

    freq = Counter()
    for word, pos in tagged:
        if pos not in POS_MAP:
            continue
        w = word.lower()
        if not w.isalpha() or len(w) < 3:
            continue
        lemma = lem.lemmatize(w, POS_MAP[pos])
        if lemma in SKIP_WORDS or lemma in EXTRA_SKIP:
            continue
        if not lemma.isalpha() or len(lemma) < 3:
            continue
        freq[lemma] += 1

    print(f"  {len(freq)} unique lemmas found", file=sys.stderr)

    result = []
    seen = set()
    for lemma, _ in freq.most_common(target * 3):
        if lemma not in seen:
            seen.add(lemma)
            result.append(lemma)
        if len(result) >= target:
            break

    return result


def main():
    parser = argparse.ArgumentParser(description="Build curated EN wordlist from Brown corpus")
    parser.add_argument("--show-sample", action="store_true",
                        help="Print sample bands to stdout without writing file")
    parser.add_argument("--target", type=int, default=1500,
                        help="Target number of output words (default 1500)")
    args = parser.parse_args()

    words = build_from_brown(target=args.target)

    if args.show_sample:
        for start, end in [(1, 60), (201, 260), (501, 560), (1001, 1060)]:
            print(f"\n--- Rank {start}-{end} ---")
            for i, w in enumerate(words[start - 1 : end], start):
                print(f"  {i:4}. {w}")
        print(f"\nTotal: {len(words)} words")
    else:
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text("\n".join(words) + "\n", encoding="utf-8")
        print(f"Written {len(words)} words -> {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()