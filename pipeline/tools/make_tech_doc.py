"""Generate docs/TECHNICAL_DOCUMENTATION.md (brief s3.1 source inventory, s12.1 technical documentation) from the live database.
Re-run after any collection so every count in the document matches ci.db."""
import json
import sqlite3
from pathlib import Path

CI = Path(__file__).resolve().parents[1]
con = sqlite3.connect(CI / "data" / "ci.db")
q = lambda s, *a: con.execute(s, a).fetchall()
one = lambda s, *a: (q(s, *a) or [[0]])[0][0]
tax = json.loads((CI / "pipeline" / "config" / "taxonomy.json").read_text(encoding="utf-8"))
BR = {"PRU_HK": "Prudential", "AIA_HK": "AIA", "MFC_HK": "Manulife", "AXA_HK": "AXA"}


def n(where):
    return f"{one(f'select count(*) from observations where {where}'):,}"


def by_brand(where):
    return ", ".join(f"{BR[c]} {k:,}" for c, k in q(f"select company_id, count(*) from observations where {where} group by 1 order by 1"))


N_TRENDS = one("select count(*) from context_stats where source like 'Google Trends%'")
N_CONTEXT = one("select count(*) from context_stats where source not like 'Google Trends%'")

N_LI_NEW = n("platform='linkedin' and record_id like 'SOC-%'")
N_LI_OLD = n("platform='linkedin' and record_id not like 'SOC-%'")
MFC_LATE = "company_id='MFC_HK' and publication_date>'2026-09-22' and publication_date<='2026-10-31'"
_hcf = CI.parent / "_report_work" / "health_ci_products.json"
_hci = json.loads(_hcf.read_text(encoding="utf-8")) if _hcf.exists() else {}
_hci_n = len(_hci.get("ci", [])) + len(_hci.get("med", []))
inv = [
    ("Official newsrooms and press releases (EN; Chinese editions checked)", "pipeline/collectors/newsrooms.py, official_pages.py; tools/scrape_prudential_newsroom.py",
     "Title, date, full text, URL, language", "Full 12-month window", "Manulife site returns HTTP 403 to automated requests: read from Internet Archive snapshots (manulife_archive.py); releases after the latest snapshot can be missing",
     n("record_type='announcement'"), "M1, M3, M4"),
    ("Official website content and product pages", "pipeline/collectors/digital_features.py, excel_imports.py (Exa / Tavily extracts)",
     "Page text, product names, features, URL", "Current pages (point in time)", "Manulife website blocked (403); features requiring policyholder login are out of scope",
     n("record_type in ('content_article','web_feature')"), "M3, M4"),
    ("Industry news and media (InsuranceAsia News, SCMP, RTHK, The Standard, Google News discovery)", "pipeline/collectors/media_feeds.py, google_news.py, excel_imports.py",
     "Headline, publisher, date, text or summary, URL", "Full window", "Labelled third-party coverage; Google News links resolved to the publisher where possible; syndicated copies clustered",
     n("record_type='news_article'"), "M1, M3, M5"),
    ("Named Hong Kong news, marketing and insurance publications (brief s5.6 list plus HK01, Hong Kong Economic Journal, Ming Pao, Sing Tao, AM730, HKET, Hong Kong Business, Marketing-Interactive, Campaign Asia, Dentsu)",
     "pipeline/collectors/hk_media_sites.py (Google News site: search per publication and brand, EN + ZH, quarter by quarter; campaign and health / critical-illness topic searches); tools/ingest_media_sites.py",
     "Headline, publisher, date, URL, query and search kind", "Full window (added 16 Nov 2026)",
     "Depends on Google News indexing of each title; paywalled titles give the headline only; stories already held from other searches are counted once (data/raw/hk_media_sites_coverage.json)",
     n("extra like '%hk_media_sites%'"), "M1, M2, M3"),
    ("Insurer product brochures and product pages (health and critical illness)", "Desk research of official documents, 16 Nov 2026 (Prudential/_report_work/health_ci_products.json)",
     "Plan, maximum cumulative payout, claims allowed, cancer cover, repeat claims, waiting periods, conditions, how it is marketed, brochure URL and page, verification status",
     "Current product versions", "Figures taken only from official brochures or product pages, each marked with how it was checked; Manulife's website blocks automated access, so figures not confirmed in an official document are marked; premiums not compared",
     f"{_hci_n} plans", "M3"),
    ("Facebook pages (official HK accounts)", "Apify actors facebook-posts-scraper + facebook-pages-scraper (tools/apify_social.py)",
     "Post text, date, URL, reactions, shares, comments (often missing), video flag, page followers", "Full window (posts back to 1 Nov 2025)",
     "Comment counts missing on most posts, so the Facebook rate uses reactions + shares; followers are capture-day only", n("platform='facebook'"), "M2"),
    ("Instagram accounts (official HK accounts; AIA from its official-platforms page)", "Apify actors instagram-post-scraper + instagram-profile-scraper",
     "Caption, date, URL, likes, comments, video views, type (image / carousel / video), followers", "Full window",
     "Shares not exposed; posts with hidden likes excluded from rates; collaboration posts owned by partners excluded", n("platform='instagram'"), "M2"),
    ("LinkedIn company pages", "LinkedIn company-posts export (Apify dataset, 11 Nov 2026), loaded by report_app/prudential/linkedin.py",
     "Post text, date, URL, reactions, comments, reposts, format, followers", "Full window", "Brand-authored originals only; reposts excluded; followers capture-day only",
     f"{N_LI_NEW} posts (plus {N_LI_OLD} records from an earlier licensed extract, kept for provenance)", "M2, M5"),
    ("YouTube official channels + HK-media search", "pipeline/collectors/youtube_public.py (public metadata); transcript datasets",
     "Title, date, URL, views, subscribers, duration", "Full window", "Views include paid ad plays; likes hidden on some videos", n("platform='youtube'"), "M2"),
    ("Meta Ad Library (Hong Kong)", "Apify actor facebook-ads-scraper, by Ad Library page id",
     "Ad text, creative format, start date, end/last-seen date, platforms, call to action, ad library URL", "Ads running on 11 Nov 2026 only",
     "The HK library lists only active ads, so ended ads cannot be retrieved; spend not disclosed (never estimated)", n("platform='meta_ads'"), "M2"),
    ("Google Ads Transparency Center (Hong Kong)", "pipeline/collectors/ads_transparency.py (Playwright, public pages)",
     "Advertiser, creative format, first / last shown, image or preview URL, landing URL", "Creatives shown in the window",
     "No spend or impressions; advertiser names verified per brand (table ad_library)", f"{one('select count(*) from ad_library'):,} (table ad_library)", "M2"),
    ("App stores (Apple App Store HK, Google Play HK)", "pipeline/collectors/apps.py",
     "App name, developer, version, update date, rating, rating count, release notes; written reviews (iOS via pipeline/collectors/apps.py, Android via tools/android_reviews.py)", "Point in time; iOS and Android reviews within the window",
     "Version history and download volumes not reliably available; Android reviews added 16 Nov 2026 for each main customer app (EN + zh-HK + zh-TW listings, de-duplicated, reviewer names not stored); ratings are signals, not satisfaction measures",
     n("record_type in ('app_snapshot','app_review')"), "M4"),
    ("Google Trends (HK)", "pipeline/collectors/context_stats.py", "Monthly search-interest index per brand name (English and Chinese)", "Full window",
     "Keyword not topic; relative within one comparison; not a measure of sales", f"{N_TRENDS:,} rows (context_stats)", "M2 context"),
    ("HKFI Monthly Brief, MPFA statistical digest", "pipeline/collectors/context_stats.py", "Awards, membership, MPF statistics", "Latest editions",
     "Context only; not attributed to a brand unless the source names it", f"{N_CONTEXT:,} rows (context_stats)", "Context"),
    ("Hong Kong company disclosures (risk-based capital disclosure statements, audited accounts)", "tools/hk_investor_collect.py (insurers' Hong Kong regulatory pages; robots.txt respected)",
     "Capital strength ratio, capital held, regulatory minimum, total assets", "FY2024 and FY2025", "Prudential (2 companies) and AXA collected; AIA's not found online; Manulife's site blocks automated downloads", "14 PDFs", "Context (M1)"),
    ("HKEX filings (Prudential 2378, AIA 1299, Manulife 945)", "tools/hk_investor_collect.py (HKEXnews title search)",
     "Date, title, category, PDF link; substantive filings downloaded", "1 Nov 2025 to 11 Nov 2026", "Routine returns (buy-back reports, monthly returns) listed only; AXA not listed in Hong Kong", "702 listed, 96 downloaded", "Context (M1)"),
    ("HKEX market lists (board meetings, dividends and entitlements, trading arrangements; Main Board and GEM)", "tools/hkex_market_lists.py (live pages plus Internet Archive copies)",
     "All rows; rows for the three listed insurers flagged", "Archived copies across the window plus 10 Nov 2026", "Pages show upcoming items only; history depends on archived copies", "about 2,400 rows", "Context"),
    ("Daily share prices (HK lines, London, Toronto, Paris, Hang Seng Index)", "tools/hk_investor_collect.py (public daily price feed)",
     "Close and volume per trading day", "1 Oct 2025 to 10 Nov 2026", "Group-level prices, not Hong Kong-only; context only", "7 series", "Context"),
    ("Manulife HK newsroom (EN, Chinese index checked)", "tools/manulife_newsroom_export.py (Internet Archive copies; live site 403 not bypassed)",
     "Date, title, lead, full text where archived", "1 Nov 2025 to the latest archived copy (22 Sep 2026; rechecked 16 Nov 2026, no newer copy)",
     f"Checked in a normal browser on 16 Nov 2026: the live newsroom lists no release from the period that the monitor lacks (in-period releases after 22 Sep: DBS partnership 28 Sep, My Flag Day 10 Oct). Other sources also cover this period: after 22 Sep 2026 the monitor holds "
     f"{n(MFC_LATE + ' and source_category=' + chr(39) + 'official' + chr(39))} manulife.com.hk pages, "
     f"{n(MFC_LATE + ' and source_category=' + chr(39) + 'media' + chr(39))} media items and "
     f"{n(MFC_LATE + ' and source_category=' + chr(39) + 'social' + chr(39))} posts from Manulife's own social accounts",
     "47 releases", "M1"),
    ("Insurance Authority quarterly provisional statistics, long term business (Table L1 by insurer)", "Manual download in a normal browser (16 Nov 2026) from market_7_2025.html and market_7_2026.html; parsed by tools/ia_market_share.py",
     "New individual business by insurer: single and annualised premiums (participating, other, linked); market totals", "Q1 2025 to H1 2026, year to date (Q3 2026 not yet published)",
     "ia.org.hk blocks automated collection (bot challenge), which the monitor does not bypass, so files are downloaded by hand each quarter. Measures reconciled to published figures (H1 2026 HSBC Life 24.3% / HK$66.8bn). Brands = sum of their IA-authorized entities. Complaints are industry-level only; Insurance Complaints Bureau robots.txt disallows collection", "6 Excel files", "Context (M1)"),
    ("Licensed company data (employees, technology, workforce)", "Licensed data provider extracts (xlsx), loaded by report_app/prudential/build.py",
     "Employee range, technology detected, hiring intent", "Snapshot 1 Nov 2026", "Some fields wrong for these entities (parent company, revenue range); those fields are not used", "4 company files", "M4, M5"),
    ("Xiaohongshu", "Dropped / out of scope for this POC", "-", "-", "Automated collection met the platform's security and access restrictions (log-in and verification checks); the platform was dropped from this POC. A collector prototype (tools/xhs_collect.py) exists but no data is used", "0 (out of scope)", "-"),
    ("WeChat", "Dropped / out of scope for this POC", "-", "-", "Official-account articles sit inside the app behind access restrictions and are not publicly accessible; dropped from this POC", "0 (out of scope)", "-"),
    ("TikTok", "Not applicable", "-", "-", "TikTok does not operate in Hong Kong", "0", "M2"),
    ("Threads (official accounts)", "Collected 17 Nov 2026 (Apify: threads-profile-api-scraper, threads-user-posts-scraper)", "1 Nov 2025 - 31 Oct 2026", "Prudential", "Prudential 21 posts (replies and reposts left out); AIA account inactive since 30 Jul 2025; AXA and Manulife have no Threads account. Engagement rate = (likes + replies + reposts + quotes) / followers", "21", "M2"),
]

