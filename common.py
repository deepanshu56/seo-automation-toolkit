"""
common.py — shared helpers for the SEO Automation Toolkit.

Small, dependency-light utilities reused across the scripts: reading URL
lists, polite HTTP fetching with a real User-Agent and retries, and writing
results to CSV. Keeping these in one place means each script stays focused on
its own SEO logic.

Author: Deepanshu Sharma
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Iterable

import requests

# A descriptive User-Agent is good manners and avoids being treated as a bot.
USER_AGENT = (
    "SEO-Automation-Toolkit/1.0 (+https://github.com/deepanshu56/seo-automation-toolkit)"
)


def read_urls(path: str) -> list[str]:
    """Read a newline-separated list of URLs, ignoring blanks and # comments."""
    urls: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    if not urls:
        raise ValueError(f"No URLs found in {path}")
    return urls


def fetch(
    url: str,
    *,
    timeout: int = 20,
    retries: int = 2,
    backoff: float = 1.5,
    session: requests.Session | None = None,
) -> requests.Response:
    """GET a URL with a real User-Agent and simple exponential-backoff retries.

    Raises requests.RequestException if every attempt fails, so callers can
    record the failure per-URL instead of crashing the whole run.
    """
    sess = session or requests
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = sess.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
            )
            return resp
        except requests.RequestException as exc:  # network/timeout/DNS
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff ** attempt)
    raise last_exc  # type: ignore[misc]


def write_csv(rows: list[dict], path: str) -> None:
    """Write a list of dicts to CSV. Columns are the union of all keys."""
    if not rows:
        print("No rows to write.", file=sys.stderr)
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


def progress(items: Iterable, label: str = "Processing"):
    """Tiny generator wrapper that prints 'label i/n' to stderr as it goes."""
    items = list(items)
    total = len(items)
    for i, item in enumerate(items, 1):
        print(f"{label} {i}/{total}", file=sys.stderr)
        yield item
