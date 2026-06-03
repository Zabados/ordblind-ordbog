#!/usr/bin/env python3
"""
fix_inflected_entries.py

Three-pass cleanup of inflected/derived-form entries that Wiktionary couldn't fill:

  PASS 1 – DELETE: remove entries whose base form already exists in the dictionary.
            Inflected duplicates (past-participles, definite forms, plural forms,
            comparative/superlative forms) serve no purpose when the base entry
            is present.

  PASS 2 – UPDATE: fix entries where only the inflected form existed (no base).
            Updates headword, pos, gender, inflections → TODO, and fills translation.

  PASS 3 – FILL: add primary_translation to genuinely independent entries that
            Wiktionary doesn't cover (loanwords, compounds, adverbs, etc.).

Usage:
    python scripts/fix_inflected_entries.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ENTRIES = Path("entries/da-en")


# ─────────────────────────────────────────────────────────────────────────────
# PASS 1 – DELETE (base form entry already exists)
# ─────────────────────────────────────────────────────────────────────────────
DELETE = [
    "da-antallet-001.md",     # antal exists
    "da-b-rnenes-001.md",     # barn exists
    "da-brudt-001.md",        # bryde exists
    "da-d-re-001.md",         # dør exists
    "da-delt-001.md",         # dele exists
    "da-enormt-001.md",       # enorm exists
    "da-forholdene-001.md",   # forhold exists
    "da-fortalt-001.md",      # fortælle exists
    "da-fremmest-001.md",     # fremme exists
    "da-hurtigere-001.md",    # hurtig exists
    "da-hurtigst-001.md",     # hurtig exists
    "da-kollegaer-001.md",    # kollega exists
    "da-landets-001.md",      # land exists
    "da-langt-001.md",        # lang exists
    "da-lavt-001.md",         # lav exists (now adj)
    "da-lokalt-001.md",       # lokal exists
    "da-m-dt-001.md",         # møde exists
    "da-m-nd-001.md",         # mand exists
    "da-m-ndene-001.md",      # mand exists
    "da-meddeler-001.md",     # meddele exists
    "da-meters-001.md",       # meter exists
    "da-midlertidigt-001.md", # midlertidig exists
    "da-normalt-001.md",      # normal exists
    "da-officielt-001.md",    # officiel exists
    "da-oplevelser-001.md",   # oplevelse exists
    "da-opstod-001.md",       # opstå exists
    "da-overhold-001.md",     # overholde exists
    "da-popul-rt-001.md",     # populær exists
    "da-pr-cist-001.md",      # præcis exists
    "da-smidt-001.md",        # smide exists
    "da-stem-001.md",         # stemme exists
    "da-tests-001.md",        # test exists
    "da-tidligt-001.md",      # tidlig exists
    "da-tilbudt-001.md",      # tilbyde exists
    "da-timen-001.md",        # time exists
    "da-trafikken-001.md",    # trafik exists
    "da-udtaler-001.md",      # udtale exists
    "da-v-sentligt-001.md",   # væsentlig exists
    "da-vejene-001.md",       # vej exists
    "da-ventet-001.md",       # vente exists
]


# ─────────────────────────────────────────────────────────────────────────────
# PASS 2 – UPDATE (fix headword → base form, correct POS/gender, fill translation)
# Tuple: (filename, new_headword, new_pos, new_gender, primary_translation)
# None means: leave the field unchanged
# ─────────────────────────────────────────────────────────────────────────────
UPDATE: list[tuple[str, str | None, str | None, str | None, str | None]] = [
    # Adverb/adj neuter forms → base adjective (no base entry existed)
    ("da-grundigt-001.md",       "grundig",         "adjective", "SKIP", "thorough; careful; methodical"),
    ("da-langsomt-001.md",       "langsom",         "adjective", "SKIP", "slow"),
    ("da-massivt-001.md",        "massiv",          "adjective", "SKIP", "massive; solid; substantial"),
    ("da-nemt-001.md",           "nem",             "adjective", "SKIP", "easy; simple; straightforward"),
    ("da-sj-ldent-001.md",       "sjælden",         "adjective", "SKIP", "rare; uncommon; infrequent"),
    ("da-specielt-001.md",       "speciel",         "adjective", "SKIP", "special; particular; peculiar"),
    ("da-tilstr-kkeligt-001.md", "tilstrækkelig",   "adjective", "SKIP", "sufficient; adequate; enough"),
    ("da-tydeligt-001.md",       "tydelig",         "adjective", "SKIP", "clear; distinct; obvious"),
    # Plural/inflected noun → base noun (no base entry existed)
    ("da-geringsm-nd-001.md",    "gerningsmand",    "noun",      "en",   "perpetrator; offender; culprit"),
    ("da-motorveje-001.md",      "motorvej",        "noun",      "en",   "motorway; highway; freeway"),
    ("da-r-dhuse-001.md",        "rådhus",          "noun",      "et",   "town hall; city hall"),
    ("da-s-en-001.md",           "sø",              "noun",      "en",   "lake; loch; sea (in place names)"),
    # Verb form → base verb (no base entry existed)
    ("da-fremstillet-001.md",    "fremstille",      "verb",      "SKIP", "to produce; to manufacture; to make"),
    ("da-n-vnt-001.md",          "nævne",           "verb",      "SKIP", "to mention; to name; to cite"),
    ("da-v-ret-001.md",          "være",            "verb",      "SKIP", "to be"),
    # POS corrections (wrong POS, keep headword)
    ("da-fat-001.md",            None,              "noun",      "et",   "grip; hold; grasp (tage fat = to take hold; få fat i = to get hold of)"),
    ("da-f-rg-001.md",           "færge",           "noun",      "en",   "ferry"),
    ("da-inviter-001.md",        "invitere",        "verb",      "SKIP", "to invite; to have over; to ask over"),
    ("da-n-je-001.md",           "nøje",            "adverb",    "SKIP", "carefully; precisely; closely"),
    ("da-optaget-001.md",        "optaget",         "adjective", "SKIP", "busy; occupied; engaged; taken"),
    ("da-udvalgte-001.md",       "udvalgt",         "adjective", "SKIP", "selected; chosen; handpicked"),
]


# ─────────────────────────────────────────────────────────────────────────────
# PASS 3 – FILL (translation only, no structural changes)
# ─────────────────────────────────────────────────────────────────────────────
FILL: dict[str, str] = {
    "da--rgerligt-001.md":    "what a pity; annoying; unfortunate",
    "da-alts--001.md":        "so; then; well; that is to say",
    "da-analyse-001.md":      "analysis; examination; study",
    "da-anbefaling-001.md":   "recommendation; endorsement",
    "da-betjent-001.md":      "police officer; constable",
    "da-centrum-001.md":      "centre; center; hub",
    "da-corona-001.md":       "corona; coronavirus pandemic",
    "da-coronavirus-001.md":  "coronavirus; COVID-19",
    "da-dertil-001.md":       "to that end; for that purpose; moreover; in addition",
    "da-driv-001.md":         "drive; impetus; momentum; push",
    "da-f-rende-001.md":      "leading; foremost; prominent",
    "da-fans-001.md":         "fans; supporters",
    "da-flot-001.md":         "great; fine; handsome; impressive",
    "da-forbrug-001.md":      "consumption; expenditure; use",
    "da-foredrag-001.md":     "lecture; talk; presentation",
    "da-forh-nd-001.md":      "in advance; beforehand; forehand (tennis)",
    "da-fremover-001.md":     "from now on; going forward; henceforth",
    "da-global-001.md":       "global; worldwide; international",
    "da-halvanden-001.md":    "one and a half; 1.5",
    "da-halvleg-001.md":      "half (of a match); half-time period",
    "da-helst-001.md":        "preferably; most of all; by preference",
    "da-henvendelser-001.md": "enquiries; requests; applications; contacts",
    "da-herhjemme-001.md":    "here at home; in this country",
    "da-hjemmefra-001.md":    "from home; working from home",
    "da-hvilket-001.md":      "which; that; what (neuter relative pronoun)",
    "da-hvoraf-001.md":       "of which; from which; whereof",
    "da-indeholde-001.md":    "to contain; to include; to hold",
    "da-interview-001.md":    "interview; press interview",
    "da-kampagne-001.md":     "campaign; drive; push",
    "da-karriere-001.md":     "career; profession",
    "da-kilo-001.md":         "kilogram; kilo",
    "da-kokain-001.md":       "cocaine",
    "da-kontant-001.md":      "cash; in cash; blunt; direct",
    "da-kontrast-001.md":     "contrast; difference",
    "da-l-bende-001.md":      "ongoing; current; continuous; running",
    "da-mange-001.md":        "many; a lot of; numerous",
    "da-minister-001.md":     "minister; secretary of state",
    "da-model-001.md":        "model; design; pattern; role model",
    "da-mods-tning-001.md":   "contrast; contradiction; opposition (i modsætning til = unlike; in contrast to)",
    "da-mundbind-001.md":     "face mask; surgical mask",
    "da-netv-rk-001.md":      "network",
    "da-ondt-001.md":         "pain; hurt; evil; ill (gøre ondt = to hurt; have ondt i = to have a pain in)",
    "da-online-001.md":       "online; on the internet",
    "da-opfordring-001.md":   "request; call; urging; invitation",
    "da-ophold-001.md":       "stay; residence; sojourn; stopover",
    "da-overbevise-001.md":   "to convince; to persuade",
    "da-personbil-001.md":    "car; passenger car; private car",
    "da-plejehjem-001.md":    "nursing home; care home",
    "da-position-001.md":     "position; role; stance; standing",
    "da-pres-001.md":         "pressure; stress",
    "da-professionel-001.md": "professional; skilled; expert",
    "da-program-001.md":      "programme; program; schedule; agenda",
    "da-racisme-001.md":      "racism; racial discrimination",
    "da-rute-001.md":         "route; road; itinerary",
    "da-s-rbare-001.md":      "vulnerable; fragile; at risk",
    "da-s-vel-001.md":        "as well as; both...and (såvel...som = both...and)",
    "da-situation-001.md":    "situation; circumstances",
    "da-sommerferie-001.md":  "summer holiday; summer vacation",
    "da-takt-001.md":         "tact; timing; beat; rhythm; pace",
    "da-teknologi-001.md":    "technology",
    "da-tide-001.md":         "time; period; era (archaic/literary)",
    "da-tilkalde-001.md":     "to call for; to summon; to send for",
    "da-tilsvarende-001.md":  "corresponding; equivalent; proportionate",
    "da-travlt-001.md":       "busy; hectic; with a lot to do",
    "da-udlevere-001.md":     "to hand over; to extradite; to deliver",
    "da-udover-001.md":       "beyond; above; in addition to; besides",
    "da-udstilling-001.md":   "exhibition; display; show",
    "da-undervejs-001.md":    "on the way; underway; in progress; en route",
    "da-von-001.md":          "von (particle in German and noble surnames)",
    "da-yderst-001.md":       "extremely; utterly; outermost",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def set_field(text: str, field: str, value: str) -> tuple[str, bool]:
    """Replace `field: <anything>` with `field: <value>` (first occurrence)."""
    pattern = re.compile(rf"^({re.escape(field)}:\s*)(.+)$", re.MULTILINE)
    new_text, n = pattern.subn(rf"\g<1>{value}", text, count=1)
    return new_text, n > 0


def reset_inflections(text: str) -> str:
    """Set inflections block to TODO (headword changed, old inflections invalid)."""
    # Match a block: inflections:\n  key: value\n  key: value … (until blank line or ```)
    pattern = re.compile(
        r"^(inflections:\n)((?:[ \t]+\S[^\n]*\n?)+)",
        re.MULTILINE,
    )
    return pattern.sub(r"inflections: TODO\n", text)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry = args.dry_run

    deleted = updated = filled = errors = 0

    # ── PASS 1: DELETE ────────────────────────────────────────────────────
    for fname in DELETE:
        path = ENTRIES / fname
        if not path.exists():
            print(f"  SKIP (not found) {fname}")
            continue
        if dry:
            print(f"[DRY-RUN] DELETE {fname}")
        else:
            path.unlink()
            print(f"  deleted  {fname}")
        deleted += 1

    # ── PASS 2: UPDATE ────────────────────────────────────────────────────
    for fname, new_hw, new_pos, new_gender, new_trans in UPDATE:
        path = ENTRIES / fname
        if not path.exists():
            print(f"  SKIP (not found) {fname}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"ERROR reading {fname}: {e}")
            errors += 1
            continue

        original = text
        changes: list[str] = []

        if new_hw:
            text, ok = set_field(text, "headword", new_hw)
            if ok:
                changes.append(f"headword→{new_hw}")
                text = reset_inflections(text)

        if new_pos:
            text, ok = set_field(text, "pos", new_pos)
            if ok:
                changes.append(f"pos→{new_pos}")

        if new_gender:
            text, ok = set_field(text, "gender", new_gender)
            if ok:
                changes.append(f"gender→{new_gender}")

        if new_trans:
            text, ok = set_field(text, "primary_translation", new_trans)
            if ok:
                changes.append(f"translation filled")

        if text != original:
            if dry:
                print(f"[DRY-RUN] UPDATE {fname}: {'; '.join(changes)}")
            else:
                path.write_text(text, encoding="utf-8")
                print(f"  updated  {fname}: {'; '.join(changes)}")
            updated += 1
        else:
            print(f"  no-op    {fname}")

    # ── PASS 3: FILL ──────────────────────────────────────────────────────
    for fname, translation in FILL.items():
        path = ENTRIES / fname
        if not path.exists():
            print(f"  SKIP (not found) {fname}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"ERROR reading {fname}: {e}")
            errors += 1
            continue

        if "primary_translation: TODO" not in text:
            print(f"  already filled {fname}")
            continue

        new_text, ok = set_field(text, "primary_translation", translation)
        if ok:
            if dry:
                print(f"[DRY-RUN] FILL {fname}: '{translation}'")
            else:
                path.write_text(new_text, encoding="utf-8")
                print(f"  filled   {fname}: '{translation}'")
            filled += 1
        else:
            print(f"ERROR: could not set translation in {fname}")
            errors += 1

    print(f"\nDone — deleted={deleted}  updated={updated}  filled={filled}  errors={errors}")


if __name__ == "__main__":
    main()