fields = [
    ("record_id", "Unique id. SOC-* = Facebook / Instagram / LinkedIn posts, ADM-* = Meta ads; others from the pipeline"),
    ("company_id", "Link to the Company Master (companies): PRU_HK, AIA_HK, MFC_HK, AXA_HK"),
    ("record_type", "announcement, news_article, content_article, social_post, advertisement, app_snapshot, app_review, web_feature"),
    ("activity_type", "Classified activity (taxonomy.activity_types), e.g. product_launch, partnership, campaign"),
    ("title / description / original_content", "As published; original language kept"),
    ("language", "en or zh"),
    ("english_summary", "English summary; for Chinese records a machine-generated summary (translation_status='machine_summary')"),
    ("translation_status", "not_required, machine_summary, done (analyst), pending"),
    ("publication_date", "Date the source published the item (YYYY-MM-DD)"),
    ("capture_ts", "When we collected it (UTC ISO timestamp), kept separate from publication_date"),
    ("source_name / source_category", "Publisher or account; official, media, social, app_store, ad_library"),
    ("source_url", "Original URL (proof link)"),
    ("evidence_ref", "Pointer to the stored raw export or HTML snapshot"),
    ("hk_relevance / hk_relevance_basis", "explicit / implicit / none, and why (e.g. official HK domain or account)"),
    ("platform / content_format", "website, news, facebook, instagram, linkedin, youtube, meta_ads, ios, android; format such as video, image, carousel"),
    ("product_name / campaign_name", "Where the record names one"),
    ("cluster_id / is_primary / cluster_size", "De-duplication: syndicated copies share a cluster; one primary record per cluster; others keep their URLs as provenance"),
    ("extra", "JSON with source-specific detail (e.g. ad call to action, active dates)"),
    ("observation_modules", "Module(s) M1-M5 per record"),
    ("observation_tags", "tag_type product_category / theme / digital_capability"),
    ("observation_metrics", "metric, value and its written definition (reactions, comments, shares, views, engagement_rate_pct, followers, rating, ...). Unavailable metrics are absent, never zero"),
    ("fact_metrics", "Analytical dataset: month x company x module x platform x category x metric, with record_ids back to the source rows"),
    ("source_coverage / context_coverage", "What each source and platform holds per brand, including what is unavailable and why"),
    ("clients / client_competitors / client_insights / client_insight_evidence", "Client lens: reference brand, competitor set, ranked insights and their evidence record ids"),
]

