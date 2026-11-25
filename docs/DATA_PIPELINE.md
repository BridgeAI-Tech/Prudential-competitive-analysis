# Data pipeline

The pipeline turns public sources into a classified, de-duplicated evidence store. It lives in `pipeline/`.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File .\pipeline\run_pipeline.ps1          # full refresh
python pipeline/pipeline/collect.py --only newsrooms,apps                       # partial collection
python pipeline/pipeline/collect.py --only excel_imports,seed_extracts,social    # re-read Excel inputs only (no network)
python pipeline/pipeline/build.py                                               # re-classify and export only
```

## Stages

| Stage | Code | Details |
|---|---|---|
| 1–2 Collect and extract | `collect.py` + `collectors/` | Each collector writes `data/raw/<name>.jsonl` and a coverage file; page snapshots go to `data/evidence/<date>/` |
| 3 Classify | `classify.py` | Module, activity type, product category, theme and capability from `config/taxonomy.json` (EN + Traditional Chinese); noise rules; clustering of syndicated coverage |
| 4–5 Store and export | `build.py` | SQLite store `data/ci.db` (shared intelligence tables + client tables) and the analytical dataset |

## Collectors (`pipeline/pipeline/collectors/`)

| Collector | Source |
|---|---|
| `newsrooms.py` | Official insurer newsrooms |
| `media_feeds.py`, `google_news.py`, `hk_media_sites.py` | HK news media, RSS feeds and Google News |
| `manulife_archive.py` | Manulife newsroom via the Internet Archive (the live site blocks automated access; not bypassed) |
| `official_pages.py` | Official platform directories and newsrooms in other languages |
| `social.py`, `youtube_public.py` | Company social accounts and official YouTube channels |
| `ads_transparency.py` | Google Ads Transparency Center (region HK) |
| `apps.py`, `digital_features.py` | App Store / Google Play data and the digital-feature audit |
| `excel_imports.py`, `seed_extracts.py` | Structured Excel inputs from research tools |
| `context_stats.py` | Market context statistics |

## Tools (`pipeline/tools/`)

Stand-alone helpers, each runnable on its own: social collection (`apify_social.py`, `ingest_social.py`), Android
reviews, page and source captures (`capture_*`, `recapture_sites.py`, `collect_visuals.py`, `evidence_images.py`),
news images and their quality check, HKEX and investor data, IA market share, Google Maps footprint and areas,
newsroom scrapers, translation of Chinese records (`translate_zh.py`, `translate_titles.py`), source status, insight
syncing and the technical-document generator.

### Local-only inputs

`tools/scrape_prudential_newsroom.py` reads press-office contacts from `tools/media_contacts.local.json`
(`[["Name", "Phone", "Email"], ...]`), which is git-ignored, so that it can strip them from scraped releases. Create it
locally if you need that behaviour.

## Credentials

Read from the project `.env` and never logged: `APIFY_TOKEN` (Facebook, Instagram, Meta Ad Library, mainland
social), `GEMINI_API_KEY` (English summaries of Chinese records). See `.env.example`.

Full reference: [pipeline/docs/TECHNICAL_DOCUMENTATION.md](../pipeline/docs/TECHNICAL_DOCUMENTATION.md).
