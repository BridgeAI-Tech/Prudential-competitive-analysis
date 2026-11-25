# Prudential Competitive Intelligence Monitor — Hong Kong (POC)

Reference brand **Prudential Hong Kong**; competitors **AIA, Manulife, AXA**; static 12-month window **1 Nov 2025 – 31 Oct 2026** (brief v1).
Core scope: Modules 1–4 (activity, brand & campaigns, products, digital). Modules 5–7 are kept in the architecture as optional extensions.

## Layout

```
ci-monitor/
├─ pipeline/
│  ├─ config/companies.json        SHARED  Company Master (domains, verified social accounts, apps)
│  ├─ config/taxonomy.json         SHARED  EN + Traditional Chinese keyword taxonomy (activity, category, theme, capability)
│  ├─ config/client_prudential.json CLIENT  analytical lens (reference brand, competitor set, colours)
│  ├─ insights/prudential_hk.json  CLIENT  analyst-authored insights; each must resolve to evidence records
│  ├─ collectors/                  newsrooms · excel_imports · google_news · seed_extracts · social · apps · digital_features
│  ├─ collect.py                   stage 1–2: collect + extract  -> data/raw/*.jsonl, data/evidence/<date>/*.html
│  ├─ classify.py                  stage 3: classify, normalise, noise rules, de-duplicate/cluster syndicated coverage
│  └─ build.py                     stage 4–5: SQLite store (data/ci.db) + analytical dataset + dashboard export
├─ data/ci.db                      one database: shared intelligence tables + client tables (see schema in build.py)
└─ web/                            (earlier Next.js prototype, not included in this repository)
```

## Excel inputs (project folder `F:\Prudential\*.xlsx`)

Every workbook is read; the dashboard's *Coverage & method → Data files ingested* table accounts for each sheet.

| Workbook | Collector | Use |
|---|---|---|
| `Exa_news_data.xlsx`, `Google_News_news_data.xlsx`, `Tavily_news_data.xlsx` (sheet `all_records`) | `excel_imports` | M1–M5 observations; out-of-scope rows kept in `excluded_records` with the vendor reason |
| `news_announcements_data.xlsx`, `exa_data.xlsx`, `tavily_data.xlsx`, `google_news_rss_data.xlsx` | `seed_extracts` | legacy M1 seed (the three per-tool files are subsets; de-duplicated by URL) |
| `<Brand>_Hong_Kong_explorium_data.xlsx` | `social` (LinkedIn posts), `excel_imports` (news events, firmographics, workforce, employer ratings, tech stack, intent) | M2 posts, M1 events, M5 context |
| `Source_Validation_v0.1.xlsx` | `excel_imports` | source inventory, app inventory, social-account verification, metric availability |
| `prudential_hk_input.xlsx` | `excel_imports` | Company Master cross-check |
| `predictleads_data.xlsx` | — | **not used**: returned finmo.net / dca-architects.com, not the four insurers |

Explorium hierarchy/subsidiary sheets are not used (entity mismatches, e.g. Prudential HK parented to Prudential Financial).

