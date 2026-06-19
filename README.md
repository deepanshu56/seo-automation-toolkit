# SEO Automation Toolkit

A set of small, focused Python command-line tools that automate the repetitive
parts of technical and content SEO — crawl and indexation checks, Core Web
Vitals, on-page audits, content-gap and answer-engine analysis, and
duplicate/cannibalization detection.

Each script does one job, reads a plain list of URLs (or a Search Console
export), and writes a tidy CSV you can sort and act on. No paid SEO API is
required; the tools talk directly to free Google APIs and to the pages
themselves.

Built and maintained by **Deepanshu Sharma** ([portfolio](https://deepanshu56.github.io/portfolio) · [LinkedIn](https://linkedin.com/in/deepanshusharma)).

---

## What's inside

### Technical SEO
| Script | What it does |
| --- | --- |
| `pagespeed_audit.py` | Bulk **Core Web Vitals** (LCP, CLS, INP) + performance score via the PageSpeed Insights API — lab and real-user (CrUX) data. |
| `index_inspector.py` | Bulk **index-status** checks via the GSC URL Inspection API: coverage state, last crawl, robots verdict, Google-selected canonical. |
| `sitemap_validator.py` | Reads an XML **sitemap** (and sitemap indexes) and flags non-200s, redirects, `noindex`, and canonical mismatches. |
| `render_gap.py` | Compares raw HTML vs the **JS-rendered DOM** to surface content and links that only exist after JavaScript runs. |

### Content & on-page
| Script | What it does |
| --- | --- |
| `onpage_auditor.py` | Crawls a URL list and audits titles, meta descriptions, H1/H2, canonicals, word count and indexability, flagging each issue. |
| `tfidf_gap.py` | **TF-IDF content-gap** analysis: terms competitors weight that your page under-uses — a concrete brief for what to add. |
| `answerability.py` | Scores how directly a page answers a query (**AEO/GEO** signal): relevance + directness + position of the best passage. |

### Content integrity
| Script | What it does |
| --- | --- |
| `cannibalization.py` | Finds **keyword cannibalization** from a GSC export — queries where multiple URLs compete — ranked by traffic at stake. |
| `near_duplicate.py` | Detects **near-duplicate pages** by content similarity (cosine over TF-IDF); a free alternative to a paid duplicate-content API. |

`common.py` holds the shared helpers (HTTP fetching, CSV writing, URL-list reading) the other scripts import.

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/deepanshu56/seo-automation-toolkit.git
cd seo-automation-toolkit
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Copy the env template and add your keys (optional for some scripts)
cp .env.example .env

# 3. Run a script — sample inputs are included so they work out of the box
python onpage_auditor.py --urls urls.txt --out output/onpage.csv
python cannibalization.py --input gsc_export.csv
python answerability.py --query "what is dlp software" --text article.txt
```

Every script supports `-h/--help` with its full options.

---

## Examples

```bash
# Core Web Vitals for a list of URLs (mobile), needs a PageSpeed API key
python pagespeed_audit.py --urls urls.txt --strategy mobile

# Which of my URLs aren't cleanly indexed? (needs GSC OAuth client_secret.json)
python index_inspector.py --urls urls.txt --site "sc-domain:example.com"

# Validate an XML sitemap
python sitemap_validator.py --sitemap https://example.com/sitemap.xml --limit 500

# What terms do competitors cover that my page doesn't?
python tfidf_gap.py --page https://you.com/post --competitors "https://a.com/x,https://b.com/y"

# Any near-duplicate pages on my site?
python near_duplicate.py --urls urls.txt --threshold 0.8
```

---

## Project structure

```
seo-automation-toolkit/
├── common.py             # shared helpers (HTTP, CSV, URL-list reading)
├── pagespeed_audit.py    # Core Web Vitals via PageSpeed Insights API
├── index_inspector.py    # bulk index status via GSC URL Inspection API
├── sitemap_validator.py  # validate every URL in an XML sitemap
├── render_gap.py         # detect JS-dependent content (raw vs rendered)
├── onpage_auditor.py     # bulk on-page SEO audit
├── tfidf_gap.py          # TF-IDF content-gap vs competitors
├── answerability.py      # AEO answer-ability scoring
├── cannibalization.py    # keyword cannibalization from a GSC export
├── near_duplicate.py     # near-duplicate page detection
├── urls.txt              # sample input (URL list)
├── gsc_export.csv        # sample input (Search Console export)
├── article.txt           # sample input (page text)
├── requirements.txt
├── .env.example          # template for API keys (real .env is git-ignored)
└── LICENSE               # MIT
```

## Credentials & cost

- **`pagespeed_audit.py`** uses a free [PageSpeed Insights API key](https://developers.google.com/speed/docs/insights/v5/get-started).
- **`index_inspector.py`** uses OAuth (a Google Cloud "Desktop app" `client_secret.json`) with the Search Console API enabled.
- Everything else needs no keys — it fetches public pages or reads a CSV you export.
- Secrets live in `.env` / `client_secret.json`, both git-ignored. Nothing sensitive is committed.

## Roadmap

- Optional Looker Studio / Google Sheets export
- Async fetching for large URL sets
- A thin CLI wrapper to run several audits in one pass

## License

MIT © 2026 Deepanshu Sharma. Use it, fork it, improve it.
