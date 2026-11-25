"""Keep the database's client insights identical to the published report (brief s8.4 traceability, s11.4 structure).

Reads the ranked insights from the built report page (so wording and numbers match exactly), then:
  * pipeline/insights/prudential_hk.json - INS-01..05 keep their evidence rules (the report's drill-downs use them) but get the
    report's current wording; insights without an INS id are added as INS-06.. with their source URLs as evidence rules;
  * ci.db client_insights / client_insight_evidence - rewritten to match (evidence resolved by record id or source URL).
Run after report_app/prudential/build.py.
"""
import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "Prudential" / "Prudential_HK_Competitive_Intelligence_Report.html"
SPEC = ROOT / "Prudential" / "ci-monitor" / "pipeline" / "insights" / "prudential_hk.json"
DB = ROOT / "Prudential" / "ci-monitor" / "data" / "ci.db"
COMP = {"prudential": "PRU_HK", "aia.com": "AIA_HK", "manulife": "MFC_HK", "axa": "AXA_HK"}
MODS = {"Results": "M1", "Products": "M3", "Activity": "M1", "Digital": "M4", "Distribution": "M5", "Risk": "M1", "Brand": "M2"}


def plain(h):
    """HTML -> text, keeping each link as 'text (url)'."""
    h = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f"{m.group(2)} ({m.group(1)})", h or "")
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(PAGE.as_uri())
        pg.wait_for_timeout(1500)
        ins = pg.evaluate("INSIGHTS.map(x => ({t: x.t, conf: x.conf, mods: x.mods, ins: x.ins || null, finding: x.finding, compare: x.compare, means: x.means, act: x.act}))")
        b.close()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    old = {i["id"]: i for i in spec["insights"]}
    out, nxt = [], 6
    for rank, x in enumerate(ins, 1):
        iid = x["ins"] or f"INS-{nxt:02d}"
        if not x["ins"]:
            nxt += 1
        base = old.get(iid, {})
        urls = list(dict.fromkeys(re.findall(r'href="(https[^"]+)"', (x["finding"] or "") + (x["compare"] or ""))))
        ev = base.get("evidence") or [{"url": u, "role": "primary" if i == 0 else "supporting"} for i, u in enumerate(urls)]
        out.append({**base, "id": iid, "rank": rank, "modules": sorted({MODS[m.strip()] for m in x["mods"].split("·") if m.strip() in MODS}),
                    "title": x["t"], "finding": plain(x["finding"]), "comparison": plain(x["compare"]), "implication": "Interpretation: " + plain(x["means"]),
                    "recommended_action": plain(x["act"]), "confidence": x["conf"],
                    "confidence_basis": base.get("confidence_basis") or "Company results filings, presentations and releases linked in the finding; figures as published.",
                    "min_evidence": base.get("min_evidence", 1), "evidence": ev})
    spec["insights"] = out
    spec["authored"] = "2026-11-11 (synced with the published report)"
    SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")

    con = sqlite3.connect(DB)
    keep = {r[0]: [] for r in con.execute("select distinct insight_id from client_insight_evidence")}
    for iid, rid, role in con.execute("select insight_id, record_id, role from client_insight_evidence").fetchall():
        keep[iid].append((rid, role))
    con.execute("delete from client_insights where client_id='prudential_hk'")
    con.execute("delete from client_insight_evidence where client_id='prudential_hk'")
    for i in out:
        con.execute("insert into client_insights values (?,?,?,?,?,?,?,?,?,?,?)",
                    (i["id"], "prudential_hk", i["rank"], i["title"], i["finding"], i["comparison"], i["implication"], i["recommended_action"],
                     i["confidence"], i["confidence_basis"], json.dumps(i["modules"])))
        ev = keep.get(i["id"]) or []
        if not ev:
            for e in i["evidence"]:
                u = e.get("url", "")
                if not u:
                    continue
                r = con.execute("select record_id from observations where rtrim(source_url,'/')=rtrim(?,'/') order by is_primary desc limit 1", (u,)).fetchone()
                if not r:   # a cited results document or release that is not yet a source-level record: add it so the insight stays traceable
                    rid = "RES-" + hashlib.sha1(u.encode()).hexdigest()[:12]
                    label = (re.search(r"([^()]+) \(" + re.escape(u) + r"\)", i["finding"] + " " + i["comparison"]) or [None, "Cited source"])[1].strip()[-120:]
                    cid = next((c for k, c in COMP.items() if k in u), None)
                    con.execute("""insert or ignore into observations (record_id, company_id, record_type, activity_type, title, description, original_content, language,
                        english_summary, translation_status, publication_date, capture_ts, source_name, source_category, source_url, evidence_ref, hk_relevance,
                        hk_relevance_basis, platform, content_format, product_name, campaign_name, cluster_id, is_primary, cluster_size, extra)
                        values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (rid, cid, "results_document", None, label, f"Cited in insight {i['id']}", None, "en", label, "not_required", None,
                         "2026-11-11T00:00:00+00:00", re.sub(r"^www\.", "", u.split("/")[2]), "official" if cid else "media", u, "cited in report",
                         "explicit", "Hong Kong figures cited from the document", "document", "pdf" if u.lower().endswith(".pdf") else "web", None, None, rid, 1, 1,
                         json.dumps({"added_by": "sync_insights"})))
                    r = (rid,)
                ev.append((r[0], e["role"]))
        for rid, role in ev:
            con.execute("insert into client_insight_evidence values (?,?,?,?)", (i["id"], "prudential_hk", rid, role))
        print(f"{i['id']} rank {i['rank']}: {len(ev)} linked records | {i['title'][:80]}")
    con.commit()


if __name__ == "__main__":
    main()
