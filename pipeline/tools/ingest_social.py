"""Bring the Facebook, Instagram, LinkedIn (full-year export) posts and the Meta Ad Library ads into the shared database (brief s8).

One row per post / ad in `observations` (record ids SOC-* and ADM-*), with metrics in `observation_metrics` (definitions kept),
themes in `observation_tags`, module M2 in `observation_modules`, monthly aggregates in `fact_metrics` (with record_ids for traceability),
and refreshed `source_coverage` / `context_coverage`. English summaries of Chinese posts come from _report_work/translations.json.
Idempotent: SOC-/ADM- rows are deleted and rebuilt on each run.
"""
import hashlib
import json
import re
import sqlite3
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRU = ROOT / "Prudential"
DB = PRU / "ci-monitor" / "data" / "ci.db"
sys.path.insert(0, str(ROOT / "report_app" / "prudential"))
import linkedin as li  # noqa: E402
import social_meta as sm  # noqa: E402

CID = {"Prudential": "PRU_HK", "AIA": "AIA_HK", "Manulife": "MFC_HK", "AXA": "AXA_HK"}
CAP = {"Facebook": "2026-11-11T05:40:00+00:00", "Instagram": "2026-11-11T05:40:00+00:00", "LinkedIn": "2026-11-11T06:23:48+00:00",
       "meta_ads": "2026-11-11T07:10:00+00:00", "Threads": "2026-11-17T04:31:00+00:00"}
DEF = {"Facebook": "follower-based: (reactions + shares) / page followers at capture x 100; comments not used (missing on most posts)",
       "Instagram": "follower-based: (likes + comments) / account followers at capture x 100; shares not exposed",
       "LinkedIn": "follower-based: (reactions + comments + reposts) / company followers at capture x 100",
       "Threads": "follower-based: (likes + replies + reposts + quotes) / account followers at capture x 100"}
CJK = re.compile(r"[一-鿿]")
TR = json.loads((PRU / "_report_work" / "translations.json").read_text(encoding="utf-8")) if (PRU / "_report_work" / "translations.json").exists() else {}
rid = lambda pre, s: f"{pre}-{hashlib.sha1(s.encode()).hexdigest()[:12]}"


