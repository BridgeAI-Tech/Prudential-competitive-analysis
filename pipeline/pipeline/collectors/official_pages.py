"""Official pages: (1) each insurer's "official platforms / beware of scams" directory -> verified official accounts,
(2) Emma by AXA page -> web_feature capability evidence (M4), (3) Prudential /tc and AXA /zh newsroom items in the
window that are not already held in English (language-neutral URL match) -> announcements in the original language.

manulife.com.hk returns 403 to bots: its official accounts are read from the Internet Archive copy of
/en/individual.html (schema.org sameAs + footer). Phone numbers and e-mail addresses on these pages are never stored.

Usage:  python -I pipeline/collectors/official_pages.py [--start 2025-11-01] [--end 2026-10-31]
Writes  data/raw/official_pages.jsonl (observations), data/raw/official_accounts.jsonl (table official_accounts),
        data/raw/official_pages_coverage.json
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup  # noqa: E402

from common import RAW, clean_text, fetch, load_json, log, make_record, now_utc, read_jsonl, write_jsonl  # noqa: E402
from digital_features import snippet  # noqa: E402
from common import TAXONOMY, save_snapshot  # noqa: E402
from newsrooms import _record, extract_article, parse_date  # noqa: E402

DIRECTORIES = {
    "Prudential": "https://www.prudential.com.hk/en/claims-and-services/tools/customer-notices/security-alerts/",
    "AIA": "https://www.aia.com.hk/en/help-and-support/information-and-faq/beware-of-scams-guide",
    "AXA": "https://www.axa.com.hk/en/beware-of-scams",
}
MANULIFE_HOME = "https://www.manulife.com.hk/en/individual.html"
EMMA = "https://emma.axa.com.hk/en/emma/"
SOCIAL = [("facebook", r"facebook\.com/"), ("instagram", r"instagram\.com/"), ("youtube", r"youtube\.com/"),
          ("linkedin", r"linkedin\.com/company/"), ("threads", r"threads\.(com|net)/"), ("xiaohongshu", r"xiaohongshu\.com/user/"),
          ("wechat_page", r"/wechat\b"), ("weibo", r"weibo\.com/"), ("tiktok", r"tiktok\.com/@")]
TEXT_IDS = [("wechat", r"WeChat ID:\s*([A-Za-z0-9_一-鿿-]+)"), ("wechat_channels", r"WeChannel ID:\s*([A-Za-z0-9_]+)"),
            ("xiaohongshu", r"Xiaohongshu ID:\s*(\d+)")]
OFFICIAL_SEG = re.compile(r"official (website|websites)\s*/?\s*(and )?platforms", re.I)
SEG_END = re.compile(r"Email Domain|Fraudulent|If in doubt|SMS send|Unauthorised", re.I)


def _norm(u: str) -> str:
    u = re.sub(r"^https?://(www\.)?", "https://", u.strip()).rstrip("/")
    return u


def _accounts_from(html: str, brand: str, page_url: str, ref: str, basis: str) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    found: dict[tuple, dict] = {}
    urls = [a["href"] for a in s.find_all("a", href=True)]
    for sc in s.find_all("script", type="application/ld+json"):  # schema.org sameAs (Manulife)
        for m in re.finditer(r'"sameAs"\s*:\s*\[([^\]]*)\]', sc.string or ""):
            urls += re.findall(r'"(https?://[^"]+)"', m.group(1))
    for u in urls:
        u = urljoin(page_url, u)
        for plat, rx in SOCIAL:
            if re.search(rx, u, re.I) and "share" not in u and "sharer" not in u:
                key = (plat, _norm(u).lower())
                found.setdefault(key, {"platform": plat, "url": _norm(u), "account_id": None})
                break
    for t in s(["script", "style"]):
        t.decompose()
    text = re.sub(r"\s+", " ", s.get_text(" "))
    m = OFFICIAL_SEG.search(text)
    seg = text[m.start():] if m else ""
    e = SEG_END.search(seg[30:]) if seg else None
    seg = seg[: e.start() + 30] if e else seg[:3000]
    for plat, rx in TEXT_IDS:
        mm = re.search(rx, seg)
        if mm:
            found.setdefault((plat, mm.group(1)), {"platform": plat, "url": None, "account_id": mm.group(1)})
    cap = now_utc()
    return [{"brand": brand, **v, "source_page": page_url, "evidence_ref": ref, "verification_basis": basis,
             "listed_in_official_table": bool(seg) and ((v["url"] or "").split("//")[-1].split("?")[0].lower().replace("www.", "") in seg.lower().replace("www.", "")
                                                          or (v["account_id"] or "~") in seg),
             "captured_at": cap} for v in found.values()]


def official_accounts():
    rows, cov = [], []
    for brand, url in DIRECTORIES.items():
        try:
            html, ref = fetch(url)
            r = _accounts_from(html, brand, url, ref, "Insurer's own official-platforms / anti-scam page")
            rows += r
            cov.append({"brand": brand, "source": "Official platforms directory", "status": "collected", "records": len(r), "note": url})
        except Exception as e:
            cov.append({"brand": brand, "source": "Official platforms directory", "status": "error", "records": 0, "note": str(e)[:150]})
    try:  # Manulife: Internet Archive copy (live site 403)
        txt, _ = fetch("https://web.archive.org/cdx/search/cdx", params={"url": MANULIFE_HOME, "output": "json", "filter": "statuscode:200",
                                                                          "from": "2026", "fl": "timestamp"}, save_evidence=False)
        ts = json.loads(txt)[-1][0]
        au = f"https://web.archive.org/web/{ts}id_/{MANULIFE_HOME}"
        html, ref = fetch(au)
        r = _accounts_from(html, "Manulife", MANULIFE_HOME, au.replace("id_/", "/"),
                           f"Internet Archive copy ({ts}) of manulife.com.hk home: schema.org sameAs + footer (live site 403)")
        rows += r
        cov.append({"brand": "Manulife", "source": "Official platforms directory", "status": "collected (archive)", "records": len(r),
                    "note": f"manulife.com.hk 403 to bots; read Wayback snapshot {ts} of {MANULIFE_HOME}; no anti-scam page read"})
    except Exception as e:
        cov.append({"brand": "Manulife", "source": "Official platforms directory", "status": "blocked", "records": 0, "note": str(e)[:150]})
    return rows, cov


def _rendered_text(url: str) -> tuple[str, str]:
    """The Emma page is a JavaScript app: render it headless (public page, no login) and keep the rendered HTML as evidence."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page()
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(2000)
        text, html = pg.inner_text("body"), pg.content()
        b.close()
    return clean_text(text), save_snapshot(url, html)


