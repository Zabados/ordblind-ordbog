"""
lookup_ordnet.py — fetch definitions from ordnet.dk using playwright.
Usage:  python scripts/lookup_ordnet.py <word>
"""
import sys
import re
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

def fetch_ordnet(word: str) -> None:
    url = f"https://ordnet.dk/ddo_en/dict?query={word}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Accept cookie banner if present
        try:
            page.click("text=Allow all cookies", timeout=3000)
            page.wait_for_timeout(500)
        except Exception:
            pass

        # Grab the main article text - try multiple selectors
        for selector in ["#id-artikel", ".artikel", "#content", "main", "body"]:
            try:
                article = page.locator(selector).first.inner_text(timeout=4000)
                break
            except Exception:
                continue
        else:
            article = ""

        browser.close()

    # Clean up whitespace
    lines = [l.strip() for l in article.splitlines() if l.strip()]
    # Print up to first 60 lines to keep it readable
    for line in lines[:60]:
        print(line)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/lookup_ordnet.py <word>")
        sys.exit(1)
    fetch_ordnet(sys.argv[1])
