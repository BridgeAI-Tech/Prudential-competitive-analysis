"""Module 2 - Google Ads Transparency Center (public, no login), region Hong Kong.

Opens each advertiser's public page in headless Chromium (Playwright; the page is a JavaScript app) and reads the
creative list the page itself requests (SearchService/SearchCreatives), paging with the page's own next-page token
at <= 1 request per second. Per creative: ad id, format, first/last shown (HK), preview/image URL.
Ad text and landing pages are only exposed inside per-creative preview scripts and are NOT fetched (kept as preview_url).

Output -> data/raw/ad_library.jsonl (loaded by build.py into table ad_library; not an observation: creatives carry no
text to classify and a shown-date range rather than a publication date), data/raw/ad_library_coverage.json.

Usage:  python -I pipeline/collectors/ads_transparency.py [--start 2025-11-01] [--end 2026-10-31]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import RAW, load_json, log, now_utc  # noqa: E402

# From Prudential/Pending_Data_Links.md section A2 (IDs from the Transparency Center's public suggestion endpoint)
ADVERTISERS = [
    ("Prudential", "AR16211246727519272961", "Prudential Hong Kong Limited", True),
    ("Prudential", "AR14600705932221480961", "Prudential Hong Kong Limited (second account)", True),
    ("AIA", "AR11876113593151782913", "AIA INTERNATIONAL LIMITED", True),
    ("AIA", "AR16203425050907377665", "AIA Hong Kong (display name; legal entity unconfirmed)", True),
    ("Manulife", "AR06046495469440335873", "MANULIFE (INTERNATIONAL) LIMITED", True),
    ("Manulife", "AR09647123371523047425", "MANULIFE INVESTMENT MANAGEMENT INTERNATIONAL HOLDINGS LIMITED (asset mgmt)", False),
    ("AXA", "AR08017510043802927105", "AXA China Region Insurance Company Limited", True),
    ("AXA", "AR08423536546656813057", "AXA China Region Insurance Company Limited (second account)", True),
    ("AXA", "AR14671266206170742785", "AXA 安盛 (display name; legal entity unconfirmed)", True),
]
HK_REGION = 2344
FORMATS = {1: "text", 2: "image", 3: "video"}
PAGE_JS = """async ([adv, token]) => {
  const req = {"2": 100, "3": {"8": [%d], "12": {"1": "", "2": true}, "13": {"1": [adv]}}, "7": {"1": 1, "2": 0, "3": 2356}};
  if (token) req["4"] = token;
  const r = await fetch("/anji/_/rpc/SearchService/SearchCreatives?authuser=", {method: "POST",
     headers: {"content-type": "application/x-www-form-urlencoded"}, body: "f.req=" + encodeURIComponent(JSON.stringify(req))});
  return await r.text();
}""" % HK_REGION


def _ts(x):
    if not x or "1" not in x:
        return None
    return dt.datetime.fromtimestamp(int(x["1"]), dt.timezone.utc).date().isoformat()


def _creative(c, brand, adv_id, adv_label, in_scope, start, end, cap):
    body = c.get("3") or {}
    html = (body.get("3") or {}).get("2") or ""
    img = re.search(r'src="([^"]+)"', html)
    preview = (body.get("1") or {}).get("4")
    first, last = _ts(c.get("6")), _ts(c.get("7"))
    inwin = bool(first and last and first <= end.isoformat() and last >= start.isoformat())
    return {"brand": brand, "advertiser_id": adv_id, "advertiser_name": c.get("12") or adv_label, "advertiser_label": adv_label,
            "in_scope": in_scope, "ad_id": c.get("2"), "format": FORMATS.get(c.get("4"), str(c.get("4"))),
            "first_shown": first, "last_shown": last, "shown_in_window": inwin, "region": "HK",
            "regions_count": c.get("13"), "image_url": img.group(1) if img else None, "preview_url": preview,
            "ad_text": None, "landing_url": None,
            "url": f"https://adstransparency.google.com/advertiser/{adv_id}/creative/{c.get('2')}?region=HK",
            "capture_ts": cap}


def collect(start: dt.date, end: dt.date):
    from playwright.sync_api import sync_playwright
    out, cov = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        for brand, adv, label, in_scope in ADVERTISERS:
            pg = b.new_page()
            cap = now_utc()
            try:
                pg.goto(f"https://adstransparency.google.com/advertiser/{adv}?region=HK", wait_until="networkidle", timeout=90000)
                pg.wait_for_timeout(2500)
                shown = re.search(r"([\d,]+|~?\d[\d,]*)\s+ads?\b", pg.inner_text("body"))
                total_label = shown.group(0) if shown else None
                rows, token, seen = [], None, set()
                for _ in range(60):  # page through with the page's own RPC (100 per call)
                    txt = pg.evaluate(PAGE_JS, [adv, token])
                    time.sleep(1.2)
                    d = json.loads(txt or "{}")
                    for c in d.get("1") or []:
                        if c.get("2") not in seen:
                            seen.add(c.get("2"))
                            rows.append(_creative(c, brand, adv, label, in_scope, start, end, cap))
                    token = d.get("2")
                    if not token or not d.get("1"):
                        break
                out += rows
                fm = {}
                for r in rows:
                    fm[r["format"]] = fm.get(r["format"], 0) + 1
                inwin = sum(r["shown_in_window"] for r in rows)
                firsts = sorted(r["first_shown"] for r in rows if r["first_shown"])
                lasts = sorted(r["last_shown"] for r in rows if r["last_shown"])
                cov.append({"brand": brand, "advertiser_id": adv, "advertiser": label, "in_scope": in_scope, "page_label": total_label,
                            "creatives_listed": len(rows), "shown_in_window": inwin, "formats": fm,
                            "first_shown_min": firsts[0] if firsts else None, "last_shown_max": lasts[-1] if lasts else None,
                            "status": "collected", "checked_at": cap})
                log(f"ads {brand} {adv}: {len(rows)} creatives ({total_label}); {inwin} shown in window; {fm}")
            except Exception as e:
                cov.append({"brand": brand, "advertiser_id": adv, "advertiser": label, "in_scope": in_scope, "status": "error",
                            "note": str(e)[:200], "checked_at": cap})
                log(f"ads {brand} {adv} FAILED: {e}")
            finally:
                pg.close()
                time.sleep(2)
        b.close()
    (RAW / "ad_library_coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    rows = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    with (RAW / "ad_library.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"ad_library: {len(rows)} creatives")
