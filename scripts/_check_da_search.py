import pandas as pd, re
from pathlib import Path

df = pd.read_parquet('data/tatoeba_da_en_pairs.parquet')
EN_DA_DIR = Path('entries/en-da')

def has_real_examples(path):
    txt = path.read_text(encoding='utf-8')
    ex_m = re.search(r'examples:(.*?)(?:\n```)', txt, re.DOTALL)
    if not ex_m: return False
    block = ex_m.group(1)
    da_items = [x.strip() for x in re.findall(r'danish:\s*(.+)', block)]
    return any(x and x not in ['TODO','SKIP'] for x in da_items)

missing = []
for p in sorted(EN_DA_DIR.glob('*.md')):
    if not has_real_examples(p):
        txt = p.read_text(encoding='utf-8')
        hw = re.search(r'^headword:\s*(.+)', txt, re.MULTILINE)
        pt = re.search(r'^primary_translation:\s*(.+)', txt, re.MULTILINE)
        if hw and pt:
            headword = hw.group(1).strip()
            trans = pt.group(1).strip()
            da_word = re.sub(r'\s*[(][^)]+[)]$', '', trans).strip()
            missing.append((p, headword, da_word))

found = []
not_found = []
for p, hw, da in missing:
    pat = re.compile(r'(?<![a-zA-Z\xe6\xf8\xe5\xc6\xd8\xc50-9])' + re.escape(da), re.IGNORECASE)
    mask = df['text_da'].str.contains(pat, regex=True, na=False)
    if mask.any():
        found.append(hw)
    else:
        not_found.append((hw, da))

print(f'Found via DA translation: {len(found)}')
print('Not found:')
for hw, da in not_found:
    print(f'  {hw:20s} -> {da}')
