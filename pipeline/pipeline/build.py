"""Stages 3-5: classify/normalise -> store (SQLite, shared vs client layers) -> analytical dataset -> dashboard export.

Usage: python pipeline/build.py [--client prudential_hk]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sqlite3
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import classify, cluster, noise_reason  # noqa: E402
from common import COMPANIES, DATA, RAW, ROOT, TAXONOMY, load_json, log, read_jsonl  # noqa: E402

DB = DATA / "ci.db"
WEB_DATA = ROOT / "web" / "src" / "data"
# order matters: the first collector holding an item wins de-duplication (official sources first)
COLLECTOR_FILES = ["newsrooms", "manulife_archive", "official_pages", "excel_imports", "google_news", "media_feeds", "seed_extracts",
                   "social", "youtube", "apps", "digital_features"]
BRANDS = [c["brand"] for c in COMPANIES]

SCHEMA = """
-- ============ SHARED MARKET-INTELLIGENCE LAYER (reusable across clients) ============
CREATE TABLE companies (company_id TEXT PRIMARY KEY, brand TEXT, display_name TEXT, legal_entity TEXT, market TEXT,
                        domains TEXT, social TEXT, apps TEXT, access_notes TEXT);
CREATE TABLE observations (record_id TEXT PRIMARY KEY, company_id TEXT REFERENCES companies, record_type TEXT,
    activity_type TEXT, title TEXT, description TEXT, original_content TEXT, language TEXT, english_summary TEXT,
    translation_status TEXT, publication_date TEXT, capture_ts TEXT, source_name TEXT, source_category TEXT,
    source_url TEXT, evidence_ref TEXT, hk_relevance TEXT, hk_relevance_basis TEXT, platform TEXT, content_format TEXT,
    product_name TEXT, campaign_name TEXT, cluster_id TEXT, is_primary INTEGER, cluster_size INTEGER, extra TEXT);
CREATE TABLE observation_modules (record_id TEXT REFERENCES observations, module TEXT);
CREATE TABLE observation_tags (record_id TEXT REFERENCES observations, tag_type TEXT, tag TEXT);
CREATE TABLE observation_metrics (record_id TEXT REFERENCES observations, metric TEXT, value REAL,
    definition TEXT);  -- only metrics actually exposed; unavailable metrics are absent (null), never 0
CREATE TABLE excluded_records (record_id TEXT, company_id TEXT, title TEXT, source_url TEXT, reason TEXT);
CREATE TABLE source_coverage (company_id TEXT, source TEXT, platform TEXT, status TEXT, records INTEGER, note TEXT, checked_at TEXT);
CREATE TABLE fact_metrics (month TEXT, company_id TEXT, module TEXT, platform TEXT, category TEXT, metric TEXT,
    value REAL, n_records INTEGER, record_ids TEXT);   -- analytical dataset; record_ids keep traceability
-- ============ CLIENT-SPECIFIC ANALYTICAL LAYER (lens, never duplicates shared rows) ============
CREATE TABLE clients (client_id TEXT PRIMARY KEY, client_name TEXT, reference_company_id TEXT, market TEXT, window_days INTEGER, config TEXT);
CREATE TABLE client_competitors (client_id TEXT REFERENCES clients, company_id TEXT REFERENCES companies);
CREATE TABLE client_insights (insight_id TEXT, client_id TEXT REFERENCES clients, rank INTEGER, title TEXT, finding TEXT,
    comparison TEXT, implication TEXT, recommended_action TEXT, confidence TEXT, confidence_basis TEXT, modules TEXT);
CREATE TABLE client_insight_evidence (insight_id TEXT, client_id TEXT, record_id TEXT REFERENCES observations, role TEXT);
-- ============ CONTEXT / REFERENCE TABLES (added 11 Nov 2026; not observations, never counted as brand activity) ============
CREATE TABLE context_stats (source TEXT, period TEXT, metric TEXT, value REAL, value_text TEXT, unit TEXT,
    company_id TEXT, url TEXT, page INTEGER, note TEXT, capture_ts TEXT);   -- company_id only when the source names the insurer
