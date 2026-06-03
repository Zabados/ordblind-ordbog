"""fill_examples_leipzig.py — Fill missing example sentences from Leipzig corpus.

For each DA->EN entry that has no examples (or only TODO), finds the best
sentence from the Leipzig 1M Danish news corpus that contains the headword.
Writes the Danish sentence only (english: SKIP) since the corpus is monolingual.

Usage:
    python scripts/fill_examples_leipzig.py
    python scripts/fill_examples_leipzig.py --dry-run
    python scripts/fill_examples_leipzig.py --max-length 120

Sentence selection criteria (in order of preference):
  1. Contains the exact headword (whole-word match)
  2. Length between MIN_LEN and max_length characters
  3. Does not start with a quotation mark / number / «»
  4. Shortest qualifying sentence (easier to read)
"""

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENTRIES_DIR   = Path("entries/da-en")
SENTENCES_FILE = Path("data/dan_news_2020_1M/dan_news_2020_1M-sentences.txt")
MIN_LEN       = 30    # discard very short fragments
DEFAULT_MAX   = 130   # discard very long sentences

# Sentence starters that make poor examples
_BAD_STARTS   = re.compile(r'^["\u00ab\u00bb\u201c\u201e\d\W]')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field(content: str, name: str) -> str:
    m = re.search(rf'\b{re.escape(name)}:\s*(.+)', content)
    return m.group(1).strip() if m else ""


def _has_examples(content: str) -> bool:
    """Return True if the entry already has at least one real example."""
    m = re.search(r'examples:\n(.*?)(?:\n```|\Z)', content, re.DOTALL)
    if not m:
        return False
    block = m.group(1)
    da_items = re.findall(r'danish:\s*(.+)', block)
    return any(d.strip() not in {"TODO", "SKIP", ""} for d in da_items)


def _todo_block_present(content: str) -> bool:
    """Return True if the entry has the TODO_EXAMPLES sentinel."""
    return "danish: TODO" in content


def _slug(word: str) -> str:
    return re.sub(r'[æøå]', '-', word.lower())


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_word_index(sentences_path: Path, max_length: int) -> dict[str, list[str]]:
    """Build a dict mapping lowercase word -> list of candidate sentences.

    Only sentences within [MIN_LEN, max_length] that pass the bad-start
    filter are kept.  We only store up to 20 candidates per word to limit
    memory use.
    """
    print(f"Indexing {sentences_path.name} …", flush=True)
    index: dict[str, list[str]] = {}
    with sentences_path.open(encoding="utf-8") as fh:
        for line in fh:
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            sent = parts[1].strip()
            if not (MIN_LEN <= len(sent) <= max_length):
                continue
            if _bad_starts(sent):
                continue
            # Tokenise: split on non-letter characters, lowercase
            for word in set(re.split(r'\W+', sent.lower())):
                if len(word) < 3:
                    continue
                bucket = index.setdefault(word, [])
                if len(bucket) < 20:
                    bucket.append(sent)
    print(f"Index built: {len(index):,} unique words.", flush=True)
    return index


def _bad_starts(sent: str) -> bool:
    return bool(_BAD_STARTS.match(sent))


def find_best_sentence(headword: str, index: dict, max_length: int) -> str | None:
    """Return the shortest sentence that contains the headword as a whole word."""
    key = headword.lower()
    candidates = index.get(key, [])
    if not candidates:
        return None
    # Re-check whole-word match (the index key is just one token from the sentence)
    pattern = re.compile(r'\b' + re.escape(headword) + r'\b', re.IGNORECASE)
    matches = [s for s in candidates if pattern.search(s)]
    if not matches:
        return None
    return min(matches, key=len)


# ---------------------------------------------------------------------------
# Entry patcher
# ---------------------------------------------------------------------------

TODO_BLOCK = """\
  - danish: TODO
    english: TODO
    source: manual"""

FILLED_TEMPLATE = """\
  - danish: {sentence}
    english: SKIP
    source: leipzig"""


def patch_entry(path: Path, sentence: str, dry_run: bool) -> bool:
    """Replace the TODO_EXAMPLES block with the Leipzig sentence."""
    content = path.read_text(encoding="utf-8")

    if TODO_BLOCK not in content:
        return False

    new_block = FILLED_TEMPLATE.format(sentence=sentence)
    new_content = content.replace(TODO_BLOCK, new_block, 1)

    if dry_run:
        return True

    path.write_text(new_content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run",    action="store_true",
                    help="Show what would be done without writing files.")
    ap.add_argument("--max-length", type=int, default=DEFAULT_MAX,
                    help=f"Max sentence length in characters (default {DEFAULT_MAX}).")
    args = ap.parse_args()

    if not SENTENCES_FILE.exists():
        sys.exit(f"Leipzig sentences file not found: {SENTENCES_FILE}")

    # Find entries that need examples
    targets = []
    for path in sorted(ENTRIES_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        if _has_examples(content):
            continue
        if not _todo_block_present(content):
            continue
        hw = _field(content, "headword")
        if not hw:
            continue
        targets.append((path, hw))

    if not targets:
        print("No entries need Leipzig examples.")
        return

    print(f"Found {len(targets)} entries needing examples.")

    index = build_word_index(SENTENCES_FILE, args.max_length)

    filled = 0
    skipped = 0
    for path, headword in targets:
        sentence = find_best_sentence(headword, index, args.max_length)
        if not sentence:
            print(f"  [no match]  {headword}")
            skipped += 1
            continue

        action = "would fill" if args.dry_run else "filling"
        print(f"  [{action}]  {headword}  ->  {sentence[:80]}{'…' if len(sentence) > 80 else ''}")

        patched = patch_entry(path, sentence, dry_run=args.dry_run)
        if patched:
            filled += 1
        else:
            print(f"    WARNING: could not patch {path.name}")
            skipped += 1

    print(f"\nDone. Filled: {filled}  /  No match: {skipped}  /  Total: {len(targets)}")
    if args.dry_run:
        print("(dry-run — no files written)")


if __name__ == "__main__":
    main()
