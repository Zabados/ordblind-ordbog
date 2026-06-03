"""
fix_backslash_format_entries.py
Convert the 3 EN->DA entries that use the \\headword: backslash format
to the standard multi-block fenced format used by all other entries.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGETS = [
    "entries/en-da/en-indian-001.md",
    "entries/en-da/en-jew-001.md",
    "entries/en-da/en-regard-001.md",
]

def fix_file(path: Path) -> None:
    txt = path.read_text(encoding="utf-8")

    # Parse fields from the backslash format
    import re

    def get(name):
        m = re.search(rf'^\\?{re.escape(name)}:\s*(.+)', txt, re.MULTILINE)
        return m.group(1).strip() if m else "TODO"

    def get_list(name):
        m = re.search(rf'^\\?{re.escape(name)}:\n((?:[ \t]+-[^\n]+\n?)+)', txt, re.MULTILINE)
        if not m:
            return []
        return [re.sub(r'^\s*-\s*', '', l).strip() for l in m.group(1).splitlines() if l.strip().startswith('-')]

    headword = get("headword")
    direction = get("direction")
    pos = get("pos")
    gender = get("gender")
    inflections = get("inflections")
    phonetic_plain = get("phonetic_plain")
    ipa = get("ipa")
    syllables = get("syllables")
    stoed = get("stoed")
    primary_translation = get("primary_translation")
    secondary_translations = get_list("secondary_translations")
    register = get("register")
    domain = get("domain")
    formality = get("formality")
    related = get("related")
    tags = get_list("tags")
    frequency_rank = get("frequency_rank")
    frequency_tier = get("frequency_tier")
    ff = get("flag_false_friend")
    ff_note = get("flag_false_friend_note") if "flag_false_friend_note" in txt else "SKIP"
    sp_trap = get("flag_spelling_trap")
    pron_trap = get("flag_pronunciation_trap")
    review_status = get("review_status")
    notes = get("notes")

    # Extract examples block as-is (already filled with real sentences)
    ex_m = re.search(r'examples:(.*)', txt, re.DOTALL)
    if ex_m:
        # Get everything from examples: to end
        ex_rest = ex_m.group(1)
        # Strip trailing \\ or \ lines
        ex_rest = re.sub(r'\n\\+\s*$', '', ex_rest.rstrip())
        # Also strip related:/tags: etc that leaked in
        # Find the last source_id line
        last_ex = list(re.finditer(r'source_id:\s*\S+', ex_rest))
        if last_ex:
            cut = last_ex[-1].end()
            ex_rest = ex_rest[:cut]
        examples_block = "examples:" + ex_rest
    else:
        examples_block = "examples:\n  - danish: TODO\n    english: TODO\n    source: manual\n    source_id: SKIP"

    # Build secondary_translations YAML
    if secondary_translations:
        sec_lines = "\n".join(f"  - {s}" for s in secondary_translations)
        sec_yaml = f"secondary_translations:\n{sec_lines}"
    else:
        sec_yaml = "secondary_translations: []"

    # Build tags YAML
    if tags and tags != ["TODO"]:
        tags_lines = "\n".join(f"  - {t}" for t in tags)
        tags_yaml = f"tags:\n{tags_lines}"
    else:
        tags_yaml = "tags:\n  - TODO"

    new_content = f"""# {headword}

```
headword: {headword}
direction: {direction}
```

```
pos: {pos}
gender: {gender}
```

```
inflections: {inflections}
```

```
phonetic_plain: {phonetic_plain}
ipa: {ipa}
syllables: {syllables}
stoed: {stoed}
```

```
primary_translation: {primary_translation}
{sec_yaml}
```

```
register: {register}
domain: {domain}
formality: {formality}
```

```yaml
{examples_block}
```

```
related: {related}
```

```
{tags_yaml}
```

```
frequency_rank: {frequency_rank}
frequency_tier: {frequency_tier}
```

```
layout:
  print_emphasis: normal
  flag_false_friend: {ff}
  flag_spelling_trap: {sp_trap}
  flag_pronunciation_trap: {pron_trap}
```

```
review_status: {review_status}
notes: {notes}
```
"""

    path.write_text(new_content, encoding="utf-8")
    print(f"Fixed: {path.name}")


for rel in TARGETS:
    fix_file(ROOT / rel)
