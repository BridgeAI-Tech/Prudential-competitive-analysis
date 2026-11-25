"""Module 1 - Manulife HK newsroom via the Internet Archive (manulife.com.hk returns HTTP 403 to bots; NOT bypassed).

Reads Wayback Machine snapshots (CDX API) of the newsroom index, which lists date / title / lead / link for every
release, then the archived copy of each in-window release page for its text. The original manulife.com.hk URL is kept
as source_url; the archive URL is the evidence reference. Releases never archived keep the index lead as content.

Usage:  python -I pipeline/collectors/manulife_archive.py [--start 2025-11-01] [--end 2026-10-31]
Writes  data/raw/manulife_archive.jsonl, data/raw/manulife_archive_coverage.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bs4 import BeautifulSoup  # noqa: E402

from common import RAW, clean_text, fetch, load_json, log, make_record, now_utc, write_jsonl  # noqa: E402

INDEX = "https://www.manulife.com.hk/en/individual/about/newsroom.html"
CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web/{ts}id_/{url}"
HK_RX = re.compile(r"hong kong|\bHK\b|macau|香港|澳門|greater bay|GBA|MPF", re.I)
DATELINE = re.compile(r"^\s*(Hong Kong|Macau)\s*\([^)]*\)\s*[—–-]\s*", re.I)


def _snapshots(url: str, since: str) -> list[str]:
    txt, _ = fetch(CDX, params={"url": url, "from": since, "output": "json", "filter": "statuscode:200", "collapse": "digest",
                                "fl": "timestamp"}, save_evidence=False)
    rows = json.loads(txt or "[]")
    return [r[0] for r in rows[1:]]


def parse_index(html: str) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    out = []
    for strong in s.find_all("strong"):
        m = re.fullmatch(r"\s*(20\d\d)/(\d{1,2})/(\d{1,2})\s*", strong.get_text())
        if not m:
            continue
        pub = dt.date(int(m[1]), int(m[2]), int(m[3]))
        title, lead, link = None, [], None
        par = strong.find_parent("p")
        if par is None:
            continue
        for sib in par.find_next_siblings():
            if sib.name == "hr":
                break
            if sib.name and sib.name.startswith("h") and not title:
                title = clean_text(sib.get_text(" "))
            elif sib.name == "p":
                a = sib.find("a", href=True)
                if a and not link:
                    link = urljoin(INDEX, a["href"])
                elif sib.get_text(strip=True):
                    lead.append(clean_text(sib.get_text(" ")))
        if title:
            out.append({"date": pub, "title": title, "lead": " ".join(lead), "url": link})
    return out


def _release_text(url: str):
    """Archived copy closest to now of a release page -> (text, archive_url) or (None, None)."""
    if not url or url.lower().endswith(".pdf"):
        return None, None
    snaps = _snapshots(url, "2025")
    if not snaps:
        return None, None
    au = WB.format(ts=snaps[-1], url=url)
    html, _ = fetch(au)
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "nav", "header", "footer"]):
        t.decompose()
    main = s.find("main") or s.find("div", class_=re.compile("root|container")) or s.body
    txt = clean_text(main.get_text(" ")) if main else ""
    i = txt.find("Hong Kong (")
    return (txt[i:] if i >= 0 else txt)[:8000], au.replace("id_/", "/")


def collect(start: dt.date, end: dt.date) -> list[dict]:
    snaps = _snapshots(INDEX, start.strftime("%Y%m%d"))
    log(f"manulife archive: {len(snaps)} index snapshots since {start}: {snaps}")
    items: dict[str, dict] = {}
    for ts in snaps:
        html, ref = fetch(WB.format(ts=ts, url=INDEX))
        for it in parse_index(html):
            key = it["url"] or it["title"]
            if key not in items:
                it["index_snapshot"] = WB.format(ts=ts, url=INDEX).replace("id_/", "/")
                it["index_ref"] = ref
                items[key] = it
    out = []
    for it in items.values():
        if not (start <= it["date"] <= end):
            continue
        try:
            body, aurl = _release_text(it["url"])
        except Exception as e:
            log(f"  archived release failed {it['url']}: {e}")
            body, aurl = None, None
        lead_wo = DATELINE.sub("", it["lead"])
        hk = bool(HK_RX.search(it["title"] + " " + lead_wo))
        out.append(make_record(
            brand="Manulife", record_type="announcement", modules=["M1"], title=it["title"], description=it["lead"][:1000] or None,
            original_content=body or it["lead"] or None, publication_date=it["date"].isoformat(), capture_ts=now_utc(),
            source_name="Manulife HK Newsroom (Internet Archive copy)", source_category="official",
            source_url=it["url"] or INDEX, evidence_ref=aurl or it["index_snapshot"],
            hk_relevance="explicit" if hk else "unconfirmed",
            hk_relevance_basis=("Official Hong Kong insurer newsroom; HK/Macau named in title or lead" if hk
                                else "Listed on HK newsroom but group-level / other-market release (no HK reference beyond dateline)"),
            platform="website", content_format="press_release" if not (it["url"] or "").endswith(".pdf") else "press_release_pdf",
            extra={"archive_index_snapshot": it["index_snapshot"], "archive_release_snapshot": aurl, "list_evidence_ref": it["index_ref"],
                   "access_note": "manulife.com.hk blocks automated access (HTTP 403); content read from Internet Archive snapshots",
                   "body_source": "archived release page" if body else "newsroom index lead"},
        ))
    latest = max((dt.datetime.strptime(s, "%Y%m%d%H%M%S").date() for s in snaps), default=None)
    cov = [{"brand": "Manulife", "platform": "official_newsroom_archive", "source": "Official newsroom (Internet Archive)",
            "status": "collected" if out else "none in window", "records": len(out),
            "note": f"manulife.com.hk 403 to bots; read {len(snaps)} Wayback snapshots of the EN newsroom index (latest {latest}) - "
                    f"releases after {latest} not yet archived; {sum(1 for r in out if r['extra']['body_source'] == 'archived release page')} with archived full text",
            "checked_at": now_utc()}]
    (RAW / "manulife_archive_coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    recs = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    write_jsonl("manulife_archive", recs)
    log(f"manulife_archive: {len(recs)} records")
