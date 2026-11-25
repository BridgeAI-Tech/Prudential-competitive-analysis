"""Module 4.2 - Google Play (Hong Kong) written reviews for each insurer's main customer app, 1 Nov 2025 - 31 Oct 2026.

Uses the public Google Play review listing (google-play-scraper). Reviews are fetched in English and Traditional
Chinese (zh-HK, zh-TW), de-duplicated by review id and kept only inside the window. Reviewer names are NOT stored.
The raw export is kept as evidence under data/raw/. Re-running adds only reviews not already in ci.db.

Usage:  python -I tools/android_reviews.py
Then:   python -I tools/translate_zh.py   (English summaries for the Chinese reviews)
"""
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from google_play_scraper import Sort, app, reviews

CI = Path(__file__).resolve().parents[1]
DB = CI / "data" / "ci.db"
START, END = dt.datetime(2025, 11, 1), dt.datetime(2026, 10, 31, 23, 59, 59)
# main customer app per brand: the same apps as the iPhone reviews (Manulife HK & Macau on Android is com.manulife.mpf)
APPS = [("PRU_HK", "myPrudential", "com.prudential.prumobile"), ("AIA_HK", "AIA+ HK", "com.aiahk.idirect"),
        ("MFC_HK", "Manulife HK & Macau", "com.manulife.mpf"), ("AXA_HK", "Emma by AXA", "com.axa.hk.emma")]
CJK = re.compile(r"[一-鿿]")


def main():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    raw_dir = CI / "data" / "raw"; raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"android_reviews_{now[:10]}.json"
    con = sqlite3.connect(DB)
    have = {r for (r,) in con.execute("select record_id from observations where record_type='app_review' and platform='android'")}
    raw, added = {}, {}
    for cid, name, pkg in APPS:
        meta = app(pkg, lang="en", country="hk")
        got = {}
        for lang in ("en", "zh-HK", "zh-TW"):
            res, _ = reviews(pkg, lang=lang, country="hk", sort=Sort.NEWEST, count=800)
            for r in res:
                if START <= r["at"] <= END:
                    got[r["reviewId"]] = r
        raw[pkg] = {"app": meta["title"], "developer": meta["developer"], "rating": meta.get("score"), "ratings": meta.get("ratings"),
                    "version": meta.get("version"), "reviews": [{"id": k, "at": v["at"].isoformat(), "score": v["score"], "text": v["content"],
                                                                 "version": v.get("reviewCreatedVersion"), "thumbs_up": v.get("thumbsUpCount")}
                                                                for k, v in got.items()]}
        n = 0
        for rid_src, r in got.items():
            rid = "GPR-" + hashlib.sha1(rid_src.encode()).hexdigest()[:14]
            if rid in have:
                continue
            text = (r["content"] or "").strip()
            lang = "zh" if CJK.search(text) else "en"
            con.execute("""insert into observations (record_id, company_id, record_type, activity_type, title, description, original_content, language,
                           english_summary, translation_status, publication_date, capture_ts, source_name, source_category, source_url, evidence_ref,
                           hk_relevance, hk_relevance_basis, platform, content_format, product_name, campaign_name, cluster_id, is_primary, cluster_size, extra)
                           values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (rid, cid, "app_review", "app_review", text[:60] or "(rating only)", None, text, lang,
                         text if lang == "en" else None, "not_required" if lang == "en" else "pending",
                         r["at"].date().isoformat(), now, "Google Play (HK) reviews", "app_store",
                         f"https://play.google.com/store/apps/details?id={pkg}&hl=en&gl=HK&showAllReviews=true",
                         str(raw_path.relative_to(CI)).replace("\\", "/"), "explicit", "Hong Kong Google Play listing (country=hk)",
                         "android", "review", name, None, rid, 1, 1,
                         json.dumps({"app_name": name, "store_id": pkg, "review_id": rid_src, "version": r.get("reviewCreatedVersion")})))
            con.execute("insert into observation_modules (record_id, module) values (?, 'M4')", (rid,))
            con.execute("insert into observation_metrics (record_id, metric, value, definition) values (?, 'rating', ?, 'star rating given by the reviewer')", (rid, float(r["score"])))
            n += 1
        added[name] = (len(got), n)
        con.execute("delete from source_coverage where company_id=? and platform='android_reviews'", (cid,))
        con.execute("insert into source_coverage (company_id, source, platform, status, records, note, checked_at) values (?,?,?,?,?,?,?)",
                    (cid, "Google Play (HK) reviews", "android_reviews", "collected", len(got),
                     f"{name} ({pkg}); written reviews 1 Nov 2025 - 31 Oct 2026, EN + zh-HK + zh-TW listings, de-duplicated; reviewer names not stored", now[:10]))
    con.commit()
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, (tot, n) in added.items():
        print(f"{k}: {tot} reviews in window, {n} newly added")


if __name__ == "__main__":
    main()
