#!/usr/bin/env python3
"""
cannibalization.py — detect keyword cannibalization from a GSC export.

Keyword cannibalization is when several of your own URLs compete for the same
query, splitting clicks and confusing Google about which page to rank. Feed
this a Search Console "Queries + Pages" export (CSV) and it returns every
query where two or more URLs pull meaningful impressions, ranked by how much
traffic is at stake — so you know which conflicts to consolidate first.

Expected columns (case-insensitive, common GSC export names handled):
    query / top queries, page / landing page, clicks, impressions, position

Usage:
    python cannibalization.py --input gsc_export.csv
    python cannibalization.py --input gsc_export.csv --min-impressions 50 --out output/cannibal.csv

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Map the various header names GSC / tools use onto canonical names.
COLUMN_ALIASES = {
    "query": ["query", "queries", "top queries", "search query", "keyword"],
    "page": ["page", "pages", "landing page", "url", "address"],
    "clicks": ["clicks", "url clicks"],
    "impressions": ["impressions", "impr.", "impr"],
    "position": ["position", "avg. pos", "average position", "avg position"],
}


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename incoming columns to canonical names; require query + page."""
    lower = {c.lower().strip(): c for c in df.columns}
    rename: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                rename[lower[alias]] = canonical
                break
    df = df.rename(columns=rename)
    missing = {"query", "page"} - set(df.columns)
    if missing:
        raise SystemExit(f"Export is missing required column(s): {', '.join(missing)}")
    for numeric in ("clicks", "impressions", "position"):
        if numeric not in df.columns:
            df[numeric] = 0
        df[numeric] = pd.to_numeric(df[numeric], errors="coerce").fillna(0)
    return df


def find_cannibalization(df: pd.DataFrame, min_impressions: int) -> list[dict]:
    """Return one row per query that has 2+ competing pages above the threshold."""
    results: list[dict] = []
    for query, group in df.groupby("query"):
        competing = group[group["impressions"] >= min_impressions]
        pages = competing["page"].nunique()
        if pages < 2:
            continue
        competing = competing.sort_values("impressions", ascending=False)
        results.append({
            "query": query,
            "competing_pages": pages,
            "total_clicks": int(competing["clicks"].sum()),
            "total_impressions": int(competing["impressions"].sum()),
            "best_position": round(competing["position"].min(), 1),
            # Pipe-separated so the detail stays readable inside one CSV cell.
            "urls": " | ".join(competing["page"].astype(str).tolist()),
        })
    # Biggest traffic conflicts first — that's your consolidation priority list.
    results.sort(key=lambda r: r["total_impressions"], reverse=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect keyword cannibalization from a GSC export.")
    parser.add_argument("--input", required=True, help="GSC Queries+Pages export (CSV).")
    parser.add_argument("--out", default="output/cannibalization.csv")
    parser.add_argument("--min-impressions", type=int, default=10,
                        help="Ignore a page for a query below this impression count.")
    args = parser.parse_args()

    df = normalise_columns(pd.read_csv(args.input))
    results = find_cannibalization(df, args.min_impressions)

    if not results:
        print("No cannibalization found above the impression threshold.", file=sys.stderr)
        return 0

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(args.out, index=False)
    print(f"Found {len(results)} cannibalized queries -> {args.out}")

    top = results[0]
    detail = f"{top['competing_pages']} pages, {top['total_impressions']} impressions"
    print(f"Top conflict: {top['query']} ({detail})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
