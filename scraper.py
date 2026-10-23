"""
Resilient Dynamic-Site Scraper (beginner mini project)

Shows three things:
1. Dynamic-site automation : Playwright loads a JavaScript-rendered page.
2. Polite anti-bot handling: robots.txt check, random delays, realistic browser
                             settings, retries with backoff, HTTP 403/429 handling.
3. Script maintenance      : selectors live in config.json with fallbacks, warnings
                             are logged when a selector breaks, and a health check
                             tells you when the site structure has probably changed.

Practice site: https://quotes.toscrape.com/js/  (built for scraping practice)
"""
import json
import logging
import random
import sys
import time
from datetime import datetime
from urllib import robotparser

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("scraper.log", encoding="utf-8"), logging.StreamHandler()],
)


def load_config(path="config.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- Anti-bot (polite scraping) helpers ----------
def allowed_by_robots(robots_url, url):
    """Check robots.txt before scraping. If it cannot be read, we allow."""
    try:
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception as e:
        logging.warning("Could not read robots.txt (%s). Continuing carefully.", e)
        return True


def polite_sleep(cfg):
    low, high = cfg["delay_range_seconds"]
    wait = random.uniform(low, high)
    logging.info("Sleeping %.1f seconds (random delay)", wait)
    time.sleep(wait)


def open_page(page, url, max_retries):
    """Open a URL with retries and exponential backoff. Returns True/False."""
    for attempt in range(1, max_retries + 1):
        try:
            response = page.goto(url, timeout=15000)
            if response and response.status in (403, 429, 503):
                raise RuntimeError(f"Blocked or rate-limited (HTTP {response.status})")
            return True
        except Exception as e:
            wait = 2 ** attempt + random.random()
            logging.warning("Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                            attempt, max_retries, url, e, wait)
            time.sleep(wait)
    logging.error("Giving up on %s after %d attempts", url, max_retries)
    return False


# ---------- Maintenance helpers (selector fallbacks) ----------
def find_items(page, selectors):
    """Try each selector in order. Warn if the main one fails (site changed!)."""
    for i, sel in enumerate(selectors):
        try:
            page.wait_for_selector(sel, timeout=5000)  # wait for JavaScript to render
            if i > 0:
                logging.warning("MAINTENANCE: primary selector failed, used fallback '%s'. "
                                "Update config.json.", sel)
            return page.locator(sel).all()
        except PlaywrightTimeoutError:
            logging.warning("Selector not found: '%s'", sel)
    return []


def get_text(card, selectors):
    for i, sel in enumerate(selectors):
        loc = card.locator(sel)
        if loc.count() > 0:
            if i > 0:
                logging.warning("MAINTENANCE: field selector fallback used: '%s'", sel)
            return loc.first.inner_text().strip()
    return None


def get_all_texts(card, selectors):
    for sel in selectors:
        loc = card.locator(sel)
        if loc.count() > 0:
            return [t.strip() for t in loc.all_inner_texts()]
    return []


# ---------- Health check ----------
def health_check(rows):
    """Tell the developer if the scraper is probably broken."""
    if not rows:
        logging.error("HEALTH CHECK FAILED: 0 records scraped. The site structure may have "
                      "changed. Inspect the page in DevTools and update config.json.")
        return False
    missing = sum(1 for r in rows if not r["quote"] or not r["author"])
    if missing / len(rows) > 0.2:
        logging.error("HEALTH CHECK FAILED: %d of %d records have missing fields.", missing, len(rows))
        return False
    logging.info("HEALTH CHECK OK: %d records, %d with missing fields.", len(rows), missing)
    return True


def main():
    cfg = load_config()
    sel = cfg["selectors"]
    first_url = cfg["start_url"].format(1)

    if not allowed_by_robots(cfg["robots_url"], first_url):
        logging.error("robots.txt does not allow scraping this URL. Stopping.")
        sys.exit(1)

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()

        for n in range(1, cfg["max_pages"] + 1):
            url = cfg["start_url"].format(n)
            logging.info("Scraping page %d: %s", n, url)

            if not open_page(page, url, cfg["max_retries"]):
                continue

            for card in find_items(page, sel["item"]):
                rows.append({
                    "quote": get_text(card, sel["text"]),
                    "author": get_text(card, sel["author"]),
                    "tags": ", ".join(get_all_texts(card, sel["tags"])),
                    "page": n,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

            polite_sleep(cfg)

        browser.close()

    healthy = health_check(rows)

    if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["quote"])
        df.to_csv(cfg["output_file"], index=False, encoding="utf-8-sig")
        logging.info("Saved %d records to %s", len(df), cfg["output_file"])

    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
