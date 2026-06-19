#!/usr/bin/env python3
"""
near_duplicate.py — find near-duplicate / thin-overlap pages on your own site.

Duplicate and near-duplicate body content dilutes relevance and can suppress
rankings. This fetches a list of your URLs, vectorises the visible text, and
reports every pair of pages whose content similarity is above a threshold —
a free, self-hosted alternative to a paid duplicate-content API. Use it to
catch boilerplate templates, syndicated copies, and pages that should be
merged or canonicalised.

Similarity is cosine over TF-IDF (character-aware, stop-words removed). 1.0
is identical text; ~0.8+ usually means "substantially the same page".

Usage:
    python near_duplicate.py --urls urls.txt --threshold 0.8
    python near_duplicate.py --urls urls.txt --out output/duplicates.csv

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import sys

from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from common import read_urls, fetch, write_csv, progress


def page_text(url: str) -> str:
    """Fetch and return visible body text, stripping chrome and scripts."""
    soup = BeautifulSoup(fetch(url).text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect near-duplicate pages by content similarity.")
    parser.add_argument("--urls", required=True, help="Text file, one URL per line.")
    parser.add_argument("--out", default="output/near_duplicates.csv")
    parser.add_argument("--threshold", type=float, default=0.8,
                        help="Report pairs with cosine similarity >= this (0-1).")
    args = parser.parse_args()

    urls = read_urls(args.urls)
    if len(urls) < 2:
        print("Need at least two URLs to compare.", file=sys.stderr)
        return 1

    texts, ok_urls = [], []
    for u in progress(urls, "Fetch"):
        try:
            body = page_text(u)
            if body.strip():
                texts.append(body)
                ok_urls.append(u)
        except Exception as exc:
            print(f"  skipping {u}: {exc}", file=sys.stderr)

    if len(texts) < 2:
        print("Could not fetch enough pages to compare.", file=sys.stderr)
        return 1

    matrix = TfidfVectorizer(stop_words="english").fit_transform(texts)
    sim = cosine_similarity(matrix)

    # Upper triangle only — each unordered pair once, no self-comparisons.
    rows = []
    for i in range(len(ok_urls)):
        for j in range(i + 1, len(ok_urls)):
            score = float(sim[i, j])
            if score >= args.threshold:
                rows.append({
                    "url_a": ok_urls[i],
                    "url_b": ok_urls[j],
                    "similarity": round(score, 3),
                })

    rows.sort(key=lambda r: r["similarity"], reverse=True)
    if rows:
        write_csv(rows, args.out)
        print(f"Found {len(rows)} near-duplicate pair(s) at threshold {args.threshold}.",
              file=sys.stderr)
    else:
        print(f"No pairs at or above similarity {args.threshold}. Try lowering --threshold.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
