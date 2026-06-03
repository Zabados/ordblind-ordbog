"""
font_comparison.py
------------------
Renders the same three dictionary entries in 7 different fonts
to a single HTML file for side-by-side visual comparison.

Usage:
    python scripts/font_comparison.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_sample import load_all, entry_html, CSS

OUT = Path("font_comparison.html")

FONTS = [
    {
        "name":   "Atkinson Hyperlegible",
        "note":   "Current font — Braille Institute",
        "import": "@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap');",
        "family": "'Atkinson Hyperlegible', Arial, sans-serif",
    },
    {
        "name":   "OpenDyslexic",
        "note":   "Heavy weighted bottoms",
        "import": "@import url('https://fonts.cdnfonts.com/css/opendyslexic');",
        "family": "'OpenDyslexic', Arial, sans-serif",
    },
    {
        "name":   "Lexie Readable",
        "note":   "Softer alternative to OpenDyslexic",
        "import": "@import url('https://fonts.cdnfonts.com/css/lexie-readable');",
        "family": "'Lexie Readable', Arial, sans-serif",
    },
    {
        "name":   "Verdana",
        "note":   "BDA-recommended — wide letterforms",
        "import": "",
        "family": "Verdana, Geneva, sans-serif",
    },
    {
        "name":   "Arial",
        "note":   "BDA standard recommendation",
        "import": "",
        "family": "Arial, Helvetica, sans-serif",
    },
    {
        "name":   "Century Gothic",
        "note":   "Open counters — research-backed",
        "import": "",
        "family": "'Century Gothic', 'Trebuchet MS', sans-serif",
    },
    {
        "name":   "Comic Sans MS",
        "note":   "Effective in studies — distinct letterforms",
        "import": "",
        "family": "'Comic Sans MS', cursive, sans-serif",
    },
]

# Pick 3 good sample entries: one noun, one verb, one with pronunciation trap
SAMPLE_WORDS = ["arbejde", "dag", "grøn"]

def build_html(entries: list) -> str:
    # Pick sample entries
    by_word = {e["headword"]: e for e in entries}
    samples = [by_word[w] for w in SAMPLE_WORDS if w in by_word]
    if not samples:
        # Fallback: top-scored entries
        samples = sorted(entries, key=lambda e: -e["_score"])[:3]

    cards_html = "\n".join(entry_html(e) for e in samples)

    # Build font sections
    all_imports = "\n".join(f["import"] for f in FONTS if f["import"])

    sections = []
    for font in FONTS:
        sections.append(f"""
<section class="font-section">
  <div class="font-label">
    <span class="font-name">{font["name"]}</span>
    <span class="font-note">{font["note"]}</span>
  </div>
  <div class="font-preview" style="font-family: {font["family"]}">
    {cards_html}
  </div>
</section>""")

    sections_html = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ordbog — Font Comparison</title>
<style>
{all_imports}

{CSS}

/* ── Comparison page chrome ── */
body {{
  background: #C8C0B5;
  padding: 12mm 0;
}}

.comparison-header {{
  width: 210mm;
  margin: 0 auto 8mm;
  font-family: Arial, sans-serif;
  font-size: 13pt;
  font-weight: 700;
  color: #2C2416;
  padding: 0 4mm;
}}
.comparison-header p {{
  font-size: 9pt;
  font-weight: 400;
  margin-top: 2mm;
  color: #5A4A38;
}}

.font-section {{
  width: 210mm;
  margin: 0 auto 14mm;
}}

.font-label {{
  background: #2C2416;
  color: #FAF6F0;
  padding: 3mm 6mm;
  display: flex;
  align-items: baseline;
  gap: 6mm;
}}
.font-name {{
  font-family: Arial, sans-serif;
  font-size: 11pt;
  font-weight: 700;
}}
.font-note {{
  font-family: Arial, sans-serif;
  font-size: 8.5pt;
  opacity: 0.75;
}}

.font-preview {{
  background: var(--cream);
  padding: 6mm 8mm;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}}

/* Override page shell — entries render inline here, not as A4 pages */
.font-preview .page {{
  display: none;
}}
.font-preview .entry {{
  border-bottom: 1px solid var(--rule);
  padding: 4mm 0;
}}
.font-preview .entry:last-child {{
  border-bottom: none;
}}
</style>
</head>
<body>
<div class="comparison-header">
  Ordbog — Font Comparison
  <p>Same three entries (arbejde, dag, grøn) rendered in each font. Scroll to compare.</p>
</div>
{sections_html}
</body>
</html>"""


def main():
    print("Loading entries…")
    entries = load_all()
    print(f"  {len(entries)} loaded")

    html = build_html(entries)
    OUT.write_text(html, encoding="utf-8")
    print(f"Written: {OUT}  ({OUT.stat().st_size // 1024} KB)")

    import webbrowser
    webbrowser.open(OUT.resolve().as_uri())
    print("Opened in browser.")


if __name__ == "__main__":
    main()