def page_caps(url: str):
    text, ref = _rendered_text(url)
    found = []
    for cap, d in TAXONOMY["digital_capabilities"].items():
        for kw in d["en"] + d["zh"]:
            hit = re.search((r"" + re.escape(kw) + r"") if len(kw) <= 4 else re.escape(kw), text, re.I)
            if hit:
                found.append((cap, snippet(text, hit.group(0)), ref))
                break
    return found


def emma_page():
    out = []
    try:
        caps = page_caps(EMMA)
    except Exception as e:
        log(f"  Emma page: {e}")
        return out, {"brand": "AXA", "source": "Emma by AXA page", "status": "error", "records": 0, "note": str(e)[:150]}
    tax = load_json("taxonomy.json")["digital_capabilities"]
    for cap, snip, ref in caps:
        label = tax[cap]["label"]
        out.append(make_record(
            brand="AXA", record_type="web_feature", modules=["M4"], activity_type="digital_capability",
            title=f"AXA Emma by AXA page: {label}", description=f"page text: {snip}", original_content=EMMA, publication_date=None,
            source_name="Emma by AXA official page", source_category="official", source_url=EMMA, evidence_ref=ref,
            hk_relevance="explicit", hk_relevance_basis="Official AXA Hong Kong app/web-portal page (listed on AXA's official platforms page)",
            platform="website", content_format="web_page",
            extra={"capability": cap, "capability_label": label, "evidence_urls": [EMMA], "method": "Emma page keyword match"}))
    return out, {"brand": "AXA", "source": "Emma by AXA page", "status": "collected", "records": len(out), "note": EMMA}


