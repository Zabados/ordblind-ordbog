#!/usr/bin/env python3
"""
fill_examples_wiktionary.py — Fill TODO example sentences from Wiktionary {{ux}} blocks.

Targets entries that still have "danish: TODO" examples.
Fetches the Wiktionary page for each headword, extracts {{ux|da|sentence|translation}}
usage examples, and writes them back to the entry file.

Usage:
    python scripts/fill_examples_wiktionary.py [--dry-run] [--throttle 1.0]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

ROOT       = Path(__file__).resolve().parent.parent
ENTRIES    = ROOT / "entries" / "da-en"
USER_AGENT = "DanishDyslexiaOrdbog/0.1 (example-filler; educational use)"
WIKT_BASE  = "https://en.wiktionary.org/w/api.php"

MAX_EXAMPLES = 2

TODO_EXAMPLES = (
    "  - danish: TODO\n"
    "    english: TODO\n"
    "    source: manual\n"
    "    source_id: SKIP"
)


# ── Wiktionary helpers ────────────────────────────────────────────────────────

def fetch_wikitext(word: str) -> str | None:
    try:
        r = requests.get(WIKT_BASE, params={
            "action": "parse", "page": word,
            "prop": "wikitext", "format": "json", "redirects": True,
        }, headers={"User-Agent": USER_AGENT}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if "error" in data:
            return None
        return data["parse"]["wikitext"]["*"]
    except Exception:
        return None


def extract_danish_section(wikitext: str) -> str | None:
    m = re.search(r"(==Danish==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    return m.group(1) if m else None


def _strip_templates(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return text


def _strip_wikilinks(text: str) -> str:
    return re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]+)\]\]", r"\1", text)


def _clean(text: str) -> str:
    """Strip wikitext markup, bold/italic, leading/trailing whitespace."""
    text = _strip_templates(text)
    text = _strip_wikilinks(text)
    text = re.sub(r"'''?([^']+)'''?", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_ux_examples(section: str) -> list[tuple[str, str]]:
    """
    Extract {{ux|da|danish sentence|english translation}} pairs.
    Returns list of (danish, english) tuples, clean text.
    """
    # Pattern: {{ux|da|sentence|translation}} — translation may be in a nested {{...}}
    # We find the raw ux template lines and parse them carefully.
    results: list[tuple[str, str]] = []

    # Find all {{ux|da|...}} occurrences
    # Use a simple iterative approach since templates can be nested
    pos = 0
    while True:
        start = section.find("{{ux|da|", pos)
        if start == -1:
            break

        # Find the matching closing }}
        depth = 0
        i = start
        while i < len(section):
            if section[i:i+2] == "{{":
                depth += 1
                i += 2
            elif section[i:i+2] == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    break
            else:
                i += 1

        raw = section[start:i]
        pos = i

        # Split on | but respect nested {{ }}
        parts = _split_template_args(raw)
        # parts[0] = "ux", parts[1] = "da", parts[2] = sentence, parts[3] = translation
        if len(parts) >= 4:
            da  = _clean(parts[2])
            en  = _clean(parts[3])
            if da and en and len(da) > 3 and len(en) > 3:
                results.append((da, en))
        elif len(parts) == 3:
            # No translation provided — skip (can't use without EN)
            pass

        if len(results) >= MAX_EXAMPLES:
            break

    return results


def _split_template_args(template: str) -> list[str]:
    """Split a {{...}} template on top-level pipes, returning all parts."""
    # Strip outer {{ }}
    inner = template[2:-2]
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if inner[i:i+2] in ("{{", "[["):
            depth += 1
            current.append(inner[i:i+2])
            i += 2
        elif inner[i:i+2] in ("}}", "]]"):
            depth -= 1
            current.append(inner[i:i+2])
            i += 2
        elif ch == "|" and depth == 0:
            parts.append("".join(current).strip())
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    parts.append("".join(current).strip())
    return parts


# ── YAML helpers ──────────────────────────────────────────────────────────────

def yaml_safe(text: str) -> str:
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}',
                                          '[', ']', '&', '*', '!', '|',
                                          '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(("-", ".", ",", "%")):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_examples_block(pairs: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for da, en in pairs:
        parts.append(
            f"  - danish: {yaml_safe(da)}\n"
            f"    english: {yaml_safe(en)}\n"
            f"    source: wiktionary\n"
            f"    source_id: SKIP"
        )
    return "\n".join(parts)


# ── Entry file updater ────────────────────────────────────────────────────────

EXAMPLES_RE = re.compile(
    r"(examples:\n)" + re.escape(TODO_EXAMPLES) + r"(\n```)",
    re.DOTALL,
)


def update_entry(path: Path, pairs: list[tuple[str, str]], dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    if TODO_EXAMPLES not in text:
        return False  # nothing to replace

    new_block = build_examples_block(pairs)
    new_text = text.replace(
        "examples:\n" + TODO_EXAMPLES,
        "examples:\n" + new_block,
        1,
    )

    if new_text == text:
        return False

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--throttle", type=float, default=1.0)
    args = ap.parse_args()

    # Find entries with TODO examples
    targets: list[tuple[str, Path]] = []
    hw_re = re.compile(r"^headword:\s*(.+)", re.MULTILINE)
    for md in sorted(ENTRIES.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        if TODO_EXAMPLES not in text:
            continue
        m = hw_re.search(text)
        if m:
            targets.append((m.group(1).strip(), md))

    print(f"{len(targets)} entries with TODO examples")
    counts = {"filled": 0, "no_examples": 0, "no_wikt": 0}

    for headword, path in targets:
        print(f"  {headword} … ", end="", flush=True)

        wikitext = fetch_wikitext(headword)
        time.sleep(args.throttle)

        if not wikitext:
            print("no Wiktionary page")
            counts["no_wikt"] += 1
            continue

        section = re.search(r"(==Danish==.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
        if not section:
            print("no Danish section")
            counts["no_wikt"] += 1
            continue

        pairs = extract_ux_examples(section.group(1))
        if not pairs:
            print("no {{ux}} examples found")
            counts["no_examples"] += 1
            continue

        updated = update_entry(path, pairs, args.dry_run)
        tag = "DRY-RUN" if args.dry_run else "written"
        if updated:
            for da, en in pairs:
                print(f"\n    DA: {da}")
                print(f"    EN: {en}")
            print(f"  -> {tag} {path.name}")
            counts["filled"] += 1
        else:
            print("already filled or mismatch")

    print()
    print("-- Summary ------------------------------------------")
    print(f"  Filled:          {counts['filled']}")
    print(f"  No ux found:     {counts['no_examples']}")
    print(f"  No Wiktionary:   {counts['no_wikt']}")


if __name__ == "__main__":
    main()
