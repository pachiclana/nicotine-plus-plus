#!/usr/bin/env python3
"""Scrape a public Spotify playlist into the track-list JSON used by batch_download.py.

Usage: python scrape_playlist.py <playlist_url_or_id> <out.json>
Headless Chromium via Playwright; no login needed for public playlists.
"""
import json
import re
import sys
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

COLLECT_JS = """(() => {
  const rows = document.querySelectorAll("[data-testid$='list']:not([data-testid='recommended-track'] *) > div:nth-of-type(2) [role='row']");
  const out = [];
  rows.forEach(row => { try {
    const t = row.querySelector("div[dir='auto']");
    const al = row.querySelector("div > div:nth-of-type(3) > span");
    const arts = [...row.querySelectorAll("div > div:nth-of-type(2) > div > span.standalone-ellipsis-one-line a")].map(a => a.textContent);
    if (t) out.push({idx:+row.getAttribute("aria-rowindex"), title:t.textContent, album:al?al.textContent:"", artist:arts});
  } catch(e) {} });
  const last = rows.length ? +rows[rows.length-1].getAttribute("aria-rowindex") : 0;
  return JSON.stringify({last:last, rows:out});
})()"""

SCROLL_JS = """(() => { const r=document.querySelector("[data-testid$='list']:not([data-testid='recommended-track'] *) > div:nth-of-type(2) [role='row']:last-of-type"); if(r) r.scrollIntoView({block:'end'}); })()"""


def playlist_url(s):
    if s.startswith("http"):
        return s.split("?")[0]
    return f"https://open.spotify.com/playlist/{s}"


def scrape(url, out_path, headless=True):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(playlist_url(url), wait_until="domcontentloaded")
        page.wait_for_selector("[data-testid$='list']:not([data-testid='recommended-track'] *):not(svg)", timeout=30000)
        time.sleep(3)
        total = int(page.get_attribute(
            "[data-testid$='list']:not([data-testid='recommended-track'] *):not(svg)", "aria-rowcount"))
        page.evaluate("document.querySelector('main').scrollTo(0,0)")
        time.sleep(2)

        seen = {}
        for _ in range(2000):
            d = json.loads(page.evaluate(COLLECT_JS))
            for r in d["rows"]:
                seen[r["idx"]] = {k: v for k, v in r.items() if k != "idx"}
            if d["last"] >= total and len(seen) >= total - 1:
                break
            page.evaluate(SCROLL_JS)
            time.sleep(0.6)
        browser.close()

    tracks = [seen[i] for i in sorted(seen) if i > 1]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=1)
    return len(tracks), total - 1


def main():
    if len(sys.argv) != 3:
        print(__doc__); return 1
    n, total = scrape(sys.argv[1], sys.argv[2])
    print(f"scraped {n}/{total} tracks -> {sys.argv[2]}")
    return 0 if n == total else 2


if __name__ == "__main__":
    sys.exit(main())
