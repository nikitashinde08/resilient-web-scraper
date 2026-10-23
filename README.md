# Resilient Dynamic-Site Scraper (Playwright)

A beginner mini project that scrapes a JavaScript-rendered website and is built so it
**survives problems and is easy to maintain**.

## What it demonstrates
| Skill | How it is shown in the code |
|---|---|
| Dynamic-site automation | Playwright opens `quotes.toscrape.com/js/` and waits for JavaScript to render the data |
| Anti-bot handling (polite) | robots.txt check, random delays, realistic user-agent/viewport, retries with backoff, HTTP 403/429 handling |
| Script maintenance | CSS selectors stored in `config.json` with fallback selectors, warnings in `scraper.log`, health check that fails loudly when the site changes |

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python -m playwright install chromium
```

## Run
```bash
python scraper.py
```
Output: `quotes.csv` and `scraper.log`.

## Try the maintenance demo (2 minutes)
1. Open `config.json` and change the first item selector from `div.quote` to `div.quote-old`.
2. Run `python scraper.py`. The log shows a MAINTENANCE warning and the scraper still works using the fallback selector.
3. Remove both item selectors (or make both wrong) and run again. The health check fails with "0 records scraped", telling you the site structure changed.

## Ethics
This project uses a practice site made for scraping. It does not bypass CAPTCHAs or protections.
Only scrape sites that allow it, respect robots.txt and terms of use, and avoid personal data.
