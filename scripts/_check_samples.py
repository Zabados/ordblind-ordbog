from pathlib import Path
import re

def field(c, n):
    m = re.search(rf'^\s*{re.escape(n)}:\s*(.+)$', c, re.MULTILINE)
    return m.group(1).strip() if m else ''

for w in ['dag', 'komme', 'mand', 'barn', 'gift', 'chef', 'se', 'sige', 'stor', 'god']:
    path = Path(f'entries/da-en/da-{w}-001.md')
    if not path.exists():
        print(f'{w}: MISSING'); continue
    c = path.read_text(encoding='utf-8')
    ipa  = field(c, 'ipa')
    phon = field(c, 'phonetic_plain')
    syl  = field(c, 'syllables')
    tier = field(c, 'frequency_tier')
    pos  = field(c, 'pos')
    gen  = field(c, 'gender')
    pt   = field(c, 'flag_pronunciation_trap')
    ff   = field(c, 'flag_false_friend')
    ff_note = field(c, 'flag_false_friend_note')
    ex_da = re.findall(r'danish:\s*(.+)', c)
    ex_en = re.findall(r'english:\s*(.+)', c)
    trans = field(c, 'primary_translation')
    sec   = re.findall(r'^\s+-\s+(.+)$', c[c.find('secondary_translations'):c.find('examples')], re.MULTILINE)
    sec   = [s for s in sec if s not in ('TODO','SKIP')][:2]
    print(f'{w}: pos={pos} gen={gen} ipa={ipa} phon={phon} syl={syl} tier={tier} pt={pt} ff={ff}')
    print(f'  trans={trans}  sec={sec}')
    print(f'  ff_note={ff_note}')
    if ex_da:
        print(f'  ex: {ex_da[0]} | {ex_en[0] if ex_en else ""}')
    print()
