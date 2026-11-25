"""Market context (not observations): industry statistics from public PDFs + Google Trends (best effort).

  * HKFI Monthly Brief (latest found)            - membership counts; Hong Kong Insurance Awards company winners
                                                    (insurer-attributed only where the source names the insurer;
                                                    awards to named individuals are NOT stored)
  * MPFA MPF Schemes Statistical Digest (latest) - summary statistics + quarterly contributions/benefits
  * Insurance Complaints Bureau annual report    - NOT fetched: icb.org.hk robots.txt disallows all automated access
                                                    ("User-agent: * / Disallow: /"). Manual download needed.
  * Google Trends (pytrends)                     - HK monthly search interest, brand terms EN + ZH; skipped if rate-limited
                                                    after 2 polite retries.

Output -> data/raw/context_stats.jsonl (table context_stats), data/raw/context_coverage.json (table context_coverage)
Usage:  python -I pipeline/collectors/context_stats.py [--no-trends]
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
import requests  # noqa: E402

from common import EVIDENCE, RAW, ROOT, USER_AGENT, load_json, log, now_utc, robots_allowed  # noqa: E402

HKFI = ("https://files.hkfi.org.hk/monthly%20brief/2026/e_202610.pdf", "Oct 2026", "HKFI Monthly Brief No.348")
MPFA = ("https://www.mpfa.org.hk/-/media/files/information-centre/research-and-statistics/quarterly-reports/mpf-schemes/june_2026_issue.pdf",
        "2026-06-30", "MPFA MPF Schemes Statistical Digest, June 2026")
ICB = "https://www.icb.org.hk/files/ar_2025_26.pdf"
BRAND_ENTITIES = {"Prudential": r"Prudential Hong Kong", "AIA": r"\bAIA\b", "Manulife": r"Manulife", "AXA": r"\bAXA\b"}
ROWS: list[dict] = []
COV: list[dict] = []


def _row(source, period, metric, value, unit, url, page, brand=None, value_text=None, note=None):
    ROWS.append({"source": source, "period": period, "metric": metric, "value": value, "value_text": value_text, "unit": unit,
                 "brand": brand, "url": url, "page": page, "note": note, "capture_ts": now_utc()})


def _pdf(url: str) -> tuple[list[str], str]:
    if not robots_allowed(url):
        raise PermissionError("robots.txt disallows")
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    p = EVIDENCE / dt.date.today().isoformat() / ("ctx_" + re.sub(r"[^A-Za-z0-9_.-]", "_", url.split("/")[-1]))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    import pymupdf
    doc = pymupdf.open(p)
    time.sleep(1.5)
    return [pg.get_text() for pg in doc], str(p.relative_to(ROOT)).replace("\\", "/")


def _num(s: str) -> float:
    return float(re.sub(r"[ , ]", "", s))


def hkfi():
    url, period, name = HKFI
    pages, ref = _pdf(url)
    n0 = len(ROWS)
    txt = "\n".join(pages)
    m = re.search(r"As at ([\d]+ \w+ \d{4}), the HKFI has (\d+) General Insurance Members and (\d+) Life Insurance Members", txt)
    if m:
        _row(name, m[1], "HKFI general insurance members", int(m[2]), "companies", url, 2)
        _row(name, m[1], "HKFI life insurance members", int(m[3]), "companies", url, 2)
    m = re.search(r"all (\d+) Motor and EC insurers", txt)
    if m:
        _row(name, period, "Motor and EC insurers in Huanggang Port market agreement", int(m[1]), "insurers", url, 1)
    # Hong Kong Insurance Awards 2026 (company awards only; individual-person awards are skipped)
    p2 = pages[1] if len(pages) > 1 else ""
    lines = [l.strip() for l in p2.splitlines() if l.strip()]
    for i, l in enumerate(lines):
        if re.search(r"Award\b", l) and i + 1 < len(lines) and not re.search(r"of the Year", l):
            winner = lines[i + 1]
            if re.search(r"Award", winner) or len(winner) < 4:
                continue
            if i + 2 < len(lines) and re.match(r"^(Limited|Hong Kong|Macau)", lines[i + 2]):
                winner += " " + lines[i + 2]
            brand = next((b for b, rx in BRAND_ENTITIES.items() if re.search(rx, winner)), None)
            _row(name, "2026", f"Hong Kong Insurance Awards 2026: {l}", 1, "award", url, 2, brand=brand, value_text=winner,
                 note="Winner as named by HKFI; brand set only when the source names the insurer")
    COV.append({"source": name, "status": "collected", "records": len(ROWS) - n0, "url": url, "evidence_ref": ref,
                "note": "Membership counts + company award winners; awards to named individuals not stored"})


MPFA_SUMMARY = [("Employers", "MPF enrolment - employers", "'000"), ("Employees", "MPF enrolment - employees", "'000"),
                ("Self-employed persons", "MPF enrolment - self-employed persons", "'000"),
                ("Contribution accounts", "MPF contribution accounts", "'000"), ("Personal accounts", "MPF personal accounts", "'000"),
                ("Tax-deductible voluntary contribution accounts", "MPF TVC accounts", "'000"),
                ("Total number of scheme members", "MPF scheme members", "'000"), ("Number of approved trustees1", "MPF approved trustees", "trustees"),
                ("Number of registered schemes", "MPF registered schemes", "schemes"),
                ("Number of approved constituent funds2", "MPF approved constituent funds", "funds"),
                ("Contributions received, Q2 2026 (HK$ million)", "MPF contributions received Q2 2026", "HK$ million"),
                ("Aggregate net asset value of all schemes3 (HK$ million)", "MPF aggregate net asset value", "HK$ million")]


def mpfa():
    url, period, name = MPFA
    pages, ref = _pdf(url)
    n0 = len(ROWS)
    p = pages[3]
    for label, metric, unit in MPFA_SUMMARY:
        m = re.search(re.escape(label) + r"\s*(?:\([^)]*\)\s*)?\n\s*([\d][\d ,]*)\s*\n", p)
        if m:
            _row(name, period, metric, _num(m[1]), unit, url, 1)
    # Table II.2.1 quarterly contributions received and benefits paid (HK$ million)
    t = next((x for x in pages if "Table II.2.1" in x), "")
    for q in re.finditer(r"(Q[1-4] 20\d\d)\s*\n((?:[\d,]+\s*\n){10})", t):
        v = [_num(x) for x in q[2].split()]
        _row(name, q[1], "MPF contributions received - total", v[4], "HK$ million", url, 5)
        _row(name, q[1], "MPF benefits paid - total", v[9], "HK$ million", url, 5)
        _row(name, q[1], "MPF tax-deductible voluntary contributions received", v[3], "HK$ million", url, 5)
    COV.append({"source": name, "status": "collected", "records": len(ROWS) - n0, "url": url, "evidence_ref": ref,
                "note": "Industry-level only; MPFA publishes no market share by scheme sponsor"})


def icb():
    ok = robots_allowed(ICB)
    COV.append({"source": "Insurance Complaints Bureau Annual Report 2025-26", "status": "skipped - robots.txt" if not ok else "not parsed",
                "records": 0, "url": ICB,
                "note": "icb.org.hk/robots.txt disallows all automated agents (User-agent: * Disallow: /); download manually in a browser"})


TRENDS_TERMS = [["Prudential", "AIA", "Manulife", "AXA"], ["保誠", "友邦", "宏利", "安盛"]]
TERM_BRAND = {"Prudential": "Prudential", "AIA": "AIA", "Manulife": "Manulife", "AXA": "AXA",
              "保誠": "Prudential", "友邦": "AIA", "宏利": "Manulife", "安盛": "AXA"}


def trends(start, end):
    try:
        from pytrends.request import TrendReq
    except ImportError:
        COV.append({"source": "Google Trends", "status": "skipped", "records": 0, "note": "pytrends not installed"})
        return
    n0 = len(ROWS)
    tf = f"{start} {end}"
    errors = []
    for terms in TRENDS_TERMS:
        df = None
        for attempt in range(3):  # first try + 2 polite retries
            try:
                pt = TrendReq(hl="en-HK", tz=-480, timeout=(10, 30))
                pt.build_payload(terms, timeframe=tf, geo="HK")
                df = pt.interest_over_time()
                break
            except Exception as e:
                errors.append(f"{terms[0]}..: {str(e)[:80]}")
                time.sleep(30 * (attempt + 1))
        if df is None or df.empty:
            continue
        url = f"https://trends.google.com/trends/explore?date={start}%20{end}&geo=HK&q=" + ",".join(terms)
        mon = df.drop(columns=[c for c in df.columns if c == "isPartial"]).resample("MS").mean()
        for ts, row in mon.iterrows():
            if not (start.strftime("%Y-%m") <= ts.strftime("%Y-%m") <= end.strftime("%Y-%m")):
                continue  # weekly buckets straddling the window edge
            for t in terms:
                _row("Google Trends (pytrends)", ts.strftime("%Y-%m"), f"search interest: {t}", round(float(row[t]), 1),
                     "index 0-100 (relative within this 4-term comparison, HK)", url, None, brand=TERM_BRAND[t],
                     note="Keyword (not topic); monthly mean of weekly values; comparable only within the same request")
        time.sleep(5)
    got = len(ROWS) - n0
    COV.append({"source": "Google Trends", "status": "collected" if got else "skipped - rate limited", "records": got,
                "note": "; ".join(errors)[:300] or "EN and ZH brand keywords, HK, window"})


def collect(start, end, do_trends=True):
    ROWS.clear()
    COV.clear()
    for fn in (hkfi, mpfa, icb):
        try:
            fn()
        except Exception as e:
            COV.append({"source": fn.__name__, "status": "error", "records": 0, "note": str(e)[:200]})
            log(f"context {fn.__name__} FAILED: {e}")
    if do_trends:
        trends(start, end)
    for c in COV:
        c["checked_at"] = now_utc()
    (RAW / "context_coverage.json").write_text(json.dumps(COV, ensure_ascii=False, indent=1), encoding="utf-8")
    with (RAW / "context_stats.jsonl").open("w", encoding="utf-8") as f:
        for r in ROWS:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"context_stats: {len(ROWS)} rows; " + "; ".join(f"{c['source']}={c['records']} ({c['status']})" for c in COV))
    return list(ROWS)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    ap.add_argument("--no-trends", action="store_true")
    a = ap.parse_args()
    collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end), do_trends=not a.no_trends)
