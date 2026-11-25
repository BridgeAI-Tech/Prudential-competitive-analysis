"""Module 1/3 - third-party media discovery via Google News RSS (English + Traditional Chinese HK editions).

Items are labelled source_category='media' (third-party coverage, not an official announcement).
Hong Kong relevance must be explicit in the headline, or the item is kept but flagged 'unconfirmed'.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

from common import COMPANIES, TAXONOMY, clean_text, fetch, log, make_record

FEEDS = {
    "en": "https://news.google.com/rss/search?q={q}&hl=en-HK&gl=HK&ceid=HK:en",
    "zh": "https://news.google.com/rss/search?q={q}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant",
}

QUERIES = {
    "Prudential": {"en": ['"Prudential Hong Kong"', '"Prudential HK"'], "zh": ["保誠 香港 保險"]},
    "AIA": {"en": ['"AIA Hong Kong"', '"AIA HK"'], "zh": ["友邦香港"]},
    "Manulife": {"en": ['"Manulife Hong Kong"', '"Manulife HK"', 'Manulife "Hong Kong" insurance'], "zh": ["宏利 香港 保險"]},
    "AXA": {"en": ['"AXA Hong Kong"', '"AXA HK"'], "zh": ["安盛 香港 保險"]},
}

# brand term must appear in headline; guards against Prudential Financial (US), AIA architects, etc.
BRAND_RX = {
    "Prudential": re.compile(r"prudential|保誠|\bpru", re.I),
    "AIA": re.compile(r"\bAIA\b|友邦"),
    "Manulife": re.compile(r"manulife|宏利", re.I),
    "AXA": re.compile(r"\bAXA\b|安盛", re.I),
}
EXCLUDE_RX = re.compile(r"prudential financial|pgim|prudential plc share|友邦人寿|宏利人寿|中宏|安盛天平|AIA Malaysia|AIA Singapore|AIA Thailand|Manulife (Philippines|Indonesia|Vietnam|Canada)|John Hancock", re.I)
HK_RX = re.compile("|".join(re.escape(t) for t in TAXONOMY["hk_terms"]), re.I)


def month_slices(start: dt.date, end: dt.date):
    """Google News RSS returns ~100 items per query, so query month by month to reach back 12 months."""
    s = start
    while s <= end:
        nxt = (s.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        yield s, min(nxt - dt.timedelta(days=1), end)
        s = nxt


def collect(start: dt.date, end: dt.date) -> list[dict]:
    out, seen = [], set()
    for brand, langs in QUERIES.items():
        n = 0
        for lang, qs in langs.items():
            for q, (ms, me) in ((q, m) for q in qs for m in month_slices(start, end)):
                url = FEEDS[lang].format(q=quote_plus(f"{q} after:{ms - dt.timedelta(days=1)} before:{me + dt.timedelta(days=1)}"))
                try:
                    xml, ref = fetch(url, check_robots=False)  # RSS endpoint intended for programmatic consumption
                except Exception as e:
                    log(f"  gnews {brand}/{lang} {ms:%Y-%m} failed: {e}")
                    continue
                root = ET.fromstring(xml.encode("utf-8"))
                for it in root.iter("item"):
                    title = clean_text(it.findtext("title"))
                    src = it.find("source")
                    publisher = clean_text(src.text) if src is not None else None
                    headline = re.sub(r"\s+-\s+[^-]+$", "", title) if publisher and title.endswith(publisher) else title
                    if not BRAND_RX[brand].search(headline) or EXCLUDE_RX.search(headline):
                        continue
                    try:
                        pub = email.utils.parsedate_to_datetime(it.findtext("pubDate")).date()
                    except Exception:
                        continue
                    if not (start <= pub <= end):
                        continue
                    key = (brand, headline.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    hk = bool(HK_RX.search(headline)) or lang == "zh" and brand != "AIA"
                    desc = clean_text(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))
                    out.append(make_record(
                        brand=brand, record_type="news_article", modules=["M1"], title=headline,
                        description=desc[:500] or None, original_content=None,
                        publication_date=pub.isoformat(), source_name=publisher or "Google News",
                        source_category="media", source_url=it.findtext("link"), evidence_ref=ref,
                        hk_relevance="explicit" if hk else "unconfirmed",
                        hk_relevance_basis=("Hong Kong term in headline" if HK_RX.search(headline)
                                            else "HK-edition Chinese feed, HK brand name" if hk else "HK-edition feed only - verify"),
                        platform="news", content_format="article",
                        extra={"feed_lang": lang, "query": q, "publisher": publisher,
                               "link_note": "Google News redirect URL; resolves to publisher"},
                    ))
                    n += 1
        log(f"gnews {brand}: {n} items")
    return out
