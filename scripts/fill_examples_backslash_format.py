"""
fill_examples_backslash_format.py
Fix the 3 EN->DA entries that use \headword: format (were silently skipped).
Uses Leipzig corpus + MyMemory translation.
"""
import re, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_FILE = ROOT / "data" / "dan_news_2020_1M" / "dan_news_2020_1M-sentences.txt"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
MAX_DA_CHARS = 110
_WB_START = r'(?<![a-zA-ZæøåÆØÅ0-9])'

TARGETS = [
    ("entries/en-da/en-indian-001.md", "indisk"),
    ("entries/en-da/en-jew-001.md", "jøde"),
    ("entries/en-da/en-regard-001.md", "betragte"),
]

TODO_BLOCK = (
    "  - danish: TODO\n"
    "    english: TODO\n"
    "    source: manual\n"
    "    source_id: SKIP"
)

def yaml_safe(text):
    text = text.strip()
    needs_quote = any(c in text for c in (':', '"', "'", '#', '{', '}', '[', ']',
                                          '&', '*', '!', '|', '>', '?', '@', '`', '\\'))
    if needs_quote or text.startswith(('-', '.', ',', '%')):
        escaped = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return text

def translate(text):
    try:
        resp = requests.get(MYMEMORY_URL, params={"q": text, "langpair": "da|en", "mt": "1"}, timeout=10)
        data = resp.json()
        if data.get("responseStatus") == 200:
            t = data["responseData"]["translatedText"]
            if t and len(t) > 5 and "PLEASE SELECT" not in t:
                return t
    except Exception:
        pass
    return None

print("Loading Leipzig sentences...", flush=True)
sentences = []
with open(SENTENCES_FILE, encoding="utf-8", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) == 2 and len(parts[1]) <= MAX_DA_CHARS:
            sentences.append(parts[1])
sentences.sort(key=len)
print(f"  {len(sentences):,} sentences loaded")

for rel_path, da_word in TARGETS:
    path = ROOT / rel_path
    pat = re.compile(_WB_START + re.escape(da_word), re.IGNORECASE)
    hits = [s for s in sentences if da_word.lower() in s.lower() and pat.search(s)]
    if not hits:
        print(f"NOT FOUND: {da_word}")
        continue

    rows = []
    for da_sent in hits[:2]:
        time.sleep(1.0)
        en = translate(da_sent) or "TODO"
        rows.append((da_sent, en))
        print(f"  DA: {da_sent[:60]}")
        print(f"  EN: {en[:60]}")

    new_block_lines = []
    for da_sent, en_sent in rows:
        new_block_lines.append(f"  - danish: {yaml_safe(da_sent)}")
        new_block_lines.append(f"    english: {yaml_safe(en_sent)}")
        new_block_lines.append(f"    source: leipzig")
        new_block_lines.append(f"    source_id: SKIP")
    new_block = "\n".join(new_block_lines)

    txt = path.read_text(encoding="utf-8")
    new_txt = txt.replace(TODO_BLOCK, new_block, 1)
    if new_txt == txt:
        print(f"INJECT FAIL for {path.name} — TODO_BLOCK not found")
        # Try to show what's around examples:
        idx = txt.find("examples:")
        if idx >= 0:
            print(repr(txt[idx:idx+150]))
    else:
        path.write_text(new_txt, encoding="utf-8")
        print(f"FILLED: {path.name}")
