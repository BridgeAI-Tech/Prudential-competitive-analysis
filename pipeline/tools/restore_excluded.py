"""Move a record that the noise rules excluded back into observations, after a human review.

The raw record is read from data/raw/*.jsonl, classified with the same rules as every other record (classify.classify),
given the reviewer's Hong Kong relevance basis, and inserted. The exclusion row is deleted and the decision is logged in
Prudential/_report_work/classification_corrections.json, so the change can be audited and re-applied.

Usage:  python -I tools/restore_excluded.py RECORD_ID "HK relevance basis" "reason for restoring"
"""
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

CI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CI / "pipeline"))
sys.path.insert(0, str(CI / "pipeline" / "collectors"))
from common import COMPANIES, RAW  # noqa: E402
import classify as C  # noqa: E402

DB = CI / "data" / "ci.db"
LOG = CI.parents[0] / "_report_work" / "classification_corrections.json"
BID = {c["brand"]: c["company_id"] for c in COMPANIES}


def find_raw(rid):
    for f in sorted(RAW.glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if rid in line:
                    r = json.loads(line)
                    if r.get("record_id") == rid:
                        return r, f.name
    raise SystemExit(f"{rid} not found in raw files")


def main(rid, basis, why):
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(DB)
    ex = con.execute("select reason from excluded_records where record_id=?", (rid,)).fetchone()
    if not ex:
        raise SystemExit(f"{rid} is not in excluded_records")
    if con.execute("select 1 from observations where record_id=?", (rid,)).fetchone():
        raise SystemExit(f"{rid} is already in observations")
    raw, src = find_raw(rid)
    r = C.classify(dict(raw))
    r["hk_relevance"], r["hk_relevance_basis"] = "explicit", "Reviewed by hand: " + basis
    r["cluster_id"], r["is_primary"], r["cluster_size"] = r["record_id"], True, 1
    for k in ("english_summary", "translation_status", "product_name", "campaign_name", "evidence_ref", "content_format", "platform"):
        r.setdefault(k, None)
    con.execute("insert into observations values (" + ",".join("?" * 26) + ")", (
        r["record_id"], BID[r["brand"]], r["record_type"], r["activity_type"], r["title"], r["description"], r["original_content"],
        r["language"], r.get("english_summary"), r.get("translation_status"), r["publication_date"], r["capture_ts"], r["source_name"],
        r["source_category"], r["source_url"], r["evidence_ref"], r["hk_relevance"], r["hk_relevance_basis"], r["platform"],
        r["content_format"], r.get("product_name"), r.get("campaign_name"), r["cluster_id"], int(r["is_primary"]), r["cluster_size"],
        json.dumps(r.get("extra") or {}, ensure_ascii=False)))
    for m in r["modules"]:
        con.execute("insert into observation_modules values (?,?)", (rid, m))
    for tt, tags in r["tags"].items():
        for t in tags:
            con.execute("insert into observation_tags values (?,?,?)", (rid, tt, t))
    con.execute("delete from excluded_records where record_id=?", (rid,))
    con.commit()
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    log.append({"record_id": rid, "field": "excluded", "from": ex[0], "to": "kept", "reason": why, "date": dt.date.today().isoformat(), "raw_file": src})
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("restored", rid, "|", r["publication_date"], r["source_name"], "| modules", r["modules"], "| activity", r["activity_type"], "| tags", r["tags"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
