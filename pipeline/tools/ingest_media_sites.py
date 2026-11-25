"""Add the named Hong Kong publication searches (pipeline/collectors/hk_media_sites.py) to ci.db without a full rebuild.

A full `pipeline/build.py` rebuild would drop the records added directly by the tools (Android reviews, social v2 ingest,
translations), so this script classifies the new records with the same rules (classify.noise_reason / classify.classify)
and inserts them. Each new story joins an existing event cluster when it reports the same event (classify.same_event,
same brand, within 10 days); otherwise it starts its own cluster. Records failing the noise rules go to excluded_records.
Re-running is safe: record_ids and URLs already in the database are skipped.

Usage:  python -I tools/ingest_media_sites.py
Then:   python -I tools/translate_zh.py   (English summaries for the new Chinese headlines)
"""
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

CI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CI / "pipeline"))
sys.path.insert(0, str(CI / "pipeline" / "collectors"))
from common import COMPANIES, RAW, read_jsonl  # noqa: E402
import classify as C  # noqa: E402

DB = CI / "data" / "ci.db"
BID = {c["brand"]: c["company_id"] for c in COMPANIES}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    recs = read_jsonl(RAW / "hk_media_sites.jsonl")
    con = sqlite3.connect(DB)
    have_ids = {r for (r,) in con.execute("select record_id from observations")}
    have_ids |= {r for (r,) in con.execute("select record_id from excluded_records")}
    have_urls = {C.url_key(u) for (u,) in con.execute("select source_url from observations where record_type in ('announcement','news_article')") if u}
    exist = [dict(zip(("record_id", "brand", "title", "publication_date", "source_url", "source_category", "record_type", "source_name", "cluster_id"), r))
             for r in con.execute("""select o.record_id, c.brand, o.title, o.publication_date, o.source_url, o.source_category, o.record_type, o.source_name, o.cluster_id
                                     from observations o join companies c on c.company_id=o.company_id
                                     where o.record_type in ('announcement','news_article') and o.publication_date is not null""")]
    C.DF.clear()
    for r in exist + recs:
        C.DF.update(C.proper_tokens(r["title"]))
    added = excluded = joined = 0
    by_brand = {}
    for r in recs:
        if r["record_id"] in have_ids or C.url_key(r.get("source_url")) in have_urls:
            continue
        reason = C.noise_reason(r)
        if reason:
            con.execute("insert into excluded_records values (?,?,?,?,?)", (r["record_id"], BID[r["brand"]], r["title"], r["source_url"], reason))
            have_ids.add(r["record_id"])
            excluded += 1
            continue
        r = C.classify(r)
        d1 = dt.date.fromisoformat(r["publication_date"])
        match = None
        for x in exist:
            if x["brand"] != r["brand"]:
                continue
            gap = abs((d1 - dt.date.fromisoformat(x["publication_date"])).days)
            if gap <= 10 and C.same_event(r, x, gap):
                match = x
                break
        if match:
            cid = match["cluster_id"] or match["record_id"]
            r["cluster_id"], r["is_primary"] = cid, False
            con.execute("update observations set cluster_size = cluster_size + 1 where cluster_id=?", (cid,))
            size = con.execute("select max(cluster_size) from observations where cluster_id=?", (cid,)).fetchone()[0] or 1
            r["cluster_size"] = size
            joined += 1
        else:
            r["cluster_id"], r["is_primary"], r["cluster_size"] = r["record_id"], True, 1
        con.execute("insert into observations values (" + ",".join("?" * 26) + ")", (
            r["record_id"], BID[r["brand"]], r["record_type"], r["activity_type"], r["title"], r["description"], r["original_content"],
            r["language"], r.get("english_summary"), r.get("translation_status"), r["publication_date"], r["capture_ts"], r["source_name"],
            r["source_category"], r["source_url"], r["evidence_ref"], r["hk_relevance"], r["hk_relevance_basis"], r["platform"],
            r["content_format"], r.get("product_name"), r.get("campaign_name"), r["cluster_id"], int(r["is_primary"]), r["cluster_size"],
            json.dumps(r["extra"], ensure_ascii=False)))
        for m in r["modules"]:
            con.execute("insert into observation_modules values (?,?)", (r["record_id"], m))
        for tt, tags in r["tags"].items():
            for t in tags:
                con.execute("insert into observation_tags values (?,?,?)", (r["record_id"], tt, t))
        exist.append({"record_id": r["record_id"], "brand": r["brand"], "title": r["title"], "publication_date": r["publication_date"],
                      "source_url": r["source_url"], "source_category": r["source_category"], "record_type": r["record_type"],
                      "source_name": r["source_name"], "cluster_id": r["cluster_id"]})
        have_ids.add(r["record_id"])
        have_urls.add(C.url_key(r["source_url"]))
        added += 1
        by_brand[r["brand"]] = by_brand.get(r["brand"], 0) + 1
    today = dt.date.today().isoformat()
    for b, cid in BID.items():
        con.execute("delete from source_coverage where company_id=? and source='Named Hong Kong publications (site: searches)'", (cid,))
        n = con.execute("select count(*) from observations where company_id=? and extra like '%\"collector\": \"hk_media_sites\"%'", (cid,)).fetchone()[0]
        con.execute("insert into source_coverage values (?,?,?,?,?,?,?)", (cid, "Named Hong Kong publications (site: searches)", "news", "collected", n,
                    "Brief s5.6 publications plus HK01, HKEJ, Ming Pao, Sing Tao, AM730, HKET, Hong Kong Business, Marketing-Interactive, Campaign Asia, Dentsu; "
                    "campaign and health / critical-illness topic searches", today))
    con.commit()
    print(f"added {added} (joined an existing story: {joined}; new stories: {added - joined}), excluded by noise rules {excluded}; by brand {by_brand}")


if __name__ == "__main__":
    main()