L = ["# Prudential Hong Kong Competitive Intelligence Monitor: technical documentation", "",
     "Generated from the live database by `tools/make_tech_doc.py`. Window 1 Nov 2025 to 31 Oct 2026; reference brand Prudential Hong Kong; competitors AIA, Manulife and AXA (Hong Kong).", "",
     f"Database totals: {one('select count(*) from observations'):,} source-level records ({by_brand('1=1')}); "
     f"{one('select count(*) from excluded_records'):,} records excluded with a reason (not Hong Kong, out of window or noise); "
     f"{one('select count(*) from fact_metrics'):,} analytical rows.", "",
     "## 1. Source inventory", "",
     "| Source | Tool or method | Fields collected | Historical coverage | Access constraints and known limits | Records | Modules |", "|---|---|---|---|---|---|---|"]
L += [f"| {' | '.join(str(c) for c in r)} |" for r in inv]
L += ["", "Per-brand, per-platform availability is kept in the `source_coverage` table and shown in the report's channel coverage table, so missing data is never read as missing activity.", "",
      "## 2. Collection approach", "",
      "1. **Collect** (`pipeline/collect.py`, `tools/apify_social.py`): only the verified official accounts and pages in `pipeline/config/companies.json`, plus targeted media and ad-library searches using brand + Hong Kong + category keywords (English and Hong Kong Traditional Chinese). No whole-platform crawling. Raw exports and HTML snapshots are kept as evidence.",
      "2. **Extract and classify** (`pipeline/classify.py`): activity type, product category, theme and digital capability from the configurable keyword taxonomy (`taxonomy.json`; add keywords without code changes); Hong Kong relevance with its basis; out-of-window and non-Hong Kong items moved to `excluded_records`.",
      "3. **De-duplicate**: syndicated and repeated coverage is clustered; one primary record per cluster, other copies kept as provenance.",
      "4. **Store** (`pipeline/build.py`, `tools/ingest_social.py`): one shared SQLite database with the Company Master; no per-brand or per-module databases.",
      "5. **Translate** (`tools/translate_zh.py`): English summaries for Chinese records; originals are always kept.",
      "6. **Analyse and publish** (`report_app/prudential/build.py`, `tools/sync_insights.py`): metrics, charts and insights for the dashboard; every number and insight links back to source records.", "",
      "Run order: `collect.py` → `classify.py` → `build.py` → `tools/ingest_social.py` → `tools/android_reviews.py` → `pipeline/collectors/hk_media_sites.py` → `tools/ingest_media_sites.py` → `tools/translate_zh.py` → `report_app/prudential/build.py` → `tools/sync_insights.py` → `tools/make_tech_doc.py`.", "",
      "Keys (`APIFY_TOKEN`, `GEMINI_API_KEY`) are read from `.env` at run time, sent only in request headers and never written to logs, data or the published site.", ""]

