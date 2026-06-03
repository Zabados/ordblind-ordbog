"""
find_missing_words.py
Cross-check Leipzig top-N words against existing entries.
Outputs a ranked CSV of words not yet covered.

Usage:
    python scripts/find_missing_words.py              # top 3000, output to missing_words.csv
    python scripts/find_missing_words.py --top 5000
    python scripts/find_missing_words.py --top 3000 --out data/missing_words.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Danish stopwords / function words — not useful in a learner's dictionary
# ---------------------------------------------------------------------------
STOPWORDS = frozenset("""
i at og er til på en af det for der har med de den ikke som et om men vil kan
han hun vi jeg du sig sin sit sine dem os jer hvad hvem hvilken
hvor hvornår da så nu her alt ingen alle meget mere mest nogen noget
anden andet andre man bare jo nok også kun ellers selv samme igen
fra eller end ind når ham hans hendes mig dig jer dem os hvad
siger fortæller mener skriver oplyser viser giver lyder ser går får fik
stod stod sagde satte tog gav lod trak brød
tidligere samt begge bag efter inden under over uden siden mens
become bliver blev blevet var var være haft gjort
""".split())

# Words that look Danish but are actually particles/conjunctions we skip
SKIP_EXACT = frozenset(["inden", "efter", "under", "over", "mod", "uden",
                         "siden", "mens", "samt", "både", "enten", "hverken",
                         "heller", "derfor", "altså", "nemlig", "dermed",
                         "hele", "nogle", "unge", "dage", "klokken", "sagen",
                         "kroner", "mennesker", "ned", "set", "ind", "nye"])


def load_leipzig(path: Path, top_n: int) -> list[tuple[int, str, int]]:
    """Return list of (rank, word, freq) for the top_n real words."""
    results = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            rank_str, word, freq_str = parts[0], parts[1], parts[2]
            try:
                rank = int(rank_str)
                freq = int(freq_str)
            except ValueError:
                continue
            if rank > top_n * 4:   # early exit — ranks aren't dense, allow slack
                break
            # keep only alphabetic words (Danish alphabet)
            if not re.fullmatch(r"[a-zæøå]+", word, re.IGNORECASE):
                continue
            word_lower = word.lower()
            if len(word_lower) < 3:
                continue
            if word_lower in STOPWORDS or word_lower in SKIP_EXACT:
                continue
            results.append((rank, word_lower, freq))
            if len(results) >= top_n:
                break
    return results


def load_headwords(entries_dir: Path) -> set[str]:
    """Extract headword values from all .md entry files."""
    headwords = set()
    hw_re = re.compile(r"^headword:\s*(.+)", re.MULTILINE)
    for md in entries_dir.glob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        m = hw_re.search(text)
        if m:
            hw = m.group(1).strip().lower()
            headwords.add(hw)
    return headwords


def is_covered(word: str, headwords: set[str]) -> bool:
    """True if word or a likely base form is in headwords."""
    if word in headwords:
        return True
    # Single-letter strip (handles: siger->sige, kører->køre, løber->løbe)
    if len(word) > 4 and word[:-1] in headwords:
        return True
    # Check common Danish inflection suffixes — if stripping them hits a headword
    for suffix in ("e", "t", "s", "er", "en", "es", "ede", "et", "erne",
                   "ens", "edes", "ede", "ernes"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            base = word[: -len(suffix)]
            if base in headwords:
                return True
            # also try base + "e" (siger -> sig -> sige)
            if base + "e" in headwords:
                return True
    # Plural -r (drenge -> dreng)
    if word.endswith("r") and len(word) > 4 and word[:-1] in headwords:
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=3000,
                        help="Consider Leipzig top-N words (default 3000)")
    parser.add_argument("--out", default="data/missing_words.csv",
                        help="Output CSV path (default data/missing_words.csv)")
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    leipzig_path = base / "data" / "dan_news_2020_1M-words.txt"
    entries_dir  = base / "entries" / "da-en"
    out_path     = base / args.out

    print(f"Loading Leipzig top {args.top} words …")
    words = load_leipzig(leipzig_path, args.top)
    print(f"  {len(words)} candidate words after filtering")

    print("Loading existing headwords …")
    headwords = load_headwords(entries_dir)
    print(f"  {len(headwords)} headwords found")

    missing = [(rank, word, freq) for rank, word, freq in words
               if not is_covered(word, headwords)]

    print(f"\n  {len(missing)} words NOT covered (out of {len(words)} candidates)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rank", "word", "freq"])
        writer.writerows(missing)

    print(f"  Written → {out_path}")
    print()
    print("Top 40 missing words:")
    print(f"  {'rank':>6}  {'word':<25}  freq")
    print(f"  {'-'*6}  {'-'*25}  ----")
    for rank, word, freq in missing[:40]:
        print(f"  {rank:>6}  {word:<25}  {freq}")


if __name__ == "__main__":
    main()