def main():
    con = sqlite3.connect(DB)
    x = con.execute
    for t in ("observation_metrics", "observation_tags", "observation_modules"):
        x(f"delete from {t} where record_id like 'SOC-%' or record_id like 'ADM-%'")
    x("delete from observations where record_id like 'SOC-%' or record_id like 'ADM-%'")
    x("delete from fact_metrics where platform in ('facebook','instagram','linkedin_export','meta_ads','threads')")

    posts, mst = sm.load()
    lip, lst = li.load()
    rows = [dict(p, platform_label=p["platform"]) for p in posts]
    for p in lip:
        rows.append({"platform_label": "LinkedIn", "brand": p["brand"], "date": p["date"], "url": p["url"], "text": p["text"], "format": p["format"],
                     "reactions": p["likes"], "comments": p["comments"], "shares": p["shares"], "er": p["er"], "themes": p["themes"]})
    fol = {"Facebook": mst["followers"]["Facebook"], "Instagram": mst["followers"]["Instagram"], "LinkedIn": lst["followers"], "Threads": mst["followers"].get("Threads", {})}
    agg = defaultdict(list)
    n = 0
    for p in rows:
        pl = p["platform_label"]
        if not p.get("url"):
            continue
        r = rid("SOC", p["url"])
        zh = bool(CJK.search(p["text"] or ""))
        en = (TR.get(p["url"]) or {}).get("en")
        summ = en if zh else (p["text"] or "")[:400]
        x("""insert or replace into observations (record_id, company_id, record_type, activity_type, title, description, original_content, language,
             english_summary, translation_status, publication_date, capture_ts, source_name, source_category, source_url, evidence_ref,
             hk_relevance, hk_relevance_basis, platform, content_format, product_name, campaign_name, cluster_id, is_primary, cluster_size, extra)
             values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (r, CID[p["brand"]], "social_post", "social_post", (p["text"] or "")[:120], summ, p["text"], "zh" if zh else "en",
           summ, ("machine_summary" if en else "pending") if zh else "not_required", p["date"], CAP[pl], f"Official {pl} account", "social",
           p["url"], f"apify_raw / LinkedIn export ({pl})", "explicit", f"Official Hong Kong {pl} account (verified)", pl.lower(),
           p.get("format"), None, None, r, 1, 1, json.dumps({"ingest": "social_v2"})))
        x("insert into observation_modules values (?, 'M2')", (r,))
        for t in p.get("themes") or []:
            x("insert into observation_tags values (?, 'theme', ?)", (r, t))
        for m, v in (("reactions", p.get("reactions")), ("comments", p.get("comments")), ("shares", p.get("shares")), ("views", p.get("views"))):
            if v is not None:
                x("insert into observation_metrics values (?,?,?,?)", (r, m, float(v), f"{pl} public count at capture ({CAP[pl][:10]})"))
        if p.get("er") is not None:
            x("insert into observation_metrics values (?,?,?,?)", (r, "engagement_rate_pct", float(p["er"]), DEF[pl]))
        f = fol[pl].get(p["brand"])
        if f:
            x("insert into observation_metrics values (?,?,?,?)", (r, "followers", float(f), "account followers at capture (not historical)"))
        agg[(p["date"][:7], CID[p["brand"]], "linkedin_export" if pl == "LinkedIn" else pl.lower())].append((r, p.get("er")))
        n += 1

    # Meta Ad Library: ads running in Hong Kong on 11 Nov 2026 (the HK library lists only active ads)
    ads = json.loads((PRU / "apify_raw" / "fb_ads.json").read_text(encoding="utf-8"))
    na = 0
    for a in ads:
        b = sm.AD_PAGE.get(str(a.get("pageId") or a.get("pageID")))
        aid = str(a.get("adArchiveID") or a.get("adArchiveId") or "")
        if not b or not aid:
            continue
        s = a.get("snapshot") or {}
        body = s.get("body")
        body = body.get("text") if isinstance(body, dict) else body
        txt = " ".join(str(v) for v in [s.get("title"), body, s.get("linkDescription")] + [c.get("body") for c in (s.get("cards") or []) if isinstance(c, dict)] if v)
        txt = re.sub(r"\s+", " ", txt).strip()
        r = f"ADM-{aid}"
        zh = bool(CJK.search(txt))
        start, end = str(a.get("startDateFormatted") or "")[:10], str(a.get("endDateFormatted") or "")[:10]
        url = f"https://www.facebook.com/ads/library/?id={aid}"
        x("""insert or replace into observations (record_id, company_id, record_type, activity_type, title, description, original_content, language,
             english_summary, translation_status, publication_date, capture_ts, source_name, source_category, source_url, evidence_ref,
             hk_relevance, hk_relevance_basis, platform, content_format, product_name, campaign_name, cluster_id, is_primary, cluster_size, extra)
             values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (r, CID[b], "advertisement", "advertisement", txt[:120] or "(no text)", None, txt, "zh" if zh else "en", None if zh else txt[:400],
           "pending" if zh else "not_required", start, CAP["meta_ads"], "Meta Ad Library (Hong Kong)", "ad_library", url, "apify_raw/fb_ads.json",
           "explicit", "Ad from the official Hong Kong page, shown in the Hong Kong library", "meta_ads", (s.get("displayFormat") or "").lower() or None,
           None, None, r, 1, 1, json.dumps({"ingest": "social_v2", "active_from": start, "last_seen_or_end": end, "cta": s.get("ctaText"),
                                            "platforms": a.get("publisherPlatform"), "spend": "not disclosed"}, ensure_ascii=False)))
        x("insert into observation_modules values (?, 'M2')", (r,))
        agg[(start[:7], CID[b], "meta_ads")].append((r, None))
        na += 1

    for (month, cid, plat), recs in agg.items():
        ids = json.dumps([r for r, _ in recs])
        x("insert into fact_metrics values (?,?,?,?,?,?,?,?,?)", (month, cid, "M2", plat, "all", "ads_started" if plat == "meta_ads" else "posts", len(recs), len(recs), ids))
        ers = [e for _, e in recs if e is not None]
        if ers:
            x("insert into fact_metrics values (?,?,?,?,?,?,?,?,?)", (month, cid, "M2", plat, "all", "median_engagement_rate_pct", round(st.median(ers), 3), len(ers), ids))

    # coverage: replace the stale "pending access" rows with what was actually collected
    today = "2026-11-11"
    cnt = lambda cid, pl: x("select count(*) from observations where company_id=? and platform=? and record_id like 'SOC-%'", (cid, pl)).fetchone()[0]
    x("delete from source_coverage where platform in ('facebook','instagram','meta_ads','linkedin_export','threads','tiktok','wechat','xiaohongshu')")
    for b, cid in CID.items():
        rows_ = [("Official Facebook page", "facebook", "collected", cnt(cid, "facebook"), f"Posts 1 Nov 2025 - 31 Oct 2026; followers {fol['Facebook'].get(b)} at capture"),
                 ("Official Instagram account", "instagram", "collected", cnt(cid, "instagram"),
                  f"Posts 1 Nov 2025 - 31 Oct 2026; followers {fol['Instagram'].get(b)} at capture" + ("; account listed on AIA's official-platforms page" if b == "AIA" else "")),
                 ("LinkedIn company page (full-year export)", "linkedin_export", "collected", cnt(cid, "linkedin"), f"Brand-authored posts; followers {fol['LinkedIn'].get(b)} at capture"),
                 ("Meta Ad Library (Hong Kong)", "meta_ads", "collected", x("select count(*) from observations where company_id=? and platform='meta_ads'", (cid,)).fetchone()[0],
                  "Ads running on 11 Nov 2026; the Hong Kong library lists only active ads, so ended ads are not available; spend not disclosed"),
                 ("Official Threads account", "threads", ("collected" if cnt(cid, "threads") else "account inactive in the period") if b in fol["Threads"] else "no official account", cnt(cid, "threads"),
                  {"Prudential": f"Posts 1 Nov 2025 - 31 Oct 2026 (replies and reposts left out); followers {fol['Threads'].get(b)} at capture (17 Nov 2026)",
                   "AIA": f"Account found (followers {fol['Threads'].get(b)}), but its last post was 30 Jul 2025: no posts in the period"}.get(b, "No Threads account (checked 17 Nov 2026)")),
                 ("Xiaohongshu", "xiaohongshu", "no official account" if b == "Manulife" else "account found - login needed", 0, "Collection needs a logged-in session; not yet run"),
                 ("WeChat", "wechat", "content not public", 0, "Official account content is not publicly accessible"),
                 ("TikTok", "tiktok", "not applicable", 0, "TikTok does not operate in Hong Kong")]
        for src, pl, status, k, note in rows_:
            x("insert into source_coverage values (?,?,?,?,?,?,?)", (cid, src, pl, status, k, note, today))
    x("update context_coverage set status='collected', note='Meta Ad Library: ads running in HK on 11 Nov 2026 (see ad rows ADM-*); TikTok Creative Center: not applicable in HK' where source like 'Meta Ad Library%'")
    x("update context_coverage set status='collected (Facebook, Instagram, LinkedIn); see source_coverage for Threads, Xiaohongshu, WeChat, TikTok' where source like 'Facebook / Instagram%'")
    con.commit()
    print(f"social posts {n}; Meta ads {na}; fact_metrics groups {len(agg)}")


if __name__ == "__main__":
    main()
