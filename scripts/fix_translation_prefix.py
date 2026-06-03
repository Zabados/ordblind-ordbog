"""
fix_translation_prefix.py
--------------------------
Fixes two translation-prefix issues found by audit_translations.py:

  MISSING_TO  — pos=verb but primary_translation doesn't start with "to "
                → prepend "to " to primary (and any bare-verb secondaries)

  SPURIOUS_TO — pos=noun/adjective/adverb but primary_translation starts "to "
                → remove the "to " prefix from primary only

Secondary translations are only touched for MISSING_TO on verb entries,
and only when the secondary looks like a bare infinitive (single lowercase
word or a short phrase without "to ").  Complex secondaries are left alone.

Usage:
    python scripts/fix_translation_prefix.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ENTRIES = Path("entries/da-en")

# Verbs that legitimately don't take "to " (modals, copulas, special forms)
SKIP_TO = {
    "burde", "skulle", "ville", "kunne", "måtte", "turde",
    "pleje",          # "used to"
    "skyldes",        # "be due to" — already has "be"
    "nøjes",          # "make do"  (nøjes med)
    "hedde",          # "to be called" — already fine
    # Derived forms we know are correct
    "afholdes",
}

# Non-verb entries where "to" in primary is actually the adverb "to" (rare)
# e.g. "to and from" → keep as-is
KEEP_TO_NONVERB: set[str] = set()


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def set_field(text: str, field: str, value: str) -> str:
    return re.sub(
        rf"^(\s*{re.escape(field)}:\s*)(.+)$",
        lambda m: m.group(1) + value,
        text, flags=re.MULTILINE,
    )


def read_secondaries_raw(text: str) -> str | None:
    """Return the raw secondary_translations block (everything after the key)."""
    m = re.search(r"secondary_translations:(.*?)```", text, re.DOTALL)
    return m.group(1) if m else None


def set_secondaries_block(text: str, new_block: str) -> str:
    return re.sub(
        r"(secondary_translations:).*?(?=```)",
        lambda m: f"secondary_translations:{new_block}",
        text, count=1, flags=re.DOTALL,
    )


def bare_verb_line(s: str) -> bool:
    """True if a secondary-translation string looks like a bare verb infinitive
    that should have "to " prepended.

    Conservative: only triggers on single-word bare verbs to avoid turning
    noun phrases like 'standstill, halt' or 'expedient use' into nonsense.
    """
    s = s.strip()
    if not s or s in ("SKIP", "TODO"):
        return False
    if s.lower().startswith("to "):
        return False
    # Skip complex / multi-meaning / explanation strings
    if any(c in s for c in ("|", "(", "–", "—", ";", ",")):
        return False
    # Only handle single lowercase words (clearest bare-verb case)
    words = s.split()
    if len(words) != 1:
        return False
    word = words[0]
    if not word[0].islower():
        return False
    # Skip obvious nouns: things ending in common noun suffixes
    # (this catches "use", "result", "standstill" etc. if they slip through)
    noun_endings = ("ness", "ment", "tion", "sion", "ity", "ance", "ence",
                    "ship", "hood", "ism", "ist", "age", "ure", "ry")
    if word.endswith(noun_endings):
        return False
    return True


def process(path: Path, dry_run: bool) -> tuple[bool, str]:
    """Returns (changed, reason)."""
    text = path.read_text(encoding="utf-8")
    headword = read_field(text, "headword")
    pos      = read_field(text, "pos")
    primary  = read_field(text, "primary_translation")

    if primary in ("TODO", "SKIP", ""):
        return False, "no primary"

    changed = False
    new_text = text
    reasons: list[str] = []

    # ── MISSING_TO — verb without "to " ──────────────────────────────────────
    if pos == "verb" and headword not in SKIP_TO:
        if not primary.lower().startswith("to "):
            new_primary = "to " + primary
            # Also lower-case the first letter of the old primary if it was Title-case
            if new_primary[3].isupper() and len(new_primary) > 4 and new_primary[4].islower():
                new_primary = new_primary[:3] + new_primary[3].lower() + new_primary[4:]
            new_text = set_field(new_text, "primary_translation", new_primary)
            reasons.append(f"primary: {primary!r} → {new_primary!r}")
            changed = True

        # Also fix bare-verb secondaries
        sec_raw = read_secondaries_raw(new_text)
        if sec_raw:
            lines = sec_raw.split("\n")
            new_lines: list[str] = []
            sec_changed = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- "):
                    val = stripped[2:].strip()
                    if bare_verb_line(val):
                        new_val = "to " + val
                        new_lines.append(line.replace(val, new_val, 1))
                        reasons.append(f"secondary: {val!r} → {new_val!r}")
                        sec_changed = True
                        continue
                new_lines.append(line)
            if sec_changed:
                new_text = set_secondaries_block(new_text, "\n".join(new_lines))
                changed = True

    # ── SPURIOUS_TO — non-verb primary starts with "to " ─────────────────────
    elif pos in ("noun", "adjective", "adverb", "pronoun",
                 "preposition", "conjunction", "interjection", "phrase"):
        if primary.lower().startswith("to ") and headword not in KEEP_TO_NONVERB:
            # Remove "to " from primary
            stripped = primary[3:]
            # Re-capitalise if it was originally capitalised
            new_primary = stripped[0].upper() + stripped[1:] if stripped else stripped
            # But our schema uses lower-case primaries — keep as-is (lower)
            new_text = set_field(new_text, "primary_translation", stripped)
            reasons.append(f"primary spurious-to: {primary!r} → {stripped!r}")
            changed = True

    if not changed:
        return False, "no change needed"

    reason_str = "; ".join(reasons)
    if dry_run:
        print(f"[DRY-RUN] {path.name}: {reason_str}")
        return True, reason_str

    path.write_text(new_text, encoding="utf-8")
    print(f"  fixed  {path.name}: {reason_str}")
    return True, reason_str


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = sorted(ENTRIES.glob("*.md"))
    fixed = skipped = 0

    for path in paths:
        try:
            changed, _ = process(path, args.dry_run)
        except Exception as exc:
            print(f"ERROR {path.name}: {exc}", file=sys.stderr)
            continue
        if changed:
            fixed += 1
        else:
            skipped += 1

    print(f"\nDone — fixed={fixed}  unchanged={skipped}")


if __name__ == "__main__":
    main()
