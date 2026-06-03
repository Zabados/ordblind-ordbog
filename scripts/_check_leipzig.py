"""Check how many of the 48 missing words appear in Leipzig corpus."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"
SENTENCES = ROOT / "data" / "dan_news_2020_1M" / "dan_news_2020_1M-sentences.txt"

def has_real_examples(path):
    txt = path.read_text(encoding="utf-8")
    ex_m = re.search(r'examples:(.*?)(?:\n```)', txt, re.DOTALL)
    if not ex_m: return False
    block = ex_m.group(1)
    da_items = [x.strip() for x in re.findall(r'danish:\s*(.+)', block)]
    return any(x and x not in ['TODO','SKIP'] for x in da_items)

missing = []
for p in sorted(EN_DA_DIR.glob("*.md")):
    if not has_real_examples(p):
        txt = p.read_text(encoding="utf-8")
        hw = re.search(r'^headword:\s*(.+)', txt, re.MULTILINE)
        pt = re.search(r'^primary_translation:\s*(.+)', txt, re.MULTILINE)
        if hw and pt:
            headword = hw.group(1).strip()
            trans = pt.group(1).strip()
            da_word = re.sub(r'\s*[(][^)]+[)]$', '', trans).strip()
            # Skip problematic translations
            if not da_word or "-" in da_word or " " in da_word:
                continue
            missing.append((p, headword, da_word))

print(f"Checking {len(missing)} words in Leipzig...")
# Load sentences into memory for fast search
print("Loading Leipzig sentences...")
sentences = []
with open(SENTENCES, encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split("\t", 1)
        if len(parts) >= 2 and len(parts[1]) <= 110:
            sentences.append(parts[1])

print(f"Loaded {len(sentences):,} short sentences")

found = []
not_found = []
for p, hw, da in missing:
    pat = re.compile(r'(?<![a-zA-ZæøåÆØÅ0-9])' + re.escape(da), re.IGNORECASE)
    hits = [s for s in sentences if pat.search(s)]
    if hits:
        found.append((hw, da, hits[0]))
    else:
        not_found.append((hw, da))

print(f"\nFound in Leipzig: {len(found)}")
for hw, da, ex in found[:10]:
    print(f"  {hw:20s} -> {da}: {ex[:60]}")

print(f"\nNot found: {len(not_found)}")
for hw, da in not_found:
    print(f"  {hw:20s} -> {da}")
