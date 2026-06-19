#!/usr/bin/env python3
"""
render_gap.py — find content that only exists after JavaScript runs.

Googlebot renders pages, but content that depends on client-side JS is
crawled less reliably and can be missed entirely. This script fetches the
*raw* HTML (what a simple crawler sees) and compares it to the *rendered*
DOM (what a browser sees after JS executes), then reports how much text and
how many links appear only after rendering. A large gap is a flag that key
content or internal links are JS-dependent.

Rendering uses Playwright if it is installed; otherwise the script still
reports the raw-HTML baseline and tells you how to enable rendering.

Setup for rendering:
    pip install playwright && playwright install chromium

Usage:
    python render_gap.py --urls urls.txt
    python render_gap.py --urls urls.txt --out output/render.csv

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import sys

from bs4 import BeautifulSoup

from common import read_urls, fetch, write_csv, progress


def extract(html: str, base_url: str) -> tuple[int, int]:
    """Return (visible_word_count, internal-ish link count) for an HTML string."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    words = len(soup.get_text(" ", strip=True).split())
    links = len([a for a in soup.find_all("a", href=True)
                 if not a["href"].startswith(("#", "mailto:", "tel:", "javascript:"))])
    return words, links


def render_html(url: str) -> str | None:
    """Return the rendered DOM via Playwright, or None if it isn't installed."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        html = page.content()
        browser.close()
        return html


def analyse(url: str, rendering_available: bool) -> dict:
    """Compare raw vs rendered for one URL."""
    row: dict = {"url": url}
    try:
        raw = fetch(url).text
    except Exception as exc:
        row["error"] = f"raw_fetch_failed: {exc}"
        return row

    raw_words, raw_links = extract(raw, url)
    row["raw_words"] = raw_words
    row["raw_links"] = raw_links

    if not rendering_available:
        row["rendered_words"] = None
        row["note"] = "rendering_disabled (install playwright to enable)"
        return row

    try:
        rendered = render_html(url)
    except Exception as exc:
        row["error"] = f"render_failed: {exc}"
        return row

    ren_words, ren_links = extract(rendered, url)
    row["rendered_words"] = ren_words
    row["rendered_links"] = ren_links
    # Share of content/links that appear ONLY after JS runs.
    row["words_js_only_pct"] = _pct(ren_words - raw_words, ren_words)
    row["links_js_only_pct"] = _pct(ren_links - raw_links, ren_links)
    row["flag"] = "JS-DEPENDENT" if (row["words_js_only_pct"] or 0) >= 25 else "ok"
    return row


def _pct(part: int, whole: int) -> int | None:
    if not whole:
        return None
    return max(0, round(100 * part / whole))


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect JS-dependent content (raw vs rendered).")
    parser.add_argument("--urls", required=True, help="Text file, one URL per line.")
    parser.add_argument("--out", default="output/render_gap.csv")
    args = parser.parse_args()

    # Probe once so we print a single clear message instead of one per URL.
    try:
        import playwright  # noqa: F401
        rendering_available = True
    except ImportError:
        rendering_available = False
        print("Playwright not installed — reporting raw-HTML baseline only. "
              "Enable rendering with: pip install playwright && playwright install chromium",
              file=sys.stderr)

    urls = read_urls(args.urls)
    rows = [analyse(u, rendering_available) for u in progress(urls, "Render")]
    write_csv(rows, args.out)

    flagged = [r for r in rows if r.get("flag") == "JS-DEPENDENT"]
    if flagged:
        print(f"{len(flagged)} URL(s) look JS-dependent (>=25% of content appears only after render).",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
