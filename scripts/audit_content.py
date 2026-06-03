"""
audit_content.py
-----------------
Scans all DA→EN entries for content quality issues and writes a report.

Checks:
  1. HEADWORD-IN-EXAMPLE  — Danish example doesn't contain the headword
                            (or any obvious stem/inflection). Catches runde-type bugs.
  2. POS-TRANSLATION      — pos=verb but primary_translation doesn't start "to ";
                            or pos!=verb but translation does start "to ".
  3. NOUN-GENDER-SKIP     — pos=noun but gender=SKIP (should be en or et).
  4. EXAMPLE-LANG-SWAP    — Danish sentence contains mostly ASCII + common English
                            words, suggesting EN/DA may be swapped.
  5. EMPTY-TRANSLATION    — primary_translation is TODO or blank.
  6. BAD-SECONDARY        — a secondary_translation is identical to the primary.

Output: audit_report.txt
"""

import re
import unicodedata
from pathlib import Path

ENTRIES_DIR = Path("entries/da-en")
OUT = Path("audit_report.txt")

# Common English function words — if a "Danish" sentence has many of these,
# it may be language-swapped
EN_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might", "shall",
    # Removed: "i", "you", "he", "she", "it", "we", "they"
    # "i" is Danish for "in/at" and "I" is Danish for "you (plural)"
    "you", "he", "she", "it", "we", "they",
    "my", "your", "his", "her", "our", "their",
    "this", "that", "these", "those",
    # Removed: "and", "or", "but", "in", "on", "at", "to", "of", "for",
    # "with", "from", "by", "not", "no", "so" — all common in Danish too
    "but",
}

# Danish-specific characters — presence strongly implies Danish text
DA_CHARS = set("æøåÆØÅ")


def read_field(text: str, field: str) -> str:
    m = re.search(rf"^\s*{re.escape(field)}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def read_examples(text: str) -> list[dict]:
    """Parse all example blocks from the examples: yaml section."""
    examples = []
    # Find danish: lines and their following english: lines
    for m in re.finditer(r"^\s+-\s+danish:\s+(.+)$", text, re.MULTILINE):
        da = m.group(1).strip()
        # Get the english line following this danish line
        rest = text[m.end():]
        en_m = re.match(r"\s+english:\s+(.+)", rest)
        en = en_m.group(1).strip() if en_m else ""
        examples.append({"danish": da, "english": en})
    return examples


def stem_variants(word: str) -> set[str]:
    """Generate a small set of likely stem variants for basic matching."""
    w = word.lower()
    variants = {w}
    # Strip common suffixes to get root
    for suffix in ("ede", "ede", "er", "es", "ne", "te", "et", "en", "t", "e", "r", "s"):
        if len(w) > len(suffix) + 2 and w.endswith(suffix):
            variants.add(w[: -len(suffix)])
    # Also add with common Danish verb prefixes stripped
    return variants


def headword_in_example(headword: str, danish_sentence: str) -> bool:
    """Check if headword (or a plausible inflection) appears in the sentence."""
    sentence_lower = danish_sentence.lower()
    variants = stem_variants(headword)
    for v in variants:
        if v and v in sentence_lower:
            return True
    return False


def looks_like_english(sentence: str) -> bool:
    """Heuristic: sentence is probably English not Danish."""
    if any(c in sentence for c in DA_CHARS):
        return False
    words = re.findall(r"\b[a-z]+\b", sentence.lower())
    if not words:
        return False
    en_count = sum(1 for w in words if w in EN_WORDS)
    return en_count / len(words) >= 0.4


def check_entry(path: Path) -> list[tuple[str, str]]:
    """Return list of (issue_code, detail) for one entry."""
    text = path.read_text(encoding="utf-8")
    issues = []

    headword = read_field(text, "headword")
    pos      = read_field(text, "pos")
    gender   = read_field(text, "gender")
    primary  = read_field(text, "primary_translation")

    # 1. EMPTY-TRANSLATION
    if primary in ("", "TODO"):
        issues.append(("EMPTY-TRANSLATION", f"primary_translation={primary!r}"))

    # 2. POS-TRANSLATION mismatch
    # Modals and reflexive verbs whose English equivalent doesn't use "to"
    MODAL_SKIP = {"skulle", "ville", "kunne", "måtte", "burde", "turde",
                  "nøje", "nøjes", "skyldes"}
    if pos == "verb" and primary not in ("", "TODO"):
        if not primary.lower().startswith("to ") and headword not in MODAL_SKIP:
            issues.append(("POS-TRANS-VERB", f"pos=verb but translation={primary!r}"))
    if pos in ("noun", "adjective", "adverb") and primary not in ("", "TODO"):
        if primary.lower().startswith("to "):
            issues.append(("POS-TRANS-NONVERB", f"pos={pos} but translation starts 'to': {primary!r}"))

    # 3. NOUN-GENDER-SKIP
    if pos == "noun" and gender == "SKIP":
        issues.append(("NOUN-GENDER-SKIP", "pos=noun but gender=SKIP"))

    # 4. BAD-SECONDARY — secondary identical to primary
    sec_block = re.search(r"secondary_translations:(.*?)(?=\n\w|\n```)", text,
                          re.DOTALL)
    if sec_block:
        secondaries = re.findall(r"-\s+(.+)", sec_block.group(1))
        for s in secondaries:
            s = s.strip().strip('"\'')
            if s.lower() == primary.lower():
                issues.append(("DUPLICATE-SECONDARY", f"{s!r} == primary"))

    # 5. HEADWORD-IN-EXAMPLE and LANG-SWAP
    examples = read_examples(text)
    for i, ex in enumerate(examples):
        da = ex["danish"]
        en = ex["english"]

        if da and headword and not headword_in_example(headword, da):
            issues.append(("HEADWORD-ABSENT", f"ex{i+1}: {da!r}"))

        if da and looks_like_english(da):
            issues.append(("LANG-SWAP?", f"ex{i+1} Danish looks English: {da!r}"))

        # Check if english field looks like Danish (has Danish chars)
        if en and any(c in en for c in DA_CHARS):
            issues.append(("LANG-SWAP?", f"ex{i+1} English contains Danish chars: {en!r}"))

    return issues


def main():
    files = sorted(ENTRIES_DIR.glob("*.md"))
    all_issues: list[tuple[str, list]] = []

    for f in files:
        issues = check_entry(f)
        if issues:
            all_issues.append((f.name, issues))

    # Write report
    lines = [
        "ORDBOG CONTENT AUDIT REPORT",
        f"Entries checked : {len(files)}",
        f"Entries flagged : {len(all_issues)}",
        "",
    ]

    # Summary by issue type
    from collections import Counter
    type_counts: Counter = Counter()
    for _, issues in all_issues:
        for code, _ in issues:
            type_counts[code] += 1

    lines.append("ISSUE SUMMARY")
    lines.append("-" * 40)
    for code, count in type_counts.most_common():
        lines.append(f"  {code:25s} {count}")
    lines.append("")

    # Detail
    lines.append("DETAIL")
    lines.append("-" * 40)
    for fname, issues in all_issues:
        lines.append(f"\n{fname}")
        for code, detail in issues:
            lines.append(f"  [{code}] {detail}")

    report = "\n".join(lines)
    OUT.write_text(report, encoding="utf-8")
    print(report[:3000])
    if len(report) > 3000:
        print(f"\n... (truncated — full report in {OUT})")
    print(f"\nFull report: {OUT}")


if __name__ == "__main__":
    main()