# ---- 2a. keywords and search logic (brief s6.1-6.3), read back from the queries stored on each record ----
import re as _re
_fam = {k: {"q": set(), "n": 0, "ex": []} for k in ("brand", "combo_news", "combo_web", "youtube", "site", "topic")}
for (_x,) in q("select extra from observations where extra like '%query%'"):
    try:
        _e = json.loads(_x or "{}")
    except Exception:
        continue
    _qq = _e.get("query") or _e.get("search_query")
    if not _qq:
        continue
    _tool = str(_e.get("tool") or _e.get("collector") or _e.get("import") or "")
    _k = (("site" if _e.get("search_kind") == "publication" else "topic") if _tool == "hk_media_sites" else
          "youtube" if _e.get("search_query") else "combo_web" if ("exa" in _tool or "tavily" in _tool) else "combo_news" if " OR " in _qq else "brand")
    _qq = _re.sub(r"\s*after:\S+|\s*before:\S+", "", _qq).strip()
    _fam[_k]["q"].add(_qq)
    _fam[_k]["n"] += 1
_FL = {"brand": ("Google News RSS (HK English and HK Traditional Chinese editions)", "s6.1 brand keywords on their own, queried month by month"),
       "combo_news": ("Google News RSS (HK editions)", "s6.3: (brand keyword OR ...) AND (group of s6.2 product / theme / activity terms), English and Traditional Chinese"),
       "combo_web": ("Exa and Tavily web search APIs", "s6.3: brand + Hong Kong + one s6.2 category or activity group, English"),
       "youtube": ("YouTube search (yt-dlp public metadata)", "brand + Hong Kong + interview / podcast / campaign 2026; Hong Kong media channels only"),
       "site": ("Google News RSS, site: search (added 16 Nov 2026)", "site:<publication domain> + brand name (English or Chinese), each named publication, quarter by quarter"),
       "topic": ("Google News RSS (added 16 Nov 2026)", "brand + campaign name or ambassador; brand + critical illness / medical / cancer (English and Chinese)")}
