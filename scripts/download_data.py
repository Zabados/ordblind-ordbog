"""
Step 0 — Download raw data files needed by the pipeline.

Run this first:
    python scripts/download_data.py

Downloads automatically:
  - Tatoeba Danish sentences  (dan_sentences.tsv)
  - Tatoeba English sentences (eng_sentences.tsv)
  - Tatoeba translation links (links.csv)

Leipzig frequency data must be downloaded manually — instructions are
printed at the end of this script.
"""

import bz2
import tarfile
from pathlib import Path

import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"

# Tatoeba per-language files — much smaller than the full multilingual dump.
# Source: https://tatoeba.org/en/downloads
TATOEBA_DAN = (
    "https://downloads.tatoeba.org/exports/per_language/dan/dan_sentences.tsv.bz2"
)
TATOEBA_ENG = (
    "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2"
)
TATOEBA_LINKS = "https://downloads.tatoeba.org/exports/links.tar.bz2"


def download_file(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  Already exists: {dest.name} — skipping")
        return
    print(f"  Downloading {dest.name} ...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=65536):
            f.write(chunk)
            bar.update(len(chunk))


def decompress_bz2(src: Path, dest: Path) -> None:
    if dest.exists():
        print(f"  Already decompressed: {dest.name} — skipping")
        return
    print(f"  Decompressing {src.name} ...")
    with bz2.open(src, "rb") as f_in, open(dest, "wb") as f_out:
        while chunk := f_in.read(65536):
            f_out.write(chunk)


def extract_links_tar(src: Path, dest: Path) -> None:
    if dest.exists():
        print(f"  Already extracted: {dest.name} — skipping")
        return
    print(f"  Extracting links from {src.name} ...")
    with tarfile.open(src, "r:bz2") as tar:
        # Find the links file inside the archive regardless of exact name
        members = tar.getmembers()
        link_members = [m for m in members if "link" in m.name.lower()]
        if not link_members:
            raise FileNotFoundError(
                f"No links file found inside {src}. "
                f"Archive contains: {[m.name for m in members]}"
            )
        member = link_members[0]
        with tar.extractfile(member) as f_in, open(dest, "wb") as f_out:
            f_out.write(f_in.read())


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\n=== Tatoeba ===")
    dan_bz2 = DATA_DIR / "dan_sentences.tsv.bz2"
    eng_bz2 = DATA_DIR / "eng_sentences.tsv.bz2"
    links_bz2 = DATA_DIR / "links.tar.bz2"

    download_file(TATOEBA_DAN, dan_bz2)
    download_file(TATOEBA_ENG, eng_bz2)
    download_file(TATOEBA_LINKS, links_bz2)  # ~200-300 MB — takes a moment

    decompress_bz2(dan_bz2, DATA_DIR / "dan_sentences.tsv")
    decompress_bz2(eng_bz2, DATA_DIR / "eng_sentences.tsv")
    extract_links_tar(links_bz2, DATA_DIR / "links.csv")

    print("\n=== Leipzig (manual step) ===")
    print("1. Go to: https://wortschatz.uni-leipzig.de/en/download/Danish")
    print("2. Download the dataset:  Danish News 2020, 1M sentences")
    print("3. Extract the archive.")
    print(
        "4. Copy the file ending in '-words.txt' into the data/ folder and "
        "rename it to:  dan_news_2020_1M-words.txt"
    )
    print()
    print("Once that file is in place, run:")
    print("    python scripts/make_wordlist.py --test")
    print("    python scripts/pipeline.py --limit 50")


if __name__ == "__main__":
    main()
