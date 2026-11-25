"""Module 4.1/4.3 - publicly observable website capabilities.

Method (repeatable, evidence-backed): read each insurer's sitemap(s) + homepage navigation, match URL slugs
and link text against the digital-capability taxonomy, and keep the matching URL as evidence.
App-store descriptions are matched too (collected in apps.py) - done in classify step.
Observation = "capability publicly evidenced on date X"; absence = "not observed", never "not offered".
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from common import COMPANIES, TAXONOMY, Blocked, clean_text, fetch, log, make_record

SITEMAPS = {
    "Prudential": ["https://www.prudential.com.hk/en/sitemap.xml"],
    "AIA": ["https://www.aia.com.hk/en/sitemap.xml"],
    "AXA": ["https://www.axa.com.hk/sitemap.xml"],
    "Manulife": ["https://www.manulife.com.hk/en/sitemap.xml"],
}
HOMES = {
    "Prudential": "https://www.prudential.com.hk/en/",
    "AIA": "https://www.aia.com.hk/en/",
    "AXA": "https://www.axa.com.hk/en",
    "Manulife": "https://www.manulife.com.hk/en/",
}
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def sitemap_urls(url, depth=0):
    xml, ref = fetch(url)
    root = ET.fromstring(xml.encode("utf-8"))
    urls = []
    if root.tag.endswith("sitemapindex") and depth < 2:
        for loc in root.iter(NS + "loc"):
            if "/tc/" in loc.text or "/sc/" in loc.text or "/zh" in loc.text:
                continue
            try:
                urls += sitemap_urls(loc.text.strip(), depth + 1)[0]
            except Exception as e:
                log(f"  sitemap child {loc.text}: {e}")
    else:
        urls = [loc.text.strip() for loc in root.iter(NS + "loc")]
    return urls, ref


def slug_text(u: str) -> str:
    return re.sub(r"[-_/.]+", " ", urlparse(u).path.lower())


def match_caps(text: str) -> list[str]:
    t = " " + text.lower() + " "
    hits = []
    for cap, d in TAXONOMY["digital_capabilities"].items():
        for kw in d["en"] + d["zh"]:
            k = kw.lower()
            if (" " + k + " ") in t or (len(k) > 4 and k in t):
                hits.append(cap)
                break
    return hits


NEWSY = re.compile(r"newsroom|press-release|news-room|/article/|/blog/|customer-notices|/campaign|promotion", re.I)
SERVICE_HINT = re.compile(r"claim|e-?service|digital|/app|aia-plus|emma|mypru|myprudential|health-services|value-added|"
                          r"wellness|vitality|tools|calculator|virtual|whatsapp|chat|medical-card|direct-billing|smartappoint|tele", re.I)
MAX_SERVICE_PAGES = 30


def snippet(text: str, kw: str, width: int = 90) -> str:
    i = text.lower().find(kw.lower())
    if i < 0:
        return ""
    return "…" + clean_text(text[max(0, i - width): i + len(kw) + width]) + "…"


def page_caps(url: str) -> list[tuple[str, str, str]]:
    """Fetch a service page and return (capability, snippet, evidence_ref) for keywords in its visible text."""
    html, ref = fetch(url)
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        t.decompose()
    text = clean_text(soup.get_text(" "))
    found = []
    for cap, d in TAXONOMY["digital_capabilities"].items():
        for kw in d["en"] + d["zh"]:
            if len(kw) <= 4:
                hit = re.search(r"\b" + re.escape(kw) + r"\b", text, re.I)
            else:
                hit = re.search(re.escape(kw), text, re.I)
            if hit:
                found.append((cap, snippet(text, hit.group(0)), ref))
                break
    return found


def collect(start, end) -> list[dict]:
    out = []
    for brand in ["Prudential", "AIA", "AXA", "Manulife"]:
        evid: dict[str, list[tuple[str, str, str]]] = {}
        # 1) service pages discovered from the sitemap (English, non-news), text-matched with snippet evidence
        for sm in SITEMAPS[brand]:
            try:
                urls, ref = sitemap_urls(sm)
            except Blocked as e:
                log(f"  {brand} sitemap blocked: {e}")
                continue
            except Exception as e:
                log(f"  {brand} sitemap failed: {e}")
                continue
            urls = [u for u in urls if "/en" in u and not NEWSY.search(u) and SERVICE_HINT.search(urlparse(u).path)]
            urls = sorted(set(urls), key=lambda u: (u.count("/"), len(u)))[:MAX_SERVICE_PAGES]
            log(f"  {brand} sitemap: {len(urls)} service pages to read")
            for u in urls:
                try:
                    for cap, snip, pref in page_caps(u):
                        evid.setdefault(cap, []).append((u, f"page text: {snip}", pref))
                except Exception as e:
                    log(f"    {u}: {e}")
        # 2) homepage links (nav + footer + body)
        try:
            html, ref = fetch(HOMES[brand])
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                txt = clean_text(a.get_text(" ") or a.get("aria-label") or a.get("title") or "")
                if not txt or len(txt) > 80:
                    continue
                u = urljoin(HOMES[brand], a["href"])
                for cap in match_caps(txt + " " + slug_text(u)):
                    evid.setdefault(cap, []).append((u, f"homepage link: '{txt}'", ref))
        except Blocked as e:
            log(f"  {brand} homepage blocked: {e}")
        if not evid:
            continue
        for cap, ev in evid.items():
            # keep up to 3 distinct evidence URLs, prefer homepage links (more explicit)
            ev = sorted({e[0]: e for e in ev}.values(), key=lambda e: (not e[1].startswith("page text"), len(e[0])))[:3]
            label = TAXONOMY["digital_capabilities"][cap]["label"]
            out.append(make_record(
                brand=brand, record_type="web_feature", modules=["M4"], activity_type="digital_capability",
                title=f"{brand} website: {label}", description="; ".join(e[1] for e in ev),
                original_content="\n".join(e[0] for e in ev), publication_date=None,
                source_name=f"{brand} official website", source_category="official", source_url=ev[0][0],
                evidence_ref=ev[0][2], hk_relevance="explicit", hk_relevance_basis="Official HK website",
                platform="website", content_format="web_page",
                extra={"capability": cap, "capability_label": label, "evidence_urls": [e[0] for e in ev],
                       "method": "sitemap+homepage keyword match"},
            ))
        log(f"web features {brand}: {len(evid)} capabilities evidenced")
    return out