L += ["## 2a. Keywords and search logic (brief s6)", "",
      "- **s6.1 brand keywords** (English and Hong Kong Traditional Chinese, e.g. Prudential Hong Kong / 保誠 / 香港保誠, AIA Hong Kong / 友邦 / 友邦香港) are used as search queries and, in the Company Master, to match each record to a brand.",
      "- **s6.2 product and thematic keywords** are used twice: (1) combined with the brand keywords as search queries (the s6.3 pattern below) and (2) after collection, to classify every record by product category, theme, activity type and digital capability (`taxonomy.json`, configurable without code changes).",
      "- **s6.3 combinations**: brand + category / product + activity, in English and Traditional Chinese. Official accounts and pages are collected directly from the verified list, not by search.", "",
      "| Search approach | Tool | How queries were built | Distinct queries | Records kept |", "|---|---|---|---|---|"]
L += [f"| {k} | {_FL[k][0]} | {_FL[k][1]} | {len(v['q']):,} | {v['n']:,} |" for k, v in _fam.items()]
L += ["", "Example queries (as run; date limits removed):", ""]
for _k in ("brand", "combo_news", "combo_web", "youtube", "site", "topic"):
    for _qq in sorted(_fam[_k]["q"], key=len)[:3]:
        L.append(f"- `{_qq}`")
