"""
Diagnostic script — scans all entry files and reports on completeness.

Usage:
    python scripts/diagnose.py              # prints summary to console
    python scripts/diagnose.py --csv        # also writes reports/diagnosis.csv
"""

import argparse
import csv
import glob
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENTRIES_DIR = ROOT / "entries" / "da-en"
REPORTS_DIR = ROOT / "reports"

REQUIRED_FIELDS = [
    "pos",
    "primary_translation",
    "ipa",
    "phonetic_plain",
    "syllables",
    "stoed",
    "frequency_rank",
    "frequency_tier",
    "tags",
]


def parse_entry_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")

    def get_field(name: str) -> str | None:
        m = re.search(rf"^{re.escape(name)}:\s*(.+)$", content, re.MULTILINE)
        return m.group(1).strip() if m else None

    def get_tags() -> str:
        """Extract tags block and check if any real tag exists."""
        m = re.search(r"^tags:\n((?:  - .+\n?)+)", content, re.MULTILINE)
        if not m:
            return "TODO"
        lines = [l.strip().lstrip("- ") for l in m.group(1).splitlines() if l.strip()]
        non_todo = [l for l in lines if l != "TODO"]
        return non_todo[0] if non_todo else "TODO"

    headword = get_field("headword") or path.stem
    record = {"file": path.name, "headword": headword}

    for field in REQUIRED_FIELDS:
        val = get_tags() if field == "tags" else get_field(field)
        record[field] = val or "MISSING"

    record["has_examples"] = "danish: TODO" not in content and "examples:" in content
    record["has_tatoeba"] = "source: tatoeba" in content
    record["todos"] = content.count("TODO")
    record["review_status"] = get_field("review_status") or "?"
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", action="store_true", help="Write reports/diagnosis.csv")
    args = parser.parse_args()

    paths = sorted(Path(p) for p in glob.glob(str(ENTRIES_DIR / "*.md")))
    if not paths:
        print(f"No entry files found in {ENTRIES_DIR}")
        return

    records = [parse_entry_file(p) for p in paths]

    # --- Summary counts ---
    total = len(records)
    print(f"\n{'='*55}")
    print(f"  ORDBOG DIAGNOSTIC — {total} entries in entries/da-en/")
    print(f"{'='*55}")

    for field in REQUIRED_FIELDS:
        todo_count = sum(1 for r in records if r[field] in ("TODO", "MISSING"))
        pct = 100 * todo_count / total
        bar = "█" * int((total - todo_count) / total * 20)
        bar = bar.ljust(20)
        status = "✓" if pct == 0 else ("!" if pct > 50 else "~")
        print(f"  {status} {field:<22} {bar} {total - todo_count:>3}/{total}  ({100-pct:.0f}% filled)")

    has_ex = sum(1 for r in records if r["has_examples"])
    has_tat = sum(1 for r in records if r["has_tatoeba"])
    print(f"\n  Examples (any):       {has_ex}/{total}")
    print(f"  Tatoeba sentences:    {has_tat}/{total}")

    avg_todos = sum(r["todos"] for r in records) / total
    print(f"  Avg TODO fields/entry: {avg_todos:.1f}")

    # --- Worst entries ---
    worst = sorted(records, key=lambda r: -r["todos"])[:10]
    print(f"\n  Most incomplete entries:")
    for r in worst:
        print(f"    {r['headword']:<20} {r['todos']} TODOs")

    # --- Zero translation ---
    no_trans = [r for r in records if r["primary_translation"] in ("TODO", "MISSING")]
    if no_trans:
        words = [r["headword"] for r in no_trans]
        print(f"\n  No translation ({len(no_trans)}): {', '.join(words[:20])}")

    # --- No examples ---
    no_ex = [r for r in records if not r["has_examples"]]
    if no_ex:
        words = [r["headword"] for r in no_ex]
        print(f"\n  No examples ({len(no_ex)}): {', '.join(words[:20])}")

    print(f"\n{'='*55}\n")

    # --- CSV output ---
    if args.csv:
        REPORTS_DIR.mkdir(exist_ok=True)
        out = REPORTS_DIR / "diagnosis.csv"
        fieldnames = ["file", "headword"] + REQUIRED_FIELDS + [
            "has_examples", "has_tatoeba", "todos", "review_status"
        ]
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        print(f"  CSV written to {out}\n")


if __name__ == "__main__":
    main()
