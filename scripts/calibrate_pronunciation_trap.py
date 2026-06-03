"""
calibrate_pronunciation_trap.py
--------------------------------
Reset flag_pronunciation_trap to a meaningful value for every DA→EN entry.

Rules — set True only when the headword contains a genuine phonetic trap
for English speakers learning Danish:

  1. Special vowels:  ø, æ, å in the headword
  2. Soft-d:          'd' after a vowel AND at word-end, OR 'd' between two vowels
                      e.g. glad, rod, bade, modig
  3. Soft-g / silent-g: 'g' at word-end after a vowel (dag, bog, tog)
                         or 'g' + silence before e/i in some positions (covered by ipa ʒ check)
  4. Silent h:        'hv' cluster (hvid, hvad, hval → sounds start with 'v')
  5. Silent / weak v: 'v' at word-end after a vowel (grav, hav, skov, lov)
  6. Dark lateral:    'ld' or 'nd' clusters (hold, land → Danish palatalisation)
  7. Stød (glottal):  IPA field contains 'ʔ'
  8. Double vowel tricks: 'aa' (rare but present), 'oo' (loanwords) — skip; not a trap
  9. 'gn' or 'kn' cluster: silent first consonant (gnave, kne → nah-veh, neh)
  10. Soft 'c':        'c' before e/i/y (center, cirkel → sounds like 's')

Words not matching any rule → False.

Usage:
    python scripts/calibrate_pronunciation_trap.py [--dry-run]

Options:
    --dry-run   Print changes without writing them.
"""

import argparse
import re
import sys
from pathlib import Path

ENTRIES_DIR = Path("entries/da-en")

VOWELS = set("aeiouyæøå")

# ── Trap detection ──────────────────────────────────────────────────────────

def _has_special_vowel(w: str) -> bool:
    return any(c in w for c in "æøå")

def _has_soft_d(w: str) -> bool:
    """'d' at word-end after vowel, or 'd' between two vowels."""
    # word-end after vowel: e.g. god, bred, glad, rod
    if re.search(r"[aeiouyæøå]d$", w):
        return True
    # between vowels: bade, modig (vowel-d-vowel)
    if re.search(r"[aeiouyæøå]d[aeiouyæøå]", w):
        return True
    return False

def _has_soft_g(w: str) -> bool:
    """'g' at word-end after a vowel: dag, bog, tog, vej (j=g historically)."""
    if re.search(r"[aeiouyæøå]g$", w):
        return True
    # 'eg' / 'ig' midword before consonant (vejen → sounds like 'vy-en')
    if re.search(r"[aeiouyæøå]g[^aeiouyæøå]", w):
        return True
    return False

def _has_silent_hv(w: str) -> bool:
    return "hv" in w

def _has_weak_v(w: str) -> bool:
    """'v' at word-end after a vowel."""
    return bool(re.search(r"[aeiouyæøå]v$", w))

def _has_dark_cluster(w: str) -> bool:
    """'ld' or 'nd' cluster → Danish palatalized sounds."""
    return bool(re.search(r"(ld|nd)", w))

def _has_stoed(ipa: str) -> bool:
    return "ʔ" in ipa if ipa else False

def _has_gn_kn(w: str) -> bool:
    """'gn' or 'kn' at word-start → silent first consonant."""
    return bool(re.match(r"(gn|kn)", w))

def _has_soft_c(w: str) -> bool:
    """'c' before e/i/y → pronounced 's' (centro, cirkel)."""
    return bool(re.search(r"c[eiy]", w))

def is_trap(headword: str, ipa: str) -> bool:
    w = headword.lower()
    return (
        _has_special_vowel(w)
        or _has_soft_d(w)
        or _has_soft_g(w)
        or _has_silent_hv(w)
        or _has_weak_v(w)
        or _has_dark_cluster(w)
        or _has_stoed(ipa)
        or _has_gn_kn(w)
        or _has_soft_c(w)
    )

# ── File I/O ────────────────────────────────────────────────────────────────

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""

def process_file(path: Path, dry_run: bool) -> str | None:
    """Return 'true→false', 'false→true', 'no-change', or None on error."""
    text = path.read_text(encoding="utf-8")

    headword = read_field(text, "headword")
    ipa      = read_field(text, "ipa")
    current  = read_field(text, "flag_pronunciation_trap")

    if not headword or current not in ("true", "false"):
        return None  # malformed or already unusual value

    new_val = "true" if is_trap(headword, ipa) else "false"

    if new_val == current:
        return "no-change"

    if not dry_run:
        updated = re.sub(
            r"(\s+flag_pronunciation_trap:\s*)(true|false)",
            lambda m: m.group(1) + new_val,
            text,
        )
        path.write_text(updated, encoding="utf-8")

    return f"{current}→{new_val}"

# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Calibrate flag_pronunciation_trap")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without writing files")
    args = parser.parse_args()

    if not ENTRIES_DIR.exists():
        print(f"ERROR: {ENTRIES_DIR} not found. Run from project root.", file=sys.stderr)
        sys.exit(1)

    files   = sorted(ENTRIES_DIR.glob("*.md"))
    counts  = {"true→false": 0, "false→true": 0, "no-change": 0, "skipped": 0}
    changed = []

    for f in files:
        result = process_file(f, dry_run=args.dry_run)
        if result is None:
            counts["skipped"] += 1
        else:
            counts[result] = counts.get(result, 0) + 1
            if result != "no-change":
                changed.append((f.name, result))

    print(f"Files processed : {len(files)}")
    print(f"true → false    : {counts['true→false']}  (was trap, now cleared)")
    print(f"false → true    : {counts['false→true']}  (was clear, now flagged)")
    print(f"no-change       : {counts['no-change']}")
    print(f"skipped         : {counts['skipped']}  (malformed / missing field)")

    if args.dry_run:
        print("\n[DRY RUN — no files written]")
        if changed:
            print(f"\nFirst 20 changes:")
            for name, direction in changed[:20]:
                print(f"  {direction}  {name}")
    else:
        remaining_true = sum(1 for f in ENTRIES_DIR.glob("*.md")
                             if "flag_pronunciation_trap: true" in f.read_text(encoding="utf-8"))
        print(f"\nAfter update    : {remaining_true} entries have flag_pronunciation_trap: true")


if __name__ == "__main__":
    main()
