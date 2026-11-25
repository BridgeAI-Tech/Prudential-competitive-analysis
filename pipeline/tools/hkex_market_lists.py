"""HKEX market-wide lists (with Internet Archive copies across 1 Nov 2025 - 10 Nov 2026 for history) (board meetings, dividends & entitlements, trading arrangements; Main Board + GEM).

Each page is a current snapshot (HKEX shows upcoming / recent items only), so the script keeps every run as a dated copy
and a cumulative history. Rows for Prudential (2378), AIA (1299) and Manulife (945) are flagged. AXA is not listed in Hong Kong.
Output: Prudential/hk_investor_data/hkex_market_lists/ (raw html per run, <list>.json history, HKEX_market_lists.xlsx)
"""
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Prudential" / "hk_investor_data" / "hkex_market_lists"
UA = {"User-Agent": "Mozilla/5.0 (research; Prudential HK CI monitor)"}
PAGES = {
    "board_meetings_main": "https://www3.hkexnews.hk/reports/bmn/ebmn.htm",
    "board_meetings_gem": "https://www3.hkexnews.hk/reports/bmn/ebmngem.htm",
    "dividends_entitlements_main": "https://www3.hkexnews.hk/reports/doe/eent.htm",
    "dividends_entitlements_gem": "https://www3.hkexnews.hk/reports/doe/eentgem.htm",
    "trading_arrangements_main": "https://www.hkex.com.hk/eng/market/sec_tradinfo/tradarng/etat.htm",
    "trading_arrangements_gem": "https://www.hkex.com.hk/eng/market/sec_tradinfo/tradarng/etatgem.htm",
}
OURS = {"2378": "Prudential", "1299": "AIA", "945": "Manulife"}


def parse(text):
    tables = pd.read_html(io.StringIO(text))
    df = max(tables, key=len)                         # the data table (the other is the page header)
    if all(isinstance(c, int) for c in df.columns):  # header row inside the table
        df.columns = [str(x).strip() for x in df.iloc[0]]
        df = df.iloc[1:]
    df = df.dropna(how="all").astype(str).map(lambda v: re.sub(r"\s+", " ", v).strip() if v != "nan" else "")
    cols, seen_c = [], {}
    for c in df.columns:                              # unique, readable column names
        c = str(c).strip() or "col"
        seen_c[c] = seen_c.get(c, 0) + 1
        cols.append(c if seen_c[c] == 1 else f"{c}_{seen_c[c]}")
    df.columns = cols

    def insurer(row):
        codes = set()
        for v in row:
            codes |= {m.lstrip("0") for m in re.findall(r"\((\d{1,5})\)", v)}
            if re.fullmatch(r"\d{1,5}", v):
                codes.add(v.lstrip("0"))
        return ", ".join(sorted({OURS[c] for c in codes if c in OURS}))
    df.insert(0, "insurer_in_scope", df.apply(lambda r: insurer(list(r.values)), axis=1))
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cap = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sheets, summary = {}, []
    meta = ("insurer_in_scope", "page_date", "source_url", "via", "captured_utc")
    for name, url in PAGES.items():
        # archived copies across the window first (oldest to newest), then today's live page
        cdx = requests.get("http://web.archive.org/cdx/search/cdx", params={"url": url.split("//")[1], "output": "json", "filter": "statuscode:200",
                           "from": "20251101", "to": "20261110", "fl": "timestamp", "collapse": "timestamp:8"}, headers=UA, timeout=90)
        snaps = [x[0] for x in (cdx.json()[1:] if cdx.text.strip() else [])]
        sources = [(f"https://web.archive.org/web/{ts}id_/{url}", f"Internet Archive copy {ts[:8]}", ts) for ts in snaps] + [(url, "HKEX live page", None)]
        rows_all, n_pages = [], 0
        for src, via, ts in sources:
            df, err = None, ""
            for attempt in range(4):
                try:
                    r = requests.get(src, headers=UA, timeout=90)
                    if r.status_code == 200:
                        r.encoding = r.apparent_encoding or "utf-8"
                        df = parse(r.text)
                        break
                    err = f"HTTP {r.status_code}"
                except Exception as e:
                    err = type(e).__name__
                time.sleep(4 * (attempt + 1))
            if df is None:
                print(f"  skipped {via} for {name}: {err}")
                continue
            time.sleep(2)
            page_date = (re.search(r"Date\s*:\s*(\d{2}/\d{2}/\d{4})", re.sub(r"<[^>]+>", " ", r.text)) or [None, None])[1]
            (OUT / "raw").mkdir(exist_ok=True)
            (OUT / "raw" / f"{name}_{(page_date or (ts or cap)[:10]).replace('/', '-')}.html").write_text(r.text, encoding="utf-8")
            df.insert(1, "page_date", page_date)
            df.insert(2, "source_url", url)
            df.insert(3, "via", via)
            df.insert(4, "captured_utc", cap if ts is None else f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z")
            rows_all += df.to_dict("records")
            n_pages += 1
        keyf = lambda x: json.dumps({k: v for k, v in x.items() if k not in meta}, sort_keys=True, ensure_ascii=False)
        hist = OUT / f"{name}.json"
        uniq = {}
        for x in (json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else []) + rows_all:   # cumulative across runs                     # one row per distinct entry; keep the earliest page that showed it
            uniq.setdefault(keyf(x), x)
        rows = list(uniq.values())
        (OUT / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        d = pd.DataFrame(rows)
        sheets[name] = d
        ours = d[d.insurer_in_scope != ""]
        summary.append({"list": name, "pages_read": n_pages, "archived_copies": len(snaps), "distinct_rows": len(d), "insurer_rows": len(ours), "url": url})
        for _, x in ours.iterrows():
            print(f"  {name}: {x['insurer_in_scope']} | {x['page_date']} | " + " | ".join(str(v) for k, v in x.items() if k not in meta)[:230])
    with pd.ExcelWriter(OUT / "HKEX_market_lists.xlsx") as xw:
        pd.DataFrame(summary).to_excel(xw, sheet_name="Summary", index=False)
        ins = pd.concat([d[d.insurer_in_scope != ""].assign(list=n) for n, d in sheets.items()], ignore_index=True)
        ins.to_excel(xw, sheet_name="Our insurers", index=False)
        for n, d in sheets.items():
            d.to_excel(xw, sheet_name=n[:31], index=False)
    for x in summary:
        print(f"{x['list']:30} pages {x['pages_read']:3} (archived {x['archived_copies']})  distinct rows {x['distinct_rows']:5}  insurer rows {x['insurer_rows']}")


if __name__ == "__main__":
    main()
