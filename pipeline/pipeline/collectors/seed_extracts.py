"""Module 1 - import prior API extracts: news_announcements_data.xlsx (combined) plus the per-tool exa_data.xlsx,
tavily_data.xlsx and google_news_rss_data.xlsx (same schema; overlapping rows are de-duplicated by URL).

Only rows with a publication date inside the window, a real article URL and the brand named in the
headline are kept. Vendor event_type labels are discarded and re-classified with our taxonomy.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlparse

import openpyxl

from common import COMPANIES, ROOT, clean_text, log, make_record

FILES = [ROOT.parent / f for f in ("news_announcements_data.xlsx", "google_news_rss_data.xlsx", "exa_data.xlsx", "tavily_data.xlsx")]
NAME_TO_BRAND = {c["display_name"]: c["brand"] for c in COMPANIES}
BRAND_RX = {
    "Prudential": re.compile(r"prudential|保誠|\bPRU", re.I),
    "AIA": re.compile(r"\bAIA\b|友邦"),
    "Manulife": re.compile(r"manulife|宏利", re.I),
    "AXA": re.compile(r"\bAXA\b|安盛", re.I),
}
EXCLUDE = re.compile(r"prudential financial|PGIM|AIA (Malaysia|Singapore|Thailand|Philippines|Vietnam|Australia)|Manulife (Philippines|Indonesia|Vietnam|Canada|Investment Management)|John Hancock|sign in|login|newsroom \|", re.I)
HK = re.compile(r"hong kong|\bHK\b|香港|GBA|greater bay|macau|澳門", re.I)
JUNK_PATH = re.compile(r"/(newsroom|press-release|news-room|media-centre)/?$|login|sign-in|search", re.I)


def collect(start, end) -> list[dict]:
    out, seen = [], set()
    for f in FILES:
        if f.exists():
            n0 = len(out)
            out += _collect_file(f, start, end, seen)
            log(f"seed extracts {f.name}: {len(out) - n0} new rows in window")
        else:
            log(f"seed extracts: {f.name} missing")
    log(f"seed extracts: {len(out)} rows in window")
    return out


def _collect_file(FILE, start, end, seen) -> list[dict]:
    ws = openpyxl.load_workbook(FILE, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = {k: i for i, k in enumerate(rows[0])}
    out = []
    for n, r in enumerate(rows[1:], start=2):
        brand = NAME_TO_BRAND.get(r[h["company_name"]])
        url, d, title = r[h["event_url"]], r[h["event_date"]], clean_text(r[h["event_headline"]])
        if not (brand and url and d and title):
            continue
        try:
            pub = dt.date.fromisoformat(str(d)[:10])
        except ValueError:
            continue
        if not (start <= pub <= end) or JUNK_PATH.search(urlparse(url).path) or EXCLUDE.search(title):
            continue
        if not BRAND_RX[brand].search(title):
            continue
        key = url.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        domain = urlparse(url).netloc.lower()
        company = next(c for c in COMPANIES if c["brand"] == brand)
        official = any(domain.endswith(dm) for dm in company["domains"])
        summary = clean_text(r[h["event_summary"]])
        hk = official or bool(HK.search(title + " " + summary[:600]))
        out.append(make_record(
            brand=brand, record_type="announcement" if official else "news_article", modules=["M1"],
            title=title, description=summary[:500] or None, original_content=summary or None,
            publication_date=pub.isoformat(), source_name=(r[h["source_publisher"]] if "source_publisher" in h else None) or domain,
            source_category="official" if official else "media", source_url=url,
            evidence_ref=f"{FILE.name}#row{n}", hk_relevance="explicit" if hk else "unconfirmed",
            hk_relevance_basis="Official HK domain" if official else ("Hong Kong term in headline/summary" if hk else "Not explicit - verify"),
            platform="website" if official else "news", content_format="press_release" if official else "article",
            extra={"import": FILE.name, "vendor_event_type": r[h["event_type"]]},
        ))
    return out
