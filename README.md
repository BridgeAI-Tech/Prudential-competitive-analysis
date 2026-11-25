# Prudential Competitive Analysis – Hong Kong

A competitive-intelligence monitor for **Prudential Hong Kong** against **AIA, Manulife and AXA**, covering the 12 months
**1 Nov 2025 – 31 Oct 2026**. It collects public evidence (newsrooms, news media, social media, ads, app stores,
filings, mainland social platforms), classifies it, and builds an interactive, password-protected web report with an
"Ask Intelligence" chat that answers only from the collected evidence.

> This repository holds the **code and documentation only**. The built report, the collected data, licensed data,
> media and credentials are kept private (see [docs/DATA_AND_PRIVACY.md](docs/DATA_AND_PRIVACY.md)).

---

## What the report covers

| Module | Question it answers | Main sources |
|---|---|---|
| 1 · Competitor activity | Who launched, partnered, campaigned or changed what, and when | Official newsrooms, HK news media, HKEX filings |
| 2 · Brand and campaigns | How each insurer shows up in ads, social media and video | Meta Ad Library, Google Ads Transparency, Facebook, Instagram, LinkedIn, Threads, YouTube |
| 3 · Products | Which products and propositions each insurer offers | Product pages, launches, health and critical-illness line-up |
| 4 · Digital and service | App quality and digital features | App Store and Google Play reviews, digital-feature audit |
| 5 · Distribution and talent (optional) | Footprint, branches and hiring | Google Maps listings, census reach, job data |
| 6 · Little Red Book (Xiaohongshu) | Mainland conversation about each insurer | Search-based post collection |
| 7 · WeChat | Mainland conversation about each insurer | Search-based post collection |

The report opens with a **Leadership Brief** and **Executive Summary**, then **Strengths, Gaps and Actions**, company
profiles, one page per module, supporting detail pages and an evidence explorer where every insight links to its
source records.

---

## Repository structure

```
.
├── pipeline/                 Data collection and processing (Python)
│   ├── pipeline/             collect.py → classify.py → build.py, collectors/, config/
│   ├── tools/                Stand-alone collectors and helpers (social, ads, apps, maps, translation, captures)
│   ├── docs/                 Detailed technical documentation of the pipeline
│   └── run_pipeline.ps1      Full refresh (Windows PowerShell)
├── report_builder/           Builds the interactive report page (Python + JavaScript + CSS)
│   ├── build.py              Main builder: assembles data, page, modules and the chat knowledge base
│   ├── *.py                  Data builders (social, LinkedIn, investors, maps, mainland social, deep findings)
│   ├── *.js                  Page modules (navigation, charts, cards, evidence explorer, galleries)
│   ├── *.css                 Design layers (theme, Stitch design system, interactive layer, final skin)
│   └── system_prompt.txt     Rules for the "Ask Intelligence" chat
├── app/                      The deployed web app (Vercel Python function)
│   ├── api/index.py          Login, security headers, protected report, media and chat routes
│   ├── backend.py            Chat backend: answers only from the knowledge base, with source links
│   └── private/login.template.html
└── docs/                     Architecture, modules, pipeline, deployment, data and privacy
```

---

## Quick start

**Requirements:** Python 3.11+, Windows PowerShell (for `run_pipeline.ps1`), and optionally Playwright with
Chromium for page captures (`pip install playwright && python -m playwright install chromium`).

1. **Configure credentials.** Copy `.env.example` to `.env` at the project root and fill in the keys you have.
   Never commit `.env`.
2. **Collect and process data.**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\pipeline\run_pipeline.ps1
   ```
3. **Build the report.** The builder expects the private inputs described in
   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#inputs-the-builder-expects) (report content, collected data, template).
   ```powershell
   python -I report_builder/build.py
   ```
4. **Run the app locally** with throwaway credentials, then open http://127.0.0.1:8765:
   ```powershell
   $env:REPORT_USERNAME="localtest"; $env:REPORT_PASSWORD="localtest-only"
   python -c "import sys; sys.path.insert(0, 'app'); from http.server import ThreadingHTTPServer; from api.index import handler; ThreadingHTTPServer(('127.0.0.1', 8765), handler).serve_forever()"
   ```
5. **Deploy** with the Vercel CLI from the built app folder – see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | End-to-end architecture, data flow, components and the inputs the builder expects |
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | Collection, classification, de-duplication and the analytical dataset |
| [docs/REPORT_MODULES.md](docs/REPORT_MODULES.md) | Every page module and design layer, in load order, and what it does |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Building, environment variables, deploying to Vercel and checking the live site |
| [docs/DATA_AND_PRIVACY.md](docs/DATA_AND_PRIVACY.md) | What is deliberately kept out of this repository, and why |
| [pipeline/docs/TECHNICAL_DOCUMENTATION.md](pipeline/docs/TECHNICAL_DOCUMENTATION.md) | Detailed pipeline reference: sources, schema, taxonomy, metrics |

---

## Principles

- **Evidence first.** Every insight, number and chart in the report traces back to collected source records, and every
  source link opens the original page.
- **Nothing invented.** Figures are computed from the data; the chat answers only from the knowledge base and cites
  its sources.
- **Public sources, respectfully collected.** No logins are bypassed and no bot protections are circumvented; sites
  that block automated access are recorded as such.
- **Privacy.** Personal contact details found in press releases are stripped before anything is built or published.
