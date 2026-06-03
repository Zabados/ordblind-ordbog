#!/usr/bin/env python3
"""
render_sample.py  —  Generate beautiful A4 dictionary pages as HTML.

Usage:
    python scripts/render_sample.py              # 5 sample pages (best ~55 entries)
    python scripts/render_sample.py --count 60   # more entries in sample
    python scripts/render_sample.py --open        # open in browser after
    python scripts/render_sample.py --full        # render all 1,710 entries → dictionary.html
    python scripts/render_sample.py --full --open
"""

import argparse
import re
from html import escape as esc
from pathlib import Path

ROOT        = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "entries" / "da-en"
OUT_SAMPLE  = ROOT / "sample_pages.html"
OUT_FULL    = ROOT / "dictionary.html"


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------

def _field(content: str, name: str) -> str:
    m = re.search(rf'^\s*{re.escape(name)}:\s*(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _list_field(content: str, name: str) -> list:
    m = re.search(rf'^{re.escape(name)}:\n((?:[ \t]+-[^\n]+\n?)+)', content, re.MULTILINE)
    if not m:
        return []
    return [
        re.sub(r'^\s*-\s*', '', ln).strip()
        for ln in m.group(1).splitlines()
        if ln.strip().startswith('-')
    ]


def _parse_secondary(content: str) -> list:
    """Parse secondary_translations into [{english, sense}] dicts.

    Supports two formats:
      - plain string:          ``- to carry``
      - with sense label:      ``- to bear | carry a load``
    """
    skip = {"TODO", "SKIP", ""}
    result = []
    for item in _list_field(content, "secondary_translations"):
        if item in skip:
            continue
        if " | " in item:
            english, sense = item.split(" | ", 1)
            result.append({"english": english.strip(), "sense": sense.strip()})
        else:
            result.append({"english": item, "sense": None})
    return result


def _examples(content: str) -> list:
    m = re.search(r'examples:\n(.*?)(?:\n```|\Z)', content, re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    da_items = re.findall(r'danish:\s*(.+)', block)
    en_items = re.findall(r'english:\s*(.+)', block)
    result = []
    for d, e in zip(da_items, en_items):
        d, e = d.strip(), e.strip()
        if not d:
            continue
        # english: SKIP means DA-only example (no translation provided)
        en = "" if e in {"SKIP", "TODO", ""} else e
        result.append({"da": d, "en": en})
    return result[:2]


def parse_entry(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    f = lambda n: _field(content, n)
    skip = {"TODO", "SKIP", ""}
    return {
        "headword":  f("headword"),
        "pos":       f("pos"),
        "gender":    f("gender"),
        "ipa":       f("ipa"),
        "phonetic":  f("phonetic_plain"),
        "syllables": f("syllables"),
        "primary":   f("primary_translation"),
        "secondary": _parse_secondary(content),
        "examples":  _examples(content),
        "tags":      [t for t in _list_field(content, "tags") if t not in skip],
        "tier":      f("frequency_tier"),
        "rank":      f("frequency_rank"),
        "ff":        f("flag_false_friend") == "true",
        "ff_note":   f("flag_false_friend_note"),
        "pt":        f("flag_pronunciation_trap") == "true",
    }


def load_all() -> list:
    entries = []
    for path in sorted(ENTRIES_DIR.glob("*.md")):
        try:
            e = parse_entry(path)
        except Exception:
            continue
        if not e["headword"]:
            continue
        score = (
            3 * bool(e["primary"]   not in {"", "TODO"}) +
            2 * bool(e["ipa"]       not in {"", "TODO"}) +
            3 * bool(e["examples"]) +
            1 * bool(e["phonetic"]  not in {"", "TODO"}) +
            1 * bool(e["syllables"] not in {"", "TODO"}) +
            1 * bool(e["tags"]) +
            5 * e["ff"]
        )
        e["_score"] = score
        entries.append(e)
    return entries


def select_entries(all_entries: list, count: int = 55, words: list = None) -> list:
    if words:
        wanted = {w.lower() for w in words}
        keep = [e for e in all_entries if e["headword"].lower() in wanted]
        seen = {e["headword"].lower() for e in keep}
        rest = sorted(
            [e for e in all_entries if e["headword"].lower() not in seen],
            key=lambda e: (-e["_score"], int(e["rank"]) if e["rank"].isdigit() else 9999),
        )
        for e in rest:
            if len(keep) >= count:
                break
            keep.append(e)
            seen.add(e["headword"].lower())
    else:
        keep, seen = [], set()
        for e in sorted(
            all_entries,
            key=lambda e: (-e["_score"], int(e["rank"]) if e["rank"].isdigit() else 9999),
        ):
            if e["headword"].lower() in seen:
                continue
            seen.add(e["headword"].lower())
            keep.append(e)
            if len(keep) >= count:
                break
    return sorted(keep, key=lambda e: danish_sort_key(e["headword"]))


def danish_sort_key(word: str) -> str:
    """Alphabetical sort that places ae, oe, aa (Danish special chars) after z."""
    _map = {"ae": "\x7bzz", "ae": "\x7bzz",
            "ae": "\x7bzz", "ae": "\x7bzz",
            "\xe6": "\x7bzz", "\xf8": "\x7czz", "\xe5": "\x7dzz",
            "\xc6": "\x7bzz", "\xd8": "\x7czz", "\xc5": "\x7dzz"}
    return "".join(_map.get(c, c.lower()) for c in word)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """\


*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --cream:          #FAF6F0;
  --text:           #2C2416;
  --text-light:     #6E5840;
  --rule:           #DDD4C8;
  --en-color:       #0072B2;
  --en-bg:          #E0EEF8;
  --et-color:       #56B4E9;
  --et-bg:          #E8F6FD;
  --verb-color:     #D55E00;
  --verb-bg:        #FBE9E0;
  --adj-color:      #009E73;
  --adj-bg:         #E0F5EE;
  --adv-color:      #CC79A7;
  --adv-bg:         #F8EAF3;
  --other-color:    #666666;
  --other-bg:       #EEEEEE;
  --phonetic-bg:    #FFF3E0;
  --phonetic-color: #7A4000;
  --example-bg:     #F0ECE6;
  --ff-bg:          #FFF8E0;
  --ff-border:      #D4A000;
  --ff-text:        #6B4400;
  --pt-bg:          #FFF0E4;
  --pt-color:       #8B4200;
  --tag-bg:         #E4EDFF;
  --tag-color:      #1A3D7A;
}

body {
  font-family: Verdana, Geneva, sans-serif;
  background: #DDD5CA;
  color: var(--text);
  font-size: 10.5pt;
  line-height: 1.45;
}

/* =========================================================
   A4 PAGE SHELL
   ========================================================= */

.page {
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  background: var(--cream);
  margin: 10mm auto;
  box-shadow: 0 6px 30px rgba(0,0,0,0.30), -2px 0 8px rgba(0,0,0,0.08);
  position: relative;
  display: flex;
  flex-direction: column;
}
.alpha-strip {
  position: absolute;
  right: 0;
  top: 14mm;
  bottom: 11mm;
  width: 10mm;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  z-index: 10;
}
.alpha-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8pt;
  font-weight: 700;
  color: #888;
  text-transform: uppercase;
  line-height: 1;
  user-select: none;
}
.alpha-active {
  flex: 1.33;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: var(--en-color);
  font-size: 8pt;
  font-weight: 700;
}
/* Verso: strip moves to left spine */
.page.verso .alpha-strip {
  right: auto;
  left: 0;
}

/* =========================================================
   PAGE HEADER / FOOTER
   ========================================================= */

.page-header {
  padding: 6mm 18mm 4mm 16mm;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1.5pt solid var(--en-color);
  flex-shrink: 0;
}
.book-title   { font-size: 8pt; font-weight: 700; color: var(--en-color); text-transform: uppercase; letter-spacing: 1.5px; }
.running-head { font-size: 8pt; color: var(--text-light); font-style: italic; }
.page-num     { font-size: 8pt; font-weight: 700; color: var(--text-light); min-width: 5mm; text-align: right; }

.page-footer {
  padding: 2.5mm 18mm 5mm 16mm;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 0.5pt solid var(--rule);
  flex-shrink: 0;
}
.footer-left  { font-size: 7pt; color: #B0A090; font-style: italic; }
.footer-right { font-size: 7pt; font-weight: 700; color: var(--en-color); letter-spacing: 1px; }
.footer-legend { display: flex; gap: 3pt; align-items: center; }
.footer-legend span { font-size: 6pt; font-weight: 700; padding: 1pt 3.5pt; border-radius: 2pt; }
.lc-en    { color: var(--en-color);    background: var(--en-bg); }
.lc-et    { color: var(--et-color);    background: var(--et-bg); }
.lc-verb  { color: var(--verb-color);  background: var(--verb-bg); }
.lc-adj   { color: var(--adj-color);   background: var(--adj-bg); }
.lc-adv   { color: var(--adv-color);   background: var(--adv-bg); }
.lc-other { color: var(--other-color); background: var(--other-bg); }

/* =========================================================
   PAGE BODY
   ========================================================= */

.page-body {
  flex: 1;
  overflow: hidden;
  padding: 4mm 18mm 4mm 16mm;
  display: flex;
  gap: 6mm;
}
.page-col {
  flex: 1;
  overflow: hidden;
  border-right: 0.5pt solid var(--rule);
  padding-right: 3mm;
}
.page-col:last-child {
  border-right: none;
  padding-right: 0;
}

/* =========================================================
   LETTER DIVIDER
   ========================================================= */

.letter-div {
  break-inside: avoid;
  display: flex;
  align-items: center;
  gap: 2.5mm;
  margin: 4mm 0 2mm;
}
.letter-div:first-child { margin-top: 0; }
.letter-char {
  font-size: 20pt;
  font-weight: 700;
  color: var(--en-color);
  opacity: 0.28;
  line-height: 1;
  min-width: 8mm;
}
.letter-div::after {
  content: '';
  flex: 1;
  height: 0.75pt;
  background: var(--en-color);
  opacity: 0.20;
}

/* =========================================================
   ENTRY CARD
   ========================================================= */

.entry {
  break-inside: avoid;
  page-break-inside: avoid;
  margin-bottom: 5mm;
  padding: 2.5mm 2.5mm 2.5mm 3mm;
  border-left: 2.5pt solid var(--rule);
  background: var(--cream);
}
.entry-noun      { border-left-color: var(--en-color); }
.entry-verb      { border-left-color: var(--verb-color); }
.entry-adjective { border-left-color: var(--adj-color); }
.entry-adverb    { border-left-color: var(--adv-color); }
.entry-other     { border-left-color: var(--other-color); }
.entry-ff        { border-left-color: var(--ff-border); background: var(--ff-bg); }

.entry-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 1.2mm;
  margin-bottom: 1mm;
}
.headword { font-size: 13pt; font-weight: 700; line-height: 1.1; margin-right: 0.5mm; }

.badge {
  font-size: 6pt;
  font-weight: 700;
  padding: 0.4mm 1.5mm;
  border-radius: 2pt;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  white-space: nowrap;
  line-height: 1.4;
}
.badge-en           { background: var(--en-bg);   color: var(--en-color); }
.badge-et           { background: var(--et-bg);   color: var(--et-color); }
.badge-pos          { background: #EDE8E2; color: #665544; }
.badge-tier-core    { background: #D6EDD6; color: #1A5C1A; }
.badge-tier-common  { background: #D6E6F5; color: #1A4070; }
.badge-tier-general { background: #FFF0C8; color: #7A5000; }
.badge-tier-rare    { background: #EEEEEE; color: #888888; }

.pron-line { font-size: 8pt; color: var(--text-light); margin-bottom: 1.5mm; line-height: 1.3; }
.ipa       { font-style: italic; color: #9A8878; }
.phonetic  {
  display: inline-block;
  background: var(--phonetic-bg);
  color: var(--phonetic-color);
  padding: 0 1.5mm;
  border-radius: 2pt;
  font-weight: 700;
  font-size: 7.5pt;
  letter-spacing: 0.5px;
}
.syllables { color: #B8A898; font-size: 7.5pt; }
.dot       { color: #CCC; margin: 0 0.3mm; }

.primary-trans   { font-size: 11pt; font-weight: 700; color: var(--text); margin-bottom: 0.5mm; }
.secondary-trans { font-size: 8pt; color: var(--text-light); margin-bottom: 1mm; }
.senses { margin-bottom: 1mm; }
.sense { font-size: 8.5pt; line-height: 1.5; }
.sense-label { color: var(--text-light); font-style: italic; font-size: 7.5pt; }
.sense-da { font-weight: 600; }

.ff-banner {
  font-size: 7.5pt;
  background: var(--ff-bg);
  border: 0.75pt solid var(--ff-border);
  border-radius: 2pt;
  padding: 1mm 2mm;
  color: var(--ff-text);
  margin: 1.5mm 0;
  line-height: 1.4;
}
.ff-icon { font-size: 8.5pt; }

.pt-flag {
  font-size: 7pt;
  color: var(--pt-color);
  background: var(--pt-bg);
  border-radius: 2pt;
  padding: 0.5mm 1.5mm;
  margin: 1mm 0;
  display: inline-block;
}

.examples {
  margin: 1.5mm 0 1mm;
  background: var(--example-bg);
  border-radius: 2pt;
  padding: 1.5mm 2mm;
}
.example + .example {
  border-top: 0.5pt solid var(--rule);
  margin-top: 1.5mm;
  padding-top: 1.5mm;
}
.ex-da { font-size: 8.5pt; font-weight: 700; color: var(--text); }
.ex-en { font-size: 8pt;   font-style: italic; color: var(--text-light); }

.tags { margin-top: 1mm; display: flex; flex-wrap: wrap; gap: 1mm; }
.tag  {
  font-size: 6pt;
  background: var(--tag-bg);
  color: var(--tag-color);
  padding: 0.25mm 1.5mm;
  border-radius: 2pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* =========================================================
   INTRO PAGES — shared
   ========================================================= */

.intro-heading {
  font-size: 16pt;
  font-weight: 700;
  color: var(--en-color);
  margin-bottom: 3mm;
  padding-bottom: 1.5mm;
  border-bottom: 0.75pt solid var(--en-color);
}
.intro-subheading {
  font-size: 9pt;
  font-weight: 700;
  color: var(--text);
  margin: 3.5mm 0 1.5mm;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.intro-text {
  font-size: 8.5pt;
  color: var(--text-light);
  margin-bottom: 2mm;
  line-height: 1.5;
}
.intro-colofon {
  margin-top: 6mm;
  border-top: 0.5pt solid var(--rule);
  padding-top: 3mm;
}
.colofon-line {
  display: flex;
  gap: 4mm;
  font-size: 7.5pt;
  line-height: 1.8;
  color: var(--text-light);
}
.colofon-label {
  min-width: 22mm;
  font-weight: 700;
  color: var(--text);
}
.colofon-value {}
.draft-placeholder {
  color: #aaa;
  font-style: italic;
}

/* =========================================================
   TITLE PAGE
   ========================================================= */

.title-page { justify-content: space-between; }

.title-band {
  background: var(--en-color);
  padding: 6mm 16mm;
}
.title-band-text {
  font-size: 7.5pt;
  font-weight: 700;
  color: rgba(255,255,255,0.85);
  letter-spacing: 2px;
  text-transform: uppercase;
}

.title-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 20mm;
  text-align: center;
}
.title-word {
  font-size: 68pt;
  font-weight: 700;
  color: var(--en-color);
  line-height: 1;
  letter-spacing: -2px;
  margin-bottom: 4mm;
}
.title-rule {
  width: 60mm;
  height: 1.5pt;
  background: var(--en-color);
  opacity: 0.35;
  margin: 0 auto 5mm;
}
.title-subtitle { font-size: 18pt; font-weight: 400; color: var(--text); margin-bottom: 4mm; }
.title-desc     { font-size: 11pt; color: var(--text-light); line-height: 1.7; }

.title-swatches { padding: 6mm 16mm 8mm; }
.swatch-grid    { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3mm; }
.swatch {
  display: flex;
  align-items: center;
  gap: 3mm;
  padding: 3mm 4mm;
  border-radius: 3pt;
  border-left: 3pt solid;
}
.swatch-en    { background: var(--en-bg);    border-color: var(--en-color); }
.swatch-et    { background: var(--et-bg);    border-color: var(--et-color); }
.swatch-verb  { background: var(--verb-bg);  border-color: var(--verb-color); }
.swatch-adj   { background: var(--adj-bg);   border-color: var(--adj-color); }
.swatch-adv   { background: var(--adv-bg);   border-color: var(--adv-color); }
.swatch-other { background: var(--other-bg); border-color: var(--other-color); }
.swatch-badge { font-size: 9pt; font-weight: 700; min-width: 14mm; }
.swatch-en    .swatch-badge { color: var(--en-color);    }
.swatch-et    .swatch-badge { color: var(--et-color);    }
.swatch-verb  .swatch-badge { color: var(--verb-color);  }
.swatch-adj   .swatch-badge { color: var(--adj-color);   }
.swatch-adv   .swatch-badge { color: var(--adv-color);   }
.swatch-other .swatch-badge { color: var(--other-color); }
.swatch-info { flex: 1; }
.swatch-name { font-size: 8.5pt; font-weight: 700; color: var(--text); }
.swatch-eg   { font-size: 7.5pt; color: var(--text-light); font-style: italic; }

.title-footer-area {
  padding: 4mm 16mm 7mm;
  display: flex;
  flex-direction: column;
  gap: 1.5mm;
  border-top: 0.5pt solid var(--rule);
}
.title-count { font-size: 8pt; font-weight: 700; color: var(--text-light); }
.title-attr  { font-size: 7.5pt; color: #B0A090; font-style: italic; }

/* =========================================================
   HOW-TO PAGE
   ========================================================= */

.page-intro .page-body { display: block; }
.how-to-page .page-body { display: block; }

.demo-box {
  border: 1pt solid var(--rule);
  border-radius: 4pt;
  padding: 3mm;
  background: #F4F0EA;
  margin: 2mm 0 3mm;
}
.demo-box .entry { margin-bottom: 0; }
.demo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; margin: 2mm 0 3mm; }

.legend-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 8.5pt;
  margin-bottom: 4mm;
}
.legend-table tr + tr td { border-top: 0.5pt solid var(--rule); }
.legend-table td { padding: 1.5mm 2mm; vertical-align: middle; }
.legend-table .legend-element { width: 32%; white-space: nowrap; }

/* =========================================================
   SYMBOL KEY PAGE
   ========================================================= */

.key-page .page-body { display: block; }

.key-row {
  display: flex;
  align-items: center;
  gap: 3mm;
  padding: 1.5mm 0;
  border-bottom: 0.5pt solid var(--rule);
  font-size: 8.5pt;
}
.key-visual { min-width: 32mm; }
.key-desc   { color: var(--text); flex: 1; line-height: 1.4; }
.key-desc em { color: var(--text-light); }
.key-eg {
  font-size: 7.5pt;
  font-style: italic;
  color: var(--text-light);
  margin: 0.5mm 0 1.5mm 35mm;
}
.tag-cloud  { display: flex; flex-wrap: wrap; gap: 1.5mm; margin-top: 1.5mm; }

/* =========================================================
   PRONUNCIATION PAGE
   ========================================================= */

.pron-page .page-body { display: block; columns: 2; }

.pron-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 7.5pt;
  margin: 1.5mm 0 3mm;
}
.pron-table th {
  font-size: 6.5pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-light);
  border-bottom: 0.75pt solid var(--en-color);
  padding: 1mm 1.5mm;
  text-align: left;
}
.pron-table td       { padding: 1mm 1.5mm; border-bottom: 0.5pt solid var(--rule); vertical-align: middle; }
.pron-table .col-ipa { font-style: italic; color: #9A8878; }
.pron-table .col-code {
  background: var(--phonetic-bg);
  color: var(--phonetic-color);
  font-weight: 700;
  font-size: 7pt;
  padding: 0.3mm 1.5mm;
  border-radius: 2pt;
  white-space: nowrap;
}
.pron-table .col-ex   { font-weight: 700; }
.pron-table .col-gl   { font-style: italic; color: var(--text-light); }

.pron-note {
  font-size: 7.5pt;
  background: var(--ff-bg);
  border-left: 2pt solid var(--ff-border);
  padding: 1.5mm 2.5mm;
  border-radius: 0 2pt 2pt 0;
  margin: 1.5mm 0 3mm;
  line-height: 1.5;
  break-inside: avoid;
}
.pron-note strong { color: var(--ff-text); }

/* =========================================================
   FULL DICTIONARY CONTINUOUS SECTION
   ========================================================= */

.dict-body {
  width: 210mm;
  background: var(--cream);
  margin: 10mm auto;
  box-shadow: 0 6px 30px rgba(0,0,0,0.30);
}
.dict-body-header {
  padding: 5mm 18mm 4mm 16mm;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1.5pt solid var(--en-color);
}
.dict-columns {
  padding: 4mm 18mm 10mm 16mm;
  columns: 2;
  column-gap: 6mm;
  column-rule: 0.5pt solid var(--rule);
}

/* =========================================================
   PRINT
   ========================================================= */

@media print {
  body { background: none; }
  .page {
    margin: 0;
    box-shadow: none;
    page-break-after: always;
    width: 100%;
    min-height: 0;
  }
  .page:last-child { page-break-after: auto; }
  .dict-body {
    width: 100%;
    margin: 0;
    box-shadow: none;
  }
  @page { size: A4; margin: 0; }
  .dict-body { box-shadow: none; }
}

/* DA-label shown in EN→DA entries before IPA */
.da-label { font-size: 6.5pt; color: #BBB; font-weight: 700; letter-spacing: 0.5px; margin-right: 1mm; }
/* Alpha-strip for EN→DA pages: slate-blue active colour */
.page-en-da .alpha-active { background: var(--et-color); }
"""


# ---------------------------------------------------------------------------
# Entry card HTML
# ---------------------------------------------------------------------------

def _badge(text: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{esc(text)}</span>'


def entry_html(e: dict, is_en_da: bool = False) -> str:
    pos    = e["pos"]    if e["pos"]    not in {"", "TODO", "SKIP"} else ""
    gender = e["gender"] if e["gender"] not in {"", "TODO", "SKIP"} else ""

    if e["ff"]:
        entry_cls = "entry entry-ff"
    elif pos == "noun":
        entry_cls = "entry entry-noun"
    elif pos == "verb":
        entry_cls = "entry entry-verb"
    elif pos == "adjective":
        entry_cls = "entry entry-adjective"
    elif pos == "adverb":
        entry_cls = "entry entry-adverb"
    else:
        entry_cls = "entry entry-other"

    def _gender_color() -> str:
        if gender == "en":     return "#0072B2"
        if gender == "et":     return "#56B4E9"
        if pos == "noun":      return "#2C2416"   # noun, gender unknown → dark
        if pos == "verb":      return "#D55E00"
        if pos == "adjective": return "#009E73"
        if pos == "adverb":    return "#CC79A7"
        return "#666666"

    if is_en_da:
        hw_color = "#2C2416"       # English headword: always dark
        tr_color = _gender_color() # Danish translation: gender/pos colour
    else:
        hw_color = _gender_color() # Danish headword: gender/pos colour
        tr_color = "#2C2416"

    badges = []
    if gender in ("en", "et"):
        badges.append(_badge(gender, "badge-en" if gender == "en" else "badge-et"))
    if pos:
        badges.append(_badge(pos, "badge-pos"))
    tier = e.get("tier", "")
    if tier and tier not in {"", "TODO", "SKIP"}:
        badges.append(_badge(tier, f"badge-tier-{tier}"))

    pron_parts = []
    if e["ipa"] not in {"", "TODO", "SKIP"}:
        pron_parts.append(f'<span class="ipa">{esc(e["ipa"])}</span>')
    if e["phonetic"] not in {"", "TODO", "SKIP"}:
        pron_parts.append(f'<span class="phonetic">{esc(e["phonetic"])}</span>')
    if e["syllables"] not in {"", "TODO", "SKIP"} and e["syllables"] != e["headword"]:
        pron_parts.append(f'<span class="syllables">{esc(e["syllables"])}</span>')
    pron_html = ""
    if pron_parts:
        joined = ' <span class="dot">\u00b7</span> '.join(pron_parts)
        if is_en_da:
            pron_html = f'<div class="pron-line"><span class="da-label">DA:</span> {joined}</div>'
        else:
            pron_html = f'<div class="pron-line">{joined}</div>'

    primary = e["primary"] if e["primary"] not in {"", "TODO", "SKIP"} else ""
    # secondary is {english, sense} dicts for DA->EN entries; plain strings for EN->DA entries
    raw_secondary = e.get("secondary", [])
    sec_display = []
    for s in raw_secondary[:3]:
        text = s["english"] if isinstance(s, dict) else s
        if text and text not in {"TODO", "SKIP"}:
            sec_display.append(text)
    trans_html = ""
    if is_en_da:
        senses = e.get("senses", [])
        has_labels = any(s.get("sense") for s in senses)
        if has_labels:
            sense_parts = []
            for s in senses[:4]:
                label = f'<span class="sense-label">({esc(s["sense"])})</span> ' if s.get("sense") else ""
                sense_parts.append(
                    f'<div class="sense">{label}'
                    f'<span class="sense-da" style="color:{tr_color}">{esc(s["da"])}</span>'
                    f'</div>'
                )
            trans_html = f'<div class="senses">{"".join(sense_parts)}</div>'
        else:
            if primary:
                trans_html += f'<div class="primary-trans" style="color:{tr_color}">{esc(primary)}</div>'
            if sec_display:
                trans_html += f'<div class="secondary-trans">also: {"; ".join(esc(s) for s in sec_display)}</div>'
    else:
        if primary:
            trans_html += f'<div class="primary-trans">{esc(primary)}</div>'
        if sec_display:
            trans_html += f'<div class="secondary-trans">also: {"; ".join(esc(s) for s in sec_display)}</div>'

    ff_html = ""
    if e["ff"]:
        note = e.get("ff_note", "")
        note = note if note and note not in {"", "TODO", "SKIP"} else ""
        note_suffix = (f" \u2014 {esc(note)}" if note else "")
        ff_html = (
            f'<div class="ff-banner">'
            f'<span class="ff-icon">\u26a0</span>'
            f' <strong>False friend</strong>'
            f'{note_suffix}'
            f'</div>'
        )

    ex_parts = []
    for ex in e.get("examples", []):
        en_line = f'<div class="ex-en">{esc(ex["en"])}</div>' if ex["en"] else ""
        ex_parts.append(
            f'<div class="example">'
            f'<div class="ex-da">{esc(ex["da"])}</div>'
            f'{en_line}'
            f'</div>'
        )
    ex_html = f'<div class="examples">{"".join(ex_parts)}</div>' if ex_parts else ""

    tags = e.get("tags", [])
    tag_html = ""
    if tags:
        pills = " ".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:3])
        tag_html = f'<div class="tags">{pills}</div>'

    return (
        f'<div class="{entry_cls}">'
        f'<div class="entry-head">'
        f'<span class="headword" style="color:{hw_color}">{esc(e["headword"])}</span>'
        f' {" ".join(badges)}'
        f'</div>'
        f'{pron_html}'
        f'{trans_html}'
        f'{ff_html}'
        f'{ex_html}'
        f'{tag_html}'
        f'</div>'
    )


def letter_divider_html(letter: str) -> str:
    return (
        f'<div class="letter-div">'
        f'<span class="letter-char">{esc(letter)}</span>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Hardcoded sample entries (real data) used on intro pages
# ---------------------------------------------------------------------------

SAMPLE_DAG = {
    "headword": "dag", "pos": "noun", "gender": "en",
    "ipa": "/da\u02d0\u02c0\u0263/", "phonetic": "DAG", "syllables": "dag",
    "primary": "day", "secondary": [],
    "examples": [{"da": "Sikke en dag!", "en": "What a day!"}],
    "tags": ["time"], "tier": "core", "rank": "198",
    "ff": False, "ff_note": "", "pt": True,
}
SAMPLE_GIFT = {
    "headword": "gift", "pos": "noun", "gender": "en",
    "ipa": "/\u0261ift/", "phonetic": "YIFT", "syllables": "gift",
    "primary": "poison", "secondary": ["venom", "married"],
    "examples": [{"da": "Er du gift?", "en": "Are you married?"}],
    "tags": [], "tier": "general", "rank": "3299",
    "ff": True, "ff_note": "Means poison (noun) or married (adj), NOT a present",
    "pt": False,
}
SAMPLE_BARN = {
    "headword": "barn", "pos": "noun", "gender": "et",
    "ipa": "/barn/", "phonetic": "BARN", "syllables": "barn",
    "primary": "child", "secondary": ["kid"],
    "examples": [{"da": "Vi venter barn.", "en": "We\u2019re expecting."}],
    "tags": ["family"], "tier": "common", "rank": "456",
    "ff": False, "ff_note": "", "pt": True,
}
SAMPLE_CHEF = {
    "headword": "chef", "pos": "noun", "gender": "en",
    "ipa": "/\u02c8sj\u025b\u02d0\u02c0f/", "phonetic": "CHEF", "syllables": "chef",
    "primary": "boss; person in charge",
    "secondary": [],
    "examples": [{"da": "Jeg er min egen chef.", "en": "I\u2019m my own boss."}],
    "tags": ["work"], "tier": "common", "rank": "1732",
    "ff": True, "ff_note": "Means boss or manager, NOT a chef/cook",
    "pt": True,
}


# ---------------------------------------------------------------------------
# Intro page 1 — Title page
# ---------------------------------------------------------------------------

def title_page_html(entry_count: int = 0) -> str:
    count_str = f"{entry_count:,}" if entry_count else "?"
    return f"""\
<div class="page title-page">
  <div class="title-band">
    <span class="title-band-text">Ordblind Ordbog &nbsp;\u00b7&nbsp; Dansk\u2013Engelsk og Engelsk\u2013Dansk &nbsp;\u00b7&nbsp; For ordblinde &nbsp;\u00b7&nbsp; B2\u2013C1 ordforr\u00e5d</span>
  </div>
  <div class="title-main-area">
    <div class="title-word">Ordblind Ordbog</div>
    <div class="title-rule"></div>
    <div class="title-subtitle">Dansk\u2013Engelsk og Engelsk\u2013Dansk</div>
    <div class="title-desc">
      For ordblinde &nbsp;\u00b7&nbsp; PD3-eksamen<br>
      B2\u2013C1 ordforr\u00e5d
    </div>
  </div>
  <div class="title-swatches">
    <div class="swatch-grid">
      <div class="swatch swatch-en">
        <div class="swatch-badge">en</div>
        <div class="swatch-info">
          <div class="swatch-name">F\u00e6lleskon &nbsp;\u00b7&nbsp; Common gender</div>
          <div class="swatch-eg">dag, mand, tid, bog, ven, vej, uge</div>
        </div>
      </div>
      <div class="swatch swatch-et">
        <div class="swatch-badge">et</div>
        <div class="swatch-info">
          <div class="swatch-name">Intetkøn &nbsp;\u00b7&nbsp; Neuter gender</div>
          <div class="swatch-eg">barn, hus, land, \u00e5r, navn, bord, liv</div>
        </div>
      </div>
      <div class="swatch swatch-verb">
        <div class="swatch-badge">verb</div>
        <div class="swatch-info">
          <div class="swatch-name">Verbum &nbsp;\u00b7&nbsp; Verb</div>
          <div class="swatch-eg">komme, se, sige, g\u00f8re, blive, tage</div>
        </div>
      </div>
      <div class="swatch swatch-adj">
        <div class="swatch-badge">adjective</div>
        <div class="swatch-info">
          <div class="swatch-name">Adjektiv &nbsp;\u00b7&nbsp; Adjective</div>
          <div class="swatch-eg">stor, god, ny, f\u00f8rste, hele, lille</div>
        </div>
      </div>
      <div class="swatch swatch-adv">
        <div class="swatch-badge">adverb</div>
        <div class="swatch-info">
          <div class="swatch-name">Adverbium &nbsp;\u00b7&nbsp; Adverb</div>
          <div class="swatch-eg">ikke, meget, altid, aldrig, her, nu</div>
        </div>
      </div>
      <div class="swatch swatch-other">
        <div class="swatch-badge">other</div>
        <div class="swatch-info">
          <div class="swatch-name">Andre ordklasser &nbsp;\u00b7&nbsp; Other</div>
          <div class="swatch-eg">pronomen, pr\u00e6position, konjunktion</div>
        </div>
      </div>
    </div>
  </div>
  <div class="title-footer-area">
    <span class="title-count">{count_str} entries &nbsp;\u00b7&nbsp; A\u2013\u00c5 &nbsp;\u00b7&nbsp; Draft edition &nbsp;\u00b7&nbsp; May 2026</span>
    <span class="title-attr">Data: English Wiktionary (CC-BY-SA) &nbsp;\u00b7&nbsp; Tatoeba sentence pairs (CC-BY 2.0) &nbsp;\u00b7&nbsp; Leipzig Corpora (CC-BY)</span>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Intro page 2 — How to read an entry
# ---------------------------------------------------------------------------

def how_to_use_html() -> str:
    demo_dag  = entry_html(SAMPLE_DAG)
    demo_gift = entry_html(SAMPLE_GIFT)
    demo_barn = entry_html(SAMPLE_BARN)
    demo_chef = entry_html(SAMPLE_CHEF)
    return f"""\
<div class="page page-intro how-to-page">
  <header class="page-header">
    <span class="book-title">Ordbog DA\u2192EN</span>
    <span class="running-head">Introduction</span>
    <span class="page-num">i</span>
  </header>
  <div class="page-body">
    <h2 class="intro-heading">How to Read an Entry</h2>
    <p class="intro-text">Every entry follows the same layout. Here is a typical noun entry:</p>
    <div class="demo-box">{demo_dag}</div>
    <table class="legend-table">
      <tr>
        <td class="legend-element"><span class="headword" style="color:#B5451B;font-size:10.5pt">dag</span></td>
        <td><strong>Headword</strong> &mdash; the Danish word, set large and bold. Colour shows gender (nouns) or part of speech.</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="badge badge-en">en</span></td>
        <td><strong>Gender</strong> &mdash; <span style="color:#B5451B">terracotta&nbsp;= common (f&aelig;lleskon)</span>; <span style="color:#1F5E9A">slate&nbsp;= neuter (intetk&oslash;n)</span>. Nouns only. Determines <em>den</em> vs <em>det</em>.</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="badge badge-pos">noun</span></td>
        <td><strong>Part of speech</strong> &mdash; noun, verb, adjective, adverb, conjunction&hellip;</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="badge badge-tier-core">core</span></td>
        <td><strong>Frequency</strong> &mdash; <span class="badge badge-tier-core">core</span> top&nbsp;500 &nbsp; <span class="badge badge-tier-common">common</span> 501&ndash;2000 &nbsp; <span class="badge badge-tier-general">general</span> 2001&ndash;5000 &nbsp; <span class="badge badge-tier-rare">rare</span> 5000+</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="ipa">/da\u02d0\u02c0\u0263/</span></td>
        <td><strong>IPA</strong> &mdash; precise phonetic transcription. Grey italic. See pronunciation guide (page&nbsp;iii).</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="phonetic">DAG</span></td>
        <td><strong>Phonetic guide</strong> &mdash; plain-English approximation in ALL&nbsp;CAPS on green. Read aloud directly. See sound key on page&nbsp;iii.</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="syllables">kom-me</span></td>
        <td><strong>Syllables</strong> &mdash; where the word breaks, e.g. <span class="syllables">kom-me</span>. Shown only for multi-syllable words.</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="primary-trans" style="font-size:9pt">day</span></td>
        <td><strong>Primary translation</strong> &mdash; main English meaning.</td>
      </tr>
      <tr>
        <td class="legend-element" style="color:#6E5840;font-size:7.5pt">also:&nbsp;&hellip;</td>
        <td><strong>Alternative translations</strong> &mdash; other senses or related meanings.</td>
      </tr>
      <tr>
        <td class="legend-element">
          <div class="examples" style="font-size:7pt;padding:0.8mm 1.5mm;margin:0">
            <div class="ex-da">Sikke en dag!</div>
            <div class="ex-en">What a day!</div>
          </div>
        </td>
        <td><strong>Example</strong> &mdash; real sentence from Tatoeba corpus (CC-BY). Danish bold; English italic below.</td>
      </tr>
      <tr>
        <td class="legend-element"><span class="tag">time</span></td>
        <td><strong>Thematic tag</strong> &mdash; for finding words by topic in the index.</td>
      </tr>
    </table>

    <p class="intro-subheading">False friends &#9888;</p>
    <p class="intro-text">Some Danish words look identical to English words but mean something completely different.
    These are flagged with an amber banner &mdash; the two most important ones to know:</p>
    <div class="demo-grid">
      <div class="demo-box">{demo_gift}</div>
      <div class="demo-box">{demo_chef}</div>
    </div>

    <p class="intro-subheading">Pronunciation trap &#128266;</p>
    <p class="intro-text">
      Entries flagged <span class="pt-flag" style="display:inline">&#128266; Pronunciation trap</span>
      contain sounds that are especially unexpected for English speakers &mdash;
      the soft-d, the st&oslash;d, or unusual vowel combinations.
      Check the IPA and the pronunciation guide on page&nbsp;iii.
    </p>
  </div>
  <footer class="page-footer">
    <span class="footer-left">Introduction</span>
    <span class="footer-right">DA &rarr; EN</span>
  </footer>
</div>"""


# ---------------------------------------------------------------------------
# Intro page 3 — Symbol and colour key
# ---------------------------------------------------------------------------

def symbol_key_html() -> str:
    all_tags = [
        "emotion", "body", "health", "food", "drink", "home", "nature", "weather",
        "work", "education", "bureaucracy", "transport", "time", "money", "social",
        "family", "culture", "politics", "environment", "technology",
    ]
    tag_pills = " ".join(f'<span class="tag">{t}</span>' for t in all_tags)
    return f"""\
<div class="page page-intro key-page">
  <header class="page-header">
    <span class="book-title">Ordbog DA&rarr;EN</span>
    <span class="running-head">Colours &amp; Symbols</span>
    <span class="page-num">ii</span>
  </header>
  <div class="page-body">
    <h2 class="intro-heading">Colours and Symbols</h2>

    <p class="intro-subheading">Gender &mdash; nouns</p>
    <div class="key-row">
      <div class="key-visual"><span class="headword" style="color:#0072B2;font-size:10.5pt">dag</span> <span class="badge badge-en">en</span></div>
      <div class="key-desc"><strong>Common gender</strong> (f&aelig;lleskon) &mdash; deep blue headword and badge.
        <em>Use <strong>den</strong> as definite article: dag<strong>en</strong>.</em></div>
    </div>
    <p class="key-eg">dag, mand, tid, bog, ven, vej, uge, skov, krig, ting, regering, k&aelig;rlighed</p>
    <div class="key-row">
      <div class="key-visual"><span class="headword" style="color:#56B4E9;font-size:10.5pt">barn</span> <span class="badge badge-et">et</span></div>
      <div class="key-desc"><strong>Neuter gender</strong> (intetk&oslash;n) &mdash; sky blue headword and badge.
        <em>Use <strong>det</strong> as definite article: barn<strong>et</strong>.</em></div>
    </div>
    <p class="key-eg">barn, hus, land, &aring;r, navn, bord, liv, svar, sp&oslash;rgsm&aring;l, omr&aring;de</p>

    <p class="intro-subheading">Parts of speech &mdash; headword colours and border</p>
    <div class="key-row">
      <div class="key-visual" style="border-left:2.5pt solid #0072B2;padding-left:2mm"><span class="headword" style="color:#0072B2;font-size:10.5pt">mand</span> <span class="badge badge-pos">noun</span></div>
      <div class="key-desc"><strong>Noun</strong> &mdash; deep blue (en) or sky blue (et) depending on gender.</div>
    </div>
    <div class="key-row">
      <div class="key-visual" style="border-left:2.5pt solid #D55E00;padding-left:2mm"><span class="headword" style="color:#D55E00;font-size:10.5pt">komme</span> <span class="badge badge-pos">verb</span></div>
      <div class="key-desc"><strong>Verb</strong> &mdash; vermillion orange.</div>
    </div>
    <div class="key-row">
      <div class="key-visual" style="border-left:2.5pt solid #009E73;padding-left:2mm"><span class="headword" style="color:#009E73;font-size:10.5pt">stor</span> <span class="badge badge-pos">adjective</span></div>
      <div class="key-desc"><strong>Adjective</strong> &mdash; teal green.</div>
    </div>
    <div class="key-row">
      <div class="key-visual" style="border-left:2.5pt solid #CC79A7;padding-left:2mm"><span class="headword" style="color:#CC79A7;font-size:10.5pt">kun</span> <span class="badge badge-pos">adverb</span></div>
      <div class="key-desc"><strong>Adverb</strong> &mdash; rose purple.</div>
    </div>
    <div class="key-row">
      <div class="key-visual" style="border-left:2.5pt solid #666666;padding-left:2mm"><span class="headword" style="color:#666666;font-size:10.5pt">og</span> <span class="badge badge-pos">conjunction</span></div>
      <div class="key-desc"><strong>Other</strong> (preposition, conjunction, phrase, interjection) &mdash; medium grey.</div>
    </div>

    <p class="intro-subheading">Frequency tiers</p>
    <div class="key-row">
      <div class="key-visual"><span class="badge badge-tier-core">core</span></div>
      <div class="key-desc"><strong>Core</strong> &mdash; top 500 most frequent words in Danish. Essential exam vocabulary.</div>
    </div>
    <div class="key-row">
      <div class="key-visual"><span class="badge badge-tier-common">common</span></div>
      <div class="key-desc"><strong>Common</strong> &mdash; ranks 501&ndash;2,000. High-frequency everyday language.</div>
    </div>
    <div class="key-row">
      <div class="key-visual"><span class="badge badge-tier-general">general</span></div>
      <div class="key-desc"><strong>General</strong> &mdash; ranks 2,001&ndash;5,000. Broad active vocabulary.</div>
    </div>
    <div class="key-row">
      <div class="key-visual"><span class="badge badge-tier-rare">rare</span></div>
      <div class="key-desc"><strong>Rare</strong> &mdash; rank 5,000+. Specialist, literary, or infrequent.</div>
    </div>

    <p class="intro-subheading">Special flags</p>
    <div class="key-row">
      <div class="key-visual">
        <div class="ff-banner" style="padding:0.5mm 1.5mm;font-size:7pt;margin:0">&#9888; <strong>False friend</strong></div>
      </div>
      <div class="key-desc"><strong>False friend</strong> &mdash; looks like an English word but has a different meaning.
        <em>gift = poison &nbsp; chef = boss &nbsp; blank = shiny &nbsp; aktuel = current</em></div>
    </div>
    <div class="key-row">
      <div class="key-visual"><span class="pt-flag" style="display:inline;font-size:7pt">&#128266; Pron. trap</span></div>
      <div class="key-desc"><strong>Pronunciation trap</strong> &mdash; sound is especially unexpected for English speakers. Check the IPA.</div>
    </div>

    <p class="intro-subheading">Thematic tags</p>
    <p class="intro-text">Tags let you find related words in the thematic index even if you cannot spell the Danish word.</p>
    <div class="tag-cloud">{tag_pills}</div>
  </div>
  <footer class="page-footer">
    <span class="footer-left">Colours &amp; Symbols</span>
    <span class="footer-right">DA &rarr; EN</span>
  </footer>
</div>"""


# ---------------------------------------------------------------------------
# Intro page 4 — Pronunciation guide
# ---------------------------------------------------------------------------

def pronunciation_guide_html() -> str:
    def row(sp, ipa_v, code, sounds, ex, gl):
        return (
            f'<tr>'
            f'<td><strong>{esc(sp)}</strong></td>'
            f'<td class="col-ipa">{esc(ipa_v)}</td>'
            f'<td><span class="col-code">{esc(code)}</span></td>'
            f'<td>{esc(sounds)}</td>'
            f'<td class="col-ex">{esc(ex)}</td>'
            f'<td class="col-gl">{esc(gl)}</td>'
            f'</tr>'
        )

    vowels = "".join([
        row("a",  "/a\u02d0/", "AH",  '"a" in father',              "dag",  "day"),
        row("e",  "/e\u02d0/", "AY",  '"a" in day',                 "se",   "see"),
        row("i",  "/i\u02d0/", "EE",  '"ee" in feet',               "vi",   "we"),
        row("o",  "/o\u02d0/", "OH",  '"o" in go',                  "stor", "large"),
        row("u",  "/u\u02d0/", "OO",  '"oo" in food',               "hus",  "house"),
        row("y",  "/y\u02d0/", "EW",  "Round lips for OO, say EE",  "by",   "town"),
        row("\xe6", "/\u025b\u02d0/", "EH", '"e" in bed',           "l\xe6se", "read"),
        row("\xf8", "/\xf8\u02d0/",  "UR", '"ur" in fur (British)', "gr\xf8n",  "green"),
        row("\xe5", "/\u0254\u02d0/", "AW", '"aw" in law',          "\xe5r",    "year"),
    ])
    cons = "".join([
        row("d (soft)",  "/\xf0/",   "-TH-",    '"th" in "the"',          "bade",   "bathe"),
        row("g (soft)",  "/\u0263/", "-w",       'Fades to a soft "w"',    "dag",    "day"),
        row("r",         "/\u0281/", "\u2014",   "Back of throat, like French r", "r\xf8d", "red"),
        row("\u02c0 st\xf8d", "\u02c0", "(catch)", "Catch in the throat \u2014 glottal stop", "hund", "dog"),
    ])

    return f"""\
<div class="page page-intro pron-page">
  <header class="page-header">
    <span class="book-title">Ordbog DA&rarr;EN</span>
    <span class="running-head">Pronunciation Guide</span>
    <span class="page-num">iii</span>
  </header>
  <div class="page-body">
    <h2 class="intro-heading">Danish Pronunciation</h2>
    <p class="intro-text">
      Danish spelling does not reliably predict pronunciation.
      Silent letters, vowel shifts, and the glot&shy;tal stop (st&oslash;d) make Danish harder to read aloud than it looks.
      Each entry gives two layers of help:
    </p>
    <p class="intro-text">
      <span class="phonetic">ALL-CAPS</span> &mdash; a plain-English read-aloud approximation. &nbsp;
      <span class="ipa">/IPA/</span> &mdash; precise phonetic transcription.
    </p>

    <p class="intro-subheading">Vowels</p>
    <table class="pron-table">
      <thead><tr><th>Spelling</th><th>IPA</th><th>Code</th><th>Sounds like</th><th>Example</th><th>Meaning</th></tr></thead>
      <tbody>{vowels}</tbody>
    </table>

    <p class="intro-subheading">Key consonants</p>
    <table class="pron-table">
      <thead><tr><th>Symbol</th><th>IPA</th><th>Code</th><th>Sounds like</th><th>Example</th><th>Meaning</th></tr></thead>
      <tbody>{cons}</tbody>
    </table>

    <p class="intro-subheading">The St&oslash;d (glottal stop)</p>
    <div class="pron-note">
      <strong>St&oslash;d</strong> is a brief catch or creak in the throat &mdash; like the pause in &ldquo;uh&ndash;oh&rdquo;.
      In IPA it is written <em class="ipa">&nbsp;\u02c0&nbsp;</em> after the affected sound:
      <em>hund</em> /hun\u02c0/ (dog), <em>se</em> /se\u02c0/ (see).
      The phonetic ALL-CAPS codes do not mark st&oslash;d &mdash; just be aware it exists.
    </div>

    <p class="intro-subheading">Soft-D</p>
    <div class="pron-note">
      When <strong>d</strong> appears between vowels or after a vowel at the end of a word,
      it softens to a fricative &mdash; like the <em>th</em> in <em>&ldquo;the&rdquo;</em>.
      Examples: <em>bade</em> (bathe), <em>ved</em> (at/by), <em>s&aelig;de</em> (seat).
      The code writes this as <span class="phonetic" style="font-size:7pt">&ndash;TH&ndash;</span>.
    </div>

    <p class="intro-subheading">The Danish R</p>
    <div class="pron-note">
      Danish <strong>r</strong> is uvular &mdash; produced at the very back of the throat, like French or German r.
      After a vowel it often weakens to a schwa /\u0250/ or disappears entirely.
      The ALL-CAPS codes mostly omit final r sounds as they are inaudible to English ears.
    </div>

    <p class="intro-subheading">Reading the phonetic codes</p>
    <div class="pron-note">
      The green <span class="phonetic" style="font-size:7pt">ALL-CAPS</span> codes use English letter combinations:
      <strong>AH</strong> (father), <strong>AY</strong> (day), <strong>EE</strong> (feet), <strong>OH</strong> (go),
      <strong>OO</strong> (food), <strong>EW</strong> (French&nbsp;<em>tu</em>),
      <strong>UR</strong> (British&nbsp;<em>fur</em>), <strong>AW</strong> (law).
      They are approximations only &mdash; always check the IPA for precise pronunciation.
    </div>
  </div>
  <footer class="page-footer">
    <span class="footer-left">Pronunciation Guide</span>
    <span class="footer-right">DA &rarr; EN</span>
  </footer>
</div>"""


def til_brugeren_html() -> str:
    return """\
<div class="page page-intro">
  <header class="page-header">
    <span class="book-title">Ordblind Ordbog</span>
    <span class="running-head">Til brugeren</span>
    <span class="page-num">ii</span>
  </header>
  <div class="page-body">
    <h2 class="intro-heading">Til brugeren</h2>

    <h3 class="intro-subheading">Hvad er denne ordbog?</h3>
    <p class="intro-text">
      <em>Ordblind Ordbog</em> er en dansk&#x2013;engelsk og engelsk&#x2013;dansk ordbog
      med fokus p&#xe5; det ordforr&#xe5;d, der anvendes p&#xe5; PD3-eksamen (B2&#x2013;C1 niveau).
      Ordbogen er udformet med dysleksivenlige principper: klare farver,
      konsekvent layout og en fonetisk vejledning p&#xe5; dansk, s&#xe5; udtalen
      kan l&#xe6;ses direkte uden kendskab til IPA.
    </p>

    <h3 class="intro-subheading">Ordvalg</h3>
    <p class="intro-text">
      Ordene er udvalgt p&#xe5; baggrund af frekvensdata fra Leipzig Corpora
      (dansk nyhedssprog, 1&#x00a0;million ord) samt PD3-pensum.
      Hvert opslag er m&#xe6;rket med et frekvensniveau:
      <strong>grundl&#xe6;ggende</strong> (top&#x00a0;500),
      <strong>almindelig</strong> (501&#x2013;2.000),
      <strong>generel</strong> (2.001&#x2013;5.000).
    </p>

    <h3 class="intro-subheading">Brug ved eksamen</h3>
    <p class="intro-text">
      Ordbogen m&#xe5; anvendes ved eksamen. Ifølge bekendtg&#xf8;relsen (bilag&#x00a03)
      m&#xe5; <em>alle ordb&#xf8;ger anvendes</em> &#x2014; med undtagelse af
      l&#xe6;seforst&#xe5;elsesprøven. Eksempelss&#xe6;tningerne er medtaget
      udelukkende som sproglige illustrationer af ordenes anvendelse.
      Er du i tvivl, b&#xf8;r du r&#xe5;dføre dig med dit sproglcenter inden eksamen.
    </p>

    <h3 class="intro-subheading">Opbygning af et opslag</h3>
    <p class="intro-text">
      Se de f&#xf8;lgende sider for en forklaring af alle symboler,
      farver og den fonetiske vejledning.
    </p>

    <h3 class="intro-subheading">Kilder og licenser</h3>
    <p class="intro-text">
      Eksempelss&#xe6;tninger er hentet fra
      <strong>Tatoeba</strong> (tatoeba.org) &#x2014; CC&#x00a0;BY&#x00a0;2.0.<br>
      Oversættelses- og grammatikdata fra
      <strong>Wiktionary</strong> (en.wiktionary.org) &#x2014; CC&#x00a0;BY-SA&#x00a0;3.0.<br>
      Frekvensdata fra
      <strong>Leipzig Corpora Collection</strong> (wortschatz.uni-leipzig.de) &#x2014; CC&#x00a0;BY.
    </p>

    <div class="intro-colofon">
      <div class="colofon-line"><span class="colofon-label">Titel</span><span class="colofon-value">Ordblind Ordbog &#x2014; Dansk&#x2013;Engelsk og Engelsk&#x2013;Dansk</span></div>
      <div class="colofon-line"><span class="colofon-label">Forlag</span><span class="colofon-value draft-placeholder">DRAFT &#x2014; udfyldes ved udgivelse</span></div>
      <div class="colofon-line"><span class="colofon-label">ISBN</span><span class="colofon-value draft-placeholder">DRAFT &#x2014; tildeles ved udgivelse</span></div>
      <div class="colofon-line"><span class="colofon-label">Udgave</span><span class="colofon-value draft-placeholder">DRAFT &#x2014; 1. udgave, &#xe5;r udfyldes</span></div>
      <div class="colofon-line"><span class="colofon-label">Copyright</span><span class="colofon-value draft-placeholder">DRAFT &#x2014; &#xa9; udfyldes ved udgivelse</span></div>
    </div>
  </div>
  <footer class="page-footer">
    <span class="footer-left">Ordblind Ordbog &#x2014; Dansk&#x2013;Engelsk og Engelsk&#x2013;Dansk</span>
    <span class="footer-center"></span>
    <span class="footer-right">ii</span>
  </footer>
</div>"""


def all_intro_pages(entry_count: int = 0) -> list:
    return [
        title_page_html(entry_count),
        til_brugeren_html(),
        how_to_use_html(),
        symbol_key_html(),
        pronunciation_guide_html(),
    ]


# ---------------------------------------------------------------------------
# Dictionary page and continuous-section rendering
# ---------------------------------------------------------------------------

_DA_ALPHA = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ\u00c6\u00d8\u00c5')
_EN_ALPHA = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def _alpha_strip_html(active_letters: set, is_en_da: bool, thumb_label: str = "") -> str:
    alphabet = _EN_ALPHA if is_en_da else _DA_ALPHA
    first_active_done = False
    items = []
    for ltr in alphabet:
        if ltr in active_letters:
            if not first_active_done and thumb_label:
                inner = esc(thumb_label[:3].upper())
                first_active_done = True
            else:
                inner = ltr
            items.append(f'<span class="alpha-active">{inner}</span>')
        else:
            items.append(f'<span class="alpha-item">{ltr}</span>')
    return f'<div class="alpha-strip">{"" .join(items)}</div>'


def render_dict_page(entries: list, page_num: int, is_en_da: bool = False) -> str:
    if not entries:
        return ""
    first_word = entries[0]["headword"].lower()
    last_word  = entries[-1]["headword"].lower()
    range_str  = f"{first_word} \u2013 {last_word}"
    active_letters = {e["headword"][0].upper() for e in entries if e["headword"]}
    thumb_label     = first_word[:3]

    recto_verso = "verso" if page_num % 2 == 0 else "recto"
    page_cls     = f"page page-en-da {recto_verso}" if is_en_da else f"page {recto_verso}"
    book_title   = "Ordbog EN&rarr;DA" if is_en_da else "Ordbog DA&rarr;EN"
    footer_left  = "English\u2013Danish" if is_en_da else "Danish\u2013English Dictionary"
    footer_right = "EN &rarr; DA" if is_en_da else "DA &rarr; EN"

    half = (len(entries) + 1) // 2
    left_entries  = entries[:half]
    right_entries = entries[half:]

    def build_col(col_entries: list) -> str:
        parts: list = []
        cur_ltr = None
        for e in col_entries:
            ltr = e["headword"][0].upper() if e["headword"] else "?"
            if ltr != cur_ltr:
                cur_ltr = ltr
                parts.append(letter_divider_html(ltr))
            parts.append(entry_html(e, is_en_da))
        return "".join(parts)

    left_body  = build_col(left_entries)
    right_body = build_col(right_entries)

    return f"""\
<div class="{page_cls}">
  {_alpha_strip_html(active_letters, is_en_da, thumb_label)}
  <header class="page-header">
    <span class="book-title">{book_title}</span>
    <span class="running-head">{esc(range_str)}</span>
    <span class="page-num">{page_num}</span>
  </header>
  <div class="page-body">
    <div class="page-col">
{left_body}
    </div>
    <div class="page-col">
{right_body}
    </div>
  </div>
  <footer class="page-footer">
    <span class="footer-left">{footer_left} &nbsp;\u00b7&nbsp; Tatoeba (CC-BY) &nbsp;\u00b7&nbsp; Leipzig (CC-BY)</span>
    <span class="footer-legend"><span class="lc-en">en</span><span class="lc-et">et</span><span class="lc-verb">verb</span><span class="lc-adj">adj</span><span class="lc-adv">adv</span><span class="lc-other">other</span></span>
    <span class="footer-right">{footer_right}</span>
  </footer>
</div>"""


def paginate_entries(entries: list, per_page: int = 8) -> list:
    """Split entries into chunks for explicit A4 page rendering."""
    return [entries[i:i + per_page] for i in range(0, len(entries), per_page)]


def _clean_en_hw(text: str) -> str:
    """Normalise an English translation into a clean dictionary headword.

    Removes parenthetical notes, leading articles (a/an/the) and the
    infinitive marker (to) so that translations like 'a quarter (of an hour)'
    become 'quarter' and 'to accept' becomes 'accept'.
    """
    # Take only the first clause (before ; or ,)
    text = re.split(r'[;,]', text)[0].strip()
    # Strip parenthetical notes, e.g. "(of an hour)"
    text = re.sub(r'\s*\([^)]*\)', '', text).strip()
    # Strip leading definite/indefinite articles
    text = re.sub(r'^(?:a|an|the)\s+', '', text, flags=re.IGNORECASE)
    # Strip infinitive "to " (verb marker)
    text = re.sub(r'^to\s+', '', text, flags=re.IGNORECASE)
    return text.strip()


def make_en_da_entries(all_da_entries: list) -> list:
    """Generate EN->DA reverse-lookup entries from DA->EN data.

    Groups all DA entries that share the same English headword into a single
    EN->DA page.  Secondary translations may carry an optional sense label
    (``{english: "to bear", sense: "carry a load"}``) which is shown on the
    EN->DA page when multiple senses exist.
    """
    from collections import defaultdict
    # groups[en_key] = list of {da_entry, sense, from_primary}
    groups: dict = defaultdict(list)
    for e in all_da_entries:
        pt = e["primary"]
        if pt and pt not in {"TODO", "SKIP", ""}:
            key = _clean_en_hw(pt).lower()
            if key and len(key) >= 2:
                groups[key].append({"da_entry": e, "sense": None, "from_primary": True})
        for sec in e.get("secondary", [])[:2]:
            en_text = sec["english"] if isinstance(sec, dict) else sec
            sense   = sec.get("sense")  if isinstance(sec, dict) else None
            if en_text and en_text not in {"TODO", "SKIP", ""}:
                key = _clean_en_hw(en_text).lower()
                if key and len(key) >= 2:
                    groups[key].append({"da_entry": e, "sense": sense, "from_primary": False})

    en_entries = []
    for en_lower, items in groups.items():
        # Deduplicate identical (da_word, sense) pairs
        seen: set = set()
        unique = []
        for item in items:
            k = (item["da_entry"]["headword"], item["sense"])
            if k not in seen:
                seen.add(k)
                unique.append(item)
        # Sort: primary-translation matches first, then by frequency rank
        unique.sort(key=lambda x: (
            not x["from_primary"],
            int(x["da_entry"]["rank"]) if x["da_entry"].get("rank", "").isdigit() else 9999,
        ))
        best = unique[0]["da_entry"]
        # Build senses list for the EN->DA page
        senses = [
            {
                "da":     item["da_entry"]["headword"],
                "sense":  item["sense"],
                "gender": item["da_entry"]["gender"],
                "pos":    item["da_entry"]["pos"],
            }
            for item in unique[:4]
        ]
        rev_ex = [{"da": ex["en"], "en": ex["da"]} for ex in best["examples"][:1]]
        hw     = en_lower[0].upper() + en_lower[1:] if en_lower else en_lower
        en_entries.append({
            "headword":  hw,
            "pos":       best["pos"],
            "gender":    best["gender"],
            "ipa":       best["ipa"],
            "phonetic":  best["phonetic"],
            "syllables": best["syllables"],
            "primary":   best["headword"],
            "secondary": [s["da"] for s in senses[1:4] if s["da"] != best["headword"]],
            "senses":    senses,
            "examples":  rev_ex,
            "tags":      best["tags"],
            "tier":      best["tier"],
            "rank":      best["rank"],
            "ff":        best["ff"],
            "ff_note":   best["ff_note"],
            "pt":        best["pt"],
            "_score":    best["_score"],
        })
    return sorted(en_entries, key=lambda x: x["headword"].lower())


def en_da_divider_page_html() -> str:
    return """\
<div class="page" style="justify-content:center;align-items:center;text-align:center">
  <div style="padding:0 30mm">
    <div style="font-size:9pt;font-weight:700;color:var(--en-color);text-transform:uppercase;letter-spacing:2px;margin-bottom:4mm">Ordbog</div>
    <div style="font-size:52pt;font-weight:700;color:var(--text);line-height:1;margin-bottom:3mm">English</div>
    <div style="font-size:26pt;color:var(--text-light);margin-bottom:6mm">&rarr; Danish</div>
    <div style="width:30mm;height:1.5pt;background:var(--en-color);opacity:0.35;margin:0 auto 6mm"></div>
    <div style="font-size:10.5pt;color:var(--text-light);line-height:1.8">
      Reverse look-up index<br>
      English headword &rarr; Danish translation<br>
      <span style="font-size:8.5pt">Gender, IPA, and phonetic guide are given for the Danish word.</span>
    </div>
  </div>
</div>"""


# ---------------------------------------------------------------------------
# HTML document assembly
# ---------------------------------------------------------------------------

def _html_doc(title: str, body: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
{CSS}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def write_sample(entries: list, output: Path) -> None:
    n = max(1, len(entries))
    size = max(1, n // 5)
    pages = [entries[i * size:(i + 1) * size] for i in range(4)]
    pages.append(entries[4 * size:])

    intro      = all_intro_pages(n)
    dict_pages = [render_dict_page(p, i + 5) for i, p in enumerate(pages) if p]

    body = "\n".join(intro + dict_pages)
    output.write_text(_html_doc("Ordbog DA\u2192EN \u2014 Sample Pages", body), encoding="utf-8")
    print(f"Written:  {output}")
    print(f"Intro:    4 pages  (title, how-to, key, pronunciation)")
    print(f"Sample:   {len(dict_pages)} dictionary pages, {n} entries")


def write_full(all_entries: list, output: Path) -> None:
    # DA→EN section
    da_sorted = sorted(all_entries, key=lambda e: danish_sort_key(e["headword"]))
    da_chunks = paginate_entries(da_sorted, per_page=8)
    intro     = all_intro_pages(len(all_entries))
    da_html   = [render_dict_page(chunk, i + 5) for i, chunk in enumerate(da_chunks)]

    # EN→DA section
    en_entries = make_en_da_entries(all_entries)
    en_chunks  = paginate_entries(en_entries, per_page=8)
    divider    = en_da_divider_page_html()
    en_start   = 5 + len(da_chunks) + 1
    en_html    = [render_dict_page(chunk, en_start + i, is_en_da=True) for i, chunk in enumerate(en_chunks)]

    body = "\n".join(intro + da_html + [divider] + en_html)
    output.write_text(_html_doc("Ordbog \u2014 Full Dictionary", body), encoding="utf-8")
    size_kb   = output.stat().st_size // 1024
    total_pg  = 5 + len(da_chunks) + 1 + len(en_chunks)
    print(f"Written:  {output}  ({size_kb} KB)")
    print(f"Intro:    5 pages")
    print(f"DA->EN:   {len(da_sorted)} entries, {len(da_chunks)} pages")
    print(f"EN->DA:   {len(en_entries)} entries, {len(en_chunks)} pages")
    print(f"Total:    {total_pg} pages")
    print(f"To print: Ctrl+P -> Save as PDF -> A4, no margins")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Render dictionary pages as HTML")
    parser.add_argument("--full",  action="store_true", help="Render all entries to dictionary.html")
    parser.add_argument("--count", type=int, default=55, help="Entries in sample mode (default 55)")
    parser.add_argument("--open",  action="store_true", help="Open in browser after")
    parser.add_argument("--words", nargs="+",           help="Specific headwords for sample")
    args = parser.parse_args()

    print("Loading entries \u2026")
    all_entries = load_all()
    print(f"  {len(all_entries)} entries loaded")

    if args.full:
        write_full(all_entries, OUT_FULL)
        target = OUT_FULL
    else:
        entries = select_entries(all_entries, count=args.count, words=args.words)
        print(f"  {len(entries)} entries selected for sample")
        write_sample(entries, OUT_SAMPLE)
        target = OUT_SAMPLE

    if args.open:
        import webbrowser
        webbrowser.open(target.as_uri())
        print("  Opened in browser")


if __name__ == "__main__":
    main()
