"""
fill_examples_en_da_leipzig.py
Fill example sentences for EN→DA entries that are still missing examples,
using the Leipzig Danish news corpus + MyMemory translation API.

Usage:
    python scripts/fill_examples_en_da_leipzig.py [--dry-run] [--email you@example.com]
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
SENTENCES_FILE = ROOT / "data" / "dan_news_2020_1M" / "dan_news_2020_1M-sentences.txt"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

MAX_DA_CHARS = 110
MAX_EXAMPLES = 2
THROTTLE = 1.0  # seconds between API calls

_DA_ALPHA = "a-zA-ZæøåÆØÅ"
_WB_START = f"(?<![{_DA_ALPHA}0-9])"


def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


def has_real_examples(path: Path) -> bool:
    txt = path.read_text(encoding="utf-8")
    ex_m = re.search(r'examples:(.*?)(?:\n```)', txt, re.DOTALL)
    if not ex_m:
        return False
    block = ex_m.group(1)
    da_items = [x.strip() for x in re.findall(r'danish:\s*(.+)', block)]
    return any(x and x not in {"TODO", "SKIP"} for x in da_items)


def load_sentences() -> list[str]:
    print("Loading Leipzig sentences...", flush=True)
    sentences = []
    with open(SENTENCES_FILE, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) == 2 and len(parts[1]) <= MAX_DA_CHARS:
                sentences.append(parts[1])
    sentences.sort(key=len)
    print(f"  {len(sentences):,} sentences loaded", flush=True)
    return sentences


def find_sentences(da_word: str, sentences: list[str], count: int = MAX_EXAMPLES) -> list[str]:
    pat = re.compile(_WB_START + re.escape(da_word), re.IGNORECASE)
    results = []
    for sent in sentences:
        if da_word.lower() in sent.lower() and pat.search(sent):
            results.append(sent)
            if len(results) >= count:
                break
    return results


def translate(text: str, email: str | None = None) -> str | None:
    params: dict = {"q": text, "langpair": "da|en", "mt": "1"}
    if email:
        params["de"] = email
    try:
        resp = requests.get(MYMEMORY_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("responseStatus") == 200:
            t = data["responseData"]["translatedText"]
            if t and len(t) > 5 and "PLEASE SELECT" not in t:
                return t
    except Exception:
        pass
    return None


def inject_examples(path: Path, rows: list[tuple[str, str]], dry_run: bool) -> bool:
    """rows = [(da_text, en_text), ...]"""
    txt = path.read_text(encoding="utf-8")
    parts = []
    for da_text, en_text in rows:
        parts.append(f"  - danish: {yaml_safe(da_text)}")
        parts.append(f"    english: {yaml_safe(en_text)}")
        parts.append(f"    source: leipzig")
        parts.append(f"    source_id: SKIP")
    new_block = "\n".join(parts)

    # Replace empty examples block
    new_txt = re.sub(
        r'(examples:)\s*\n(\s*```)',
        lambda m: f"examples:\n{new_block}\n{m.group(2)}",
        txt, count=1
    )
    # Replace block with only TODO entries
    new_txt = re.sub(
        r'(examples:\n(?:\s+-\s+danish:\s*TODO\n\s+english:\s*TODO\n\s+source:\s*\S+\n\s+source_id:\s*\S+\n?)+)(\s*```)',
        lambda m: f"examples:\n{new_block}\n{m.group(2)}",
        new_txt, count=1
    )
    if new_txt == txt:
        return False
    if not dry_run:
        path.write_text(new_txt, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--email", default=None, help="Email for MyMemory 10K/day limit")
    args = ap.parse_args()

    sentences = load_sentences()

    missing = []
    for p in sorted(EN_DA_DIR.glob("*.md")):
        if not has_real_examples(p):
            txt = p.read_text(encoding="utf-8")
            hw = re.search(r"^headword:\s*(.+)", txt, re.MULTILINE)
            pt = re.search(r"^primary_translation:\s*(.+)", txt, re.MULTILINE)
            if hw and pt:
                headword = hw.group(1).strip()
                trans = pt.group(1).strip()
                da_word = re.sub(r"\s*[(][^)]+[)]$", "", trans).strip()
                # Skip multi-word or hyphen-only translations
                if da_word and " " not in da_word and da_word != "-":
                    missing.append((p, headword, da_word))

    print(f"\nEntries to fill: {len(missing)}")

    filled = 0
    not_found = 0
    translate_fail = 0

    for p, hw, da_word in missing:
        da_sentences = find_sentences(da_word, sentences)
        if not da_sentences:
            print(f"  not found: {hw} ({da_word})")
            not_found += 1
            continue

        rows = []
        for da_sent in da_sentences:
            time.sleep(THROTTLE)
            en_trans = translate(da_sent, args.email)
            if not en_trans:
                print(f"  translate fail: {da_sent[:50]}")
                translate_fail += 1
                en_trans = "TODO"
            rows.append((da_sent, en_trans))

        if inject_examples(p, rows, args.dry_run):
            status = "(dry)" if args.dry_run else ""
            print(f"  filled{status}: {hw} | {rows[0][0][:50]}")
            filled += 1
        else:
            print(f"  inject fail: {hw}")

    print(f"\nDone. Filled: {filled}, not found: {not_found}, translate fail: {translate_fail}")


if __name__ == "__main__":
    main()
