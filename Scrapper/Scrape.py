from playwright.sync_api import sync_playwright
import time
import os

PROFILE_PATH = r"C:\Users\au712008\AppData\Local\Microsoft\Edge\User Data"
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE_URL = "https://saalangtsaagodt.ibog.gyldendal.dk/?id="

PAGE_IDS = list(range(154, 266))

OUTPUT_DIR = "ibog_pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def wait_for_content(page):
    """
    Waits for the actual article content to load.
    Systime iBog pages always render content blocks with IDs like sec1, sec2, etc.
    """
    try:
        page.wait_for_selector("[id^='sec']", timeout=10000)
    except:
        # fallback: wait for any heading
        page.wait_for_selector("h1, h2, h3", timeout=10000)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        PROFILE_PATH,
        headless=False,
        executable_path=EDGE_EXE,
        args=["--profile-directory=Profile 1"]
    )

    page = browser.new_page()

    # Step 1: Login manually
    first_url = f"{BASE_URL}{PAGE_IDS[0]}"
    print(f"Opening first page for login: {first_url}")
    page.goto(first_url)

    print("\n🔵 Log in manually in the browser window.")
    input("Press ENTER here ONLY after you see the book page loaded.\n")

    # Step 2: Scrape all pages
    for pid in PAGE_IDS:
        url = f"{BASE_URL}{pid}"
        print(f"\nFetching {url}...")

        page.goto(url)

        # Wait for dynamic content to load
        wait_for_content(page)

        # Extract only the main article content
        text = page.inner_text("main")

        # Save to file
        with open(f"{OUTPUT_DIR}/page_{pid}.txt", "w", encoding="utf-8") as f:
            f.write(text)

        print(f"✔ Saved page_{pid}.txt")

    browser.close()
