#!/usr/bin/env python3
"""
index_inspector.py — bulk index-status check via the GSC URL Inspection API.

Instead of pasting URLs into Search Console one at a time, this inspects a
whole list and writes a CSV showing, for each URL, whether Google has it
indexed, the coverage state (e.g. "Crawled - currently not indexed"), the
last crawl time, the robots.txt verdict and the Google-selected canonical.
That last batch of fields is exactly what you need to triage an indexation
problem at scale.

Auth: OAuth via a Google Cloud "Desktop app" client_secret.json with the
Search Console API enabled. First run opens a browser to authorise; the
token is cached in token.json for subsequent runs.

Usage:
    python index_inspector.py --urls urls.txt --site "https://example.com/"
    python index_inspector.py --urls urls.txt --site "sc-domain:example.com" --out output/index.csv

Author: Deepanshu Sharma
"""
from __future__ import annotations

import argparse
import os
import sys

from common import read_urls, write_csv, progress

# Read-only scope — this script never changes anything in Search Console.
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def get_service(client_secret: str, token_path: str = "token.json"):
    """Build an authenticated Search Console API client, caching the token."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - guidance only
        raise SystemExit(
            "Missing Google client libraries. Install with:\n"
            "  pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from exc

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return build("searchconsole", "v1", credentials=creds)


def inspect(service, site_url: str, page_url: str) -> dict:
    """Run one URL Inspection call and flatten the result to a CSV row."""
    row: dict = {"url": page_url}
    body = {"inspectionUrl": page_url, "siteUrl": site_url}
    try:
        result = service.urlInspection().index().inspect(body=body).execute()
    except Exception as exc:  # API errors are surfaced per-URL, not fatal.
        row["error"] = str(exc)[:200]
        return row

    index_status = result.get("inspectionResult", {}).get("indexStatusResult", {})
    row["verdict"] = index_status.get("verdict")               # PASS / FAIL / NEUTRAL
    row["coverage_state"] = index_status.get("coverageState")  # human-readable status
    row["robots_txt"] = index_status.get("robotsTxtState")
    row["indexing_allowed"] = index_status.get("indexingState")
    row["last_crawl"] = index_status.get("lastCrawlTime")
    row["google_canonical"] = index_status.get("googleCanonical")
    row["user_canonical"] = index_status.get("userCanonical")
    row["page_fetch"] = index_status.get("pageFetchState")
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk index-status check via GSC URL Inspection API.")
    parser.add_argument("--urls", required=True, help="Text file, one URL per line.")
    parser.add_argument("--site", required=True,
                        help='Property, e.g. "https://example.com/" or "sc-domain:example.com".')
    parser.add_argument("--out", default="output/index_status.csv")
    parser.add_argument("--client-secret", default=os.getenv("GSC_CLIENT_SECRET", "client_secret.json"))
    args = parser.parse_args()

    if not os.path.exists(args.client_secret):
        print(f"client_secret not found at '{args.client_secret}'. "
              "Download an OAuth Desktop-app client from Google Cloud Console.",
              file=sys.stderr)
        return 1

    service = get_service(args.client_secret)
    urls = read_urls(args.urls)
    rows = [inspect(service, args.site, u) for u in progress(urls, "Inspect")]
    write_csv(rows, args.out)

    not_indexed = [r for r in rows if r.get("verdict") and r["verdict"] != "PASS"]
    if not_indexed:
        print(f"{len(not_indexed)}/{len(rows)} URLs are not cleanly indexed — review them first.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
