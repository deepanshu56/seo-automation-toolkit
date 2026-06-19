#!/usr/bin/env python3
"""
sitemap_validator.py — validate every URL in an XML sitemap.

Fetches a sitemap (transparently following <sitemapindex> children), then
checks each listed URL for the problems that quietly waste crawl budget:
non-200 status codes, redirects (a sitemap should only list final URLs),
noindex directives, and canonicals that point somewhere else. The output
CSV flags each issue so you can hand engineering a clean fix list.

Usage:
    python sitemap_validator.py --sitemap https://example.com/sitemap.xml
    python sitemap_validator.py --sitemap https://example.com/sitemap_index.xml --out output/sitemap.csv --limit 500

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from common import fetch, write_csv, progress

# Sitemaps use this namespace; strip it so we can match plain <loc> tags.
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def collect_urls(sitemap_url: str, seen: set[str] | None = None) -> list[str]:
    """Return all page URLs in a sitemap, recursing into sitemap indexes."""
    seen = seen if seen is not None else set()
    if sitemap_url in seen:
        return []
    seen.add(sitemap_url)

    resp = fetch(sitemap_url)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    tag = root.tag.replace(SITEMAP_NS, "")
    locs = [el.text.strip() for el in root.iter(f"{SITEMAP_NS}loc") if el.text]

    if tag == "sitemapindex":
        # Each <loc> here is a child sitemap; recurse into all of them.
        urls: list[str] = []
        for child in locs:
            urls.extend(collect_urls(child, seen))
        return urls
    return locs  # a urlset: these are real page URLs


def check_url(url: str) -> dict:
    """Fetch one URL and flag status / redirect / noindex / canonical issues."""
    row: dict = {"url": url}
    try:
        resp = fetch(url)
    except Exception as exc:
        row.update(status="ERR", issues=f"request_failed: {exc}")
        return row

    row["status"] = resp.status_code
    redirected = bool(resp.history)
    row["redirected"] = redirected
    row["final_url"] = resp.url if redirected else ""

    noindex = False
    canonical = ""
    # Only parse HTML bodies; skip images/PDFs etc. listed in some sitemaps.
    if "text/html" in resp.headers.get("Content-Type", ""):
        soup = BeautifulSoup(resp.text, "html.parser")
        robots = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
        if robots and "noindex" in (robots.get("content", "").lower()):
            noindex = True
        link = soup.find("link", attrs={"rel": lambda v: v and "canonical" in v})
        if link and link.get("href"):
            canonical = link["href"].strip()
    # The X-Robots-Tag header can also carry noindex.
    if "noindex" in resp.headers.get("X-Robots-Tag", "").lower():
        noindex = True

    row["noindex"] = noindex
    row["canonical"] = canonical
    row["canonical_mismatch"] = bool(canonical) and canonical.rstrip("/") != url.rstrip("/")

    issues = []
    if row["status"] != 200:
        issues.append(f"status_{row['status']}")
    if redirected:
        issues.append("redirect")
    if noindex:
        issues.append("noindex")
    if row["canonical_mismatch"]:
        issues.append("canonical_mismatch")
    row["issues"] = ", ".join(issues) or "ok"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate every URL in an XML sitemap.")
    parser.add_argument("--sitemap", required=True, help="Sitemap or sitemap-index URL.")
    parser.add_argument("--out", default="output/sitemap_audit.csv")
    parser.add_argument("--limit", type=int, default=0, help="Cap URLs checked (0 = all).")
    args = parser.parse_args()

    print(f"Reading sitemap: {args.sitemap}", file=sys.stderr)
    urls = collect_urls(args.sitemap)
    if args.limit:
        urls = urls[: args.limit]
    print(f"Found {len(urls)} URLs to check.", file=sys.stderr)

    rows = [check_url(u) for u in progress(urls, "Check")]
    write_csv(rows, args.out)

    problems = [r for r in rows if r.get("issues") not in ("ok", None)]
    print(f"{len(problems)}/{len(rows)} URLs have at least one issue.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
