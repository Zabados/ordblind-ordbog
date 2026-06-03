from pathlib import Path
path = Path('entries/en-da/en-indian-001.md')
txt = path.read_text(encoding='utf-8')
import re
m = re.search(r'examples:.*', txt, re.DOTALL)
if m: print(repr(m.group(0)[:400]))