_vf = CI.parent / "_report_work" / "search_validation_6_3.json"
if _vf.exists():
    _v = json.loads(_vf.read_text(encoding="utf-8"))
    L += ["", "**Check of the s6.3 examples (16 Nov 2026).** The seven example combinations in the brief were run word for word on Google News (HK English and HK Traditional Chinese editions, "
          "1 Nov 2025 – 31 Oct 2026). Results naming the brand were matched against the monitor by headline, and the unmatched Hong Kong items were then checked by their key terms "
          "(product, partner or event name). Every Hong Kong development returned was already held, often under a different headline; the remaining results were further copies "
          "of the same stories or items outside Hong Kong (AIA Singapore, AIA Australia, Tata AIA in India, AXA Mansard in Nigeria and similar), which the scope rules exclude.", "",
          "| Language | Query | Results in window | Naming the brand | Headline already held |", "|---|---|---|---|---|"]
    L += [f"| {r['lang']} | `{r['query']}` | {r.get('hits', 0)} | {r.get('brand_named', 0)} | {r.get('in_db', 0)} |" for r in _v if "error" not in r]
# ---- 2b. additions after the walkthrough call of 16 Nov 2026 ----
_msf = CI / "data" / "raw" / "hk_media_sites_coverage.json"
L += ["", "## 2b. Additions after the walkthrough call (16 Nov 2026)", "",
      "**Named publications.** Each publication named in brief s5.6 and on the call is searched one by one for each brand. Coverage per publication "
      "(brand headlines found, new records, stories already held) is stored in `data/raw/hk_media_sites_coverage.json` and shown in the dashboard's Evidence tab.", ""]
if _msf.exists():
    L += ["| Publication or search | Group | Brand headlines found | New records | Already held | Status |", "|---|---|---|---|---|---|"]
    L += [f"| {c['source']} | {c['group']} | {c['hits']} | {c['records']} | {c['already_held']} | {c['status']} |" for c in json.loads(_msf.read_text(encoding="utf-8"))]
L += ["",
      "**Value proposition and call to action (Module 2).** Campaign level: value proposition (promise, need, benefit), emotional narrative and call to action are read from each campaign's "
      "own release, trade-press coverage and ads, and reviewed by hand (`report_app/prudential/data.js`, CAMPAIGNS). Brand level: every Facebook, Instagram and LinkedIn post and every "
      "Facebook / Instagram ad is tagged by keyword rules in English and Chinese (`report_app/prudential/build.py`, NARR_RX and CTA_RX): narratives = family and promises; health, wellness "
      "and longevity; wealth and financial independence; premium / high-net-worth; rewards and promotions (a record can carry several). Calls to action: ads use the ad's own button "
      "(Learn more / See details = explore; Contact us = talk to an adviser; Apply now / Get quote = quote or apply; Sign up = register or leave details); posts use call-to-action wording.", "",
      "**Health and critical illness (Module 3).** Product figures (maximum cumulative payout, claims allowed, cancer and repeat-claim cover, waiting periods, conditions, marketing wording) "
      "come only from each insurer's official brochure or product page, with the URL and page, and a verification status per plan (`Prudential/_report_work/health_ci_products.json`). "
      "Premiums are not compared.", "",
      "**Ask Dashboard (AI assistant).** Answers come only from the knowledge base built with the dashboard (report text, data tables, evidence records, filings, posts, ads, product "
      "documents). Each answer follows: Answer, Business implication for Prudential, Evidence and supporting metrics, Evidence strength (High / Medium / Low with the reason), Sources. "
      "Successes, issues, signals, threats and opportunities are derived from the records for each question; no separate static list exists. Answers may include a table or a simple bar "
      "chart built only from figures in the knowledge base.", "",
      "**Dashboard behaviour.** Insights and Evidence are separate tabs. Picking one brand in the filter bar (or in the Evidence tab) shows only that brand everywhere, including fixed tables "
      "and cards; Ctrl-click adds a brand. Colour highlights were replaced by bold text and word labels (Observed, Interpretation, Suggested), explained in a first-visit guide.", ""]
