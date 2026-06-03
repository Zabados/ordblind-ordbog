"""
fill_gender_en_da_manual.py
Manual gender patch for the 58 EN→DA noun entries not resolved by DA→EN lookup.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"

# headword (English) -> (correct Danish primary translation with gender)
# Only entries where we know the gender with confidence.
# Entries where the primary is a verb or phrase are flagged separately.
MANUAL = {
    "appeal":        "appel (en)",
    "art":           "kunst (en)",
    "band":          "band (et)",
    "blood":         "blod (et)",
    "brother":       "bror (en)",
    "care":          "pleje (en)",
    "cloud":         "sky (en)",
    "college":       "college (et)",
    "combination":   "kombination (en)",
    "consequence":   "følge (en)",
    "consideration": "overvejelse (en)",
    "edge":          "kant (en)",
    "existence":     "eksistens (en)",
    "fellow":        "fyr (en)",
    "finance":       "økonomi (en)",       # "finanser" is plural; økonomi better
    "god":           "gud (en)",
    "graduate":      "akademiker (en)",
    "guard":         "vagt (en)",
    "handle":        "håndtag (et)",       # klinke is door handle specifically
    "ideal":         "ideal (et)",
    "institute":     "institut (et)",
    "intellectual":  "intellektuel (en)",
    "issue":         "emne (et)",
    "king":          "konge (en)",
    "knee":          "knæ (et)",
    "maintenance":   "vedligeholdelse (en)",
    "maximum":       "maksimum (et)",
    "measurement":   "måling (en)",
    "method":        "metode (en)",
    "missile":       "missil (et)",
    "object":        "objekt (et)",
    "operator":      "operatør (en)",
    "pace":          "tempo (et)",
    "paper":         "papir (et)",
    "pattern":       "mønster (et)",
    "performance":   "præstation (en)",
    "provision":     "forråd (et)",
    "publication":   "udgivelse (en)",
    "railroad":      "jernbane (en)",
    "rate":          "sats (en)",
    "reserve":       "reserve (en)",
    "river":         "flod (en)",
    "sex":           "køn (et)",
    "shoulder":      "skulder (en)",
    "sin":           "synd (en)",
    "sky":           "himmel (en)",
    "speaker":       "taler (en)",
    "sponsor":       "sponsor (en)",
    "star":          "stjerne (en)",
    "sum":           "sum (en)",
    "text":          "tekst (en)",
    "total":         "total (et)",
    "wagon":         "vogn (en)",
    # Entries with wrong/verb primaries — fix primary too:
    "cover":         "dæksel (et)",   # was "dække" (verb)
    "news":          "nyhed (en)",    # was "nyheder" (plural), singular is nyhed
    "reveal":        "afsløring (en)", # was "afsløre" (verb)
    # "one" and "yesterday" have non-noun primaries; skip gender (structural issues)
}


def main():
    updated = 0
    not_found = 0

    for headword, new_primary in MANUAL.items():
        slug = headword.lower().replace(" ", "-").replace("'", "")
        path = EN_DA_DIR / f"en-{slug}-001.md"
        if not path.exists():
            print(f"  NOT FOUND: {headword}")
            not_found += 1
            continue

        txt = path.read_text(encoding="utf-8")
        new_txt = re.sub(
            r"^(primary_translation:\s*)(.+)$",
            lambda m: f"{m.group(1)}{new_primary}",
            txt,
            flags=re.M,
        )
        if new_txt != txt:
            path.write_text(new_txt, encoding="utf-8")
            updated += 1

    print(f"Done. Updated: {updated}, Not found: {not_found}")


if __name__ == "__main__":
    main()
