"""Module 1 - extra third-party media: InsuranceAsia News HK feed, insuranceasia.com HK market page, SCMP + RTHK RSS,
and extra Google News RSS queries ("<Brand> Hong Kong" EN and the Chinese brand name ZH, month by month).

Kept only when the brand is named in the headline/lead and the item has a Hong Kong link. Items already held by the
existing collectors (same URL or same brand + headline) are skipped, so the build does not double count.

Usage:  python -I pipeline/collectors/media_feeds.py [--start 2025-11-01] [--end 2026-10-31]
Writes  data/raw/media_feeds.jsonl, data/raw/media_feeds_coverage.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote_plus, urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from common import RAW, clean_text, fetch, load_json, log, make_record, now_utc, read_jsonl, write_jsonl  # noqa: E402
from google_news import BRAND_RX, EXCLUDE_RX, FEEDS, HK_RX, month_slices  # noqa: E402

GNEWS_EXTRA = {"Prudential": {"en": ["Prudential Hong Kong"], "zh": ["保誠"]},
               "AIA": {"en": ["AIA Hong Kong"], "zh": ["友邦"]},
               "Manulife": {"en": ["Manulife Hong Kong"], "zh": ["宏利"]},
               "AXA": {"en": ["AXA Hong Kong"], "zh": ["安盛"]}}
IAN_FEED = "https://insuranceasianews.com/country/hong-kong/feed/?paged={p}"
IA_MARKET = "https://insuranceasia.com/market/hong-kong?page={p}"
RSS = {"SCMP Business": "https://www.scmp.com/rss/92/feed", "SCMP Hong Kong": "https://www.scmp.com/rss/2/feed",
       "RTHK Finance": "https://rthk.hk/rthk/news/rss/e_expressnews_efinance.xml", "RTHK Local": "https://rthk.hk/rthk/news/rss/e_expressnews_elocal.xml"}
COV: list[dict] = []


def _norm_title(t: str) -> str:
    t = re.sub(r"\s+[-|–]\s+[^-|–]{2,60}$", "", t or "")
    return re.sub(r"[\W_]+", "", t.lower())


def _norm_url(u: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", (u or "").split("?")[0].split("#")[0].rstrip("/").lower())


class Known:
    """URLs and (brand, headline) already held by the other collectors."""

    def __init__(self):
        self.urls, self.titles = set(), set()
        for f in ("newsrooms", "google_news", "seed_extracts", "excel_imports"):
            p = RAW / f"{f}.jsonl"
            if p.exists():
                for r in read_jsonl(p):
                    self.add(r)

    def add(self, r):
        self.urls.add(_norm_url(r.get("source_url")))
        self.titles.add((r.get("brand"), _norm_title(r.get("title"))))

    def has(self, brand, url, title):
        return _norm_url(url) in self.urls or (brand, _norm_title(title)) in self.titles


def _brands_in(text: str) -> list[str]:
    return [b for b, rx in BRAND_RX.items() if rx.search(text) and not EXCLUDE_RX.search(text)]


def _rec(brand, title, url, pub, desc, source_name, ref, basis, hk, extra):
    return make_record(brand=brand, record_type="news_article", modules=["M1"], title=title, description=(desc or "")[:500] or None,
                       original_content=desc or None, publication_date=pub.isoformat(), source_name=source_name,
                       source_category="media", source_url=url, evidence_ref=ref, hk_relevance="explicit" if hk else "unconfirmed",
                       hk_relevance_basis=basis, platform="news", content_format="article", extra=extra)


def _rss_items(xml: str):
    root = ET.fromstring(xml.encode("utf-8"))
    for it in root.iter("item"):
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate")).date()
        except Exception:
            continue
        desc = clean_text(BeautifulSoup(it.findtext("description") or "", "lxml").get_text(" "))
        desc = re.sub(r"The post .* appeared first on .*$", "", desc).strip()
        yield clean_text(it.findtext("title")), it.findtext("link"), pub, desc, it


def insuranceasia_news(start, end, known):
    out, oldest = [], None
    for p in range(1, 80):
        try:
            xml, ref = fetch(IAN_FEED.format(p=p))
        except Exception as e:
            log(f"  IAN feed page {p}: {e}")
            break
        items = list(_rss_items(xml))
        if not items:
            break
        for title, url, pub, desc, _ in items:
            oldest = pub
            if not (start <= pub <= end):
                continue
            for b in _brands_in(title + " " + desc[:300]):
                if known.has(b, url, title):
                    continue
                r = _rec(b, title, url, pub, desc, "InsuranceAsia News", ref, "InsuranceAsia News Hong Kong section (country tag)", True,
                         {"publisher": "InsuranceAsia News", "feed": "country/hong-kong", "paywalled": True, "cov_source": "InsuranceAsia News HK feed"})
                known.add(r)
                out.append(r)
        if oldest and oldest < start:
            break
    COV.append({"source": "InsuranceAsia News HK feed", "records": len(out), "status": "collected", "note": f"paged RSS back to {oldest}"})
    return out


def _ia_article(url):
    html, ref = fetch(url)
    s = BeautifulSoup(html, "lxml")
    m = s.find("meta", attrs={"property": "article:published_time"})
    pub = dt.date.fromisoformat(m["content"][:10]) if m and m.get("content") else None
    d = s.find("meta", attrs={"name": "description"}) or s.find("meta", attrs={"property": "og:description"})
    return pub, clean_text(d.get("content") if d else ""), ref


def insuranceasia_market(start, end, known):
    out, last_date = [], None
    for p in range(0, 61):
        try:
            html, ref = fetch(IA_MARKET.format(p=p))
        except Exception as e:
            log(f"  insuranceasia page {p}: {e}")
            break
        s = BeautifulSoup(html, "lxml")
        links = []
        for a in s.select("a[href]"):
            href, t = a["href"], a.get_text(" ", strip=True)
            if re.search(r"/(insurance/)?(news|event-news|exclusive|interview|commentary|in-focus)/", href) and len(t) > 25:
                u = urljoin("https://insuranceasia.com", href)
                if u not in [x[0] for x in links]:
                    links.append((u, t))
        if not links:
            break
        for u, t in links:
            bs = [b for b in _brands_in(t)]
            if not bs or all(known.has(b, u, t) for b in bs):
                continue
            try:
                pub, desc, aref = _ia_article(u)
            except Exception as e:
                log(f"  insuranceasia article {u}: {e}")
                continue
            if not pub or not (start <= pub <= end):
                continue
            hk = bool(HK_RX.search(t + " " + desc))
            for b in bs:
                if known.has(b, u, t):
                    continue
                r = _rec(b, t, u, pub, desc, "Insurance Asia", aref,
                         "Listed on insuranceasia.com Hong Kong market page" + ("; HK named in headline/lead" if hk else ""), True,
                         {"publisher": "Insurance Asia", "list_page": IA_MARKET.format(p=p), "list_evidence_ref": ref, "cov_source": "insuranceasia.com Hong Kong market page"})
                known.add(r)
                out.append(r)
        try:  # page oldest item date (list is newest first) -> stop once past the window start
            last_date = _ia_article(links[-1][0])[0]
        except Exception:
            last_date = None
        if last_date and last_date < start:
            break
    COV.append({"source": "insuranceasia.com Hong Kong market page", "records": len(out), "status": "collected", "note": f"scanned list pages 0-{p}; brand-named headlines opened for dates (last-link date {last_date} may be a sidebar item)"})
    return out


def latest_rss(start, end, known):
    out = []
    for name, url in RSS.items():
        try:
            xml, ref = fetch(url)
        except Exception as e:
            COV.append({"source": name + " RSS", "records": 0, "status": "error", "note": str(e)[:150]})
            continue
        n, dates = 0, []
        for title, link, pub, desc, _ in _rss_items(xml):
            dates.append(pub)
            if not (start <= pub <= end):
                continue
            for b in _brands_in(title + " " + desc[:300]):
                if known.has(b, link, title):
                    continue
                hk = name.startswith("RTHK") or name == "SCMP Hong Kong" or bool(HK_RX.search(title + " " + desc))
                r = _rec(b, title, link, pub, desc, name.split()[0], ref, f"{name} feed" + ("; HK feed/terms" if hk else ""), hk,
                         {"publisher": name.split()[0], "feed": url, "cov_source": name + " RSS"})
                known.add(r)
                out.append(r)
                n += 1
        span = f"{min(dates)}..{max(dates)}" if dates else "empty"
        COV.append({"source": name + " RSS", "records": n, "status": "collected" if n else "none in window",
                    "note": f"RSS carries only latest items ({span}); no archive paging"})
    return out


def gnews_extra(start, end, known):
    out = []
    for brand, langs in GNEWS_EXTRA.items():
        n = 0
        for lang, qs in langs.items():
            for q in qs:
                for ms, me in month_slices(start, end):
                    url = FEEDS[lang].format(q=quote_plus(f"{q} after:{ms - dt.timedelta(days=1)} before:{me + dt.timedelta(days=1)}"))
                    try:
                        xml, ref = fetch(url, check_robots=False)  # RSS endpoint intended for programmatic use (as google_news.py)
                    except Exception as e:
                        log(f"  gnews+ {brand}/{lang} {ms:%Y-%m}: {e}")
                        continue
                    for title, link, pub, desc, it in _rss_items(xml):
                        src = it.find("source")
                        publisher = clean_text(src.text) if src is not None else None
                        headline = re.sub(r"\s+-\s+[^-]+$", "", title) if publisher and title.endswith(publisher) else title
                        if not BRAND_RX[brand].search(headline) or EXCLUDE_RX.search(headline) or not (start <= pub <= end):
                            continue
                        if known.has(brand, link, headline):
                            continue
                        hk_head = bool(HK_RX.search(headline))
                        hk = hk_head or (lang == "zh" and brand != "AIA")
                        r = _rec(brand, headline, link, pub, None, publisher or "Google News", ref,
                                 "Hong Kong term in headline" if hk_head else "HK-edition Chinese feed, HK brand name" if hk else "HK-edition feed only - verify",
                                 hk, {"feed_lang": lang, "query": q, "publisher": publisher, "collector": "media_feeds/gnews_extra", "cov_source": "Google News RSS (extra queries)",
                                      "link_note": "Google News redirect URL; resolves to publisher"})
                        known.add(r)
                        out.append(r)
                        n += 1
        log(f"gnews+ {brand}: {n} new items")
    COV.append({"source": "Google News RSS (extra queries)", "records": len(out), "status": "collected",
                "note": "EN '<Brand> Hong Kong' + ZH brand name, month by month; de-duplicated against existing collectors"})
    return out


def collect(start, end):
    COV.clear()
    known = Known()
    out = []
    for fn in (insuranceasia_news, insuranceasia_market, latest_rss, gnews_extra):
        try:
            r = fn(start, end, known)
            log(f"media_feeds {fn.__name__}: {len(r)}")
            out += r
        except Exception as e:
            log(f"media_feeds {fn.__name__} FAILED: {e}")
            COV.append({"source": fn.__name__, "records": 0, "status": "error", "note": str(e)[:200]})
    for c in COV:
        c["checked_at"] = now_utc()
        c["by_brand"] = {}
    for r in out:
        src = next((c for c in COV if c["source"] == r["extra"].get("cov_source")), None)
        if src:
            src["by_brand"][r["brand"]] = src["by_brand"].get(r["brand"], 0) + 1
    (RAW / "media_feeds_coverage.json").write_text(json.dumps(COV, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    recs = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    write_jsonl("media_feeds", recs)
    log(f"media_feeds: {len(recs)} records")
