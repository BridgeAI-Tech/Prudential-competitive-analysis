"""Module 1/2/3 - named Hong Kong news, marketing and insurance-industry publications (walkthrough call, 16 Nov 2026).

For each publication in brief s5.6 plus the extra Hong Kong titles named on the call, query the Google News RSS
search endpoint with `site:<domain>` and each brand name (English and Chinese), quarter by quarter, so every
publication is searched explicitly rather than only when it surfaces in a general query. Also runs:
  * campaign queries (Prudential "Promises Made Real" coverage, and each rival's 2026 campaign), and
  * health and critical-illness queries per brand (client priority, 16 Nov 2026).

Kept only when the brand is named in the headline and not on the exclusion list (other markets). Items already held
by the other collectors (same URL, or same brand + headline) are skipped, so nothing is double counted.
Hong Kong relevance: publications based in Hong Kong count as explicit; regional titles need a Hong Kong term.

Usage:  python -I pipeline/collectors/hk_media_sites.py [--start 2025-11-01] [--end 2026-10-31]
Writes  data/raw/hk_media_sites.jsonl, data/raw/hk_media_sites_coverage.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, clean_text, fetch, load_json, log, now_utc, write_jsonl  # noqa: E402
from google_news import BRAND_RX, EXCLUDE_RX, FEEDS, HK_RX  # noqa: E402
from media_feeds import Known, _rec, _rss_items  # noqa: E402

# name, domain, languages to query, based in Hong Kong?, group shown on the dashboard
PUBS = [
    ("South China Morning Post", "scmp.com", ["en"], True, "Hong Kong news"),
    ("The Standard", "thestandard.com.hk", ["en"], True, "Hong Kong news"),
    ("RTHK", "news.rthk.hk", ["en", "zh"], True, "Hong Kong news"),
    ("HK01", "hk01.com", ["zh"], True, "Hong Kong news"),
    ("Hong Kong Economic Journal", "hkej.com", ["zh"], True, "Hong Kong news"),
    ("Ming Pao Finance", "mingpao.com", ["zh"], True, "Hong Kong news"),
    ("Sing Tao", "stheadline.com", ["zh"], True, "Hong Kong news"),
    ("AM730", "am730.com.hk", ["zh"], True, "Hong Kong news"),
    ("Hong Kong Economic Times", "hket.com", ["zh"], True, "Hong Kong news"),
    ("Hong Kong Business", "hongkongbusiness.hk", ["en"], True, "Business and marketing"),
    ("Marketing-Interactive", "marketing-interactive.com", ["en"], False, "Business and marketing"),
    ("Campaign Asia", "campaignasia.com", ["en"], False, "Business and marketing"),
    ("InsuranceAsia News", "insuranceasianews.com", ["en"], False, "Insurance industry"),
    ("Asia Insurance Review", "asiainsurancereview.com", ["en"], False, "Insurance industry"),
    ("Hong Kong Insurance Journal", "hkinsurancenews.com", ["en", "zh"], True, "Insurance industry"),
    ("Dentsu", "dentsu.com", ["en"], False, "Agency press releases"),
]
BRAND_TERMS = {"Prudential": {"en": "Prudential", "zh": "保誠"}, "AIA": {"en": "AIA", "zh": "友邦"},
               "Manulife": {"en": "Manulife", "zh": "宏利"}, "AXA": {"en": "AXA", "zh": "安盛"}}
CAMPAIGN_Q = {
    "Prudential": {"en": ['"Promises Made Real" Prudential', '"A Promise Made, A Promise Kept" Prudential', '"Every Promise Has a Story" Prudential',
                          'Prudential "Eason Chan"'], "zh": ["保誠 陳奕迅", "保誠 承諾"]},
    "AIA": {"en": ['AIA "Protection Comes in Many Ways"', "AIA Hong Kong campaign"], "zh": ["友邦 廣告", "友邦 品牌"]},
    "Manulife": {"en": ['Manulife "Where will better take you"', 'Manulife "Andy Lau"'], "zh": ["宏利 劉德華"]},
    "AXA": {"en": ['AXA "Sammi Cheng"', "AXA Hong Kong campaign"], "zh": ["安盛 鄭秀文"]},
}
HEALTH_Q = {
    "Prudential": {"en": ["Prudential Hong Kong critical illness", "Prudential Hong Kong medical insurance", "PRUHealth"],
                   "zh": ["保誠 危疾", "保誠 醫療保險", "保誠 癌症"]},
    "AIA": {"en": ["AIA Hong Kong critical illness", "AIA Hong Kong medical insurance"], "zh": ["友邦 危疾", "友邦 醫療保險", "友邦 癌症"]},
    "Manulife": {"en": ["Manulife Hong Kong critical illness", "Manulife Hong Kong medical insurance"], "zh": ["宏利 危疾", "宏利 醫療保險", "宏利 癌症"]},
    "AXA": {"en": ["AXA Hong Kong critical illness", "AXA Hong Kong medical insurance"], "zh": ["安盛 危疾", "安盛 醫療保險", "安盛 癌症"]},
}
# brief s5.6: "Google News - HK Insurance" (news discovery; links are validated against the original publisher on ingest)
DISCOVERY_Q = {b: {"en": [f'"Hong Kong" insurance {t["en"]}'], "zh": [f"香港 保險 {t['zh']}"]} for b, t in
               {"Prudential": {"en": "Prudential", "zh": "保誠"}, "AIA": {"en": "AIA", "zh": "友邦"},
                "Manulife": {"en": "Manulife", "zh": "宏利"}, "AXA": {"en": "AXA", "zh": "安盛"}}.items()}
HEALTH_RX = re.compile(r"critical illness|cancer|medical|health|hospital|VHIS|危疾|嚴重疾病|癌|醫療|健康|醫院|自願醫保", re.I)
COV: dict[str, dict] = {}


def quarters(start: dt.date, end: dt.date):
    s = start
    while s <= end:
        m = s.month - 1 + 3
        nxt = dt.date(s.year + m // 12, m % 12 + 1, 1)
        yield s, min(nxt - dt.timedelta(days=1), end)
        s = nxt


def _cov(name, group="", domain=""):
    return COV.setdefault(name, {"source": name, "group": group, "domain": domain, "queries": 0, "errors": 0,
                                 "hits": 0, "records": 0, "already_held": 0, "by_brand": {}})


def _run(query, lang, start, end, brand, known, cov, *, hk_pub, source_label, kind, need_rx=None):
    out = []
    for qs, qe in quarters(start, end):
        url = FEEDS[lang].format(q=quote_plus(f"{query} after:{qs - dt.timedelta(days=1)} before:{qe + dt.timedelta(days=1)}"))
        cov["queries"] += 1
        try:
            xml, ref = fetch(url, check_robots=False)  # RSS endpoint intended for programmatic consumption (as google_news.py)
        except Exception as e:
            cov["errors"] += 1
            log(f"  {source_label} {brand}/{lang} {qs:%Y-%m}: {e}")
            continue
        for title, link, pub, _desc, it in _rss_items(xml):
            src = it.find("source")
            publisher = clean_text(src.text) if src is not None else None
            headline = re.sub(r"\s+-\s+[^-]+$", "", title) if publisher and title.endswith(publisher) else title
            if not BRAND_RX[brand].search(headline) or EXCLUDE_RX.search(headline) or not (start <= pub <= end):
                continue
            if need_rx and not need_rx.search(headline):
                continue
            cov["hits"] += 1
            if known.has(brand, link, headline):
                cov["already_held"] += 1
                continue
            hk_head = bool(HK_RX.search(headline))
            hk = hk_pub or hk_head or (lang == "zh" and brand != "AIA")
            basis = ("Hong Kong publication" if hk_pub else "Hong Kong term in headline" if hk_head
                     else "HK-edition Chinese feed, HK brand name" if hk else "Regional publication; Hong Kong link not confirmed")
            r = _rec(brand, headline, link, pub, None, publisher or source_label, ref, basis, hk,
                     {"feed_lang": lang, "query": query, "publisher": publisher, "collector": "hk_media_sites", "search_kind": kind,
                      "cov_source": source_label, "link_note": "Google News redirect URL; resolves to publisher"})
            known.add(r)
            out.append(r)
            cov["records"] += 1
            cov["by_brand"][brand] = cov["by_brand"].get(brand, 0) + 1
    return out


def collect(start: dt.date, end: dt.date) -> list[dict]:
    COV.clear()
    known = Known()
    p = RAW / "media_feeds.jsonl"
    if p.exists():
        from common import read_jsonl
        for r in read_jsonl(p):
            known.add(r)
    out = []
    for name, domain, langs, hk_pub, group in PUBS:
        cov = _cov(name, group, domain)
        for brand, terms in BRAND_TERMS.items():
            for lang in langs:
                out += _run(f"site:{domain} {terms[lang]}", lang, start, end, brand, known, cov, hk_pub=hk_pub, source_label=name, kind="publication")
        log(f"hk_media_sites {name}: {cov['hits']} brand headlines, {cov['records']} new")
    for label, qmap, kind, rx in (("Campaign coverage searches", CAMPAIGN_Q, "campaign", None),
                                  ("Health and critical-illness searches", HEALTH_Q, "health_ci", HEALTH_RX),
                                  ("Google News: Hong Kong insurance discovery", DISCOVERY_Q, "discovery", None)):
        cov = _cov(label, "Topic searches")
        for brand, langs in qmap.items():
            for lang, qs in langs.items():
                for q in qs:
                    out += _run(q, lang, start, end, brand, known, cov, hk_pub=False, source_label=label, kind=kind, need_rx=rx)
        log(f"hk_media_sites {label}: {cov['hits']} brand headlines, {cov['records']} new")
    for c in COV.values():
        c["checked_at"] = now_utc()
        c["status"] = "error" if c["errors"] and not c["hits"] else "collected" if c["records"] else "searched; nothing new" if c["hits"] else "searched; no brand headlines"
    (RAW / "hk_media_sites_coverage.json").write_text(json.dumps(list(COV.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    recs = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    write_jsonl("hk_media_sites", recs)
    log(f"hk_media_sites: {len(recs)} records")
