"""Remove ## MEMORY HOOK [MANUAL] sections from all DA->EN entries."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DA_EN_DIR = ROOT / "entries" / "da-en"

# The section always looks like:
# \n---\n\n## MEMORY HOOK [MANUAL]\n\n```\n```\n
PATTERN = re.compile(r'\n---\n\n## MEMORY HOOK \[MANUAL\]\n\n```\n```\n')

changed = 0
for path in DA_EN_DIR.glob("*.md"):
    txt = path.read_text(encoding="utf-8")
    new = PATTERN.sub("\n", txt)
    if new != txt:
        path.write_text(new, encoding="utf-8")
        changed += 1

print(f"Removed memory hook from {changed} entries")
