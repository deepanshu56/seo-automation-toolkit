#!/usr/bin/env python3
"""
answerability.py — score how well a page answers a query (AEO / GEO signal).

Answer engines (AI Overviews, ChatGPT, Perplexity) lift passages that answer
a question directly and early. This script splits a page into passages,
finds the one most relevant to your target query, and combines three signals
into a 0-100 "answer-ability" score:

  * relevance  — semantic similarity of the best passage to the query
  * directness — is that passage a tight, quotable length (~40-60 words)?
  * position   — does the answer appear early on the page, not buried?

It is a from-scratch, lightweight implementation: TF-IDF + cosine similarity
by default (no model download). If sentence-transformers is installed it is
used automatically for stronger semantic matching.

Usage:
    python answerability.py --query "what is dlp software" --url https://you.com/dlp
    python answerability.py --query "how does sso work" --text article.txt

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import re
import sys

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from common import fetch


def load_text(url: str | None, text_path: str | None) -> str:
    """Get page text either from a URL or a local text file."""
    if text_path:
        from pathlib import Path
        return Path(text_path).read_text(encoding="utf-8")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fetch(url).text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def split_passages(text: str) -> list[str]:
    """Split into sentence-ish passages, dropping very short fragments."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.split()) >= 5]


def similarities(query: str, passages: list[str]) -> list[float]:
    """Cosine similarity of each passage to the query.

    Prefers sentence-transformers embeddings; falls back to TF-IDF so the
    script always runs without a model download.
    """
    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("all-MiniLM-L6-v2")
        q = model.encode(query, convert_to_tensor=True)
        ps = model.encode(passages, convert_to_tensor=True)
        return util.cos_sim(q, ps)[0].tolist()
    except Exception:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vec.fit_transform([query] + passages)
        return cosine_similarity(matrix[0:1], matrix[1:])[0].tolist()


def directness(passage: str) -> float:
    """1.0 for a tight, quotable answer (~40-60 words); tapers off either side."""
    n = len(passage.split())
    if 40 <= n <= 60:
        return 1.0
    if n < 40:
        return max(0.3, n / 40)
    return max(0.3, 60 / n)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a page's answer-ability for a query.")
    parser.add_argument("--query", required=True, help="The target question/query.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Page URL to score.")
    src.add_argument("--text", help="Local text file to score instead of a URL.")
    args = parser.parse_args()

    text = load_text(args.url, args.text)
    passages = split_passages(text)
    if not passages:
        print("No usable passages found on the page.", file=sys.stderr)
        return 1

    sims = similarities(args.query, passages)
    best_i = max(range(len(passages)), key=lambda i: sims[i])
    best_passage = passages[best_i]

    relevance = max(0.0, min(1.0, sims[best_i]))
    direct = directness(best_passage)
    # Position: 1.0 if the best answer is in the first 10% of passages, decaying after.
    position = max(0.2, 1.0 - (best_i / len(passages)))

    score = round(100 * (0.6 * relevance + 0.25 * direct + 0.15 * position))

    print(f"\nAnswer-ability score: {score}/100")
    print(f"  relevance : {relevance:.2f}")
    print(f"  directness: {direct:.2f}  ({len(best_passage.split())} words)")
    print(f"  position  : {position:.2f}  (passage {best_i + 1} of {len(passages)})")
    print(f"\nBest-matching passage:\n  \"{best_passage[:300]}\"")
    if score < 60:
        print("\nTip: add a concise 40-60 word answer to this query high on the page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
