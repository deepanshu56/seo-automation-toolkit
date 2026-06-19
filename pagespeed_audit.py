#!/usr/bin/env python3
"""
pagespeed_audit.py — bulk Core Web Vitals & performance audit.

Runs a list of URLs through the Google PageSpeed Insights API (Lighthouse)
and writes a tidy CSV with the metrics that actually matter for SEO: the
three Core Web Vitals (LCP, CLS, INP), plus FCP, TTFB and the overall
performance score. Where Google has enough real-user data, the CrUX field
values are included alongside the lab numbers.

Usage:
    python pagespeed_audit.py --urls urls.txt --strategy mobile
    python pagespeed_audit.py --urls urls.txt --out output/cwv.csv --key YOUR_KEY

The API key is read from --key, then the PAGESPEED_API_KEY env var. An
unauthenticated call works for light testing but is heavily rate-limited.

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

from common import read_urls, write_csv, progress

API_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _lab_metric(audits: dict, key: str) -> float | None:
    """Pull a numeric lab value from a Lighthouse audit, if present."""
    audit = audits.get(key) or {}
    return audit.get("numericValue")


def _field_metric(loading_experience: dict, key: str) -> int | None:
    """Pull a CrUX field percentile (real-user data) if Google has it."""
    metrics = (loading_experience or {}).get("metrics", {})
    metric = metrics.get(key) or {}
    return metric.get("percentile")


def audit_url(url: str, api_key: str | None, strategy: str) -> dict:
    """Call PageSpeed Insights for one URL and flatten the response to a row."""
    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    if api_key:
        params["key"] = api_key

    row: dict = {"url": url, "strategy": strategy}
    try:
        resp = requests.get(API_ENDPOINT, params=params, timeout=60)
    except requests.RequestException as exc:
        row["error"] = f"request_failed: {exc}"
        return row

    if resp.status_code != 200:
        # Surface the API's own error message — usually quota or a bad URL.
        detail = resp.json().get("error", {}).get("message", resp.text[:120])
        row["error"] = f"api_{resp.status_code}: {detail}"
        return row

    data = resp.json()
    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})

    # Overall performance score is 0-1 in the API; present it as 0-100.
    score = (lighthouse.get("categories", {}).get("performance", {}) or {}).get("score")
    row["performance_score"] = round(score * 100) if score is not None else None

    # Lab data (Lighthouse) — milliseconds, except CLS which is unitless.
    row["lab_LCP_ms"] = _round(_lab_metric(audits, "largest-contentful-paint"))
    row["lab_CLS"] = _round(_lab_metric(audits, "cumulative-layout-shift"), 3)
    row["lab_TBT_ms"] = _round(_lab_metric(audits, "total-blocking-time"))
    row["lab_FCP_ms"] = _round(_lab_metric(audits, "first-contentful-paint"))
    row["lab_SI_ms"] = _round(_lab_metric(audits, "speed-index"))

    # Field data (CrUX real users) — only present for pages with enough traffic.
    field = data.get("loadingExperience", {})
    row["field_LCP_ms"] = _field_metric(field, "LARGEST_CONTENTFUL_PAINT_MS")
    row["field_INP_ms"] = _field_metric(field, "INTERACTION_TO_NEXT_PAINT")
    row["field_CLS"] = _crux_cls(_field_metric(field, "CUMULATIVE_LAYOUT_SHIFT_SCORE"))
    row["field_verdict"] = field.get("overall_category")  # FAST / AVERAGE / SLOW

    return row


def _round(value, ndigits: int = 0):
    if value is None:
        return None
    return round(value, ndigits) if ndigits else round(value)


def _crux_cls(percentile):
    """CrUX returns CLS*100 as an int; convert back to the real 0-x.xx scale."""
    return None if percentile is None else round(percentile / 100, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk Core Web Vitals audit via PageSpeed Insights.")
    parser.add_argument("--urls", required=True, help="Text file, one URL per line.")
    parser.add_argument("--out", default="output/cwv_audit.csv", help="CSV output path.")
    parser.add_argument("--strategy", choices=["mobile", "desktop"], default="mobile")
    parser.add_argument("--key", default=None, help="PageSpeed API key (else PAGESPEED_API_KEY env).")
    args = parser.parse_args()

    api_key = args.key or os.getenv("PAGESPEED_API_KEY")
    if not api_key:
        print("Warning: no API key supplied; running unauthenticated and rate-limited.",
              file=sys.stderr)

    urls = read_urls(args.urls)
    rows = [audit_url(u, api_key, args.strategy) for u in progress(urls, "PSI")]
    write_csv(rows, args.out)

    failed = [r for r in rows if r.get("error")]
    if failed:
        print(f"{len(failed)}/{len(rows)} URLs returned an error (see 'error' column).",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
