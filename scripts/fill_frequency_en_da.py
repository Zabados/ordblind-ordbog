"""
fill_frequency_en_da.py
Fill frequency_rank and frequency_tier in all entries/en-da/*.md
based on position in data/en_wordlist.txt (rank 1 = most frequent).

Tiers (from AGENTS.md / entry_template.md):
  core   = 1–500
  common = 501–2000
  general = 2001–5000
  rare   = 5000+
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
WORDLIST = ROOT / "data" / "en_wordlist.txt"


def tier(rank: int) -> str:
    if rank <= 500:
        return "core"
    elif rank <= 2000:
        return "common"
    elif rank <= 5000:
        return "general"
    else:
        return "rare"


def slug(word: str) -> str:
    return word.lower().replace(" ", "-").replace("'", "")


def update_field(content: str, field: str, value: str) -> tuple[str, bool]:
    pattern = rf"(^{re.escape(field)}:\s*)(.+)$"
    new_content, n = re.subn(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)
    return new_content, n > 0


def main():
    # Build rank lookup: word -> rank (1-based)
    words = [line.strip() for line in WORDLIST.read_text(encoding="utf-8").splitlines() if line.strip()]
    rank_map = {w: i + 1 for i, w in enumerate(words)}

    changed = 0
    not_found = 0

    for path in sorted(EN_DA_DIR.glob("en-*-001.md")):
        # Extract headword from filename: en-{slug}-001.md
        stem = path.stem  # e.g. en-time-001
        headword_slug = stem[3:-4]  # strip "en-" prefix and "-001" suffix

        # Find matching word in rank_map (try exact slug match first)
        rank = None
        for word, r in rank_map.items():
            if slug(word) == headword_slug:
                rank = r
                break

        if rank is None:
            not_found += 1
            continue

        content = path.read_text(encoding="utf-8")
        original = content

        content, ok1 = update_field(content, "frequency_rank", str(rank))
        content, ok2 = update_field(content, "frequency_tier", tier(rank))

        if content != original:
            path.write_text(content, encoding="utf-8")
            changed += 1

    print(f"Done. Updated: {changed}, No rank found: {not_found}")


if __name__ == "__main__":
    main()
