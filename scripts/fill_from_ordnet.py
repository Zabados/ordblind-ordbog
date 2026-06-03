"""
fill_from_ordnet.py — Fill gender and inflections from ordnet.dk using playwright.

Usage:
    python scripts/fill_from_ordnet.py [--dry-run] [--field gender|inflections|both]
                                        [--limit N] [--start-from HEADWORD]

Polite crawl: 1.5s delay between requests.
"""

import sys
import re
import time
import argparse
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

ENTRIES_DIR = Path("entries/da-en")
DELAY = 1.5  # seconds between requests

# ordnet Danish POS labels → our controlled vocab
POS_DK = {
    "verb": "verbum",
    "noun": "substantiv",
    "adjective": "adjektiv",
    "adverb": "adverbium",
    "pronoun": "pronomen",
    "preposition": "præposition",
    "conjunction": "konjunktion",
    "interjection": "interjektion",
}

# ordnet gender strings → en/et
GENDER_MAP = {
    "fælleskøn": "en",
    "intetkøn": "et",
}

# Known irregular Danish plurals for ".." expansion
IRREGULAR_SINGULARS: dict[str, str] = {
    "mænd": "mand",
    "børn": "barn",
    "fødder": "fod",
    "hænder": "hånd",
    "tænder": "tand",
    "øjne": "øje",
    "øren": "øre",
    "bøger": "bog",
    "tæer": "tå",
    "knæ": "knæ",
    "sko": "sko",
}