## Run

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1          # full refresh
python pipeline/collect.py --only newsrooms,apps                      # partial collection
python pipeline/collect.py --only excel_imports,seed_extracts,social   # re-read the Excel files only (no network)
python pipeline/build.py                                              # re-classify + export only
cd web; npx next dev                                                  # local dashboard at http://localhost:3000
```

Credentials (read from the project `.env`, never logged): `APIFY_TOKEN` (Facebook, Instagram, Meta Ad Library), `GEMINI_API_KEY` (English summaries of Chinese records).

### Extra public sources (added 11 Nov 2026, no keys, no login)

Each collector runs standalone (writes `data/raw/<name>.jsonl` + a `*_coverage.json`) or via `collect.py --only <key>`;
then `build.py` re-classifies, de-duplicates and reloads `data/ci.db`. Needs `pip install yt-dlp pytrends playwright` (+ `python -m playwright install chromium`).

```powershell
python -I pipeline/collectors/youtube_public.py       # key youtube: 4 official HK channels + 12 HK-media searches (yt-dlp metadata only; ~30-60 min)
python -I pipeline/collectors/media_feeds.py          # key media_feeds: InsuranceAsia News HK feed, insuranceasia.com HK page, SCMP/RTHK RSS, extra Google News
python -I pipeline/collectors/manulife_archive.py     # key manulife_archive: Manulife newsroom via Internet Archive (live site 403 - not bypassed)
python -I pipeline/collectors/official_pages.py       # key official_pages: official-platform directories, Emma by AXA page, PRU /tc + AXA /zh newsrooms
python -I pipeline/collectors/ads_transparency.py     # key ad_library: Google Ads Transparency Center, region HK (headless Playwright)
python -I pipeline/collectors/context_stats.py        # key context_stats: HKFI monthly brief, MPFA digest, Google Trends (--no-trends to skip)
python -I pipeline/build.py                           # reload ci.db (always run after any collector)
# or: python pipeline/collect.py --only youtube,media_feeds,manulife_archive,official_pages,ad_library,context_stats; python pipeline/build.py
```

Schema additions (backward compatible; existing tables unchanged): observations gain `platform='youtube'` social posts
(metrics views/likes/comments/followers at capture) and Manulife `announcement`s from archive copies (`source_url` = original
manulife.com.hk URL, `evidence_ref` = web.archive.org URL). New reference tables: `ad_library` (one row per Google ad creative),
`official_accounts` (accounts listed on each insurer's official-platforms page), `channel_context` (YouTube subscribers at capture),
`context_stats` (industry statistics: source, period, metric, value, unit, url, page; `company_id` only when the source names the
insurer) and `context_coverage` (non-brand sources and skips). `source_coverage` gains rows per brand for every new source.
Not collected: Xiaohongshu (needs a user login; `tools/xhs_collect.py`), WeChat (content not public), TikTok (not in HK),
Threads posts (only AIA lists a profile), ia.org.hk (403), Google web-search pages, and the ICB annual report (robots.txt; download manually).

### Social, ads, translation and documentation (added 11 Nov 2026)

```powershell
python tools/apify_social.py                 # Facebook + Instagram posts/profiles, AIA Threads profile, Meta Ad Library (APIFY_TOKEN in ../../.env)
python tools/ingest_social.py                # load Facebook, Instagram, LinkedIn export posts (SOC-*) and Meta ads (ADM-*) into ci.db + fact_metrics + coverage
python tools/translate_zh.py                 # English summaries for Chinese records (GEMINI_API_KEY in ../../.env); cached in _report_work/translations.json
python ../../report_app/prudential/build.py  # rebuild the published report (run from the project root)
python tools/sync_insights.py                # copy the report's ranked insights into insights/prudential_hk.json and client_insights
python tools/make_tech_doc.py                # regenerate docs/TECHNICAL_DOCUMENTATION.md from the live database
python tools/hk_investor_collect.py          # HK company disclosures, HKEX filings (2378/1299/945), daily share prices -> ../hk_investor_data/
python tools/hkex_market_lists.py            # HKEX board-meeting, dividend and trading-arrangement lists (+ archived copies) -> ../hk_investor_data/hkex_market_lists/
python tools/manulife_newsroom_export.py     # Manulife HK newsroom from Internet Archive copies -> ../manulife_newsroom/
python tools/hk_maps_footprint.py            # Google Maps footprint (18 districts) + location reviews -> ../hk_maps/ (Apify; report section appears once footprint.json exists)
```
`pipeline/build.py` rebuilds ci.db from raw data, so run `ingest_social.py` and `translate_zh.py` again after it.
Full source inventory, field definitions and metric definitions: [docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md).

## Data model (shared vs client)

| Layer | Tables |
|---|---|
| Shared market intelligence | `companies`, `observations` (one row per announcement/article/post/app snapshot/review/web feature), `observation_modules`, `observation_tags`, `observation_metrics` (only metrics actually exposed — no zeros for missing), `source_coverage`, `excluded_records`, `fact_metrics` (Brand × Month × Module × Platform × Category × Metric, with `record_ids` for traceability) |
| Client lens | `clients`, `client_competitors`, `client_insights`, `client_insight_evidence` |

A second subscribing client adds a new `client_*.json` + insights file; shared observations are reused, never copied.

Each observation keeps: brand, module(s), activity type, category/theme tags, title, description, original content, language,
English summary (EN sources as published; Chinese records machine-summarised, status in `translation_status`), **publication date and capture timestamp separately**,
source name/category, original URL, evidence snapshot reference, HK-relevance level and basis, cluster id (syndication).

## Deploy to Vercel

```powershell
cd web
npx vercel link
npx vercel env add DASHBOARD_PASSWORD production
npx vercel --prod
```
The data is bundled at build time (run `pipeline/build.py` before deploying). Basic-auth middleware protects all routes and assets.

## Known constraints (POC)

* `manulife.com.hk` and `ia.org.hk` return HTTP 403 to automated requests — Manulife's newsroom is read from Internet Archive snapshots (`manulife_archive`; releases after the latest snapshot are missing); its website features remain uncovered.
* Facebook comment counts are missing on most posts (rate uses reactions + shares); Instagram does not expose shares (rate uses likes + comments); LinkedIn uses reactions + comments + reposts. Rates are compared within a platform only.
* Meta Ad Library keeps only active ads for HK, so ended ads are unavailable; weekly snapshots would build history. Spend is never estimated.
* App ratings/follower counts are point-in-time; trends accumulate from scheduled runs.
* Chinese records are retained in the original, with a machine-generated English summary (`translation_status='machine_summary'`).
* Classification is rule-based and auditable; edge cases can be mislabelled and are traceable to source.