L += ["", "## 3. Data fields", "", "| Field or table | Definition |", "|---|---|"]
L += [f"| `{a}` | {b} |" for a, b in fields]
L += ["", "## 4. Metric definitions", "",
      "| Metric | Definition | Notes |", "|---|---|---|",
      "| Facebook engagement rate | (reactions + shares) / page followers at capture x 100 | Comment counts missing on most posts, so not used |",
      "| Instagram engagement rate | (likes + comments) / account followers at capture x 100 | Shares not exposed; hidden-like posts excluded |",
      "| LinkedIn engagement rate | (reactions + comments + reposts) / company followers at capture x 100 | |",
      "| Engagement comparisons | Medians per brand, platform, month or theme; only within one platform | Rates shown only where at least 3 posts |",
      "| YouTube views | Public view count at capture | Includes paid ad plays |",
      "| Google ads | Creatives shown in Hong Kong in the window, by format | No spend or impressions |",
      "| Meta ads | Ads running in Hong Kong on 11 Nov 2026, by start month | Ended ads not available |",
      "| App rating | Store rating and rating count at capture; review stars | A signal, not a satisfaction measure |",
      "| Google search interest | Index 0-100 relative within one four-term comparison, monthly mean of weekly values | Not comparable across requests |", "",
      "Followers are audience-size context only, never the headline performance signal. Reach-based rates are not calculated because reach and impressions are not exposed for organic posts.", "",
      "## 5. Classification taxonomy", ""]
for k in ("activity_types", "product_categories", "themes", "digital_capabilities"):
    L.append(f"- **{k.replace('_', ' ')}**: {', '.join(tax[k].keys())}")
L += [f"- **Hong Kong terms**: {', '.join(tax['hk_terms'])}", "",
      "## 6. Translation status", "", "| Language | Status | Records |", "|---|---|---|"]
L += [f"| {a} | {b} | {c:,} |" for a, b, c in q("select language, translation_status, count(*) from observations group by 1,2 order by 1,2")]
L += ["", "## 7. Validation checklist (brief s14.3)", "", "| Area | Result |", "|---|---|",
      "| Scraping tools | Apify actors cover Facebook, Instagram, Meta Ad Library and Threads profiles; LinkedIn via the company-posts dataset; public pages via Playwright and HTTP. Bright Data not needed |",
      "| Social media | Post-level reactions, shares and views available; Facebook comments mostly missing; Instagram shares not exposed (see metric definitions) |",
      "| Engagement calculations | Follower-based rates per platform with written definitions; never mixed across platforms |",
      "| Chinese content | Original kept; English summaries generated and stored per record |",
      "| Historical data | Full 12-month history for Facebook, Instagram, LinkedIn, YouTube and newsrooms; Meta Ad Library only current ads |",
      "| Mobile apps | Current version, update date, rating, rating count and iOS reviews; version history and downloads not reliable |",
      "| Data architecture | One database for all modules; client layer separate (clients, client_insights) for future subscribers |",
      "| Evidence | Every record keeps its URL; fact_metrics and insights hold record_ids back to the sources |",
      "| Dashboard | Brand, month, module, category and platform filters with drill-down to source records; one-brand view applies to fixed tables and cards too; separate Insights and Evidence tabs |",
      "| AI assistant | Ask Dashboard answers from the knowledge base only, in the agreed format, with evidence strength and source links |", ""]
out = CI / "docs" / "TECHNICAL_DOCUMENTATION.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(L), encoding="utf-8")
print("written", out, len(L), "lines")
