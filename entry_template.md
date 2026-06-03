# Dictionary Entry Template
# Dyslexia-Friendly Danish–English / English–Danish Ordbog
# Schema version: 0.1
#
# PIPELINE INSTRUCTIONS:
# - One file per headword
# - All fields marked [REQUIRED] must be populated before an entry is considered complete
# - Fields marked [OPTIONAL] are populated where data is available
# - Fields marked [MANUAL] cannot be auto-populated and require human review
# - Use SKIP if a field is not applicable for this entry
# - Use TODO if a field is applicable but not yet populated
# - Do not delete any fields — the pipeline checks for their presence

---

## HEADWORD [REQUIRED]

```
headword: hygge
direction: DA→EN
```

<!-- direction is either DA→EN or EN→DA -->
<!-- For EN→DA entries, headword is the English word -->

---

## GRAMMAR [REQUIRED]

```
pos: noun
gender: en
```

<!-- pos options: noun | verb | adjective | adverb | pronoun | preposition | conjunction | interjection | phrase -->
<!-- gender options (nouns only): en | et | SKIP -->
<!-- For verbs, adjectives etc. gender is SKIP -->

### Inflections [OPTIONAL]

```
inflections:
  indefinite_singular: hygge
  definite_singular: hyggen
  indefinite_plural: SKIP
  definite_plural: SKIP
```

<!-- For verbs use: infinitive | present | past | past_participle | present_participle -->
<!-- For adjectives use: base | comparative | superlative | neuter | plural -->
<!-- Only include forms that exist — mark irregular forms with [irreg] -->

---

## PRONUNCIATION [REQUIRED]

```
phonetic_plain: HOO-yeh
ipa: ˈhygə
syllables: hyg-ge
stoed: false
```

<!-- phonetic_plain: plain English approximation of Danish pronunciation -->
<!-- ipa: International Phonetic Alphabet transcription -->
<!-- syllables: word broken into syllables with hyphens -->
<!-- stoed: true | false — does this word use the Danish stød (glottal stop feature)? -->
<!-- soft_d: true | false — add this field if the word contains a soft-d (blødt d) -->

---

## TRANSLATION [REQUIRED]

```
primary_translation: cosiness; a feeling of warmth and convivial togetherness
secondary_translations:
  - conviviality
  - a cosy atmosphere
```

<!-- primary_translation: the best single translation or short definition -->
<!-- secondary_translations: list additional translations in order of relevance -->
<!--   Plain form:      - to carry                                             -->
<!--   With sense hint: - to bear | carry a load    (pipe + label)             -->
<!--   The sense label appears on the EN->DA page when a headword has multiple -->
<!--   Danish senses, e.g. "bear" -> bære (carry a load) / tåle (endure).     -->
<!-- For DA→EN entries, translations are English (use the pipe hint for polysemous words) -->
<!-- For EN→DA entries, translations are Danish, with gender marked: e.g. "hygge (en)" -->

---

## REGISTER [OPTIONAL]

```
register: neutral
domain: SKIP
formality: informal
```

<!-- register options: neutral | colloquial | formal | slang | archaic | technical | literary -->
<!-- domain options: SKIP | legal | medical | academic | bureaucratic | nature | food | emotion | work | family -->
<!-- formality options: informal | neutral | formal -->

---

## EXAMPLE SENTENCES [REQUIRED — minimum 1, aim for 2]

```yaml
examples:
  - danish: Vi hyggede os hele aftenen.
    english: We had a lovely cosy evening together.
    source: tatoeba
    source_id: 12345

  - danish: Der er hygge på caféen om vinteren.
    english: The café has a warm, cosy atmosphere in winter.
    source: manual
    source_id: SKIP
```

<!-- source options: tatoeba | wiktionary | manual | ordnet -->
<!-- source_id: the source's sentence ID where available, else SKIP -->
<!-- Sentences should be natural, mid-length, and use the headword in an everyday context -->
<!-- Avoid very long or syntactically complex sentences -->

---

## RELATED WORDS [OPTIONAL]

```
related:
  - hyggelig (adjective — cosy, pleasant)
  - hyggekrog (en — a cosy nook or corner)
  - hyggebukser (plural — cosy home trousers)
```

<!-- List related words with brief gloss -->
<!-- Prioritise words that share the same root or appear in the same thematic cluster -->
<!-- Link to their own entry files where they exist -->

---

## THEMATIC TAGS [REQUIRED]

```
tags:
  - emotion
  - home
  - social
```

<!-- Choose 1–3 tags from the controlled vocabulary below -->
<!-- Controlled tag list: -->
<!-- emotion | body | health | food | drink | home | nature | weather | -->
<!-- work | education | bureaucracy | transport | time | money | -->
<!-- social | family | culture | politics | environment | technology -->

---

## FREQUENCY [REQUIRED]

```
frequency_rank: 847
frequency_tier: common
```

<!-- frequency_rank: integer rank from Leipzig Danish corpus (1 = most frequent) -->
<!-- frequency_tier options: core (top 500) | common (501–2000) | general (2001–5000) | rare (5000+) -->
<!-- If rank unavailable from corpus, use TODO and set tier manually -->

---

## LAYOUT HINTS [OPTIONAL — MANUAL]

```
layout:
  print_emphasis: high
  flag_false_friend: false
  flag_spelling_trap: false
  flag_pronunciation_trap: true
```

<!-- print_emphasis: high | normal | low — how prominently to feature this entry -->
<!-- flag_false_friend: true if this word looks/sounds like an English word but means something different -->
<!-- flag_spelling_trap: true if commonly misspelled by DA learners -->
<!-- flag_pronunciation_trap: true if pronunciation is especially counterintuitive -->
<!-- These flags trigger visual indicators in the printed layout -->

---

## PIPELINE METADATA [AUTO-POPULATED]

```
entry_id: da-hygge-001
created: 2026-05-04
last_modified: 2026-05-04
source_wiktionary: true
source_tatoeba: true
source_leipzig: true
review_status: draft
reviewed_by: SKIP
notes: SKIP
```

<!-- review_status: draft | reviewed | approved | flagged -->
<!-- reviewed_by: initials of human reviewer -->
<!-- notes: any pipeline or editorial notes -->

---
<!-- END OF ENTRY -->
