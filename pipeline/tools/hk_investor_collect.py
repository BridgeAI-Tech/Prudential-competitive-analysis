"""Hong Kong investor and regulatory data for the four insurers (window 1 Nov 2025 - 31 Oct 2026).

1. Hong Kong-entity disclosures from the insurers' own Hong Kong websites (RBC public disclosure statements, audited financial statements,
   fact sheets) - only from pages and files that robots.txt allows; manulife.com.hk disallows PDFs and returns 403, so it is skipped.
2. HKEXnews filings for the HK-listed groups (Prudential 2378, AIA 1299, Manulife 945): full list saved; substantive filings downloaded
   (results, reports, business updates, dividends, major announcements); routine returns (buy-back reports, monthly returns) listed only.
3. Daily share prices (close, volume) for the HK lines plus home listings and the Hang Seng Index, for market context.
Outputs: Prudential/hk_investor_data/ (pdfs/<brand>/..., hkex_filings.json, share_prices.json, manifest.json) and an Excel summary.
"""
import json
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Prudential" / "hk_investor_data"
UA = {"User-Agent": "Mozilla/5.0 (research; Prudential HK CI monitor)"}
WIN = ("20251101", "20261031")
_robots = {}


def allowed(url):
    host = re.match(r"https?://[^/]+", url).group(0)
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(host + "/robots.txt", headers=UA, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch("ClaudeBot", url) and _robots[host].can_fetch("*", url)


def get(url, tries=4, **kw):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404):
                return r
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return None


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 1000:
        return "already"
    if not allowed(url):
        return "robots-disallowed"
    r = get(url)
    if r is None or r.status_code != 200 or b"%PDF" not in r.content[:1024]:
        return f"failed ({r.status_code if r is not None else 'no response'})"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    time.sleep(1)
    return "downloaded"


DISCLOSURES = {
    "Prudential": ("https://www.prudential.com.hk/en/claims-and-services/tools/customer-notices/regulatory-information/",
                   r"regulatory-information/(?:PHKL|PGHK)-[^\"']+\.pdf"),
    "AXA": ("https://www.axa.com.hk/en/crihk-hk-disclosure", r"https://hk-axa-web-2024\.cdn\.prismic\.io/[^\"']+\.pdf"),
}
EXTRA = {
    "AIA": ["https://www.aia.com.hk/content/dam/hk-wise/pdf/about-aia/about-us/fact-sheet/aiahk-fact-sheet-en.pdf",
            "https://www.aia.com.hk/content/dam/hk/en/pdf/factsheet/AIAI-Financial-Condition-Report_FY21.pdf"],
}
HKEX = {"Prudential": "02378", "AIA": "01299", "Manulife": "00945"}
KEEP = re.compile(r"result|annual report|interim report|business performance|new business|quarter|dividend|ESG|sustainab|appointment|"
                  r"change of|director|chief executive|acquisition|disposal|connected transaction|inside information|voluntary|"
                  r"investor|presentation|capital|buy-?back programme|update", re.I)
SKIP = re.compile(r"next day disclosure|monthly return|transaction in own shares|form of proxy|notification letter|request form|"
                  r"reply slip|change in issued share|total voting rights|director/pdmr|block listing|forfeit", re.I)
PRICES = {"Prudential (HK 2378)": "2378.HK", "Prudential (London PRU)": "PRU.L", "AIA (HK 1299)": "1299.HK", "Manulife (HK 945)": "0945.HK",
          "Manulife (Toronto MFC)": "MFC.TO", "AXA (Paris CS)": "CS.PA", "Hang Seng Index": "^HSI"}


def disclosures(manifest):
    for brand, (page, pat) in DISCLOSURES.items():
        r = get(page)
        if r is None or r.status_code != 200:
            manifest.append({"brand": brand, "source": page, "status": "page unavailable"})
            continue
        urls = sorted(set(re.findall(pat, r.text)))
        for u in urls:
            u = u if u.startswith("http") else "https://www.prudential.com.hk/content/dam/prudential-phkl/pdf/en/" + u
            name = re.sub(r"^[A-Za-z0-9_-]{16}_", "", u.split("/")[-1])
            st = download(u, OUT / "pdfs" / brand / name)
            manifest.append({"brand": brand, "kind": "HK entity disclosure", "title": name, "url": u, "page": page, "status": st})
    for brand, urls in EXTRA.items():
        for u in urls:
            st = download(u, OUT / "pdfs" / brand / u.split("/")[-1])
            manifest.append({"brand": brand, "kind": "HK entity disclosure", "title": u.split("/")[-1], "url": u, "status": st})
    manifest.append({"brand": "Manulife", "kind": "HK entity disclosure", "title": "Annual disclosures page",
                     "url": "https://www.manulife.com.hk/en/individual/about/annual-disclosures.html",
                     "status": "not collected: site returns 403 and robots.txt disallows PDFs for all bots"})


