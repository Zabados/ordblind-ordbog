import sys, re
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

def rf(t, f): m=re.search(rf'^{re.escape(f)}:\s*(.+)$', t, re.M); return m.group(1).strip() if m else ''
def sf(t, f, v): return re.sub(rf'^{re.escape(f)}:.*$', f'{f}: {v}', t, flags=re.M)
def set_block(t, block):
    if re.search(r'^inflections: TODO$', t, re.M):
        return re.sub(r'^inflections: TODO$', block, t, flags=re.M)
    return re.sub(r'^inflections:\s*\n(?:  \S[^\n]*\n?)*', block+'\n', t, flags=re.M)

fixes = {
    'absolut':   ('SKIP', 'inflections:\n  base: absolut\n  neuter: absolut\n  plural: absolutte\n  comparative: mere absolut\n  superlative: mest absolut'),
    'høj':       ('SKIP', 'inflections:\n  base: høj\n  neuter: højt\n  plural: høje\n  comparative: højere\n  superlative: højest'),
    'konkret':   ('SKIP', 'inflections:\n  base: konkret\n  neuter: konkret\n  plural: konkrete\n  comparative: mere konkret\n  superlative: mest konkret'),
    'massiv':    ('SKIP', 'inflections:\n  base: massiv\n  neuter: massivt\n  plural: massive\n  comparative: mere massiv\n  superlative: massivest'),
    'permanent': ('SKIP', 'inflections:\n  base: permanent\n  neuter: permanent\n  plural: permanente\n  comparative: mere permanent\n  superlative: mest permanent'),
    'min':       ('SKIP', 'inflections:\n  base: min\n  neuter: mit\n  plural: mine\n  comparative: SKIP\n  superlative: SKIP'),
    'flere':     ('SKIP', 'SKIP'),
    'intet':     ('et',   'SKIP'),
    'driv':      ('SKIP', None),
    'få':        ('et',   None),
    'love':      ('SKIP', None),
    'tide':      ('SKIP', None),
}

for f in sorted(Path('entries/da-en').glob('*.md')):
    t = f.read_text(encoding='utf-8')
    hw = rf(t, 'headword')
    if hw not in fixes:
        continue
    gender_fix, infl_fix = fixes[hw]
    changed = False

    if rf(t, 'gender') == 'TODO' and gender_fix:
        t = sf(t, 'gender', gender_fix)
        changed = True

    if infl_fix is not None:
        if infl_fix == 'SKIP':
            t = set_block(t, 'inflections: SKIP')
        else:
            t = set_block(t, infl_fix)
        changed = True

    if changed:
        f.write_text(t, encoding='utf-8')
        g = rf(t, 'gender')
        infl_line = re.search(r'^inflections:.*$', t, re.M)
        infl_show = infl_line.group(0) if infl_line else '?'
        print(f'Fixed {hw}: gender={g}, {infl_show}')
