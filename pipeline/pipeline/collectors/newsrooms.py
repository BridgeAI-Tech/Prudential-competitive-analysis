"""Module 1/3/4 - official insurer newsrooms (Priority 1 sources)."""
from __future__ import annotations

import datetime as dt
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common import Blocked, clean_text, fetch, log, make_record

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s: str) -> dt.date | None:
    s = clean_text(s).replace(".", "").replace(",", "")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def extract_article(html: str) -> dict:
    """Generic article body extraction: JSON-LD date, meta description, main paragraphs, lead image."""
    soup = BeautifulSoup(html, "lxml")
    out = {"date": None, "description": None, "body": None, "image": None}
    for s in soup.find_all("script", type="application/ld+json"):
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', s.string or "")
        if m:
            out["date"] = m.group(1)[:10]
            break
    md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if md and md.get("content"):
        out["description"] = clean_text(md["content"])
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        out["image"] = og["content"]
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "form"]):
        t.decompose()
    paras = [clean_text(p.get_text(" ")) for p in soup.find_all(["p", "li"])]
    paras = [p for p in paras if len(p) > 60 and "cookie" not in p.lower()]
    seen, body = set(), []
    for p in paras:
        if p not in seen:
            seen.add(p)
            body.append(p)
    out["body"] = "\n".join(body)[:8000] or None
    return out


def _record(brand, title, url, pub, art, list_ref, art_ref, source_name):
    return make_record(
        brand=brand, record_type="announcement", modules=["M1"], title=clean_text(title),
        description=art.get("description"), original_content=art.get("body"),
        publication_date=pub.isoformat() if pub else None, source_name=source_name,
        source_category="official", source_url=url, evidence_ref=art_ref or list_ref,
        hk_relevance="explicit", hk_relevance_basis="Official Hong Kong insurer newsroom",
        platform="website", content_format="press_release",
        extra={"image": art.get("image"), "list_evidence_ref": list_ref},
    )


def collect_prudential(start: dt.date, end: dt.date) -> list[dict]:
    base = "https://www.prudential.com.hk"
    html, ref = fetch(base + "/en/about-us/newsroom/")
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("article.article-card"):
        a = card.find("a", href=True)
        pub = parse_date(card.get("data-date", ""))
        if not a or not pub or not (start <= pub <= end):
            continue
        url = urljoin(base, a["href"])
        title = (card.find(["h3", "h2", "h4"]) or card.find("img") or a)
        title = title.get("alt") if title.name == "img" else title.get_text(" ")
        try:
            ahtml, aref = fetch(url)
            art = extract_article(ahtml)
        except Exception as e:  # keep list-level evidence even if article fails
            log(f"  PRU article failed {url}: {e}")
            art, aref = {}, None
        if art.get("date"):
            pub = parse_date(art["date"]) or pub
        out.append(_record("Prudential", title, url, pub, art, ref, aref, "Prudential HK Newsroom"))
    return _dedupe_urls(out)


def collect_aia(start: dt.date, end: dt.date) -> list[dict]:
    base = "https://www.aia.com.hk"
    html, ref = fetch(base + "/en/about-aia/about-us/media-centre/press-releases")
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select(".cmp-promotioncard"):
        a = card.find("a", href=re.compile("press-releases/"))
        d = card.select_one(".cmp-promotioncard__date")
        t = card.select_one(".cmp-promotioncard__title")
        if not (a and d and t):
            continue
        pub = parse_date(d.get_text())
        if not pub or not (start <= pub <= end):
            continue
        url = urljoin(base, a["href"])
        try:
            ahtml, aref = fetch(url)
            art = extract_article(ahtml)
        except Exception as e:
            log(f"  AIA article failed {url}: {e}")
            art, aref = {}, None
        out.append(_record("AIA", t.get_text(" "), url, pub, art, ref, aref, "AIA HK Press Releases"))
    return _dedupe_urls(out)


def collect_axa(start: dt.date, end: dt.date) -> list[dict]:
    base = "https://www.axa.com.hk"
    out = []
    for year in sorted({start.year, end.year}):
        try:
            html, ref = fetch(f"{base}/en/news-room/{year}")
        except Blocked as e:
            log(f"  AXA newsroom {year}: {e}")
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            continue
        nd = json.loads(m.group(1))
        items = []
        for sl in nd["props"]["pageProps"].get("sliceZone", {}).get("slices", []):
            for it in (sl.get("value") or {}).get("items", []) or []:
                if isinstance(it, dict) and it.get("publishDate") and it.get("url"):
                    items.append(it)
        for it in items:
            pub = parse_date(it["publishDate"])
            if not pub or not (start <= pub <= end):
                continue
            url = urljoin(base, it["url"])
            try:
                ahtml, aref = fetch(url)
                art = extract_article(ahtml)
            except Exception as e:
                log(f"  AXA article failed {url}: {e}")
                art, aref = {}, None
            out.append(_record("AXA", it["title"], url, pub, art, ref, aref, "AXA HK Newsroom"))
    return _dedupe_urls(out)


def collect_manulife(start, end) -> list[dict]:
    """manulife.com.hk denies automated access (HTTP 403). Record the gap instead of guessing."""
    try:
        fetch("https://www.manulife.com.hk/en/individual/about/newsroom.html")
    except Exception as e:
        log(f"  Manulife newsroom blocked: {e}")
        return []
    return []


def _dedupe_urls(recs):
    seen, out = set(), []
    for r in recs:
        if r["source_url"] not in seen:
            seen.add(r["source_url"])
            out.append(r)
    return out


def collect(start, end) -> list[dict]:
    recs = []
    for name, fn in [("Prudential", collect_prudential), ("AIA", collect_aia), ("AXA", collect_axa), ("Manulife", collect_manulife)]:
        try:
            r = fn(start, end)
            log(f"newsroom {name}: {len(r)} records in window")
            recs += r
        except Exception as e:
            log(f"newsroom {name} FAILED: {e}")
    return recs
