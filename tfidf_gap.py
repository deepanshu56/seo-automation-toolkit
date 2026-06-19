#!/usr/bin/env python3
"""
tfidf_gap.py — TF-IDF content-gap analysis vs the pages you compete with.

Builds a TF-IDF model over your page plus the competitor pages currently
ranking for a query, then surfaces the terms and phrases (unigrams + bigrams)
that competitors weight heavily but your page barely uses. Those gaps are a
concrete, defensible brief for what to add to the page — not guesswork.

This is a from-scratch implementation built on scikit-learn's vectoriser;
it does not call any paid SEO API.

Usage:
    python tfidf_gap.py --page https://you.com/post --competitors comps.txt
    python tfidf_gap.py --page https://you.com/post \\
        --competitors "https://a.com/x,https://b.com/y" --top 25

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import os
import sys

from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer

from common import fetch, write_csv


def page_text(url: str) -> str:
    """Fetch a URL and return its visible text (scripts/styles stripped)."""
    resp = fetch(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def parse_competitors(value: str) -> list[str]:
    """Accept either a path to a URL list or a comma-separated string."""
    if os.path.exists(value):
        from common import read_urls
        return read_urls(value)
    return [u.strip() for u in value.split(",") if u.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="TF-IDF content-gap analysis vs competitors.")
    parser.add_argument("--page", required=True, help="Your URL (the page to improve).")
    parser.add_argument("--competitors", required=True,
                        help="Competitor URLs: a file path or comma-separated list.")
    parser.add_argument("--out", default="output/tfidf_gap.csv")
    parser.add_argument("--top", type=int, default=30, help="How many gap terms to return.")
    args = parser.parse_args()

    comp_urls = parse_competitors(args.competitors)
    if not comp_urls:
        print("No competitor URLs supplied.", file=sys.stderr)
        return 1

    print(f"Fetching your page + {len(comp_urls)} competitors...", file=sys.stderr)
    try:
        your_doc = page_text(args.page)
    except Exception as exc:
        print(f"Failed to fetch your page: {exc}", file=sys.stderr)
        return 1

    comp_docs, ok_urls = [], []
    for u in comp_urls:
        try:
            comp_docs.append(page_text(u))
            ok_urls.append(u)
        except Exception as exc:
            print(f"  skipping {u}: {exc}", file=sys.stderr)

    if not comp_docs:
        print("Could not fetch any competitor pages.", file=sys.stderr)
        return 1

    corpus = [your_doc] + comp_docs
    vectoriser = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z-]{2,}\b",  # words of 3+ letters
    )
    matrix = vectoriser.fit_transform(corpus)
    terms = vectoriser.get_feature_names_out()

    your_vec = matrix[0].toarray()[0]
    comp_matrix = matrix[1:]
    comp_mean = comp_matrix.mean(axis=0).A1  # average competitor weight per term

    # Gap = how much more competitors emphasise a term than you do.
    rows = []
    for i, term in enumerate(terms):
        gap = comp_mean[i] - your_vec[i]
        if gap <= 0:
            continue
        rows.append({
            "term": term,
            "competitor_avg_tfidf": round(float(comp_mean[i]), 4),
            "your_tfidf": round(float(your_vec[i]), 4),
            "gap": round(float(gap), 4),
            "on_your_page": "yes" if your_vec[i] > 0 else "no",
        })

    rows.sort(key=lambda r: r["gap"], reverse=True)
    rows = rows[: args.top]
    write_csv(rows, args.out)
    print(f"Top gap term: '{rows[0]['term']}'" if rows else "No gaps found.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
