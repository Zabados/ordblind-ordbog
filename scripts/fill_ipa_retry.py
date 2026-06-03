"""
fill_ipa_retry.py
Targeted retry for specific headwords that failed in fill_ipa_en_da.py.
Uses a longer throttle to avoid rate limiting.
"""

import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
USER_AGENT = "DanishDyslexiaOrdbog/0.1 (ipa-retry; educational use)"
WIKT_BASE = "https://en.wiktionary.org/w/api.php"

# Words that reported "no page" — likely rate-limited, not genuinely missing
RETRY_WORDS = [
    "analysis", "application", "award", "beach", "bottom", "building",
    "character", "class", "complete", "considerable", "contrast", "cover",
    "degree", "develop", "discuss", "draw", "eat", "equipment",
    "evil", "face", "feel", "find", "forth", "function",
    "head", "historical", "importance", "inform", "interview", "labor",
    "lay", "legal", "long", "manner", "measurement", "minute",
    "neck", "notice", "operate", "owner", "period", "play",
    "positive", "process", "proposal", "put", "receive", "region",
    "represent", "review", "russian", "sea", "send", "shoot",
    "significant", "slight", "song", "speed", "statement", "strip",
    "sum", "tax", "therefore", "top", "tree", "vary",
    "way", "whole", "young",
]

# Manual IPA for "no IPA" entries (page exists but no IPA template)
MANUAL_IPA = {
    "european": "/ˌjʊər.əˈpiː.ən/",
    "indian": "/ˈɪn.di.ən/",
    "membership": "/ˈmem.bər.ʃɪp/",
    "vocational": "/vəʊˈkeɪ.ʃən.əl/",
}


def fetch_wikitext(word: str, retries: int = 4) -> str | None:
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
                wait = 10 * (attempt + 1)
                print(f"  429 — waiting {wait}s")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return None
            data = r.json()
            if "error" in data:
                return None
            return data["parse"]["wikitext"]["*"]
        except Exception as e:
            print(f"  error: {e}")
            time.sleep(3)
    return None


def extract_english_ipa(wikitext: str) -> str | None:
    m = re.search(r"(==English==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    if not m:
        return None
    section = m.group(1)
    ipa_m = re.search(r"\{\{IPA\|en\|([^}]+)\}\}", section)
    if ipa_m:
        for part in ipa_m.group(1).split("|"):
            part = part.strip()
            if part.startswith("/") or part.startswith("["):
                return part
    return None


def update_ipa(path: Path, ipa: str) -> bool:
    txt = path.read_text(encoding="utf-8")
    new_txt = re.sub(r"^(ipa:\s*)TODO", rf"\g<1>{ipa}", txt, flags=re.MULTILINE)
    if new_txt != txt:
        path.write_text(new_txt, encoding="utf-8")
        return True
    return False


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    throttle = 3.0
    filled = 0
    still_missing = []

    # Apply manual IPA first
    for word, ipa in MANUAL_IPA.items():
        slug = word.replace(" ", "-")
        path = EN_DA_DIR / f"en-{slug}-001.md"
        if path.exists():
            if update_ipa(path, ipa):
                print(f"[manual] {word} -> {ipa}")
                filled += 1
            else:
                print(f"[manual] {word} already set")
        else:
            print(f"[manual] {word} file not found")

    # Retry network lookups
    total = len(RETRY_WORDS)
    for i, word in enumerate(RETRY_WORDS, 1):
        slug = word.replace(" ", "-")
        path = EN_DA_DIR / f"en-{slug}-001.md"
        if not path.exists():
            print(f"[{i}/{total}] {word} ... no file")
            still_missing.append(word)
            continue

        # Skip if already filled
        txt = path.read_text(encoding="utf-8")
        if not re.search(r"^ipa:\s*TODO", txt, re.MULTILINE):
            print(f"[{i}/{total}] {word} ... already set")
            continue

        print(f"[{i}/{total}] {word} ...", end=" ", flush=True)
        wikitext = fetch_wikitext(word)
        if not wikitext:
            print("no page")
            still_missing.append(word)
            time.sleep(throttle)
            continue

        ipa = extract_english_ipa(wikitext)
        if not ipa:
            print("no IPA on page")
            still_missing.append(word)
            time.sleep(throttle)
            continue

        update_ipa(path, ipa)
        print(ipa, flush=True)
        filled += 1
        time.sleep(throttle)

    print(f"\nDone. Filled: {filled}, Still missing: {len(still_missing)}")
    if still_missing:
        print("Still missing:", ", ".join(still_missing))


if __name__ == "__main__":
    main()