def hkex(manifest):
    filings = []
    for brand, code in HKEX.items():
        r = get(f"https://www1.hkexnews.hk/search/prefix.do?&callback=callback&lang=EN&type=A&name={code}&market=SEHK")
        sid = None
        if r is not None and r.status_code == 200:
            m = [x for x in json.loads(re.search(r"\((.*)\)", r.text, re.S).group(1))["stockInfo"] if x["code"] == code]
            sid = m[0]["stockId"] if m else None
        if not sid:
            manifest.append({"brand": brand, "kind": "HKEX filings", "status": "stock id lookup failed"})
            continue
        url = ("https://www1.hkexnews.hk/search/titleSearchServlet.do?sortDir=0&sortByOptions=DateTime&category=0&market=SEHK"
               f"&stockId={sid}&documentType=-1&fromDate={WIN[0]}&toDate={WIN[1]}&title=&searchType=0&t1code=-2&t2Gcode=-2&t2code=-2"
               "&rowRange=3000&lang=E")
        r = get(url)
        rows = json.loads(json.loads(r.text)["result"]) if r is not None and r.status_code == 200 else []
        for x in rows:
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x.get("TITLE", ""))).strip()
            cat = re.sub(r"<[^>]+>", " ", x.get("LONG_TEXT", "")).strip()
            link = "https://www1.hkexnews.hk" + x.get("FILE_LINK", "")
            date = x.get("DATE_TIME", "")
            keep = bool(KEEP.search(title + " " + cat)) and not SKIP.search(title + " " + cat) and link.lower().endswith(".pdf")
            f = {"brand": brand, "stock_code": code, "date": date, "title": title, "category": cat, "url": link,
                 "size": x.get("FILE_INFO"), "downloaded": False}
            if keep:
                d = re.sub(r"(\d\d)/(\d\d)/(\d{4}).*", r"\3\2\1", date)
                st = download(link, OUT / "pdfs" / brand / "hkex" / f"{d}_{link.split('/')[-1]}")
                f["downloaded"] = st in ("downloaded", "already")
                f["status"] = st
            filings.append(f)
        manifest.append({"brand": brand, "kind": "HKEX filings", "status": f"{len(rows)} filings listed, {sum(f['downloaded'] for f in filings if f['brand'] == brand)} downloaded"})
    (OUT / "hkex_filings.json").write_text(json.dumps(filings, ensure_ascii=False, indent=1), encoding="utf-8")
    return filings


def prices(manifest):
    out = {}
    p1 = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(2026, 11, 11, tzinfo=timezone.utc).timestamp())
    for label, sym in PRICES.items():
        r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d")
        try:
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), c, v] for t, c, v in zip(res["timestamp"], q["close"], q["volume"]) if c]
            out[label] = {"symbol": sym, "currency": res["meta"].get("currency"), "rows": rows}
            manifest.append({"brand": label, "kind": "share prices", "status": f"{len(rows)} trading days"})
        except Exception:
            manifest.append({"brand": label, "kind": "share prices", "status": "failed"})
    (OUT / "share_prices.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    disclosures(manifest)
    filings = hkex(manifest)
    px = prices(manifest)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Downloads"
    ws.append(["Brand", "Kind", "Title", "URL", "Status"])
    for m in manifest:
        ws.append([m.get("brand"), m.get("kind"), m.get("title"), m.get("url"), m.get("status")])
    ws2 = wb.create_sheet("HKEX filings")
    ws2.append(["Brand", "Stock code", "Date", "Title", "Category", "URL", "Downloaded"])
    for f in filings:
        ws2.append([f["brand"], f["stock_code"], f["date"], f["title"], f["category"], f["url"], f["downloaded"]])
    ws3 = wb.create_sheet("Share prices")
    labels = list(px)
    ws3.append(["Date"] + [f"{l} ({px[l]['currency']})" for l in labels])
    dates = sorted({r[0] for l in labels for r in px[l]["rows"]})
    look = {l: {r[0]: r[1] for r in px[l]["rows"]} for l in labels}
    for d in dates:
        ws3.append([d] + [look[l].get(d) for l in labels])
    wb.save(OUT / "HK_investor_data_summary.xlsx")
    for m in manifest:
        print(f"{m.get('brand'):24} {m.get('kind', ''):22} {str(m.get('title') or '')[:55]:55} {m.get('status')}")


if __name__ == "__main__":
    main()
