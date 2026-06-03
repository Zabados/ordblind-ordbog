import glob, re

results = []
for path in sorted(glob.glob('entries/da-en/*.md')):
    content = open(path, encoding='utf-8').read()
    word = re.search(r'headword: (.+)', content)
    has_pos = 'pos: TODO' not in content
    has_trans = 'primary_translation: TODO' not in content
    has_ex = 'danish: TODO' not in content
    todos = content.count('TODO')
    results.append((word.group(1).strip() if word else '?', has_pos, has_trans, has_ex, todos))

print('Word                 POS  Trans  Examples  TODOs')
print('-' * 50)
for w, p, t, e, n in results:
    pos_s = 'Y' if p else '-'
    trans_s = 'Y' if t else '-'
    ex_s = 'Y' if e else '-'
    print('{:<20} {}    {}      {}         {}'.format(w, pos_s, trans_s, ex_s, n))

good = sum(1 for _, p, t, e, _ in results if t)
print('\n{}/50 have a translation'.format(good))
