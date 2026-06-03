"""
fill_tags_en_da.py
Auto-assign 1–3 tags to EN→DA entries where tags: TODO.

Tags (from AGENTS.md):
  emotion | body | health | food | drink | home | nature | weather | work |
  education | bureaucracy | transport | time | money | social | family |
  culture | politics | environment | technology

Strategy: keyword lookup on headword, then POS-based fallback.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EN_DA_DIR = ROOT / "entries" / "en-da"

# headword -> list of tags (1–3)
KEYWORD_TAGS: dict[str, list[str]] = {
    # --- emotion ---
    "feel": ["emotion"], "feeling": ["emotion"], "love": ["emotion", "social"],
    "fear": ["emotion"], "hope": ["emotion"], "worry": ["emotion"],
    "anger": ["emotion"], "happy": ["emotion"], "sad": ["emotion"],
    "joy": ["emotion"], "surprise": ["emotion"], "desire": ["emotion"],
    "smile": ["emotion", "social"], "laugh": ["emotion", "social"],
    "cry": ["emotion"], "suffer": ["emotion", "health"], "pain": ["health", "body"],
    "pleasure": ["emotion"], "wonder": ["emotion"], "dream": ["emotion"],

    # --- body ---
    "arm": ["body"], "leg": ["body"], "head": ["body"], "eye": ["body"],
    "hand": ["body"], "finger": ["body"], "face": ["body"], "mouth": ["body"],
    "nose": ["body"], "ear": ["body"], "heart": ["body", "health"],
    "blood": ["body", "health"], "skin": ["body"], "hair": ["body"],
    "shoulder": ["body"], "knee": ["body"], "lip": ["body"], "neck": ["body"],
    "muscle": ["body"], "back": ["body"], "foot": ["body"], "bone": ["body"],
    "brain": ["body"], "breath": ["body", "health"], "stomach": ["body"],
    "chest": ["body"], "throat": ["body"], "tongue": ["body"],

    # --- health ---
    "health": ["health"], "disease": ["health"], "medicine": ["health"],
    "doctor": ["health", "work"], "hospital": ["health"], "patient": ["health"],
    "treatment": ["health"], "surgery": ["health"], "illness": ["health"],
    "sick": ["health"], "drug": ["health"], "cancer": ["health"],
    "death": ["health"], "dead": ["health"], "die": ["health"],
    "radiation": ["health", "technology"], "birth": ["health", "family"],

    # --- food ---
    "food": ["food"], "eat": ["food"], "meal": ["food"], "cook": ["food", "home"],
    "bread": ["food"], "meat": ["food"], "fruit": ["food"], "sugar": ["food"],
    "salt": ["food"], "rice": ["food"], "fish": ["food"], "egg": ["food"],
    "milk": ["food"], "butter": ["food"], "cheese": ["food"], "soup": ["food"],
    "dinner": ["food", "home"], "lunch": ["food"], "breakfast": ["food"],
    "taste": ["food"], "hungry": ["food"], "fat": ["food", "body"],

    # --- drink ---
    "drink": ["drink"], "water": ["drink"], "wine": ["drink"], "beer": ["drink"],
    "coffee": ["drink"], "tea": ["drink"], "juice": ["drink"], "alcohol": ["drink"],
    "bottle": ["drink", "home"],

    # --- home ---
    "home": ["home"], "house": ["home"], "room": ["home"], "bed": ["home"],
    "door": ["home"], "window": ["home"], "floor": ["home"], "wall": ["home"],
    "kitchen": ["home", "food"], "garden": ["home", "nature"], "roof": ["home"],
    "apartment": ["home"], "furniture": ["home"], "table": ["home"],
    "chair": ["home"], "clothes": ["home"], "wash": ["home"], "clean": ["home"],
    "maintenance": ["home", "work"], "lock": ["home"],

    # --- nature ---
    "nature": ["nature"], "water": ["nature"], "tree": ["nature"],
    "forest": ["nature"], "animal": ["nature"], "bird": ["nature"],
    "fish": ["nature"], "flower": ["nature"], "plant": ["nature", "environment"],
    "river": ["nature"], "sea": ["nature"], "mountain": ["nature"],
    "stone": ["nature"], "earth": ["nature", "environment"], "soil": ["nature"],
    "cloud": ["nature", "weather"], "sky": ["nature"], "sun": ["nature", "weather"],
    "moon": ["nature"], "star": ["nature"], "wind": ["weather", "nature"],
    "snow": ["weather", "nature"], "rain": ["weather", "nature"],
    "horse": ["nature"], "dog": ["nature"], "cat": ["nature"],
    "cattle": ["nature"], "snake": ["nature"], "clay": ["nature"],
    "wood": ["nature", "home"], "metal": ["technology", "nature"],
    "seed": ["nature"], "valley": ["nature"], "coast": ["nature"],
    "island": ["nature"], "hill": ["nature"], "fog": ["nature", "weather"],

    # --- weather ---
    "weather": ["weather"], "rain": ["weather"], "snow": ["weather"],
    "wind": ["weather"], "storm": ["weather"], "temperature": ["weather"],
    "heat": ["weather"], "cold": ["weather"], "season": ["weather", "time"],
    "summer": ["weather", "time"], "winter": ["weather", "time"],
    "spring": ["weather", "time"], "atmosphere": ["weather", "environment"],

    # --- work ---
    "work": ["work"], "job": ["work"], "worker": ["work"], "employee": ["work"],
    "manager": ["work"], "director": ["work"], "officer": ["work"],
    "secretary": ["work"], "employer": ["work"], "salary": ["work", "money"],
    "wage": ["work", "money"], "career": ["work"], "labor": ["work"],
    "office": ["work"], "company": ["work", "money"], "business": ["work", "money"],
    "industry": ["work"], "trade": ["work", "money"], "staff": ["work"],
    "task": ["work"], "training": ["work", "education"], "operate": ["work"],
    "operation": ["work"], "service": ["work"], "produce": ["work"],
    "production": ["work"], "manufacture": ["work"], "engineer": ["work", "technology"],
    "performance": ["work"], "procedure": ["work"],

    # --- education ---
    "education": ["education"], "school": ["education"], "university": ["education"],
    "student": ["education"], "teacher": ["education"], "study": ["education"],
    "learn": ["education"], "book": ["education", "culture"], "read": ["education"],
    "write": ["education"], "science": ["education"], "knowledge": ["education"],
    "theory": ["education"], "research": ["education"], "library": ["education"],
    "professor": ["education"], "college": ["education"], "graduate": ["education"],
    "degree": ["education"], "lecture": ["education"], "test": ["education"],
    "exam": ["education"], "assignment": ["education"], "skill": ["education"],
    "vocational": ["education", "work"], "chapter": ["education", "culture"],

    # --- bureaucracy ---
    "government": ["politics", "bureaucracy"], "law": ["bureaucracy"],
    "rule": ["bureaucracy"], "regulation": ["bureaucracy"], "court": ["bureaucracy"],
    "judge": ["bureaucracy"], "justice": ["bureaucracy"], "legal": ["bureaucracy"],
    "attorney": ["bureaucracy"], "lawyer": ["bureaucracy"], "contract": ["bureaucracy", "money"],
    "document": ["bureaucracy"], "department": ["bureaucracy", "work"],
    "ministry": ["bureaucracy", "politics"], "minister": ["bureaucracy", "politics"],
    "administration": ["bureaucracy", "politics"], "commission": ["bureaucracy"],
    "committee": ["bureaucracy"], "congress": ["bureaucracy", "politics"],
    "federal": ["bureaucracy", "politics"], "tax": ["bureaucracy", "money"],
    "fee": ["bureaucracy", "money"], "permit": ["bureaucracy"],
    "application": ["bureaucracy"], "license": ["bureaucracy"],

    # --- transport ---
    "car": ["transport"], "bus": ["transport"], "train": ["transport"],
    "plane": ["transport"], "aircraft": ["transport"], "ship": ["transport"],
    "boat": ["transport"], "road": ["transport"], "street": ["transport", "home"],
    "bridge": ["transport"], "railroad": ["transport"], "truck": ["transport"],
    "vehicle": ["transport"], "driver": ["transport"], "travel": ["transport"],
    "trip": ["transport"], "ride": ["transport"], "fly": ["transport"],
    "automobile": ["transport"], "motor": ["transport", "technology"],
    "engine": ["transport", "technology"], "wheel": ["transport"],
    "speed": ["transport"], "traffic": ["transport"],

    # --- time ---
    "time": ["time"], "year": ["time"], "day": ["time"], "hour": ["time"],
    "minute": ["time"], "second": ["time"], "week": ["time"], "month": ["time"],
    "morning": ["time"], "afternoon": ["time"], "evening": ["time"],
    "night": ["time"], "today": ["time"], "yesterday": ["time"], "tomorrow": ["time"],
    "age": ["time"], "century": ["time"], "decade": ["time"], "moment": ["time"],
    "past": ["time"], "future": ["time"], "history": ["time", "culture"],
    "early": ["time"], "late": ["time"], "soon": ["time"], "ago": ["time"],
    "date": ["time"], "season": ["time", "weather"], "period": ["time"],

    # --- money ---
    "money": ["money"], "price": ["money"], "cost": ["money"], "pay": ["money"],
    "bank": ["money"], "fund": ["money"], "income": ["money"], "profit": ["money"],
    "loss": ["money"], "tax": ["money", "bureaucracy"], "sale": ["money"],
    "market": ["money"], "trade": ["money", "work"], "economy": ["money"],
    "financial": ["money"], "budget": ["money"], "investment": ["money"],
    "stock": ["money"], "dollar": ["money"], "cent": ["money"],
    "credit": ["money"], "loan": ["money"], "debt": ["money"],
    "purchase": ["money"], "buy": ["money"], "sell": ["money"],
    "fee": ["money", "bureaucracy"], "wage": ["money", "work"],
    "expense": ["money"], "payment": ["money"], "worth": ["money"],

    # --- social ---
    "friend": ["social"], "family": ["family", "social"], "people": ["social"],
    "society": ["social"], "community": ["social"], "group": ["social"],
    "meeting": ["social", "work"], "party": ["social"], "event": ["social"],
    "conversation": ["social"], "relationship": ["social"], "marriage": ["family", "social"],
    "love": ["social", "emotion"], "hate": ["social", "emotion"],
    "help": ["social"], "support": ["social"], "trust": ["social"],
    "respect": ["social"], "honor": ["social"], "guest": ["social"],
    "neighbor": ["social"], "citizen": ["social", "politics"],
    "club": ["social"], "association": ["social"], "member": ["social"],

    # --- family ---
    "family": ["family"], "mother": ["family"], "father": ["family"],
    "son": ["family"], "daughter": ["family"], "brother": ["family"],
    "sister": ["family"], "child": ["family"], "baby": ["family"],
    "parent": ["family"], "husband": ["family", "social"], "wife": ["family", "social"],
    "marriage": ["family", "social"], "birth": ["family", "health"],
    "home": ["family", "home"], "kid": ["family"],

    # --- culture ---
    "culture": ["culture"], "art": ["culture"], "music": ["culture"],
    "book": ["culture", "education"], "film": ["culture"], "story": ["culture"],
    "history": ["culture", "time"], "language": ["culture", "education"],
    "religion": ["culture"], "tradition": ["culture"], "poetry": ["culture"],
    "poem": ["culture"], "song": ["culture"], "dance": ["culture"],
    "theater": ["culture"], "concert": ["culture"], "orchestra": ["culture"],
    "museum": ["culture"], "literature": ["culture"], "painting": ["culture"],
    "radio": ["culture", "technology"], "television": ["culture", "technology"],
    "sport": ["culture"], "game": ["culture"], "festival": ["culture"],
    "god": ["culture"], "soul": ["culture", "emotion"], "belief": ["culture"],
    "faith": ["culture"], "spirit": ["culture"], "hero": ["culture"],
    "jazz": ["culture"], "musician": ["culture"], "artist": ["culture"],
    "writer": ["culture"], "poet": ["culture"], "author": ["culture"],
    "reader": ["culture", "education"], "publication": ["culture"],

    # --- politics ---
    "politics": ["politics"], "government": ["politics"], "president": ["politics"],
    "king": ["politics", "culture"], "state": ["politics"], "nation": ["politics"],
    "war": ["politics"], "peace": ["politics"], "army": ["politics"],
    "military": ["politics"], "soldier": ["politics"], "weapon": ["politics"],
    "gun": ["politics"], "bomb": ["politics"], "enemy": ["politics"],
    "victory": ["politics"], "defeat": ["politics"], "battle": ["politics"],
    "election": ["politics"], "vote": ["politics"], "party": ["politics", "social"],
    "democratic": ["politics"], "republican": ["politics"], "liberal": ["politics"],
    "communist": ["politics"], "revolution": ["politics"], "independence": ["politics"],
    "federal": ["politics", "bureaucracy"], "congress": ["politics", "bureaucracy"],
    "minister": ["politics", "bureaucracy"], "chairman": ["politics"],
    "leader": ["politics", "work"], "union": ["politics", "work"],
    "communist": ["politics"], "soviet": ["politics"],

    # --- environment ---
    "environment": ["environment"], "nature": ["environment", "nature"],
    "pollution": ["environment"], "climate": ["environment", "weather"],
    "energy": ["environment", "technology"], "oil": ["environment", "technology"],
    "gas": ["technology", "environment"], "nuclear": ["environment", "technology"],
    "earth": ["environment", "nature"], "soil": ["environment", "nature"],
    "forest": ["environment", "nature"], "waste": ["environment"],
    "water": ["environment", "nature"], "air": ["environment", "nature"],
    "carbon": ["environment"], "chemical": ["environment", "technology"],

    # --- technology ---
    "technology": ["technology"], "computer": ["technology"], "machine": ["technology"],
    "device": ["technology"], "tool": ["technology"], "engine": ["technology", "transport"],
    "motor": ["technology", "transport"], "electric": ["technology"],
    "electronic": ["technology"], "digital": ["technology"], "screen": ["technology"],
    "phone": ["technology", "social"], "internet": ["technology"],
    "program": ["technology"], "data": ["technology"], "system": ["technology"],
    "network": ["technology"], "signal": ["technology"], "radio": ["technology", "culture"],
    "atom": ["technology"], "missile": ["technology", "politics"],
    "instrument": ["technology"], "measure": ["technology"],
    "science": ["education", "technology"], "research": ["education", "technology"],
}

# POS-based fallback when keyword not found
POS_FALLBACK: dict[str, str] = {
    "verb": "work",
    "noun": "social",
    "adjective": "social",
    "adverb": "social",
}


def get_tags(headword: str, pos: str) -> list[str]:
    tags = KEYWORD_TAGS.get(headword.lower())
    if tags:
        return tags[:3]
    # Try partial match for compound words
    for kw, t in KEYWORD_TAGS.items():
        if kw in headword.lower() or headword.lower() in kw:
            return t[:3]
    fallback = POS_FALLBACK.get(pos, "social")
    return [fallback]


def main():
    entries = sorted(EN_DA_DIR.glob("en-*-001.md"))
    updated = 0
    skipped = 0

    for path in entries:
        txt = path.read_text(encoding="utf-8")

        # Check if tags need filling
        has_todo_tags = bool(re.search(r"^tags:\s*\n\s*-\s*TODO", txt, re.M) or
                             re.search(r"^tags:\s*TODO", txt, re.M))
        # Also fill if tags block is empty or only has TODO
        if not has_todo_tags:
            # Check for tags block that has only a single existing tag we should keep
            skipped += 1
            continue

        headword = path.stem[3:-4].replace("-", " ")
        pos_m = re.search(r"^pos:\s*(\S+)", txt, re.M)
        pos = pos_m.group(1) if pos_m else "noun"

        tags = get_tags(headword, pos)
        tags_yaml = "\n".join(f"  - {t}" for t in tags)
        new_tags_block = f"tags:\n{tags_yaml}"

        # Replace "tags:\n  - TODO" or "tags: TODO"
        new_txt = re.sub(r"^tags:\s*\n\s*-\s*TODO", new_tags_block, txt, flags=re.M)
        new_txt = re.sub(r"^tags:\s*TODO", new_tags_block, new_txt, flags=re.M)

        if new_txt != txt:
            path.write_text(new_txt, encoding="utf-8")
            updated += 1

    print(f"Done. Updated: {updated}, Already set / skipped: {skipped}")


if __name__ == "__main__":
    main()