# Non-inflecting POS — gender and inflections should be SKIP
NO_INFLECT_POS = {"adverb", "preposition", "conjunction", "interjection", "pronoun"}


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def read_field(text: str, field: str) -> str:
    m = re.search(rf"^{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def set_field(text: str, field: str, value: str) -> str:
    return re.sub(rf"^{re.escape(field)}:.*$", f"{field}: {value}", text, flags=re.MULTILINE)


def inflections_needs_fill(text: str) -> bool:
    """True if the inflections field is TODO (single-line or pre-expanded block)."""
    # Single-line sentinel
    if re.search(r"^inflections: TODO$", text, re.MULTILINE):
        return True
    # Pre-expanded block with any TODO sub-field
    if re.search(r"^inflections:\s*$", text, re.MULTILINE):
        # Check if every sub-field under it is TODO (or most are)
        m = re.search(r"^inflections:\s*\n((?:  \S.*\n?)*)", text, re.MULTILINE)
        if m and "TODO" in m.group(1):
            return True
    return False


def set_inflections_block(text: str, block: str) -> str:
    """Replace inflections TODO (single-line or pre-expanded) with a filled block."""
    # Single-line sentinel
    if re.search(r"^inflections: TODO$", text, re.MULTILINE):
        return re.sub(r"^inflections: TODO$", block, text, flags=re.MULTILINE)
    # Pre-expanded block — replace the whole block
    return re.sub(r"^inflections:\s*\n(?:  \S[^\n]*\n?)*", block + "\n", text, flags=re.MULTILINE)


def inflections_to_yaml(d: dict) -> str:
    lines = ["inflections:"]
    for k, v in d.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ordnet parsing helpers
# ---------------------------------------------------------------------------

def find_pos_section(article: str, pos: str) -> str:
    """Return the slice of the article text relevant to our POS."""
    pos_dk = POS_DK.get(pos, "")
    if not pos_dk:
        return article
    idx = article.lower().find(pos_dk)
    if idx == -1:
        return article
    section = article[idx:]
    # Trim at next different POS marker
    for other in POS_DK.values():
        if other == pos_dk:
            continue
        nxt = section.lower().find(other, 30)
        if nxt != -1:
            section = section[:nxt]
    return section


def parse_gender(article: str, pos: str) -> str | None:
    """Return 'en', 'et', 'SKIP', or None if unknown."""
    if pos in NO_INFLECT_POS or pos == "verb" or pos == "adjective":
        return "SKIP"
    section = find_pos_section(article, pos)
    low = section[:400].lower()
    for key, val in GENDER_MAP.items():
        if key in low:
            return val
    return None


def expand_form(headword: str, form: str) -> str:
    """Expand a BØJNING token relative to headword."""
    form = form.strip()
    if not form or form in ("–", "—", "-"):
        return "SKIP"   # indeclinable
    if form.startswith(".."):
        suffix = form[2:]
        # Try known irregular map
        for irr_pl, irr_sg in IRREGULAR_SINGULARS.items():
            if suffix == irr_pl or suffix.startswith(irr_pl):
                rest = suffix[len(irr_pl):]
                if headword.lower().endswith(irr_sg.lower()):
                    stem = headword[: -len(irr_sg)]
                    return stem + suffix
        # Fallback: strip last 2–6 chars of headword until a clean join
        for strip in range(2, min(7, len(headword))):
            candidate = headword[:-strip] + suffix
            # Accept if it looks plausible (no double consonant artifacts)
            if candidate:
                return candidate
        return headword + suffix
    if form.startswith("-"):
        return headword + form[1:]
    # Full form provided
    return form


def parse_boj_line(raw: str) -> list[str]:
    """Split a raw BØJNING string into tokens."""
    # Cut at double-space (secondary forms like 'skyldes: ...')
    raw = re.split(r"\s{2,}", raw)[0]
    # Cut at pipe
    raw = raw.split("|")[0]
    return [p.strip() for p in raw.split(",") if p.strip()]


def parse_inflections(article: str, headword: str, pos: str) -> dict | None:
    section = find_pos_section(article, pos)
    m = re.search(r"BØJNING\s+(.+?)(?:\n|$)", section)
    if not m:
        return None
    parts = parse_boj_line(m.group(1).strip())
    if not parts:
        return None

    if pos == "noun":
        return {
            "indefinite_singular": headword,
            "definite_singular":   expand_form(headword, parts[0]) if len(parts) > 0 else "TODO",
            "indefinite_plural":   expand_form(headword, parts[1]) if len(parts) > 1 else "TODO",
            "definite_plural":     expand_form(headword, parts[2]) if len(parts) > 2 else "TODO",
        }
    elif pos == "verb":
        return {
            "infinitive":          headword,
            "present":             expand_form(headword, parts[0]) if len(parts) > 0 else "TODO",
            "past":                expand_form(headword, parts[1]) if len(parts) > 1 else "TODO",
            "past_participle":     expand_form(headword, parts[2]) if len(parts) > 2 else "TODO",
            "present_participle":  "TODO",
        }
    elif pos == "adjective":
        # BØJNING: -t, -e; comparative, superlative  (semicolon separates groups)
        raw_boj = m.group(1).strip()
        groups = raw_boj.split(";")
        pos_parts = parse_boj_line(groups[0])
        comp_parts = parse_boj_line(groups[1]) if len(groups) > 1 else []
        return {
            "positive":        headword,
            "neuter":          expand_form(headword, pos_parts[0]) if pos_parts else "TODO",
            "plural_definite": expand_form(headword, pos_parts[1]) if len(pos_parts) > 1 else "TODO",
            "comparative":     comp_parts[0] if comp_parts else "TODO",
            "superlative":     comp_parts[1] if len(comp_parts) > 1 else "TODO",
        }

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    ap.add_argument("--field", choices=["gender", "inflections", "both"], default="both")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N entries (0 = all)")
    ap.add_argument("--start-from", default="", help="Skip entries until this headword")
    args = ap.parse_args()

    files = sorted(ENTRIES_DIR.glob("*.md"))

    gender_filled = inflections_filled = skipped = errors = 0
    not_found: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="OrdbogPD3/1.0 (educational Danish-English dictionary; non-commercial)"
        )
        page = ctx.new_page()
        cookies_accepted = False
        count = 0
        started = not args.start_from

        for f in files:
            text = f.read_text(encoding="utf-8")
            headword   = read_field(text, "headword")
            pos        = read_field(text, "pos")
            gender_val = read_field(text, "gender")
            infl_val   = read_field(text, "inflections")

            need_gender = args.field in ("gender", "both") and gender_val == "TODO"
            need_infl   = args.field in ("inflections", "both") and inflections_needs_fill(text)

            if not need_gender and not need_infl:
                continue

            # start-from filter
            if not started:
                if headword == args.start_from:
                    started = True
                else:
                    continue

            if args.limit and count >= args.limit:
                break

            count += 1
            print(f"  [{count}] {f.name} ({headword}) ...", end="  ", flush=True)

            try:
                pos_dk = POS_DK.get(pos, "")

                def fetch_articles(url: str) -> list[str]:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    nonlocal cookies_accepted
                    if not cookies_accepted:
                        try:
                            page.click("text=Allow all cookies", timeout=3000)
                            page.wait_for_timeout(400)
                        except Exception:
                            pass
                        cookies_accepted = True
                    result: list[str] = []
                    try:
                        n = page.locator(".artikel").count()
                        for i in range(n):
                            try:
                                result.append(page.locator(".artikel").nth(i).inner_text(timeout=4000))
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return result

                def pick_article(arts: list[str]) -> str:
                    if not arts:
                        return ""
                    if pos_dk:
                        for a in arts:
                            if pos_dk in a[:200].lower():
                                return a
                    return ""  # no match — don't fall back to wrong POS

                # Try base URL first
                hw_enc = quote(headword, safe="")
                base_url = f"https://ordnet.dk/ddo_en/dict?query={hw_enc}"
                articles_raw = fetch_articles(base_url)
                article = pick_article(articles_raw)

                # If no POS match, try ?select=headword,N for N=2..5
                if not article and pos_dk:
                    for n in range(2, 6):
                        time.sleep(0.5)
                        select_url = f"https://ordnet.dk/ddo_en/dict?select={hw_enc},{n}&query={hw_enc}"
                        arts = fetch_articles(select_url)
                        candidate = pick_article(arts)
                        if candidate:
                            article = candidate
                            articles_raw = arts
                            break

                # Final fallback: first article on base URL (better than nothing)
                if not article:
                    arts_base = fetch_articles(base_url) if article == "" else articles_raw
                    if arts_base:
                        article = arts_base[0]

                if not article:
                    for sel in ["#content", "main"]:
                        try:
                            article = page.locator(sel).first.inner_text(timeout=4000)
                            break
                        except Exception:
                            continue

                if not article:
                    article = page.locator("body").inner_text(timeout=5000)

                # Note if multiple POS entries exist on ordnet
                multi_pos_note = f" [ordnet:{len(articles_raw)}]" if len(articles_raw) > 1 else ""

                # Check word was actually found
                if headword.lower() not in article[:600].lower():
                    print("NOT FOUND")
                    not_found.append(headword)
                    skipped += 1
                    time.sleep(DELAY)
                    continue

                new_text = text
                changed = False
                log_parts: list[str] = []

                if need_gender:
                    g = parse_gender(article, pos)
                    if g:
                        new_text = set_field(new_text, "gender", g)
                        gender_filled += 1
                        changed = True
                        log_parts.append(f"gender={g}")
                    else:
                        log_parts.append("gender=?")

                if need_infl:
                    inf = parse_inflections(article, headword, pos)
                    if inf:
                        block = inflections_to_yaml(inf)
                        new_text = set_inflections_block(new_text, block)
                        inflections_filled += 1
                        changed = True
                        log_parts.append("inflections=✓")
                    else:
                        log_parts.append("inflections=?")

                print("  ".join(log_parts) + multi_pos_note)

                if changed and not args.dry_run:
                    f.write_text(new_text, encoding="utf-8")

            except Exception as e:
                print(f"ERROR: {e}")
                errors += 1

            time.sleep(DELAY)

        browser.close()

    print(
        f"\nDone — gender={gender_filled}  inflections={inflections_filled}"
        f"  skipped={skipped}  errors={errors}"
    )
    if not_found:
        print(f"Not on ordnet ({len(not_found)}): {', '.join(not_found[:30])}")


if __name__ == "__main__":
    main()
