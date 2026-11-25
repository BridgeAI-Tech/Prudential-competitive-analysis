# Architecture

The system has three layers: a **data pipeline** that collects and classifies public evidence, a **report builder**
that turns the evidence into an interactive page and a chat knowledge base, and a small **web app** that serves the
page and the chat behind a login.

```
                ┌──────────────────────────── 1. DATA PIPELINE (pipeline/) ────────────────────────────┐
 Public sources │  collectors/ + tools/          collect.py          classify.py          build.py         │
 newsrooms,     │  newsrooms, media feeds,  ──►  raw records   ──►  classify,       ──►  SQLite store      │
 news, social,  │  social, ads, apps, maps,      (jsonl) +          normalise,          (ci.db) +          │
 ads, apps,     │  filings, captures,            evidence           noise rules,        analytical         │
 filings, maps  │  mainland social               snapshots          de-duplicate        dataset            │
                └──────────────────────────────────────────────────────────────────────────┬──────────────┘
                                                                                           │
                ┌──────────────────────────── 2. REPORT BUILDER (report_builder/) ─────────▼──────────────┐
                │  build.py reads the dataset + data builders (social_meta, linkedin, investors, maps,     │
                │  cnsoc, deep) + report content, then writes ONE self-contained page:                     │
                │     design layers (CSS)  +  page content  +  data (JS constants)  +  page modules (JS)   │
                │  and a text-only knowledge base (corpus.md) for the chat.                                │
                └──────────────────────────────────────────────────────────────────────────┬──────────────┘
                                                                                           │
                ┌──────────────────────────── 3. WEB APP (app/, Vercel) ───────────────────▼──────────────┐
                │  api/index.py: login (HMAC cookie), security headers, protected report and media,       │
                │  narration clips, chat route  ──►  backend.py: answers only from corpus.md, with links   │
                └─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Data pipeline

| Step | Code | What it does | Output |
|---|---|---|---|
| Collect | `pipeline/pipeline/collect.py`, `collectors/*`, `tools/*` | Pulls records from each source; saves raw responses and page snapshots | `data/raw/*.jsonl`, `data/evidence/<date>/*.html` |
| Classify | `pipeline/pipeline/classify.py` | Assigns module, activity type, product category, theme and capability using the EN + Traditional Chinese taxonomy; applies noise rules; clusters syndicated coverage | classified records |
| Build | `pipeline/pipeline/build.py` | Loads the SQLite store and exports the analytical dataset | `data/ci.db` |

Configuration lives in `pipeline/pipeline/config/`:

- `companies.json` – the company master: domains, verified social accounts, apps (shared across clients)
- `taxonomy.json` – keyword taxonomy in English and Traditional Chinese
- `client_prudential.json` – the client lens: reference brand, competitor set, brand colours

See [DATA_PIPELINE.md](DATA_PIPELINE.md) and [pipeline/docs/TECHNICAL_DOCUMENTATION.md](../pipeline/docs/TECHNICAL_DOCUMENTATION.md).

---

## 2. Report builder

`report_builder/build.py` produces a single HTML page plus the chat knowledge base:

1. **Data.** Reads the analytical dataset and runs the data builders:
   `social_meta.py` (Facebook and Instagram statistics), `linkedin.py` (company posts), `investors.py` (share prices
   and HK capital data), `maps.py` (physical footprint), `cnsoc.py` (Little Red Book and WeChat conversation) and
   `deep.py` (computed findings across social, ads, video and search). All numbers are computed, none typed by hand.
2. **Page.** Combines the base template's head, chat panel and interactions with the report content, then injects the
   design layers (CSS) into `<head>` and the page modules (JS) after the data, in a fixed order (see
   [REPORT_MODULES.md](REPORT_MODULES.md)).
3. **Knowledge base.** Writes `private/corpus.md`, a text-only knowledge base for the chat, after stripping personal
   contact details (emails and phone numbers) and asserting none remain.
4. **Tour.** `build_tour.py` adds a narrated guided tour (recorded clips if present, browser voice otherwise).

Quality tools: `check_links.py` (sources in the content) and `check_all_links.py` (every link on the built page).

### Inputs the builder expects

These are private and **not in this repository**. The builder reads them from a project folder laid out as follows:

| Path (relative to the project root) | What it is |
|---|---|
| `vercel_report/` | The Bridge AI base report template (head, chat panel, interactions) |
| `report_app/prudential/body.html` | Report content: the written analysis and page structure |
| `report_app/prudential/data.js` | Report data: insights, evidence rows and chart data |
| `report_app/prudential/dashboard.js` | Dashboard logic and narrative for the module pages |
| `report_app/prudential/media/` | Images: page captures, ad creatives, news images, video thumbnails |
| `Prudential/ci-monitor/data/ci.db` and `pipeline/insights/` | The analytical dataset and analyst-authored insights |
| `Prudential/_report_work/`, `apify_raw/`, `hk_investor_data/`, `hk_maps/`, `manulife_newsroom/` | Supporting collected data |

The builder writes the deployable app to `vercel_prudential_report/`.

---

## 3. Web app

| File | Responsibility |
|---|---|
| `app/api/index.py` | Entry point. Login page and `POST /api/login`; an HMAC-signed, HttpOnly, Secure cookie derived from the credentials; fails closed if credentials are not configured; security headers (no-store, nosniff, DENY framing, no-referrer, noindex); serves `/` (report), `/media/*`, `/narration/*` and `/api/status` only to signed-in users; `POST /api/ask` for the chat with request validation |
| `app/backend.py` | Chat backend. Loads `private/corpus.md`, retrieves the most relevant passages and streams answers that cite only URLs present in the knowledge base |
| `app/private/login.template.html` | Sign-in page (logos injected at start-up) |
| `app/vercel.json` | Routes every path to the Python function |

Credentials and the model API key are **Vercel environment variables**, never files: `REPORT_USERNAME`,
`REPORT_PASSWORD`, `GEMINI_API_KEY`. See [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Not included

An earlier prototype dashboard (Next.js, `ci-monitor/web/`) is not included: it is superseded by the report builder and
web app above, and it bundles collected data.
