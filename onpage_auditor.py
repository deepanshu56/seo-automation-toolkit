#!/usr/bin/env python3
"""
onpage_auditor.py — crawl a URL list and audit on-page SEO elements.

For each URL it extracts the elements that on-page SEO actually turns on —
title, meta description, canonical, H1/H2 structure, word count, indexability
and Open Graph presence — then flags the common problems (missing or
over-length titles/descriptions, missing or multiple H1s, thin content,
noindex). The result is a single CSV you can sort by 'issues' to prioritise.

Usage:
    python onpage_auditor.py --urls urls.txt
    python onpage_auditor.py --urls urls.txt --out output/onpage.csv

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import sys

from bs4 import BeautifulSoup

from common import read_urls, fetch, write_csv, progress

# Widely-cited pixel-safe limits, expressed here as character bounds.
TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 70, 160
THIN_CONTENT_WORDS = 300


def audit(url: str) -> dict:
    """Fetch one URL and return a row of on-page facts plus an 'issues' list."""
    row: dict = {"url": url}
    try:
        resp = fetch(url)
    except Exception as exc:
        row.update(status="ERR", issues=f"request_failed: {exc}")
        return row

    row["status"] = resp.status_code
    if "text/html" not in resp.headers.get("Content-Type", ""):
        row["issues"] = "not_html"
        return row

    soup = BeautifulSoup(resp.text, "html.parser")

    title = (soup.title.string or "").strip() if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
    description = (desc_tag.get("content", "").strip() if desc_tag else "")
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = soup.find_all("h2")
    canonical_tag = soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""

    robots_tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    noindex = bool(robots_tag and "noindex" in robots_tag.get("content", "").lower())

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    word_count = len(soup.get_text(" ", strip=True).split())

    row["title"] = title
    row["title_len"] = len(title)
    row["meta_description"] = description
    row["desc_len"] = len(description)
    row["h1"] = h1s[0] if h1s else ""
    row["h1_count"] = len(h1s)
    row["h2_count"] = len(h2s)
    row["word_count"] = word_count
    row["canonical"] = canonical
    row["noindex"] = noindex
    row["has_og"] = bool(soup.find("meta", attrs={"property": lambda v: v and v.startswith("og:")}))

    # Build a human-readable issue list — this is what you act on.
    issues: list[str] = []
    if not title:
        issues.append("missing_title")
    elif not (TITLE_MIN <= len(title) <= TITLE_MAX):
        issues.append("title_length")
    if not description:
        issues.append("missing_description")
    elif not (DESC_MIN <= len(description) <= DESC_MAX):
        issues.append("description_length")
    if len(h1s) == 0:
        issues.append("missing_h1")
    elif len(h1s) > 1:
        issues.append("multiple_h1")
    if word_count < THIN_CONTENT_WORDS:
        issues.append("thin_content")
    if noindex:
        issues.append("noindex")
    if resp.status_code != 200:
        issues.append(f"status_{resp.status_code}")
    row["issues"] = ", ".join(issues) or "ok"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk on-page SEO audit.")
    parser.add_argument("--urls", required=True, help="Text file, one URL per line.")
    parser.add_argument("--out", default="output/onpage_audit.csv")
    args = parser.parse_args()

    urls = read_urls(args.urls)
    rows = [audit(u) for u in progress(urls, "Audit")]
    write_csv(rows, args.out)

    flagged = [r for r in rows if r.get("issues") not in ("ok", None)]
    print(f"{len(flagged)}/{len(rows)} URLs have on-page issues.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
