# ordblind-ordbog

Dyslexia-friendly Danish–English / English–Danish dictionary project targeting PD3 exam vocabulary (B2–C1).

## Key files

| File | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Project-specific AI agent instructions, entry conventions, controlled vocabularies, and editorial guidance. |
| [entry_template.md](entry_template.md) | Authoritative schema for every dictionary entry field, including sentinel values and layout flags. |
| [pipeline_guide.md](pipeline_guide.md) | End-to-end pipeline documentation from word list creation through entry generation. |
| [requirements.txt](requirements.txt) | Python dependencies used by the documented pipeline. |

## Project structure

```text
ordbog/
├── AGENTS.md
├── entry_template.md
├── pipeline_guide.md
├── requirements.txt
├── wordlist.txt
├── skipped.txt
├── data/
│   └── .gitkeep
└── entries/
    ├── da-en/
    │   └── .gitkeep
    └── en-da/
        └── .gitkeep
```

## Entry conventions

- Entry filenames follow `{lang}-{headword}-001.md`.
- Use `SKIP` for non-applicable fields.
- Use `TODO` for applicable but unpopulated fields.
- Never delete schema fields from an entry file.
- Keep manual `layout` content as `TODO` until a human editor fills it in.

## Pipeline dependencies

```bash
pip install -r requirements.txt
```

Python 3.10+ is required.
