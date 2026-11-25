# Prudential Hong Kong Competitive Intelligence Monitor: technical documentation

Generated from the live database by `tools/make_tech_doc.py`. Window 1 Nov 2025 to 31 Oct 2026; reference brand Prudential Hong Kong; competitors AIA, Manulife and AXA (Hong Kong).

Database totals: 6,249 source-level records (AIA 2,262, AXA 1,342, Manulife 1,466, Prudential 1,179); 1,295 records excluded with a reason (not Hong Kong, out of window or noise); 1,062 analytical rows.

## 1. Source inventory

| Source | Tool or method | Fields collected | Historical coverage | Access constraints and known limits | Records | Modules |
|---|---|---|---|---|---|---|
| Official newsrooms and press releases (EN; Chinese editions checked) | pipeline/collectors/newsrooms.py, official_pages.py; tools/scrape_prudential_newsroom.py | Title, date, full text, URL, language | Full 12-month window | Manulife site returns HTTP 403 to automated requests: read from Internet Archive snapshots (manulife_archive.py); releases after the latest snapshot can be missing | 192 | M1, M3, M4 |
| Official website content and product pages | pipeline/collectors/digital_features.py, excel_imports.py (Exa / Tavily extracts) | Page text, product names, features, URL | Current pages (point in time) | Manulife website blocked (403); features requiring policyholder login are out of scope | 83 | M3, M4 |
| Industry news and media (InsuranceAsia News, SCMP, RTHK, The Standard, Google News discovery) | pipeline/collectors/media_feeds.py, google_news.py, excel_imports.py | Headline, publisher, date, text or summary, URL | Full window | Labelled third-party coverage; Google News links resolved to the publisher where possible; syndicated copies clustered | 1,868 | M1, M3, M5 |
| Named Hong Kong news, marketing and insurance publications (brief s5.6 list plus HK01, Hong Kong Economic Journal, Ming Pao, Sing Tao, AM730, HKET, Hong Kong Business, Marketing-Interactive, Campaign Asia, Dentsu) | pipeline/collectors/hk_media_sites.py (Google News site: search per publication and brand, EN + ZH, quarter by quarter; campaign and health / critical-illness topic searches); tools/ingest_media_sites.py | Headline, publisher, date, URL, query and search kind | Full window (added 16 Nov 2026) | Depends on Google News indexing of each title; paywalled titles give the headline only; stories already held from other searches are counted once (data/raw/hk_media_sites_coverage.json) | 191 | M1, M2, M3 |
| Insurer product brochures and product pages (health and critical illness) | Desk research of official documents, 16 Nov 2026 (Prudential/_report_work/health_ci_products.json) | Plan, maximum cumulative payout, claims allowed, cancer cover, repeat claims, waiting periods, conditions, how it is marketed, brochure URL and page, verification status | Current product versions | Figures taken only from official brochures or product pages, each marked with how it was checked; Manulife's website blocks automated access, so figures not confirmed in an official document are marked; premiums not compared | 21 plans | M3 |
| Facebook pages (official HK accounts) | Apify actors facebook-posts-scraper + facebook-pages-scraper (tools/apify_social.py) | Post text, date, URL, reactions, shares, comments (often missing), video flag, page followers | Full window (posts back to 1 Nov 2025) | Comment counts missing on most posts, so the Facebook rate uses reactions + shares; followers are capture-day only | 822 | M2 |
| Instagram accounts (official HK accounts; AIA from its official-platforms page) | Apify actors instagram-post-scraper + instagram-profile-scraper | Caption, date, URL, likes, comments, video views, type (image / carousel / video), followers | Full window | Shares not exposed; posts with hidden likes excluded from rates; collaboration posts owned by partners excluded | 885 | M2 |
| LinkedIn company pages | LinkedIn company-posts export (Apify dataset, 11 Nov 2026), loaded by report_app/prudential/linkedin.py | Post text, date, URL, reactions, comments, reposts, format, followers | Full window | Brand-authored originals only; reposts excluded; followers capture-day only | 598 posts (plus 164 records from an earlier licensed extract, kept for provenance) | M2, M5 |
| YouTube official channels + HK-media search | pipeline/collectors/youtube_public.py (public metadata); transcript datasets | Title, date, URL, views, subscribers, duration | Full window | Views include paid ad plays; likes hidden on some videos | 252 | M2 |
| Meta Ad Library (Hong Kong) | Apify actor facebook-ads-scraper, by Ad Library page id | Ad text, creative format, start date, end/last-seen date, platforms, call to action, ad library URL | Ads running on 11 Nov 2026 only | The HK library lists only active ads, so ended ads cannot be retrieved; spend not disclosed (never estimated) | 799 | M2 |
| Google Ads Transparency Center (Hong Kong) | pipeline/collectors/ads_transparency.py (Playwright, public pages) | Advertiser, creative format, first / last shown, image or preview URL, landing URL | Creatives shown in the window | No spend or impressions; advertiser names verified per brand (table ad_library) | 2,094 (table ad_library) | M2 |
| App stores (Apple App Store HK, Google Play HK) | pipeline/collectors/apps.py | App name, developer, version, update date, rating, rating count, release notes; written reviews (iOS via pipeline/collectors/apps.py, Android via tools/android_reviews.py) | Point in time; iOS and Android reviews within the window | Version history and download volumes not reliably available; Android reviews added 16 Nov 2026 for each main customer app (EN + zh-HK + zh-TW listings, de-duplicated, reviewer names not stored); ratings are signals, not satisfaction measures | 572 | M4 |
| Google Trends (HK) | pipeline/collectors/context_stats.py | Monthly search-interest index per brand name (English and Chinese) | Full window | Keyword not topic; relative within one comparison; not a measure of sales | 96 rows (context_stats) | M2 context |
| HKFI Monthly Brief, MPFA statistical digest | pipeline/collectors/context_stats.py | Awards, membership, MPF statistics | Latest editions | Context only; not attributed to a brand unless the source names it | 47 rows (context_stats) | Context |
| Hong Kong company disclosures (risk-based capital disclosure statements, audited accounts) | tools/hk_investor_collect.py (insurers' Hong Kong regulatory pages; robots.txt respected) | Capital strength ratio, capital held, regulatory minimum, total assets | FY2024 and FY2025 | Prudential (2 companies) and AXA collected; AIA's not found online; Manulife's site blocks automated downloads | 14 PDFs | Context (M1) |
| HKEX filings (Prudential 2378, AIA 1299, Manulife 945) | tools/hk_investor_collect.py (HKEXnews title search) | Date, title, category, PDF link; substantive filings downloaded | 1 Nov 2025 to 11 Nov 2026 | Routine returns (buy-back reports, monthly returns) listed only; AXA not listed in Hong Kong | 702 listed, 96 downloaded | Context (M1) |
| HKEX market lists (board meetings, dividends and entitlements, trading arrangements; Main Board and GEM) | tools/hkex_market_lists.py (live pages plus Internet Archive copies) | All rows; rows for the three listed insurers flagged | Archived copies across the window plus 10 Nov 2026 | Pages show upcoming items only; history depends on archived copies | about 2,400 rows | Context |
| Daily share prices (HK lines, London, Toronto, Paris, Hang Seng Index) | tools/hk_investor_collect.py (public daily price feed) | Close and volume per trading day | 1 Oct 2025 to 10 Nov 2026 | Group-level prices, not Hong Kong-only; context only | 7 series | Context |
| Manulife HK newsroom (EN, Chinese index checked) | tools/manulife_newsroom_export.py (Internet Archive copies; live site 403 not bypassed) | Date, title, lead, full text where archived | 1 Nov 2025 to the latest archived copy (22 Sep 2026; rechecked 16 Nov 2026, no newer copy) | Checked in a normal browser on 16 Nov 2026: the live newsroom lists no release from the period that the monitor lacks (in-period releases after 22 Sep: DBS partnership 28 Sep, My Flag Day 10 Oct). Other sources also cover this period: after 22 Sep 2026 the monitor holds 5 manulife.com.hk pages, 57 media items and 76 posts from Manulife's own social accounts | 47 releases | M1 |
| Insurance Authority quarterly provisional statistics, long term business (Table L1 by insurer) | Manual download in a normal browser (16 Nov 2026) from market_7_2025.html and market_7_2026.html; parsed by tools/ia_market_share.py | New individual business by insurer: single and annualised premiums (participating, other, linked); market totals | Q1 2025 to H1 2026, year to date (Q3 2026 not yet published) | ia.org.hk blocks automated collection (bot challenge), which the monitor does not bypass, so files are downloaded by hand each quarter. Measures reconciled to published figures (H1 2026 HSBC Life 24.3% / HK$66.8bn). Brands = sum of their IA-authorized entities. Complaints are industry-level only; Insurance Complaints Bureau robots.txt disallows collection | 6 Excel files | Context (M1) |
| Licensed company data (employees, technology, workforce) | Licensed data provider extracts (xlsx), loaded by report_app/prudential/build.py | Employee range, technology detected, hiring intent | Snapshot 1 Nov 2026 | Some fields wrong for these entities (parent company, revenue range); those fields are not used | 4 company files | M4, M5 |
| Xiaohongshu | Dropped / out of scope for this POC | - | - | Automated collection met the platform's security and access restrictions (log-in and verification checks); the platform was dropped from this POC. A collector prototype (tools/xhs_collect.py) exists but no data is used | 0 (out of scope) | - |
| WeChat | Dropped / out of scope for this POC | - | - | Official-account articles sit inside the app behind access restrictions and are not publicly accessible; dropped from this POC | 0 (out of scope) | - |
| TikTok | Not applicable | - | - | TikTok does not operate in Hong Kong | 0 | M2 |
| Threads (official accounts) | Collected 17 Nov 2026 (Apify: threads-profile-api-scraper, threads-user-posts-scraper) | 1 Nov 2025 - 31 Oct 2026 | Prudential | Prudential 21 posts (replies and reposts left out); AIA account inactive since 30 Jul 2025; AXA and Manulife have no Threads account. Engagement rate = (likes + replies + reposts + quotes) / followers | 21 | M2 |

Per-brand, per-platform availability is kept in the `source_coverage` table and shown in the report's channel coverage table, so missing data is never read as missing activity.

## 2. Collection approach

1. **Collect** (`pipeline/collect.py`, `tools/apify_social.py`): only the verified official accounts and pages in `pipeline/config/companies.json`, plus targeted media and ad-library searches using brand + Hong Kong + category keywords (English and Hong Kong Traditional Chinese). No whole-platform crawling. Raw exports and HTML snapshots are kept as evidence.
2. **Extract and classify** (`pipeline/classify.py`): activity type, product category, theme and digital capability from the configurable keyword taxonomy (`taxonomy.json`; add keywords without code changes); Hong Kong relevance with its basis; out-of-window and non-Hong Kong items moved to `excluded_records`.
3. **De-duplicate**: syndicated and repeated coverage is clustered; one primary record per cluster, other copies kept as provenance.
4. **Store** (`pipeline/build.py`, `tools/ingest_social.py`): one shared SQLite database with the Company Master; no per-brand or per-module databases.
5. **Translate** (`tools/translate_zh.py`): English summaries for Chinese records; originals are always kept.
6. **Analyse and publish** (`report_app/prudential/build.py`, `tools/sync_insights.py`): metrics, charts and insights for the dashboard; every number and insight links back to source records.

Run order: `collect.py` → `classify.py` → `build.py` → `tools/ingest_social.py` → `tools/android_reviews.py` → `pipeline/collectors/hk_media_sites.py` → `tools/ingest_media_sites.py` → `tools/translate_zh.py` → `report_app/prudential/build.py` → `tools/sync_insights.py` → `tools/make_tech_doc.py`.

Keys (`APIFY_TOKEN`, `GEMINI_API_KEY`) are read from `.env` at run time, sent only in request headers and never written to logs, data or the published site.

## 2a. Keywords and search logic (brief s6)

- **s6.1 brand keywords** (English and Hong Kong Traditional Chinese, e.g. Prudential Hong Kong / 保誠 / 香港保誠, AIA Hong Kong / 友邦 / 友邦香港) are used as search queries and, in the Company Master, to match each record to a brand.
- **s6.2 product and thematic keywords** are used twice: (1) combined with the brand keywords as search queries (the s6.3 pattern below) and (2) after collection, to classify every record by product category, theme, activity type and digital capability (`taxonomy.json`, configurable without code changes).
- **s6.3 combinations**: brand + category / product + activity, in English and Traditional Chinese. Official accounts and pages are collected directly from the verified list, not by search.

| Search approach | Tool | How queries were built | Distinct queries | Records kept |
|---|---|---|---|---|
| brand | Google News RSS (HK English and HK Traditional Chinese editions) | s6.1 brand keywords on their own, queried month by month | 20 | 608 |
| combo_news | Google News RSS (HK editions) | s6.3: (brand keyword OR ...) AND (group of s6.2 product / theme / activity terms), English and Traditional Chinese | 72 | 427 |
| combo_web | Exa and Tavily web search APIs | s6.3: brand + Hong Kong + one s6.2 category or activity group, English | 61 | 617 |
| youtube | YouTube search (yt-dlp public metadata) | brand + Hong Kong + interview / podcast / campaign 2026; Hong Kong media channels only | 2 | 2 |
| site | Google News RSS, site: search (added 16 Nov 2026) | site:<publication domain> + brand name (English or Chinese), each named publication, quarter by quarter | 40 | 158 |
| topic | Google News RSS (added 16 Nov 2026) | brand + campaign name or ambassador; brand + critical illness / medical / cancer (English and Chinese) | 17 | 33 |

Example queries (as run; date limits removed):

- `保誠`
- `宏利`
- `安盛`
- `("友邦香港" OR "友邦") ("健康管理" OR "身心健康" OR "預防" OR "身體檢查" OR "精神健康" OR "健康評估")`
- `("香港保誠" OR "保誠") ("健康管理" OR "身心健康" OR "預防" OR "身體檢查" OR "精神健康" OR "健康評估")`
- `("宏利香港" OR "宏利") ("健康管理" OR "身心健康" OR "預防" OR "身體檢查" OR "精神健康" OR "健康評估")`
- `AIA Hong Kong new product plan launch`
- `AXA Hong Kong new product plan launch`
- `Manulife Hong Kong insurer announcement`
- `Prudential Hong Kong podcast`
- `Manulife Hong Kong campaign 2026`
- `site:hk01.com 安盛`
- `site:hkej.com 宏利`
- `site:hkej.com 友邦`
- `保誠 承諾`
- `友邦 品牌`
- `友邦 廣告`

**Check of the s6.3 examples (16 Nov 2026).** The seven example combinations in the brief were run word for word on Google News (HK English and HK Traditional Chinese editions, 1 Nov 2025 – 31 Oct 2026). Results naming the brand were matched against the monitor by headline, and the unmatched Hong Kong items were then checked by their key terms (product, partner or event name). Every Hong Kong development returned was already held, often under a different headline; the remaining results were further copies of the same stories or items outside Hong Kong (AIA Singapore, AIA Australia, Tata AIA in India, AXA Mansard in Nigeria and similar), which the scope rules exclude.

| Language | Query | Results in window | Naming the brand | Headline already held |
|---|---|---|---|---|
| en | `"AIA" "Hong Kong" critical illness launch` | 8 | 7 | 4 |
| zh | `友邦 香港 危疾 推出` | 6 | 3 | 2 |
| en | `"Manulife" "Hong Kong" retirement product` | 9 | 5 | 4 |
| zh | `宏利 香港 退休 產品` | 10 | 8 | 2 |
| en | `"AXA" "Hong Kong" digital claims` | 10 | 5 | 4 |
| zh | `安盛 香港 電子索償` | 5 | 2 | 2 |
| en | `"Prudential" "Hong Kong" wellness campaign` | 6 | 5 | 5 |
| zh | `保誠 香港 健康 推廣` | 10 | 9 | 2 |
| en | `"AIA" health insurance partnership` | 9 | 7 | 1 |
| zh | `友邦 醫療保險 合作` | 9 | 6 | 0 |
| en | `"Manulife" mobile app new features` | 2 | 2 | 0 |
| zh | `宏利 應用程式 新功能` | 2 | 1 | 0 |
| en | `"AXA" customer experience digital services` | 8 | 5 | 1 |
| zh | `安盛 客戶體驗 數碼服務` | 6 | 5 | 4 |

## 2b. Additions after the walkthrough call (16 Nov 2026)

**Named publications.** Each publication named in brief s5.6 and on the call is searched one by one for each brand. Coverage per publication (brand headlines found, new records, stories already held) is stored in `data/raw/hk_media_sites_coverage.json` and shown in the dashboard's Evidence tab.

| Publication or search | Group | Brand headlines found | New records | Already held | Status |
|---|---|---|---|---|---|
| South China Morning Post | Hong Kong news | 23 | 5 | 18 | collected |
| The Standard | Hong Kong news | 36 | 9 | 27 | collected |
| RTHK | Hong Kong news | 32 | 11 | 21 | collected |
| HK01 | Hong Kong news | 79 | 9 | 70 | collected |
| Hong Kong Economic Journal | Hong Kong news | 58 | 18 | 40 | collected |
| Ming Pao Finance | Hong Kong news | 42 | 14 | 28 | collected |
| Sing Tao | Hong Kong news | 82 | 17 | 65 | collected |
| AM730 | Hong Kong news | 28 | 22 | 6 | collected |
| Hong Kong Economic Times | Hong Kong news | 112 | 31 | 81 | collected |
| Hong Kong Business | Business and marketing | 21 | 1 | 20 | collected |
| Marketing-Interactive | Business and marketing | 24 | 7 | 17 | collected |
| Campaign Asia | Business and marketing | 13 | 6 | 7 | collected |
| InsuranceAsia News | Insurance industry | 20 | 16 | 4 | collected |
| Asia Insurance Review | Insurance industry | 21 | 12 | 9 | collected |
| Hong Kong Insurance Journal | Insurance industry | 0 | 0 | 0 | searched; no brand headlines |
| Dentsu | Agency press releases | 1 | 1 | 0 | collected |
| Campaign coverage searches | Topic searches | 142 | 31 | 111 | collected |
| Health and critical-illness searches | Topic searches | 96 | 18 | 78 | collected |

**Value proposition and call to action (Module 2).** Campaign level: value proposition (promise, need, benefit), emotional narrative and call to action are read from each campaign's own release, trade-press coverage and ads, and reviewed by hand (`report_app/prudential/data.js`, CAMPAIGNS). Brand level: every Facebook, Instagram and LinkedIn post and every Facebook / Instagram ad is tagged by keyword rules in English and Chinese (`report_app/prudential/build.py`, NARR_RX and CTA_RX): narratives = family and promises; health, wellness and longevity; wealth and financial independence; premium / high-net-worth; rewards and promotions (a record can carry several). Calls to action: ads use the ad's own button (Learn more / See details = explore; Contact us = talk to an adviser; Apply now / Get quote = quote or apply; Sign up = register or leave details); posts use call-to-action wording.

**Health and critical illness (Module 3).** Product figures (maximum cumulative payout, claims allowed, cancer and repeat-claim cover, waiting periods, conditions, marketing wording) come only from each insurer's official brochure or product page, with the URL and page, and a verification status per plan (`Prudential/_report_work/health_ci_products.json`). Premiums are not compared.

**Ask Dashboard (AI assistant).** Answers come only from the knowledge base built with the dashboard (report text, data tables, evidence records, filings, posts, ads, product documents). Each answer follows: Answer, Business implication for Prudential, Evidence and supporting metrics, Evidence strength (High / Medium / Low with the reason), Sources. Successes, issues, signals, threats and opportunities are derived from the records for each question; no separate static list exists. Answers may include a table or a simple bar chart built only from figures in the knowledge base.

**Dashboard behaviour.** Insights and Evidence are separate tabs. Picking one brand in the filter bar (or in the Evidence tab) shows only that brand everywhere, including fixed tables and cards; Ctrl-click adds a brand. Colour highlights were replaced by bold text and word labels (Observed, Interpretation, Suggested), explained in a first-visit guide.


## 3. Data fields

| Field or table | Definition |
|---|---|
| `record_id` | Unique id. SOC-* = Facebook / Instagram / LinkedIn posts, ADM-* = Meta ads; others from the pipeline |
| `company_id` | Link to the Company Master (companies): PRU_HK, AIA_HK, MFC_HK, AXA_HK |
| `record_type` | announcement, news_article, content_article, social_post, advertisement, app_snapshot, app_review, web_feature |
| `activity_type` | Classified activity (taxonomy.activity_types), e.g. product_launch, partnership, campaign |
| `title / description / original_content` | As published; original language kept |
| `language` | en or zh |
| `english_summary` | English summary; for Chinese records a machine-generated summary (translation_status='machine_summary') |
| `translation_status` | not_required, machine_summary, done (analyst), pending |
| `publication_date` | Date the source published the item (YYYY-MM-DD) |
| `capture_ts` | When we collected it (UTC ISO timestamp), kept separate from publication_date |
| `source_name / source_category` | Publisher or account; official, media, social, app_store, ad_library |
| `source_url` | Original URL (proof link) |
| `evidence_ref` | Pointer to the stored raw export or HTML snapshot |
| `hk_relevance / hk_relevance_basis` | explicit / implicit / none, and why (e.g. official HK domain or account) |
| `platform / content_format` | website, news, facebook, instagram, linkedin, youtube, meta_ads, ios, android; format such as video, image, carousel |
| `product_name / campaign_name` | Where the record names one |
| `cluster_id / is_primary / cluster_size` | De-duplication: syndicated copies share a cluster; one primary record per cluster; others keep their URLs as provenance |
| `extra` | JSON with source-specific detail (e.g. ad call to action, active dates) |
| `observation_modules` | Module(s) M1-M5 per record |
| `observation_tags` | tag_type product_category / theme / digital_capability |
| `observation_metrics` | metric, value and its written definition (reactions, comments, shares, views, engagement_rate_pct, followers, rating, ...). Unavailable metrics are absent, never zero |
| `fact_metrics` | Analytical dataset: month x company x module x platform x category x metric, with record_ids back to the source rows |
| `source_coverage / context_coverage` | What each source and platform holds per brand, including what is unavailable and why |
| `clients / client_competitors / client_insights / client_insight_evidence` | Client lens: reference brand, competitor set, ranked insights and their evidence record ids |

## 4. Metric definitions

| Metric | Definition | Notes |
|---|---|---|
| Facebook engagement rate | (reactions + shares) / page followers at capture x 100 | Comment counts missing on most posts, so not used |
| Instagram engagement rate | (likes + comments) / account followers at capture x 100 | Shares not exposed; hidden-like posts excluded |
| LinkedIn engagement rate | (reactions + comments + reposts) / company followers at capture x 100 | |
| Engagement comparisons | Medians per brand, platform, month or theme; only within one platform | Rates shown only where at least 3 posts |
| YouTube views | Public view count at capture | Includes paid ad plays |
| Google ads | Creatives shown in Hong Kong in the window, by format | No spend or impressions |
| Meta ads | Ads running in Hong Kong on 11 Nov 2026, by start month | Ended ads not available |
| App rating | Store rating and rating count at capture; review stars | A signal, not a satisfaction measure |
| Google search interest | Index 0-100 relative within one four-term comparison, monthly mean of weekly values | Not comparable across requests |

Followers are audience-size context only, never the headline performance signal. Reach-based rates are not calculated because reach and impressions are not exposed for organic posts.

## 5. Classification taxonomy

- **activity types**: product_launch, product_enhancement, partnership, campaign, sponsorship_community, award_recognition, corporate_announcement, service_enhancement
- **product categories**: health_medical, critical_illness, life_protection, retirement, savings_wealth, sme_corporate, wellness, general_travel
- **themes**: health_wellness, medical_hospitalisation, critical_illness, life_protection, retirement_wealth, family_lifestyle, customer_education, corporate_sme, brand_awareness, digital_innovation
- **digital capabilities**: online_purchase, quotation_tool, customer_portal, digital_claims, claims_tracking, ehealth_card, telemedicine, wellness_programme, chatbot_ai, financial_planning, agent_finder, whatsapp_support
- **Hong Kong terms**: hong kong, hk, 香港, gba, greater bay, 大灣區, macau, 澳門

## 6. Translation status

| Language | Status | Records |
|---|---|---|
| en | not_required | 2,274 |
| zh | machine_summary | 3,176 |
| zh | pending | 799 |

## 7. Validation checklist (brief s14.3)

| Area | Result |
|---|---|
| Scraping tools | Apify actors cover Facebook, Instagram, Meta Ad Library and Threads profiles; LinkedIn via the company-posts dataset; public pages via Playwright and HTTP. Bright Data not needed |
| Social media | Post-level reactions, shares and views available; Facebook comments mostly missing; Instagram shares not exposed (see metric definitions) |
| Engagement calculations | Follower-based rates per platform with written definitions; never mixed across platforms |
| Chinese content | Original kept; English summaries generated and stored per record |
| Historical data | Full 12-month history for Facebook, Instagram, LinkedIn, YouTube and newsrooms; Meta Ad Library only current ads |
| Mobile apps | Current version, update date, rating, rating count and iOS reviews; version history and downloads not reliable |
| Data architecture | One database for all modules; client layer separate (clients, client_insights) for future subscribers |
| Evidence | Every record keeps its URL; fact_metrics and insights hold record_ids back to the sources |
| Dashboard | Brand, month, module, category and platform filters with drill-down to source records; one-brand view applies to fixed tables and cards too; separate Insights and Evidence tabs |
| AI assistant | Ask Dashboard answers from the knowledge base only, in the agreed format, with evidence strength and source links |
