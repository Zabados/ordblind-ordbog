"""
fill_examples_missing.py
Fill example sentences for entries that have an empty examples block
(no real Danish sentence at all). Uses the Tatoeba parquet for DA->EN
and the raw TSV files + links for EN->DA.

Usage:
    python scripts/fill_examples_missing.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DA_EN_DIR = ROOT / "entries" / "da-en"
EN_DA_DIR = ROOT / "entries" / "en-da"
PARQUET_PATH = ROOT / "data" / "tatoeba_da_en_pairs.parquet"
DAN_TSV = ROOT / "data" / "dan_sentences.tsv"
ENG_TSV = ROOT / "data" / "eng_sentences.tsv"
LINKS_CSV = ROOT / "data" / "links.csv"

MAX_DA_CHARS = 120
MAX_EXAMPLES = 2
_DA_ALPHA = "a-zA-ZæøåÆØÅ"
_WB_START = f"(?<![{_DA_ALPHA}0-9])"
_WB_END   = f"(?![{_DA_ALPHA}0-9])"


def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_block(rows: list[tuple[int, str, str]]) -> str:
    parts = []
    for da_id, da_text, en_text in rows:
        parts.append(f"  - danish: {yaml_safe(da_text)}")
        parts.append(f"    english: {yaml_safe(en_text)}")
        parts.append(f"    source: tatoeba")
        parts.append(f"    source_id: {da_id}")
    return "\n".join(parts)


def has_real_examples(path: Path) -> bool:
    txt = path.read_text(encoding="utf-8")
    ex_m = re.search(r'examples:(.*?)(?:\n```)', txt, re.DOTALL)
    if not ex_m:
        return False
    block = ex_m.group(1)
    da_items = [x.strip() for x in re.findall(r'danish:\s*(.+)', block)]
    return any(x and x not in {"TODO", "SKIP"} for x in da_items)


def inject_examples(path: Path, rows: list[tuple[int, str, str]], dry_run: bool) -> bool:
    txt = path.read_text(encoding="utf-8")
    new_block = build_block(rows)
    # Replace empty examples block: "examples:\n```" -> "examples:\n  - ...\n```"
    new_txt = re.sub(
        r'(examples:)\s*\n(\s*```)',
        lambda m: f"examples:\n{new_block}\n{m.group(2)}",
        txt,
        count=1
    )
    # Also replace block with only TODO entries
    new_txt = re.sub(
        r'(examples:\n(?:\s+-\s+danish:\s*TODO\n\s+english:\s*TODO\n\s+source:\s*\S+\n\s+source_id:\s*\S+\n?)+)(\s*```)',
        lambda m: f"examples:\n{new_block}\n{m.group(2)}",
        new_txt,
        count=1
    )
    if new_txt == txt:
        return False
    if not dry_run:
        path.write_text(new_txt, encoding="utf-8")
    return True


def search_da(headword: str, text_da, sent_id, text_en) -> list[tuple[int, str, str]]:
    hw_escaped = re.escape(headword)
    pattern = re.compile(_WB_START + hw_escaped, re.IGNORECASE)
    mask = text_da.str.contains(pattern, regex=True, na=False)
    if not mask.any():
        return []
    lengths = text_da.str.len()
    mask = mask & (lengths <= MAX_DA_CHARS)
    if not mask.any():
        return []
    candidates = sorted(
        zip(sent_id[mask], text_da[mask], text_en[mask]),
        key=lambda t: len(t[1]),
    )
    result = []
    seen: set[int] = set()
    for sid, da, en in candidates:
        sid_int = int(sid)
        if sid_int in seen:
            continue
        seen.add(sid_int)
        result.append((sid_int, str(da), str(en)))
        if len(result) >= MAX_EXAMPLES:
            break
    return result


def search_en(headword: str, eng_sents: dict, dan_sents: dict,
              en_to_da: dict) -> list[tuple[int, str, str]]:
    """Search English sentences for headword, return (da_id, da_text, en_text)."""
    hw_escaped = re.escape(headword)
    pattern = re.compile(r'(?<![a-zA-Z0-9])' + hw_escaped + r'(?![a-zA-Z0-9])', re.IGNORECASE)
    results = []
    for en_id, en_text in eng_sents.items():
        if not pattern.search(en_text):
            continue
        if len(en_text) > 120:
            continue
        da_ids = en_to_da.get(en_id, [])
        for da_id in da_ids:
            da_text = dan_sents.get(da_id, "")
            if da_text and len(da_text) <= MAX_DA_CHARS:
                results.append((da_id, da_text, en_text))
                break
        if len(results) >= MAX_EXAMPLES:
            break
    return results


def load_en_da_data():
    """Load eng sentences, dan sentences, and en->da links."""
    print("Loading Danish sentences...", flush=True)
    dan_sents = {}
    for line in DAN_TSV.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            dan_sents[int(parts[0])] = parts[2]

    print("Loading English sentences (sample for speed)...", flush=True)
    eng_sents = {}
    for line in ENG_TSV.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            eng_sents[int(parts[0])] = parts[2]

    print("Loading links...", flush=True)
    en_to_da: dict[int, list[int]] = {}
    dan_ids = set(dan_sents.keys())
    eng_ids = set(eng_sents.keys())
    for line in LINKS_CSV.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        a, b = int(parts[0]), int(parts[1])
        if a in eng_ids and b in dan_ids:
            en_to_da.setdefault(a, []).append(b)
        elif b in eng_ids and a in dan_ids:
            en_to_da.setdefault(b, []).append(a)

    return dan_sents, eng_sents, en_to_da


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas required")

    # --- DA->EN entries ---
    print("\n=== DA->EN ===")
    print("Loading Tatoeba parquet...", flush=True)
    df = pd.read_parquet(PARQUET_PATH)
    text_da = df["text_da"]
    sent_id = df["sentence_id"]
    text_en = df["text_en"]

    da_missing = [p for p in sorted(DA_EN_DIR.glob("*.md")) if not has_real_examples(p)]
    print(f"Missing examples: {len(da_missing)}")

    da_filled = da_not_found = 0
    for path in da_missing:
        txt = path.read_text(encoding="utf-8")
        m = re.search(r"^headword:\s*(.+)$", txt, re.MULTILINE)
        if not m:
            continue
        headword = m.group(1).strip()
        rows = search_da(headword, text_da, sent_id, text_en)
        if not rows:
            print(f"  not found: {headword}")
            da_not_found += 1
            continue
        if inject_examples(path, rows, args.dry_run):
            print(f"  filled: {headword}")
            da_filled += 1

    print(f"DA->EN: filled {da_filled}, not found {da_not_found}")

    # --- EN->DA entries ---
    print("\n=== EN->DA ===")
    dan_sents, eng_sents, en_to_da = load_en_da_data()

    en_missing = [p for p in sorted(EN_DA_DIR.glob("*.md")) if not has_real_examples(p)]
    print(f"Missing examples: {len(en_missing)}")

    en_filled = en_not_found = 0
    for path in en_missing:
        txt = path.read_text(encoding="utf-8")
        m = re.search(r"^headword:\s*(.+)$", txt, re.MULTILINE)
        if not m:
            continue
        headword = m.group(1).strip()
        rows = search_en(headword, eng_sents, dan_sents, en_to_da)
        if not rows:
            print(f"  not found: {headword}")
            en_not_found += 1
            continue
        if inject_examples(path, rows, args.dry_run):
            print(f"  filled: {headword}")
            en_filled += 1

    print(f"EN->DA: filled {en_filled}, not found {en_not_found}")


if __name__ == "__main__":
    main()
