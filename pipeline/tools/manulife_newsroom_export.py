"""Manulife Hong Kong newsroom (EN + Traditional Chinese) -> Prudential/manulife_newsroom/.

manulife.com.hk returns HTTP 403 to automated requests, so this is NOT read live and the block is not bypassed. Content comes
from Internet Archive copies: every archived copy of the newsroom index (date, title, lead, link per release) plus every archived
release page under /newsroom/. Releases published after the latest archived index copy cannot be seen this way and are listed
as a known gap. Output: manulife_newsroom.json, Manulife_HK_newsroom.xlsx, raw/ (archived HTML), coverage.json.
"""
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Prudential" / "ci-monitor" / "pipeline" / "collectors"))
sys.path.insert(0, str(ROOT / "Prudential" / "ci-monitor" / "pipeline"))
from manulife_archive import parse_index  # noqa: E402

OUT = ROOT / "Prudential" / "manulife_newsroom"
UA = {"User-Agent": "Mozilla/5.0 (research; Prudential HK CI monitor)"}
CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web/{ts}id_/{url}"
INDEX = {"en": "https://www.manulife.com.hk/en/individual/about/newsroom.html",
         "zh": "https://www.manulife.com.hk/zh-hk/individual/about/newsroom.html"}
START = dt.date(2025, 11, 1)
TR = ROOT / "Prudential" / "_report_work" / "translations.json"


def get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=90)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        time.sleep(4 * (i + 1))
    return None


def snaps(url, since="2025", prefix=False):
    r = get(CDX, {"url": url + ("*" if prefix else ""), "from": since, "output": "json", "filter": "statuscode:200",
                  "fl": "timestamp,original", "collapse": "digest"})
    return (r.json()[1:] if r is not None and r.text.strip() else [])


def page_text(html):
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "nav", "header", "footer", "noscript"]):
        t.decompose()
    title = (s.find("h1") or s.find("title"))
    main = s.find("main") or s.find("div", class_=re.compile("root|container")) or s.body
    txt = re.sub(r"\s+", " ", main.get_text(" ") if main else "").strip()
    for mark in ("Hong Kong (", "香港（", "（香港", "Hong Kong, "):
        i = txt.find(mark)
        if 0 <= i < 3000:
            txt = txt[i:]
            break
    return (re.sub(r"\s+", " ", title.get_text(" ")).strip() if title else ""), txt[:12000]


def date_from(text, url):
    m = re.search(r"(20\d\d)[-/年](\d{1,2})[-/月](\d{1,2})", text[:400]) or re.search(r"(20\d\d)(\d\d)(\d\d)", url)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.search(r"\((\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (20\d\d)\)", text[:300])
    if m:
        return dt.datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%d %B %Y").date()
    return None


def main():
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    items, latest_index = {}, {}
    for lang, idx in INDEX.items():
        ss = snaps(idx, "20250901")
        latest_index[lang] = max((s[0] for s in ss), default=None)
        for ts, _ in ss:
            r = get(WB.format(ts=ts, url=idx))
            if r is None:
                continue
            r.encoding = "utf-8"
            for it in parse_index(r.text):
                url = urljoin(idx, it["url"]) if it["url"] else None
                key = url or f"{lang}:{it['title']}"
                if key not in items:
                    items[key] = {"language": lang, "date": it["date"], "title": it["title"], "lead": it["lead"], "url": url,
                                  "index_copy": WB.format(ts=ts, url=idx).replace("id_/", "/")}
            time.sleep(1)
    # archived release pages not on any index copy
    for lang, idx in INDEX.items():
        base = idx.replace(".html", "/")
        for ts, orig in snaps(base, "2025", prefix=True):
            orig = orig.replace("http://", "https://").split("?")[0]
            if orig.endswith(".html") and orig not in items:
                items[orig] = {"language": lang, "date": None, "title": None, "lead": "", "url": orig, "index_copy": None, "_ts": ts}
    out = []
    for key, it in items.items():
        if it["date"] and it["date"] < START:
            continue
        body, arch = "", None
        if it["url"] and not it["url"].lower().endswith(".pdf"):
            ss = [s for s in snaps(it["url"], "2025")]
            if ss:
                ts = ss[-1][0]
                r = get(WB.format(ts=ts, url=it["url"]))
                if r is not None:
                    r.encoding = "utf-8"
                    t, body = page_text(r.text)
                    it["title"] = it["title"] or t
                    arch = WB.format(ts=ts, url=it["url"]).replace("id_/", "/")
                    (OUT / "raw" / (re.sub(r"[^\w-]", "_", it["url"].split("/")[-1])[:120] + f"_{it['language']}.html")).write_text(r.text, encoding="utf-8")
                time.sleep(1)
        d = it["date"] or date_from(body, it["url"] or "")
        if not d or d < START:
            continue
        out.append({"date": d.isoformat(), "language": it["language"], "title": it["title"], "lead": it["lead"], "full_text": body,
                    "text_source": "archived release page" if body else "newsroom index lead", "url": it["url"],
                    "archive_copy": arch or it["index_copy"], "hk_mention": bool(re.search(r"hong kong|macau|香港|澳門|大灣區|greater bay", (it["title"] or "") + body + it["lead"], re.I))})
    out.sort(key=lambda x: (x["date"], x["language"]), reverse=True)
    tr = json.loads(TR.read_text(encoding="utf-8")) if TR.exists() else {}
    for x in out:
        x["english_summary"] = (tr.get(x["url"] or "") or {}).get("en") if x["language"] == "zh" else None
    (OUT / "manulife_newsroom.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    cov = {"source": "https://www.manulife.com.hk/en/individual/about/newsroom.html",
           "access": "manulife.com.hk returns HTTP 403 to automated requests; content read from Internet Archive copies (block not bypassed)",
           "latest_archived_index_copy": latest_index, "releases": len(out),
           "with_full_text": sum(1 for x in out if x["text_source"] == "archived release page"),
           "gap": "Releases published after the latest archived index copy are not visible here; check the live page in a browser."}
    (OUT / "coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1), encoding="utf-8")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Releases"
    ws.append(["Date", "Language", "Title", "Lead", "English summary (Chinese items)", "Hong Kong mentioned", "Text source", "Original URL", "Archive copy", "Full text"])
    for x in out:
        ws.append([x["date"], x["language"], x["title"], x["lead"], x["english_summary"], x["hk_mention"], x["text_source"], x["url"], x["archive_copy"], x["full_text"][:32000]])
    ws2 = wb.create_sheet("Coverage")
    for k, v in cov.items():
        ws2.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v])
    wb.save(OUT / "Manulife_HK_newsroom.xlsx")
    print(json.dumps(cov, ensure_ascii=False, indent=1))
    for x in out[:80]:
        print(x["date"], x["language"], x["text_source"][:8], "|", (x["title"] or "")[:90])


if __name__ == "__main__":
    main()
