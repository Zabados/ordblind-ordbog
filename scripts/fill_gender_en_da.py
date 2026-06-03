"""
fill_gender_en_da.py
Fill missing (en)/(et) gender suffixes on primary_translation for EN→DA noun entries.

Strategy:
1. Build a gender lookup from all DA→EN entries (headword → gender).
2. For each EN→DA noun entry where primary_translation lacks (en)/(et):
   - Strip any existing suffix, look up the Danish word in the lookup.
   - If found, append the correct (en)/(et) suffix.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
DA_EN_DIR = ROOT / "entries" / "da-en"


def build_gender_lookup() -> dict[str, str]:
    """Return {danish_headword_lowercase: 'en'|'et'} from all DA→EN noun entries."""
    lookup: dict[str, str] = {}
    for path in DA_EN_DIR.glob("da-*-001.md"):
        txt = path.read_text(encoding="utf-8")
        if not re.search(r"^pos:\s*noun", txt, re.M):
            continue
        hw_m = re.search(r"^headword:\s*(.+)", txt, re.M)
        g_m = re.search(r"^gender:\s*(en|et)", txt, re.M)
        if hw_m and g_m:
            lookup[hw_m.group(1).strip().lower()] = g_m.group(1)
    return lookup


def strip_gender(s: str) -> str:
    """Remove trailing (en) or (et) from a string."""
    return re.sub(r"\s*\((en|et)\)\s*$", "", s).strip()


def main():
    gender_map = build_gender_lookup()
    print(f"Gender lookup built: {len(gender_map)} DA nouns")

    updated = 0
    not_found = 0

    for path in sorted(EN_DA_DIR.glob("en-*-001.md")):
        txt = path.read_text(encoding="utf-8")

        # Only process noun entries
        if not re.search(r"^pos:\s*noun", txt, re.M):
            continue

        # Check if primary_translation already has gender
        prim_m = re.search(r"^(primary_translation:\s*)(.+)$", txt, re.M)
        if not prim_m:
            continue
        prim_val = prim_m.group(2).strip()
        if re.search(r"\((en|et)\)", prim_val):
            continue  # already has gender

        # Try to look up gender for the Danish word
        da_word = strip_gender(prim_val).lower()
        # For multi-word primaries, use the first word
        first_word = da_word.split()[0] if " " in da_word else da_word

        gender = gender_map.get(da_word) or gender_map.get(first_word)

        if gender:
            new_prim = f"{prim_val} ({gender})"
            new_txt = re.sub(
                r"^(primary_translation:\s*)(.+)$",
                lambda m: f"{m.group(1)}{new_prim}",
                txt,
                flags=re.M,
            )
            path.write_text(new_txt, encoding="utf-8")
            updated += 1
        else:
            not_found += 1

    print(f"Done. Updated: {updated}, Gender not found: {not_found}")


if __name__ == "__main__":
    main()
