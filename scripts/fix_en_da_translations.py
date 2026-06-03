"""
fix_en_da_translations.py
Apply bulk corrections to entries/en-da/*.md based on full audit.
Covers ranks 1–1443.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"

# key = English headword (lowercase, as used in the filename slug)
# value = dict with keys: pos, primary, secondaries (list of strings)
# Only include fields that need changing.
CORRECTIONS = {
    # --- POS errors ---
    "new":        {"pos": "adjective"},
    "get":        {"pos": "verb"},
    "show":       {"pos": "verb", "primary": "vise", "secondaries": ["show (et)", "forestilling (en)"]},
    "bring":      {"pos": "verb"},
    "let":        {"pos": "verb"},
    "next":       {"pos": "adjective"},
    "like":       {"pos": "verb", "primary": "lide", "secondaries": ["holde af", "synes om"]},
    "speak":      {"pos": "verb"},
    "death":      {"pos": "noun", "primary": "død (en)", "secondaries": ["dødsfald (et)"]},
    "short":      {"pos": "adjective"},
    "probably":   {"pos": "adverb", "primary": "sandsynligvis", "secondaries": ["formodentlig", "nok"]},
    "past":       {"pos": "noun", "primary": "fortid (en)", "secondaries": ["tidligere", "forbi"]},
    "finally":    {"pos": "adverb"},
    "brown":      {"pos": "adjective"},
    "dead":       {"pos": "adjective"},
    "lead":       {"pos": "verb"},
    "find":       {"pos": "verb", "primary": "finde", "secondaries": ["opdage", "konstatere"]},
    "actually":   {"pos": "adverb"},
    "suddenly":   {"pos": "adverb"},
    "somewhat":   {"pos": "adverb"},
    "immediately":{"pos": "adverb"},
    "recently":   {"pos": "adverb"},
    "completely": {"pos": "adverb"},
    "relatively": {"pos": "adverb"},
    "approximately": {"pos": "adverb"},
    "rapidly":    {"pos": "adverb"},
    "primarily":  {"pos": "adverb"},
    "straight":   {"pos": "adjective"},
    "hardly":     {"pos": "adverb"},
    "pretty":     {"pos": "adjective"},

    # --- Wrong primary translation ---
    "time":       {"pos": "noun", "primary": "tid (en)", "secondaries": ["tidspunkt (et)", "gang (en)", "klokke (en)"]},
    "work":       {"pos": "noun", "primary": "arbejde (et)", "secondaries": ["job (et)", "virke", "værk (et)"]},
    "see":        {"pos": "verb", "primary": "se", "secondaries": ["forstå", "besøge"]},
    "great":      {"pos": "adjective", "primary": "stor", "secondaries": ["fremragende", "vidunderlig"]},
    "need":       {"pos": "verb", "primary": "have brug for", "secondaries": ["behøve", "behov (et)", "savne"]},
    "want":       {"pos": "verb", "primary": "ville", "secondaries": ["ønske", "have lyst til"]},
    "part":       {"pos": "noun", "primary": "del (en)", "secondaries": ["afsnit (et)", "rolle (en)"]},
    "far":        {"pos": "adjective", "primary": "fjern", "secondaries": ["langt", "vidt"]},
    "head":       {"pos": "noun", "primary": "hoved (et)", "secondaries": ["chef (en)", "leder (en)"]},
    "fact":       {"pos": "noun", "primary": "faktum (et)", "secondaries": ["kendsgerning (en)", "virkelighed (en)"]},
    "stand":      {"pos": "verb", "primary": "stå", "secondaries": ["stand (en)", "stativ (et)"]},
    "order":      {"pos": "noun", "primary": "orden (en)", "secondaries": ["bestille", "ordne", "ordre (en)"]},
    "increase":   {"pos": "verb", "primary": "øge", "secondaries": ["stigning (en)", "vokse"]},
    "study":      {"pos": "verb", "primary": "studere", "secondaries": ["studie (et)", "undersøge"]},
    "service":    {"pos": "noun", "primary": "service (en)", "secondaries": ["tjeneste (en)", "drift (en)"]},
    "light":      {"pos": "noun", "primary": "lys (et)", "secondaries": ["let", "antænde"]},
    "car":        {"pos": "noun", "primary": "bil (en)", "secondaries": ["personbil (en)", "automobil (en)"]},
    "mind":       {"pos": "noun", "primary": "sind (et)", "secondaries": ["tanke (en)", "forstand (en)"]},
    "return":     {"pos": "verb", "primary": "vende tilbage", "secondaries": ["tilbagevenden (en)", "afkast (et)"]},
    "appear":     {"pos": "verb", "primary": "dukke op", "secondaries": ["synes", "forekomme", "optræde"]},
    "type":       {"pos": "noun", "primary": "type (en)", "secondaries": ["slags", "art (en)"]},
    "hour":       {"pos": "noun", "primary": "time (en)", "secondaries": ["timestid (en)"]},
    "street":     {"pos": "noun", "primary": "gade (en)"},
    "job":        {"pos": "noun", "primary": "job (et)", "secondaries": ["arbejde (et)", "stilling (en)"]},
    "sound":      {"pos": "noun", "primary": "lyd (en)", "secondaries": ["klang (en)", "lyde"]},
    "board":      {"pos": "noun", "primary": "bestyrelse (en)", "secondaries": ["bord (et)", "nævn (et)", "planke (en)"]},
    "note":       {"pos": "noun", "primary": "note (en)", "secondaries": ["bemærkning (en)", "seddel (en)"]},
    "record":     {"pos": "noun", "primary": "rekord (en)", "secondaries": ["optegnelse (en)", "plade (en)"]},
    "court":      {"pos": "noun", "primary": "ret (en)", "secondaries": ["domstol (en)", "bane (en)", "gård (en)"]},
    "cut":        {"pos": "verb", "primary": "skære", "secondaries": ["klippe", "snit (et)"]},
    "arm":        {"pos": "noun", "primary": "arm (en)", "secondaries": ["våben (et)", "ærme (et)"]},
    "land":       {"pos": "noun", "primary": "land (et)", "secondaries": ["jord (en)", "lande"]},
    "subject":    {"pos": "noun", "primary": "emne (et)", "secondaries": ["fag (et)", "subjekt (et)"]},
    "cannot":     {"pos": "verb phrase", "primary": "kan ikke", "secondaries": []},
    "major":      {"pos": "adjective", "primary": "stor", "secondaries": ["vigtig", "major (en)"]},
    "department": {"pos": "noun", "primary": "afdeling (en)", "secondaries": ["ministerium (et)", "division (en)"]},
    "base":       {"pos": "noun", "primary": "base (en)", "secondaries": ["grundlag (et)", "basis (en)", "hovedkvarter (et)"]},
    "true":       {"pos": "adjective", "primary": "sand", "secondaries": ["ægte", "virkelig"]},
    "bad":        {"pos": "adjective", "primary": "dårlig", "secondaries": ["slem", "skidt"]},
    "evidence":   {"pos": "noun", "primary": "bevis (et)", "secondaries": ["vidnesbyrd (et)", "dokumentation (en)"]},
    "top":        {"pos": "noun", "primary": "top (en)", "secondaries": ["toppe", "bedst"]},
    "range":      {"pos": "noun", "primary": "rækkevidde (en)", "secondaries": ["sortiment (et)", "område (et)"]},
    "visit":      {"pos": "verb", "primary": "besøge", "secondaries": ["gæste", "besøg (et)"]},
    "food":       {"pos": "noun", "primary": "mad (en)", "secondaries": ["føde (en)", "spise"]},
    "plant":      {"pos": "noun", "primary": "plante (en)", "secondaries": ["fabrik (en)", "sætte", "plante"]},
    "horse":      {"pos": "noun", "primary": "hest (en)", "secondaries": ["hingst (en)"]},
    "event":      {"pos": "noun", "primary": "begivenhed (en)", "secondaries": ["arrangement (et)", "hændelse (en)"]},
    "sort":       {"pos": "noun", "primary": "slags", "secondaries": ["sortere", "type (en)"]},
    "volume":     {"pos": "noun", "primary": "lydstyrke (en)", "secondaries": ["bind (et)", "volumen (et)", "mængde (en)"]},
    "factor":     {"pos": "noun", "primary": "faktor (en)", "secondaries": ["omstændighed (en)"]},
    "trial":      {"pos": "noun", "primary": "retssag (en)", "secondaries": ["prøve (en)", "forsøg (et)"]},
    "opportunity":{"pos": "noun", "primary": "mulighed (en)", "secondaries": ["lejlighed (en)", "chance (en)"]},
    "spring":     {"pos": "noun", "primary": "forår (et)", "secondaries": ["fjeder (en)", "kilde (en)", "springe"]},
    "secretary":  {"pos": "noun", "primary": "sekretær (en)", "secondaries": ["minister (en)"]},
    # 501–1443 additional corrections:
    "obtain":     {"pos": "verb", "primary": "opnå", "secondaries": ["skaffe", "erhverve"]},
    "stock":      {"pos": "noun", "primary": "lager (et)", "secondaries": ["aktie (en)", "bestand (en)"]},
    "difficult":  {"pos": "adjective", "primary": "svær", "secondaries": ["vanskelig"]},
    "prove":      {"pos": "verb", "primary": "bevise", "secondaries": ["godtgøre", "vise"]},
    "eat":        {"pos": "verb", "primary": "spise", "secondaries": ["fortære"]},
    "main":       {"pos": "adjective", "primary": "vigtigste", "secondaries": ["hoved-", "generel"]},
    "objective":  {"pos": "noun", "primary": "mål (et)", "secondaries": ["formål (et)", "objektiv (et)"]},
    "former":     {"pos": "adjective", "primary": "tidligere", "secondaries": ["forhenværende"]},
    "hot":        {"pos": "adjective", "primary": "varm", "secondaries": ["hed", "stærk"]},
    "wage":       {"pos": "noun", "primary": "løn (en)", "secondaries": ["arbejdsløn (en)"]},
    "pick":       {"pos": "verb", "primary": "plukke", "secondaries": ["vælge", "hente"]},
    "express":    {"pos": "verb", "primary": "udtrykke", "secondaries": ["ytre", "udtrykke sig"]},
    "gain":       {"pos": "verb", "primary": "vinde", "secondaries": ["opnå", "gavn (et)"]},
    "file":       {"pos": "noun", "primary": "fil (en)", "secondaries": ["mappe (en)", "linje (en)"]},
    "heat":       {"pos": "noun", "primary": "varme (en)", "secondaries": ["runde (en)"]},
    "bar":        {"pos": "noun", "primary": "bar (en)", "secondaries": ["stang (en)", "spærre"]},
    "finger":     {"pos": "noun", "primary": "finger (en)", "secondaries": ["udpege"]},
    "honor":      {"pos": "noun", "primary": "ære (en)", "secondaries": ["hæder (en)", "agtelse (en)"]},
    "rock":       {"pos": "noun", "primary": "klippe (en)", "secondaries": ["sten (en)", "rock (en)"]},
    "oil":        {"pos": "noun", "primary": "olie (en)", "secondaries": ["madolie (en)"]},
    "clean":      {"pos": "adjective", "primary": "ren", "secondaries": ["rydde op", "gøre rent"]},
    "burn":       {"pos": "verb", "primary": "brænde", "secondaries": ["forbrænding (en)", "brandsår (et)"]},
    "post":       {"pos": "noun", "primary": "post (en)", "secondaries": ["stilling (en)", "stolpe (en)"]},
    "trip":       {"pos": "noun", "primary": "tur (en)", "secondaries": ["rejse (en)", "fart (en)"]},
    "mouth":      {"pos": "noun", "primary": "mund (en)", "secondaries": ["udmunding (en)"]},
    "straight":   {"pos": "adjective", "primary": "lige", "secondaries": ["ret", "direkte"]},
    "current":    {"pos": "noun", "primary": "strøm (en)", "secondaries": ["nuværende", "aktuel"]},
    "speed":      {"pos": "noun", "primary": "hastighed (en)", "secondaries": ["fart (en)"]},
    "circle":     {"pos": "noun", "primary": "cirkel (en)", "secondaries": ["ring (en)", "kreds (en)"]},
    "staff":      {"pos": "noun", "primary": "personale (et)", "secondaries": ["stab (en)", "stav (en)"]},
    "justice":    {"pos": "noun", "primary": "retfærdighed (en)", "secondaries": ["dommer (en)"]},
    "equal":      {"pos": "adjective", "primary": "lige", "secondaries": ["ens", "samme"]},
    "pressure":   {"pos": "noun", "primary": "tryk (et)", "secondaries": ["pres (et)"]},
    "news":       {"pos": "noun", "primary": "nyheder", "secondaries": ["nyhed (en)", "budskab (et)"]},
    "indicate":   {"pos": "verb", "primary": "angive", "secondaries": ["vise", "antyde"]},
    "repair":     {"pos": "verb", "primary": "reparere", "secondaries": []},
    "seat":       {"pos": "noun", "primary": "plads (en)", "secondaries": ["sæde (et)"]},
    "repair":     {"pos": "verb", "primary": "reparere"},
    "usual":      {"pos": "adjective", "primary": "sædvanlig", "secondaries": ["almindelig", "vant"]},
    "quiet":      {"pos": "adjective", "primary": "stille", "secondaries": ["rolig"]},
    "count":      {"pos": "verb", "primary": "tælle", "secondaries": ["greve (en)"]},
    "clearly":    {"pos": "adverb", "primary": "tydeligt", "secondaries": ["klart", "tydeligvis"]},
    "principal":  {"pos": "adjective", "primary": "vigtigste", "secondaries": ["rektor (en)", "hoved-"]},
    "failure":    {"pos": "noun", "primary": "fiasko (en)", "secondaries": ["fejl (en)", "konkurs (en)"]},
    "refuse":     {"pos": "verb", "primary": "afslå", "secondaries": ["nægte", "affald (et)"]},
    "brief":      {"pos": "adjective", "primary": "kort", "secondaries": ["kortfattet"]},
    "broad":      {"pos": "adjective", "primary": "bred", "secondaries": ["vid", "omfangsrig"]},
    "natural":    {"pos": "adjective", "primary": "naturlig", "secondaries": ["selvfølgelig"]},
    "poor":       {"pos": "adjective", "primary": "fattig", "secondaries": ["dårlig"]},
    "generation": {"pos": "noun", "primary": "generation (en)", "secondaries": ["slægt (en)", "udvikling (en)"]},
    "twice":      {"pos": "adverb", "primary": "to gange", "secondaries": []},
    "nobody":     {"pos": "pronoun", "primary": "ingen", "secondaries": []},
    "trust":      {"pos": "noun", "primary": "tillid (en)", "secondaries": ["tro (en)", "fond (en)"]},
    "nobody":     {"pos": "pronoun", "primary": "ingen"},
    "nose":       {"pos": "noun", "primary": "næse (en)", "secondaries": ["snude (en)", "snuse"]},
    "ear":        {"pos": "noun", "primary": "øre (et)", "secondaries": ["aks (et)"]},
    "phone":      {"pos": "noun", "primary": "telefon (en)", "secondaries": ["ringe", "sproglyd (en)"]},
    "hide":       {"pos": "verb", "primary": "gemme sig", "secondaries": ["skjule", "skind (et)"]},
    "mistake":    {"pos": "noun", "primary": "fejl (en)", "secondaries": ["misforståelse (en)"]},
    "passage":    {"pos": "noun", "primary": "passage (en)", "secondaries": ["afsnit (et)", "sted (et)"]},
    "uniform":    {"pos": "adjective", "primary": "ensartet", "secondaries": ["uniform (en)", "uforanderlig"]},
    "vocational": {"pos": "adjective", "primary": "erhvervsfaglig", "secondaries": ["faglig", "erhvervs-"]},
    "tire":       {"pos": "verb", "primary": "trætte", "secondaries": ["dæk (et)", "blive træt"]},
    "release":    {"pos": "noun", "primary": "frigivelse (en)", "secondaries": ["udgave (en)", "version (en)"]},
    "deliver":    {"pos": "verb", "primary": "levere", "secondaries": ["aflevere", "befri"]},
    "troop":      {"pos": "noun", "primary": "troppe (en)", "secondaries": ["soldat (en)", "militærstyrke (en)"]},
    "site":       {"pos": "noun", "primary": "sted (et)", "secondaries": ["hjemmeside (en)", "plads (en)"]},
    "location":   {"pos": "noun", "primary": "sted (et)", "secondaries": ["placering (en)", "beliggenhed (en)"]},
    "positive":   {"pos": "adjective", "primary": "positiv", "secondaries": []},
    "potential":  {"pos": "adjective", "primary": "potentiel", "secondaries": ["potentiale (et)"]},
    "curve":      {"pos": "noun", "primary": "kurve (en)", "secondaries": []},
    "print":      {"pos": "verb", "primary": "udskrive", "secondaries": ["trykke", "printe"]},
    "reading":    {"pos": "noun", "primary": "læsning (en)", "secondaries": ["aflæsning (en)", "forelæsning (en)"]},
    "musical":    {"pos": "adjective", "primary": "musikalsk", "secondaries": ["musical (en)"]},
    "rapidly":    {"pos": "adverb", "primary": "hurtigt", "secondaries": []},
    "primarily":  {"pos": "adverb", "primary": "primært", "secondaries": []},
    "approximately": {"pos": "adverb", "primary": "cirka", "secondaries": ["omtrent", "næsten"]},
    "extreme":    {"pos": "adjective", "primary": "ekstrem", "secondaries": ["yderlig", "yderst"]},
    "youthful":   {"pos": "adjective", "primary": "ungdommelig"},
    "youth":      {"pos": "noun", "primary": "ungdom (en)", "secondaries": ["ung person (en)"]},
    "fancy":      {"pos": "adjective", "primary": "fin", "secondaries": ["luksuriøs"]},
    "cook":       {"pos": "verb", "primary": "lave mad", "secondaries": ["tilberede", "koge"]},
    "radio":      {"pos": "noun", "primary": "radio (en)", "secondaries": []},
    "belong":     {"pos": "verb", "primary": "tilhøre", "secondaries": ["hjemme", "passe"]},
    "generation": {"pos": "noun", "primary": "generation (en)", "secondaries": ["slægt (en)"]},
    "engage":     {"pos": "verb", "primary": "engagere", "secondaries": ["involvere", "angribe"]},
    "dress":      {"pos": "verb", "primary": "klæde på", "secondaries": ["kjole (en)", "klæde sig"]},
}


def slug(word: str) -> str:
    """Convert English headword to filename slug (same logic as entry creation)."""
    return word.lower().replace(" ", "-").replace("'", "")


def find_entry_file(word: str) -> Path | None:
    s = slug(word)
    p = EN_DA_DIR / f"en-{s}-001.md"
    return p if p.exists() else None


def update_field(content: str, field: str, new_value: str) -> str:
    """Replace a YAML field value in a fenced code block."""
    pattern = rf"(^{re.escape(field)}:\s*)(.+)$"
    replacement = rf"\g<1>{new_value}"
    new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if n == 0:
        print(f"  WARNING: field '{field}' not found")
    return new_content


def update_entry(word: str, changes: dict) -> bool:
    path = find_entry_file(word)
    if path is None:
        print(f"  SKIP (not found): {word}")
        return False

    content = path.read_text(encoding="utf-8")
    original = content

    if "pos" in changes:
        content = update_field(content, "pos", changes["pos"])

    if "primary" in changes:
        content = update_field(content, "primary_translation", changes["primary"])

    if "secondaries" in changes:
        secondaries_val = changes["secondaries"]
        if isinstance(secondaries_val, list):
            val_str = " | ".join(secondaries_val) if secondaries_val else "TODO"
        else:
            val_str = secondaries_val
        content = update_field(content, "secondary_translations", val_str)

    if content != original:
        path.write_text(content, encoding="utf-8")
        return True
    return False


def main():
    changed = 0
    skipped = 0
    for word, changes in CORRECTIONS.items():
        print(f"Processing: {word}")
        if update_entry(word, changes):
            changed += 1
        else:
            skipped += 1
    print(f"\nDone. Changed: {changed}, Skipped/not found: {skipped}")


if __name__ == "__main__":
    main()