CREATE TABLE context_coverage (source TEXT, status TEXT, records INTEGER, url TEXT, note TEXT, checked_at TEXT);
CREATE TABLE ad_library (company_id TEXT, advertiser_id TEXT, advertiser_name TEXT, advertiser_label TEXT, in_scope INTEGER,
    ad_id TEXT, format TEXT, first_shown TEXT, last_shown TEXT, shown_in_window INTEGER, region TEXT, regions_count INTEGER,
    image_url TEXT, preview_url TEXT, ad_text TEXT, landing_url TEXT, url TEXT, capture_ts TEXT);  -- Google Ads Transparency Center
CREATE TABLE official_accounts (company_id TEXT, platform TEXT, url TEXT, account_id TEXT, source_page TEXT, evidence_ref TEXT,
    verification_basis TEXT, listed_in_official_table INTEGER, captured_at TEXT);
CREATE TABLE channel_context (company_id TEXT, platform TEXT, channel_id TEXT, channel_title TEXT, url TEXT, followers INTEGER,
    followers_definition TEXT, videos_in_window INTEGER, captured_at TEXT);
"""


def month(d: str | None) -> str | None:
    return d[:7] if d else None


def load_records():
    recs, excluded = [], []
    for f in COLLECTOR_FILES:
        p = RAW / f"{f}.jsonl"
        if not p.exists():
            log(f"missing {p.name} - run collect.py")
            continue
        for r in read_jsonl(p):
            reason = noise_reason(r)
            if reason:
                excluded.append((r, reason))
                continue
            recs.append(classify(r))
    # de-duplicate exact record_ids (same item from two collectors) - keep first (official collectors run first)
    seen, uniq = set(), []
    for r in recs:
        key = (r["record_type"], (r["source_url"] or "").split("?")[0].rstrip("/"), r["title"]) if r["record_type"] in ("announcement", "news_article") else r["record_id"]
        url_key = (r["record_type"] in ("announcement", "news_article"), (r["source_url"] or "").split("?")[0].rstrip("/"))
        k2 = url_key if url_key[0] else None
        if r["record_id"] in seen or (k2 and k2 in seen):
            continue
        seen.add(r["record_id"])
        if k2:
            seen.add(k2)
        uniq.append(r)
    cluster(uniq)
    return uniq, excluded


def analytics_records(recs):
    """Records eligible for analytical counts: HK relevance explicit, primary instance of each event cluster."""
    return [r for r in recs if r["hk_relevance"] == "explicit" and r.get("is_primary", True)]


def build_facts(recs):
    facts = []
    A = analytics_records(recs)

    def add(m, brand, module, platform, category, metric, items, value=None):
        facts.append({"month": m, "brand": brand, "module": module, "platform": platform, "category": category,
                      "metric": metric, "value": value if value is not None else len(items), "n_records": len(items),
                      "record_ids": [x["record_id"] for x in items]})

    # M1 activity: brand x month x activity type (distinct developments = event clusters)
    g = collections.defaultdict(list)
    for r in A:
        if r["record_type"] in ("announcement", "news_article") and r["activity_type"] not in ("other",):
            g[(month(r["publication_date"]), r["brand"], r["activity_type"])].append(r)
    for (m, b, a), items in g.items():
        add(m, b, "M1", "all", a, "developments", items)
    # M1 official vs media split
    g = collections.defaultdict(list)
    for r in A:
        if r["record_type"] in ("announcement", "news_article"):
            g[(month(r["publication_date"]), r["brand"], r["source_category"])].append(r)
    for (m, b, s), items in g.items():
        add(m, b, "M1", s, "all", "developments_by_source", items)
    # M3 category emphasis: brand x product category (all M1 developments + social posts mentioning category)
    g = collections.defaultdict(list)
    for r in A:
        if r["record_type"] in ("announcement", "news_article"):
            for c in r["tags"]["product_category"]:
                g[(r["brand"], c)].append(r)
    for (b, c), items in g.items():
        add(None, b, "M3", "all", c, "category_mentions", items)
    # M2 social: brand x platform x month posts + engagement (within-platform only)
    g = collections.defaultdict(list)
    for r in A:
        if r["record_type"] == "social_post":
            g[(month(r["publication_date"]), r["brand"], r["platform"])].append(r)
    for (m, b, p), items in g.items():
        add(m, b, "M2", p, "all", "posts", items)
        for metric in ("likes", "comments", "shares", "views"):
            vals = [x["metrics"].get(metric) for x in items if x["metrics"].get(metric) is not None]
            if vals:
                add(m, b, "M2", p, "all", f"{metric}_total", [x for x in items if x["metrics"].get(metric) is not None], value=sum(vals))
                add(m, b, "M2", p, "all", f"{metric}_avg_per_post", [x for x in items if x["metrics"].get(metric) is not None], value=round(sum(vals) / len(vals), 1))
    # M2 theme distribution
    g = collections.defaultdict(list)
    for r in A:
        if r["record_type"] == "social_post":
            for t in r["tags"]["theme"] or ["unclassified"]:
                g[(r["brand"], r["platform"], t)].append(r)
    for (b, p, t), items in g.items():
        likes = [x["metrics"].get("likes") for x in items if x["metrics"].get("likes") is not None]
        add(None, b, "M2", p, t, "theme_posts", items)
        if likes:
            add(None, b, "M2", p, t, "theme_avg_likes", items, value=round(sum(likes) / len(likes), 1))
    return facts


def capability_matrix(recs):
    caps = TAXONOMY["digital_capabilities"]
    m = {cap: {b: {"web": [], "app": [], "news": []} for b in BRANDS} for cap in caps}
    for r in recs:
        for cap in r["tags"]["digital_capability"]:
            if cap not in m:
                continue
            kind = "web" if r["record_type"] == "web_feature" else "app" if r["record_type"] == "app_snapshot" else "news"
            m[cap][r["brand"]][kind].append(r["record_id"])
    blocked = {c["brand"] for c in COMPANIES if c.get("access_notes")}
    out = []
    for cap, d in m.items():
        row = {"capability": cap, "label": caps[cap]["label"], "brands": {}}
        for b in BRANDS:
            ev = d[b]
            status = "observed" if ev["web"] or ev["app"] else ("web_blocked" if b in blocked else "not_observed")
            row["brands"][b] = {"status": status, "web": ev["web"], "app": ev["app"]}
        out.append(row)
    return out


SKIPPED_NOTE = "Not attempted (11 Nov 2026 extra collection): login wall / licensed access needed; no login or bypass used"


def extra_coverage():
    """Per-brand coverage rows written by the extra collectors (YouTube, media feeds, Manulife archive, ads, official pages)."""
    rows = []
    for f in ("youtube_coverage.json", "manulife_archive_coverage.json", "official_pages_coverage.json"):
        for c in _raw_json(f, []):
            if c.get("brand"):
                rows.append({"brand": c["brand"], "source": c.get("source") or c["platform"].title(), "platform": c.get("platform") or c["source"],
                             "status": c["status"], "records": c["records"], "note": c.get("note") or ""})
    for c in _raw_json("media_feeds_coverage.json", []):
        for b in BRANDS:
            n = (c.get("by_brand") or {}).get(b, 0)
            st = c["status"] if c["status"] != "collected" else ("collected" if n else "none in window")
            rows.append({"brand": b, "source": c["source"], "platform": "media", "status": st, "records": n, "note": c.get("note") or ""})
    ads = _raw_json("ad_library_coverage.json", [])
    for b in BRANDS:
        a = [x for x in ads if x["brand"] == b]
        if not a:
            continue
        ok = [x for x in a if x["status"] == "collected"]
        n = sum(x.get("shown_in_window", 0) for x in ok if x["in_scope"])
        fm = collections.Counter()
        for x in ok:
            if x["in_scope"]:
                fm.update(x.get("formats") or {})
        note = "; ".join(f"{x['advertiser_id']} {x['advertiser']}: {x.get('creatives_listed', 0)} creatives ({x.get('page_label')}), "
                         f"{x.get('shown_in_window', 0)} shown in window" + ("" if x["in_scope"] else " [out of scope]") for x in a)
        rows.append({"brand": b, "source": "Google Ads Transparency Center (HK)", "platform": "google_ads",
                     "status": "collected" if ok else "error", "records": n,
                     "note": f"in-scope formats {dict(fm)}; ad text/landing page not read (per-creative preview only); " + note})
    for b in BRANDS:
        rows.append({"brand": b, "source": "Threads", "platform": "threads", "status": "skipped", "records": 0, "note": SKIPPED_NOTE})
        rows.append({"brand": b, "source": "LinkedIn search", "platform": "linkedin_search", "status": "skipped", "records": 0, "note": SKIPPED_NOTE})
    return rows


def coverage(recs):
    soc = json.loads((RAW / "social_coverage.json").read_text(encoding="utf-8")) if (RAW / "social_coverage.json").exists() else []
    extra = extra_coverage()
    if any(r["platform"] == "youtube" for r in extra):  # yt-dlp collector supersedes the API-key placeholder rows
        soc = [x for x in soc if x["platform"] != "youtube"]
    for x in soc:
        if x["platform"] in ("facebook", "instagram", "tiktok", "xiaohongshu", "wechat") and x["status"] != "collected":
            x["note"] = "; ".join(t for t in (x.get("note"), SKIPPED_NOTE) if t)
    cnt = collections.Counter()
    for r in recs:
        key = {"announcement": "official_newsroom" if r["source_category"] == "official" else "media",
               "news_article": "media", "app_snapshot": f"app_{r['platform']}", "app_review": "app_reviews_ios",
               "web_feature": "website_features"}.get(r["record_type"])
        if key:
            cnt[(r["brand"], key)] += 1
    rows = []
    blocked = {c["brand"]: c.get("access_notes") for c in COMPANIES}
    for b in BRANDS:
        for src, label in [("official_newsroom", "Official newsroom"), ("media", "Third-party media"),
                           ("website_features", "Website features"), ("app_ios", "iOS app listing"),
                           ("app_android", "Android app listing"), ("app_reviews_ios", "iOS reviews (12 months)")]:
            n = cnt[(b, src)]
            if n:
                status = "collected"
            elif src in ("official_newsroom", "website_features") and blocked.get(b):
                status = "blocked"
            elif src == "app_android" and b == "Manulife":
                status = "package unverified"
            else:
                status = "none in window"
            rows.append({"brand": b, "source": label, "platform": src, "status": status, "records": n,
                         "note": blocked.get(b) if status == "blocked" else ""})
        for s in soc:
            if s["brand"] == b:
                rows.append({"brand": b, "source": s["platform"].title(), "platform": s["platform"], "status": s["status"],
                             "records": s["records"], "note": s["note"]})
        rows += [r for r in extra if r["brand"] == b]
    return rows


def resolve_insights(client_id, recs):
    p = ROOT / "pipeline" / "insights" / f"{client_id}.json"
    if not p.exists():
        return []
    spec = json.loads(p.read_text(encoding="utf-8"))
    by_url = {}
    for r in recs:
        by_url.setdefault((r["source_url"] or "").split("?")[0].rstrip("/"), []).append(r)
    by_id = {r["record_id"]: r for r in recs}
    out = []
    for ins in spec["insights"]:
        ev = []
        for e in ins["evidence"]:
            hits = []
            if "record_id" in e:
                hits = [by_id[e["record_id"]]] if e["record_id"] in by_id else []
            elif "url" in e:
                hits = by_url.get(e["url"].split("?")[0].rstrip("/"), [])
            elif "title_contains" in e:
                hits = [r for r in recs if r["brand"] == e.get("brand", r["brand"]) and e["title_contains"].lower() in (r["title"] or "").lower()]
            if not hits:
                log(f"  !! insight {ins['id']}: evidence not found {e}")
                continue
            hits.sort(key=lambda h: (h["source_category"] != "official", h["hk_relevance"] != "explicit", not h.get("is_primary", True)))
            for h in hits[:1]:
                ev.append({"record_id": h["record_id"], "role": e.get("role", "supporting"), "note": e.get("note")})
        if len(ev) < ins.get("min_evidence", 2):
            log(f"  !! insight {ins['id']} has only {len(ev)} evidence records - flagged")
            ins["evidence_warning"] = True
        ins["evidence_resolved"] = ev
        out.append(ins)
    return out


def write_db(recs, excluded, facts, cov, client, insights):
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    for c in COMPANIES:
        con.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?)", (c["company_id"], c["brand"], c["display_name"], c["legal_entity"], "HK",
                    json.dumps(c["domains"]), json.dumps(c["social"]), json.dumps(c["apps"]), c.get("access_notes")))
    defs = {"likes": "platform-reported likes/reactions at capture", "comments": "platform-reported comment count at capture",
            "shares": "platform-reported shares at capture", "views": "platform-reported views at capture",
            "rating": "store average rating at capture", "rating_count": "store rating count at capture",
            "followers": "account followers at capture (not historical)"}
    for r in recs:
        con.execute("INSERT INTO observations VALUES (" + ",".join("?" * 26) + ")", (
            r["record_id"], r["company_id"], r["record_type"], r["activity_type"], r["title"], r["description"], r["original_content"],
            r["language"], r.get("english_summary"), r.get("translation_status"), r["publication_date"], r["capture_ts"], r["source_name"],
            r["source_category"], r["source_url"], r["evidence_ref"], r["hk_relevance"], r["hk_relevance_basis"], r["platform"],
            r["content_format"], r.get("product_name"), r.get("campaign_name"), r["cluster_id"], int(r["is_primary"]), r["cluster_size"],
            json.dumps(r["extra"], ensure_ascii=False)))
        for m in r["modules"]:
            con.execute("INSERT INTO observation_modules VALUES (?,?)", (r["record_id"], m))
        for tt, tags in r["tags"].items():
            for t in tags:
                con.execute("INSERT INTO observation_tags VALUES (?,?,?)", (r["record_id"], tt, t))
        for k, v in r["metrics"].items():
            if isinstance(v, (int, float)) and v is not None:
                con.execute("INSERT INTO observation_metrics VALUES (?,?,?,?)", (r["record_id"], k, v, defs.get(k, k)))
    for r, reason in excluded:
        con.execute("INSERT INTO excluded_records VALUES (?,?,?,?,?)", (r["record_id"], r["company_id"], r["title"], r["source_url"], reason))
    bid = {c["brand"]: c["company_id"] for c in COMPANIES}
    for c in cov:
        con.execute("INSERT INTO source_coverage VALUES (?,?,?,?,?,?,?)", (bid[c["brand"]], c["source"], c["platform"], c["status"], c["records"], c["note"], dt.date.today().isoformat()))
    for f in facts:
        con.execute("INSERT INTO fact_metrics VALUES (?,?,?,?,?,?,?,?,?)", (f["month"], bid[f["brand"]], f["module"], f["platform"], f["category"],
                    f["metric"], f["value"], f["n_records"], json.dumps(f["record_ids"])))
    write_context_tables(con, bid)
    con.execute("INSERT INTO clients VALUES (?,?,?,?,?,?)", (client["client_id"], client["client_name"], client["reference_company_id"],
                client["market"], client["window_days"], json.dumps(client)))
    for cid in client["competitor_company_ids"]:
        con.execute("INSERT INTO client_competitors VALUES (?,?)", (client["client_id"], cid))
    for i in insights:
        con.execute("INSERT INTO client_insights VALUES (?,?,?,?,?,?,?,?,?,?,?)", (i["id"], client["client_id"], i["rank"], i["title"], i["finding"],
                    i["comparison"], i["implication"], i["recommended_action"], i["confidence"], i["confidence_basis"], json.dumps(i["modules"])))
        for e in i["evidence_resolved"]:
            con.execute("INSERT INTO client_insight_evidence VALUES (?,?,?,?)", (i["id"], client["client_id"], e["record_id"], e["role"]))
    con.commit()
    con.close()


def write_context_tables(con, bid):
    """Reference tables from the extra collectors (raw files are optional: absent file -> empty table)."""
    p = RAW / "context_stats.jsonl"
    for r in (read_jsonl(p) if p.exists() else []):
        con.execute("INSERT INTO context_stats VALUES (?,?,?,?,?,?,?,?,?,?,?)", (r["source"], r["period"], r["metric"], r["value"], r.get("value_text"),
                    r["unit"], bid.get(r.get("brand")), r["url"], r.get("page"), r.get("note"), r["capture_ts"]))
    for c in _raw_json("context_coverage.json", []):
        con.execute("INSERT INTO context_coverage VALUES (?,?,?,?,?,?)", (c["source"], c["status"], c["records"], c.get("url"), c.get("note"), c["checked_at"]))
    for c in INDUSTRY_SKIPS:
        con.execute("INSERT INTO context_coverage VALUES (?,?,?,?,?,?)", (*c, dt.date.today().isoformat()))
    p = RAW / "ad_library.jsonl"
    for r in (read_jsonl(p) if p.exists() else []):
        con.execute("INSERT INTO ad_library VALUES (" + ",".join("?" * 18) + ")", (bid[r["brand"]], r["advertiser_id"], r["advertiser_name"],
                    r["advertiser_label"], int(r["in_scope"]), r["ad_id"], r["format"], r["first_shown"], r["last_shown"], int(r["shown_in_window"]),
                    r["region"], r.get("regions_count"), r.get("image_url"), r.get("preview_url"), r.get("ad_text"), r.get("landing_url"),
                    r["url"], r["capture_ts"]))
    p = RAW / "official_accounts.jsonl"
    for r in (read_jsonl(p) if p.exists() else []):
        con.execute("INSERT INTO official_accounts VALUES (?,?,?,?,?,?,?,?,?)", (bid[r["brand"]], r["platform"], r.get("url"), r.get("account_id"),
                    r["source_page"], r["evidence_ref"], r["verification_basis"], int(bool(r.get("listed_in_official_table"))), r["captured_at"]))
    for c in _raw_json("youtube_channels.json", []):
        con.execute("INSERT INTO channel_context VALUES (?,?,?,?,?,?,?,?,?)", (bid[c["brand"]], c["platform"], c["channel_id"], c.get("channel_title"),
                    c["url"], c.get("followers"), c.get("followers_definition"), c.get("videos_in_window"), c["captured_at"]))


INDUSTRY_SKIPS = [
    ("Insurance Authority (ia.org.hk) statistics / register / complaints", "skipped - blocked", 0, "https://www.ia.org.hk/",
     "HTTP 403 to automated requests; files must be downloaded manually in a browser (not bypassed)"),
    ("Google web search result pages (leadership interview / podcast queries)", "skipped", 0, "https://www.google.com/search",
     "Not attempted by design; YouTube search and Google News RSS used instead"),
    ("Facebook / Instagram / Threads / LinkedIn search / Xiaohongshu / WeChat / TikTok", "skipped", 0, None,
     "Login walls (TikTok not available in HK); no login, no bypass. Official account IDs recorded in official_accounts"),
    ("Meta Ad Library / TikTok Creative Center", "skipped", 0, "https://www.facebook.com/ads/library/",
     "Not attempted (login / JS wall to automated access)"),
]


def _raw_json(name, default):
    p = RAW / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def data_inventory(recs, excluded):
    """Per-workbook accounting: rows read -> observations kept after noise rules and cross-source de-duplication."""
    inv = _raw_json("data_inventory.json", [])
    kept = collections.Counter((r.get("extra") or {}).get("import") for r in recs)
    primary = collections.Counter((r.get("extra") or {}).get("import") for r in recs if r.get("is_primary", True) and r["hk_relevance"] == "explicit")
    dropped = collections.defaultdict(collections.Counter)
    for r, reason in excluded:
        imp = (r.get("extra") or {}).get("import")
        if imp:
            dropped[imp][reason] += 1
    seen = set()
    for row in inv:
        f = row["file"]
        if f in kept and f not in seen and (row["use"].startswith("M") or "observations" in row["use"]):
            row["observations"] = kept[f]
            row["analytics_eligible"] = primary[f]
            row["excluded"] = dict(dropped.get(f, {}))
            seen.add(f)
    return inv


def export(recs, excluded, facts, cov, client, insights, caps):
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    slim = []
    for r in recs:
        slim.append({k: r.get(k) for k in ("record_id", "brand", "record_type", "activity_type", "modules", "title", "english_summary",
                                            "language", "translation_status", "publication_date", "capture_ts", "source_name",
                                            "source_category", "source_url", "evidence_ref", "hk_relevance", "hk_relevance_basis",
                                            "platform", "content_format", "product_name", "metrics", "tags", "cluster_id",
                                            "is_primary", "cluster_size", "cluster_sources")})
        slim[-1]["description"] = (r.get("description") or "")[:600] or None
        slim[-1]["original_excerpt"] = (r.get("original_content") or "")[:1200] or None
        ex = r.get("extra") or {}
        slim[-1]["extra"] = {k: ex[k] for k in ("app_name", "version", "evidence_urls", "capability_label", "publisher", "image", "seller",
                                                 "post_url_available", "metric_note", "app_role", "first_release", "import", "tool",
                                                 "vendor_activity_type", "activity_basis", "explorium_event", "partner_company",
                                                 "awarding_body") if k in ex}
    runs = json.loads((RAW / "_run_status.json").read_text()) if (RAW / "_run_status.json").exists() else {}
    win = next(iter(runs.values()), {}).get("window", [None, None])
    meta = {"client": client, "window_start": win[0], "window_end": win[1], "built_at": dt.datetime.now().isoformat(timespec="seconds"),
            "collector_runs": runs, "counts": {"records": len(recs), "excluded_noise": len(excluded),
            "analytics_eligible": len(analytics_records(recs))},
            "excluded_by_reason": dict(collections.Counter(reason for _, reason in excluded)),
            "taxonomy": {k: {kk: vv["label"] for kk, vv in TAXONOMY[k].items() if isinstance(vv, dict) and "label" in vv}
                         for k in ("product_categories", "themes", "digital_capabilities")},
            "companies": [{k: c.get(k) for k in ("company_id", "brand", "display_name", "legal_entity", "social", "apps", "access_notes")} for c in COMPANIES]}
    ctx = _raw_json("company_context.json", {})
    src_inv = _raw_json("source_inventory.json", {})
    data_inv = data_inventory(recs, excluded)
    files = {"meta.json": meta, "records.json": slim, "facts.json": facts, "coverage.json": cov, "insights.json": insights,
             "capabilities.json": caps, "context.json": ctx, "source_inventory.json": src_inv, "data_inventory.json": data_inv}
    for name, obj in files.items():
        (WEB_DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"exported {', '.join(files)} -> {WEB_DATA}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default="prudential_hk")
    a = ap.parse_args()
    client = load_json(f"client_{a.client.split('_')[0]}.json")
    recs, excluded = load_records()
    log(f"records {len(recs)} | excluded noise {len(excluded)} {collections.Counter(x for _, x in excluded)}")
    facts = build_facts(recs)
    cov = coverage(recs)
    caps = capability_matrix(recs)
    insights = resolve_insights(client["client_id"], recs)
    write_db(recs, excluded, facts, cov, client, insights)
    export(recs, excluded, facts, cov, client, insights, caps)
    log(f"facts {len(facts)} | insights {len(insights)} | db {DB}")


if __name__ == "__main__":
    main()
