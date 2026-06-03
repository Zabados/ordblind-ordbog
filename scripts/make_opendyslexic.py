"""
make_opendyslexic.py
--------------------
Creates dictionary_opendyslexic.html from the already-rendered dictionary.html
by swapping the font to OpenDyslexic.

Usage:
    python scripts/make_opendyslexic.py
"""

from pathlib import Path

SRC  = Path("dictionary.html")
DEST = Path("dictionary_opendyslexic.html")

OLD_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap');"
NEW_IMPORT = "@import url('https://fonts.cdnfonts.com/css/opendyslexic');"

OLD_FONT = "font-family: 'Atkinson Hyperlegible', Arial, sans-serif;"
NEW_FONT = "font-family: 'OpenDyslexic', Arial, sans-serif;"

if not SRC.exists():
    print(f"ERROR: {SRC} not found. Run render_sample.py --full first.")
    raise SystemExit(1)

html = SRC.read_text(encoding="utf-8")
html = html.replace(OLD_IMPORT, NEW_IMPORT)
html = html.replace(OLD_FONT, NEW_FONT)
DEST.write_text(html, encoding="utf-8")
print(f"Written: {DEST}  ({DEST.stat().st_size // 1024} KB)")

import webbrowser
webbrowser.open(DEST.resolve().as_uri())
print("Opened in browser.")
