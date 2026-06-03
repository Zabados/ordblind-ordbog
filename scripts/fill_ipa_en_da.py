"""
fill_ipa_en_da.py
Fetch English IPA pronunciation from English Wiktionary for all EN→DA entries
where ipa: TODO.

Usage:
    python scripts/fill_ipa_en_da.py [--throttle 1.0] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
USER_AGENT = "DanishDyslexiaOrdbog/0.1 (ipa-filler; educational use)"
WIKT_BASE = "https://en.wiktionary.org/w/api.php"


def fetch_wikitext(word: str, retries: int = 3) -> str | None:
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json",
        "redirects": True,
    }
    for attempt in range(retries):
        try:
            r = requests.get(
                WIKT_BASE,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return None
            data = r.json()
            if "error" in data:
                return None
            return data["parse"]["wikitext"]["*"]
        except Exception:
            time.sleep(2)
    return None


def extract_english_ipa(wikitext: str) -> str | None:
    """Extract first IPA string from the English section."""
    # Find English section
    m = re.search(r"(==English==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    if not m:
        return None
    english_section = m.group(1)

    # Try {{IPA|en|/.../ }} or {{IPA|en|[...]}}
    ipa_m = re.search(r"\{\{IPA\|en\|([^}]+)\}\}", english_section)
    if ipa_m:
        # Extract the first IPA value (may be |/x/|/y/| ...)
        parts = ipa_m.group(1).split("|")
        for part in parts:
            part = part.strip()
            if part.startswith("/") or part.startswith("["):
                return part
    return None


def extract_phonetic(wikitext: str) -> str | None:
    """Extract SAMPA/phonetic plain from enPR or respelling templates."""
    m = re.search(r"(==English==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    if not m:
        return None
    section = m.group(1)
    enpr = re.search(r"\{\{enPR\|([^|}]+)", section)
    if enpr:
        return enpr.group(1).strip()
    return None


def update_field(content: str, field: str, value: str) -> str:
    pattern = rf"^({re.escape(field)}:\s*)(.+)$"
    new, n = re.subn(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)
    return new if n else content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--throttle", type=float, default=1.0, help="Seconds between requests")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entries = sorted(EN_DA_DIR.glob("en-*-001.md"))
    todo = [p for p in entries if re.search(r"^ipa:\s*TODO", p.read_text(encoding="utf-8"), re.M)]
    print(f"IPA TODO: {len(todo)} entries")

    filled = 0
    not_found = 0

    for i, path in enumerate(todo, 1):
        headword = path.stem[3:-4].replace("-", " ")
        print(f"[{i}/{len(todo)}] {headword}", end=" ... ", flush=True)

        wikitext = fetch_wikitext(headword)
        if not wikitext:
            print("no page")
            not_found += 1
            time.sleep(args.throttle)
            continue

        ipa = extract_english_ipa(wikitext)
        phonetic = extract_phonetic(wikitext)

        if not ipa:
            print("no IPA")
            not_found += 1
            time.sleep(args.throttle)
            continue

        print(ipa.encode("ascii", errors="replace").decode())
        if not args.dry_run:
            content = path.read_text(encoding="utf-8")
            content = update_field(content, "ipa", ipa)
            if phonetic:
                content = update_field(content, "phonetic_plain", phonetic)
            path.write_text(content, encoding="utf-8")
        filled += 1
        time.sleep(args.throttle)

    print(f"\nDone. Filled: {filled}, Not found/no IPA: {not_found}")


if __name__ == "__main__":
    main()
