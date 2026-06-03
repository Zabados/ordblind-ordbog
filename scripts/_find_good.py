import glob, re
from pathlib import Path

def get(content, field):
    m = re.search(rf'^{re.escape(field)}:\s*(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else ''

for f in sorted(glob.glob('entries/da-en/*.md')):
    c = Path(f).read_text(encoding='utf-8')
    ff = get(c, 'flag_false_friend')
    if ff == 'true':
        hw = get(c, 'headword')
        trans = get(c, 'primary_translation')
        ipa = get(c, 'ipa')
        rank = get(c, 'frequency_rank')
        note = get(c, 'flag_false_friend_note')
        print(f'{rank:6}  {hw:18}  {trans:25}  {note[:70]}')
