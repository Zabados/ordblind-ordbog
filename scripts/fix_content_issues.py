"""
fix_content_issues.py
----------------------
Fixes the content quality issues found by audit_content.py:

  1. POS-TRANS-NONVERB  — entries where pos=noun/adj/adv but translation
                          clearly describes a verb: change pos→verb
  2. POS-TRANS-VERB (wrong POS) — entries marked pos=verb that are actually
                          adjective / adverb / noun: correct the pos
  3. POS-TRANS-VERB (missing "to ") — true verbs whose primary_translation
                          doesn't start "to ": prepend "to "
  4. WRONG-TRANSLATION  — specific known bad translations: replace them
  5. DUPLICATE-SECONDARY — remove secondary_translations identical to primary
  6. NOUN-GENDER-SKIP   — nouns with gender=SKIP: look up on ordnet.dk,
                          fall back to TODO

Usage:
    python scripts/fix_content_issues.py [--dry-run] [--throttle SECONDS]
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ENTRIES_DIR = Path("entries/da-en")

HEADERS = {"User-Agent": "ordbog-dict-pipeline/1.0 (educational DA-EN dictionary)"}
BASE_URL = "https://ordnet.dk/ddo/ordbog"

GENDER_MAP = {
    "fælleskøn":           "en",
    "fælles- og intetkøn": "en",
    "intetkøn":            "et",
}

# ── 1. Entries that should be verb (currently noun/adj/adv) ─────────────────
# Maps filename stem → correct pos (all become verb, gender SKIP)
# da-chance-001 intentionally excluded: kept as noun, translation fixed below
SHOULD_BE_VERB = {
    "da-drive-001",
    "da-f-lge-001",
    "da-fange-001",
    "da-grunde-001",
    "da-k-re-001",
    "da-koste-001",
    "da-l-be-001",
    "da-l-re-001",
    "da-lave-001",
    "da-lede-001",
    "da-m-des-001",
    "da-rette-001",
    "da-spare-001",
    "da-vide-001",
}

# ── 2. Entries that should NOT be verb (currently verb) ─────────────────────
# Maps filename stem → (correct_pos, correct_gender)
SHOULD_NOT_BE_VERB = {
    "da-afg-rende-001":    ("adjective",  "SKIP"),
    "da-bare-001":         ("adverb",     "SKIP"),
    "da-bekendt-001":      ("adjective",  "SKIP"),
    "da-bestemt-001":      ("adjective",  "SKIP"),
    "da-efterf-lgende-001":("adjective",  "SKIP"),
    "da-forbudt-001":      ("adjective",  "SKIP"),
    "da-kendt-001":        ("adjective",  "SKIP"),
    "da-levende-001":      ("adjective",  "SKIP"),
    "da-n-dt-001":         ("adjective",  "SKIP"),
    "da-sp-ndende-001":    ("adjective",  "SKIP"),
    "da-spredt-001":       ("adjective",  "SKIP"),
    "da-studerende-001":   ("noun",       "en"),
    "da-udelukkende-001":  ("adverb",     "SKIP"),
    "da-udsat-001":        ("adjective",  "SKIP"),
    "da-viden-001":        ("noun",       "en"),
}

# ── 3. Verbs where only "to " prefix is missing ──────────────────────────────
# (auto-detected by script — entries not in SHOULD_NOT_BE_VERB and not in
# TRANSLATION_FIXES where translation doesn't start "to ")

# Verbs whose translations are fine without "to " (modals, special forms)
SKIP_TO_PREFIX = {
    "da-burde-001",     # ought (modal)
    "da-husk-001",      # imperative form — will be handled in TRANSLATION_FIXES
    "da-n-jes-001",     # "make do" — fine as-is
    "da-pleje-001",     # "used to" — fine
    "da-skyldes-001",   # "be due to" — already has "be"
}

# ── 4. Wrong translations to fix entirely ────────────────────────────────────
TRANSLATION_FIXES = {
    "da-bryde-001":   "to break; to violate",
    "da-give-001":    "to give",
    "da-tvinge-001":  "to force, compel",
    "da-husk-001":    "to remember",
    "da-burde-001":   "to ought to; should",
    "da-n-dt-001":    "forced to; obliged",  # nødt (til at)
    # chance: kept as noun — fix translation to English noun form
    "da-chance-001":  "a chance; an opportunity",
    # gæste: verb entry — fix broken primary
    "da-g-ste-001":   "to visit; to be a guest at",
}

# ── 4b. Gender overrides (for entries where gender is just plain wrong) ──────
GENDER_OVERRIDES = {
    "da-chance-001": "en",   # chance is fælleskøn (en chance), not et
}

# ── 4c. Secondary translation overrides ─────────────────────────────────────
# Maps stem → new secondary_translations block content (replaces everything
# after "secondary_translations:").  Use SKIP to clear all secondaries.
SECONDARY_OVERRIDES = {
    # fange: remove noun meaning "prisoner" (→ separate da-fange-002.md)
    "da-fange-001":   "  - SKIP",
    # følge: remove noun meanings "consequence"/"succession" (→ da-f-lge-002.md)
    "da-f-lge-001":   "  - to be a logical consequence of",
    # lære: remove noun meanings (→ da-l-re-002.md)
    "da-l-re-001":    "  - to learn",
    # vide: secondaries 'to widen' and 'penalty' are wrong — clear them
    "da-vide-001":    "  - SKIP",
    # løbe: remove duplicate 'to curdle' and noun 'rennet'
    "da-l-be-001":    "  - to curdle",
    # spare: remove truncated/blank 'to' entry
    "da-spare-001":   "  - to economize\n  - to save up",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def set_field(text: str, field: str, value: str) -> str:
    """Replace the value of a field (handles indented fields too)."""
    return re.sub(
        rf"^(\s*{re.escape(field)}:\s*)(.+)$",
        lambda m: m.group(1) + value,
        text, flags=re.MULTILINE,
    )


def remove_duplicate_secondaries(text: str) -> str:
    """Remove secondary_translations entries that duplicate the primary."""
    primary = read_field(text, "primary_translation").strip().lower().strip('"\'')
    if not primary or primary == "todo":
        return text

    def remove_dup(m: re.Match) -> str:
        block = m.group(0)
        lines = block.split("\n")
        kept = []
        for line in lines:
            stripped = line.strip().lstrip("- ").strip().strip('"\'').lower()
            if stripped == primary:
                continue  # drop this line
            kept.append(line)
        return "\n".join(kept)

    return re.sub(
        r"secondary_translations:.*?(?=\n\w|\n```)",
        remove_dup,
        text, flags=re.DOTALL,
    )


def fetch_ordnet_gender(word: str) -> str | None:
    """Return 'en', 'et', or None."""
    try:
        r = requests.get(BASE_URL, params={"query": word}, headers=HEADERS, timeout=5)
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    text_lower = soup.get_text(" ", strip=True).lower()

    # Find first gender keyword in page
    for dk_g, en_g in GENDER_MAP.items():
        if dk_g in text_lower:
            return en_g
    return None


# ── Main per-file processing ─────────────────────────────────────────────────

def apply_secondary_override(text: str, override: str) -> str:
    """Replace the secondary_translations block with override content."""
    return re.sub(
        r"(secondary_translations:)[^\n]*(\n(?:  - .*\n?)*)",
        lambda m: f"secondary_translations:\n{override}\n",
        text, count=1,
    )


def process(path: Path, dry_run: bool, throttle: float,
            no_gender: bool = False) -> list[str]:
    """Return list of changes made."""
    text = path.read_text(encoding="utf-8")
    stem = path.stem
    changes = []
    new = text

    # 1 & 2: POS corrections
    if stem in SHOULD_BE_VERB:
        curr_pos = read_field(new, "pos")
        if curr_pos != "verb":
            new = set_field(new, "pos", "verb")
            new = set_field(new, "gender", "SKIP")
            changes.append(f"pos {curr_pos}→verb")

    if stem in SHOULD_NOT_BE_VERB:
        target_pos, target_gender = SHOULD_NOT_BE_VERB[stem]
        curr_pos = read_field(new, "pos")
        if curr_pos != target_pos:
            new = set_field(new, "pos", target_pos)
            changes.append(f"pos {curr_pos}→{target_pos}")
        curr_gender = read_field(new, "gender")
        if curr_gender != target_gender:
            new = set_field(new, "gender", target_gender)
            changes.append(f"gender {curr_gender}→{target_gender}")

    # 4b: Gender overrides
    if stem in GENDER_OVERRIDES:
        target_gender = GENDER_OVERRIDES[stem]
        curr_gender = read_field(new, "gender")
        if curr_gender != target_gender:
            new = set_field(new, "gender", target_gender)
            changes.append(f"gender {curr_gender}→{target_gender} (override)")

    # 4c: Secondary translation overrides
    if stem in SECONDARY_OVERRIDES:
        overridden = apply_secondary_override(new, SECONDARY_OVERRIDES[stem])
        if overridden != new:
            new = overridden
            changes.append("secondary_translations overridden")

    # 4: Wrong translations
    if stem in TRANSLATION_FIXES:
        target = TRANSLATION_FIXES[stem]
        curr = read_field(new, "primary_translation")
        if curr.strip().strip('"\'') != target:
            new = set_field(new, "primary_translation", target)
            changes.append(f"translation '{curr}'→'{target}'")

    # 3: Prepend "to " for verbs missing it
    current_pos = read_field(new, "pos")
    if current_pos == "verb" and stem not in SKIP_TO_PREFIX and stem not in TRANSLATION_FIXES:
        primary = read_field(new, "primary_translation")
        if (primary and primary not in ("TODO", "SKIP")
                and not primary.lower().startswith("to ")):
            new_primary = f"to {primary}"
            new = set_field(new, "primary_translation", new_primary)
            changes.append(f"prepend 'to ': '{primary}'→'{new_primary}'")

    # 5: Remove duplicate secondaries
    deduped = remove_duplicate_secondaries(new)
    if deduped != new:
        new = deduped
        changes.append("removed duplicate secondary")

    # 6: NOUN-GENDER-SKIP → look up gender
    if not no_gender:
        current_pos = read_field(new, "pos")
        current_gender = read_field(new, "gender")
        if current_pos == "noun" and current_gender == "SKIP":
            headword = read_field(new, "headword")
            gender = fetch_ordnet_gender(headword)
            time.sleep(throttle)
            new_gender = gender if gender else "TODO"
            new = set_field(new, "gender", new_gender)
            changes.append(f"gender SKIP→{new_gender} (noun '{headword}')")

    if new != text:
        if not dry_run:
            path.write_text(new, encoding="utf-8")

    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--no-gender", action="store_true",
                        help="Skip ordnet.dk gender lookups (run quick fixes only)")
    parser.add_argument("--throttle",  type=float, default=0.3,
                        help="Seconds between ordnet.dk requests")
    args = parser.parse_args()

    files = sorted(ENTRIES_DIR.glob("*.md"))
    print(f"Processing {len(files)} entries…")
    if args.dry_run:
        print("[DRY RUN — no files written]\n")

    totals: dict[str, int] = {}
    changed_files = 0

    for f in files:
        changes = process(f, dry_run=args.dry_run, throttle=args.throttle,
                          no_gender=args.no_gender)
        if changes:
            changed_files += 1
            for c in changes:
                # Bucket by change type prefix
                key = c.split(" ")[0]
                totals[key] = totals.get(key, 0) + 1

    print(f"\nFiles changed: {changed_files}")
    print("Change summary:")
    for k, v in sorted(totals.items()):
        print(f"  {k:30s} {v}")


if __name__ == "__main__":
    main()