LANG_SEG = re.compile(r"/(en|en-hk|zh|zh-hk|zh-hant|tc|sc)(?=/)", re.I)


def _key(u):
    u = re.sub(r"^https?://(www\.)?", "", (u or "").split("?")[0].split("#")[0].rstrip("/").lower())
    return LANG_SEG.sub("", u)


def _known_keys():
    keys = set()
    for f in ("newsrooms", "seed_extracts", "excel_imports", "google_news"):
        p = RAW / f"{f}.jsonl"
        if p.exists():
            keys |= {_key(r.get("source_url")) for r in read_jsonl(p)}
    return keys


def prudential_tc(start, end, known):
    base = "https://www.prudential.com.hk"
    html, ref = fetch(base + "/tc/about-us/newsroom/")
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("article.article-card"):
        a = card.find("a", href=True)
        pub = parse_date(card.get("data-date", ""))
        if not a or not pub or not (start <= pub <= end):
            continue
        url = urljoin(base, a["href"])
        if _key(url) in known:
            continue
        t = card.find(["h3", "h2", "h4"]) or card.find("img") or a
        title = t.get("alt") if t.name == "img" else t.get_text(" ")
        try:
            ahtml, aref = fetch(url)
            art = extract_article(ahtml)
        except Exception as e:
            log(f"  PRU tc article failed {url}: {e}")
            art, aref = {}, None
        r = _record("Prudential", title, url, parse_date(art.get("date") or "") or pub, art, ref, aref, "Prudential HK Newsroom (Traditional Chinese)")
        out.append(r)
        known.add(_key(url))
    return out


def axa_zh(start, end, known):
    base = "https://www.axa.com.hk"
    out = []
    for year in sorted({start.year, end.year}):
        html, ref = fetch(f"{base}/zh/news-room/{year}")
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            continue
        nd = json.loads(m.group(1))
        for sl in nd["props"]["pageProps"].get("sliceZone", {}).get("slices", []):
            for it in (sl.get("value") or {}).get("items", []) or []:
                if not (isinstance(it, dict) and it.get("publishDate") and it.get("url")):
                    continue
                pub = parse_date(it["publishDate"])
                url = urljoin(base, it["url"])
                if not pub or not (start <= pub <= end) or _key(url) in known:
                    continue
                try:
                    ahtml, aref = fetch(url)
                    art = extract_article(ahtml)
                except Exception as e:
                    log(f"  AXA zh article failed {url}: {e}")
                    art, aref = {}, None
                out.append(_record("AXA", it["title"], url, pub, art, ref, aref, "AXA HK Newsroom (Chinese)"))
                known.add(_key(url))
    return out


def collect(start, end):
    accounts, cov = official_accounts()
    emma, c = emma_page()
    cov.append(c)
    known = _known_keys()
    news = []
    for brand, fn in (("Prudential", prudential_tc), ("AXA", axa_zh)):
        try:
            r = fn(start, end, known)
            news += r
            cov.append({"brand": brand, "source": "Official newsroom (Chinese edition)", "status": "collected" if r else "none new in window",
                        "records": len(r), "note": "only items not already held in English (language-neutral URL match)"})
            log(f"{brand} Chinese newsroom: {len(r)} new items")
        except Exception as e:
            cov.append({"brand": brand, "source": "Official newsroom (Chinese edition)", "status": "error", "records": 0, "note": str(e)[:150]})
    for c in cov:
        c["checked_at"] = now_utc()
    with (RAW / "official_accounts.jsonl").open("w", encoding="utf-8") as f:
        for r in accounts:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (RAW / "official_pages_coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"official accounts: {len(accounts)} | emma features: {len(emma)} | chinese newsroom items: {len(news)}")
    return emma + news


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    recs = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end))
    write_jsonl("official_pages", recs)
