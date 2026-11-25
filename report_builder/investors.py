"""Investor and Hong Kong capital data for the report (all values computed from downloaded files; sources linked).

share prices  : Prudential/hk_investor_data/share_prices.json (daily closes; group-level, not Hong Kong-only)
HK capital    : figures read from the Hong Kong companies' 2025 public disclosure statements (pages cited)
investor moves: HKEX filings (Prudential/hk_investor_data/hkex_filings*.json)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "Prudential" / "hk_investor_data"
WIN = ("2025-11-03", "2026-10-30")          # first and last trading days in the window
LINES = {"Prudential": "Prudential (HK 2378)", "AIA": "AIA (HK 1299)", "Manulife": "Manulife (HK 945)", "AXA": "AXA (Paris CS)", "Hang Seng Index": "Hang Seng Index"}
QUOTE = {"Prudential": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=2378&sc_lang=en",
         "AIA": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=1299&sc_lang=en",
         "Manulife": "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym=945&sc_lang=en",
         "AXA": "https://live.euronext.com/en/product/equities/FR0000120628-XPAR",
         "Hang Seng Index": "https://www.hsi.com.hk/eng/indexes/all-indexes/hsi"}
HX = "https://www1.hkexnews.hk/listedco/listconews/sehk/"
EVENTS = [  # brand, date, label, HKEX filing
    ("Manulife", "2025-11-13", "Q3 2025 results and refreshed strategy", HX + "2025/1113/2025111300053.pdf"),
    ("Prudential", "2026-01-06", "Launches a US$1.2bn share buyback", HX + "2026/0106/2026010600407.pdf"),
    ("Prudential", "2026-01-14", "Names Sir Douglas Flint as next Chair", HX + "2026/0114/2026011400165.pdf"),
    ("Prudential", "2026-01-22", "Agrees to raise its stake in Prudential Assurance Malaysia to 70%", HX + "2026/0122/2026012200329.pdf"),
    ("Manulife", "2026-02-12", "Full-year 2025 results; dividend raised 10.2%", HX + "2026/0212/2026021200110.pdf"),
    ("Prudential", "2026-03-18", "Full-year 2025 results", HX + "2026/0318/2026031800001.pdf"),
    ("AIA", "2026-03-19", "Full-year 2025 results", HX + "2026/0319/2026031900001.pdf"),
    ("AIA", "2026-03-27", "Launches a US$1.743bn share buyback", HX + "2026/0327/2026032701974.pdf"),
    ("Prudential", "2026-04-29", "Q1 2026 business update", HX + "2026/0429/2026042900005.pdf"),
    ("AIA", "2026-04-30", "Q1 2026 new business highlights", HX + "2026/0430/2026043000001.pdf"),
    ("Manulife", "2026-05-14", "Q1 2026 results", HX + "2026/0514/2026051400007.pdf"),
    ("Manulife", "2026-08-06", "Q2 2026 results (same day as the mainland tax reports)", HX + "2026/0806/2026080600019.pdf"),
    ("AIA", "2026-08-20", "Half-year 2026 results", HX + "2026/0820/2026082000001.pdf"),
    ("Prudential", "2026-08-27", "Half-year 2026 results; sells a further 2% of ICICI Prudential Asset Management", HX + "2026/0827/2026082700001.pdf"),
    ("Prudential", "2026-09-02", "Raises its 2026 buyback from US$1.2bn to US$1.472bn (about 4% of its shares)", HX + "2026/0902/2026090201563.pdf"),
    ("AIA", "2026-10-30", "Q3 2026 new business highlights", HX + "2026/1030/2026103000001.pdf"),
    ("Prudential", "2026-11-05", "Q3 2026 business update (after the window)", HX + "2026/1105/2026110500001.pdf"),
    ("Manulife", "2026-11-05", "Q3 2026 results (after the window)", HX + "2026/1105/2026110500097.pdf"),
]
PRU_PDF = "https://www.prudential.com.hk/content/dam/prudential-phkl/pdf/en/regulatory-information/"
AXA_DS = "https://hk-axa-web-2024.cdn.prismic.io/hk-axa-web-2024/aa-Au_YbudlmRCdn_ACRIHKDisclosure_Statement_Template_for_Public_Disclosure_Eng_Jul2026_forsubmission_v8_clean.pdf"
CAPITAL = [  # Hong Kong companies' 2025 public disclosure statements (HKD); ratio = capital base / prescribed capital amount
    {"brand": "Prudential", "entity": "Prudential Hong Kong Limited (life insurance)", "ratio": 223, "ratio_prev": 239,
     "capital_base_bn": 130.3, "required_bn": 58.4, "assets_bn": 719.5, "assets_prev_bn": 617.2,
     "src": PRU_PDF + "PHKL-RBC-public-disclosure-statement-2025.pdf", "pages": "p.3 (assets), p.13 (capital)"},
    {"brand": "Prudential", "entity": "Prudential General Insurance Hong Kong Limited", "ratio": 310, "ratio_prev": 290,
     "capital_base_bn": 0.611, "required_bn": 0.197, "assets_bn": 1.78, "assets_prev_bn": 1.55,
     "src": PRU_PDF + "PGHK-RBC-public-disclosure-statement-2025.pdf", "pages": "p.3 (assets), p.11-12 (capital); 2024 ratio derived from p.11"},
    {"brand": "AXA", "entity": "AXA China Region Insurance Company (Hong Kong) Limited", "ratio": 235, "ratio_prev": 238,
     "capital_base_bn": 42.6, "required_bn": 18.1, "assets_bn": 290.1, "assets_prev_bn": 250.7,
     "src": AXA_DS, "pages": "p.4 (assets), p.13-14 (capital)"},
    {"brand": "AIA", "entity": "AIA International Limited (Hong Kong branch)", "ratio": None, "note": "Not included in this edition"},
    {"brand": "Manulife", "entity": "Manulife (International) Limited", "ratio": None, "note": "Not included in this edition"},
]


def build():
    p = json.loads((D / "share_prices.json").read_text(encoding="utf-8"))
    out = {"series": {}, "change": {}, "peak": {}, "events": [], "capital": CAPITAL, "quote": QUOTE, "currency": {}}
    for b, lab in LINES.items():
        rows = [r for r in p[lab]["rows"] if WIN[0] <= r[0] <= "2026-11-10"]
        base = rows[0][1]
        inwin = [r for r in rows if r[0] <= WIN[1]]
        weekly, wk = [], None
        for d, c, _ in inwin:                    # last close of each week, indexed to 100 on 3 Nov 2025; ends on the same day as the table
            w = d[:4] + str(__import__("datetime").date.fromisoformat(d).isocalendar()[1]).zfill(2)
            if w != wk:
                weekly.append([d, round(c / base * 100, 1)])
                wk = w
            else:
                weekly[-1] = [d, round(c / base * 100, 1)]
        out["series"][b] = weekly
        out["change"][b] = round((inwin[-1][1] / base - 1) * 100, 1)
        pk = max(inwin, key=lambda r: r[1])
        out["peak"][b] = [pk[0], round(pk[1], 2), round((inwin[-1][1] / pk[1] - 1) * 100, 1)]
        out["currency"][b] = p[lab]["currency"]
    for b, d, lab, url in EVENTS:
        rows = p[LINES[b]]["rows"]
        before = [r for r in rows if r[0] < d]
        after = [r for r in rows if r[0] >= d]
        mv = round((after[0][1] / before[-1][1] - 1) * 100, 1) if before and after else None
        out["events"].append({"brand": b, "date": d, "label": lab, "url": url, "move": mv})
    hs = p["Hang Seng Index"]["rows"]
    tax = [r for r in hs if r[0] in ("2026-08-05", "2026-08-06")]
    out["tax_day"] = {b: round((([r for r in p[LINES[b]]["rows"] if r[0] == "2026-08-06"] or [[0, None]])[0][1] or 0) /
                                (([r for r in p[LINES[b]]["rows"] if r[0] == "2026-08-05"] or [[0, 1]])[0][1]) * 100 - 100, 1) for b in ("Prudential", "AIA", "Manulife")}
    out["tax_date"] = "2026-08-06"
    out["tax_day"]["Hang Seng Index"] = round((tax[1][1] / tax[0][1] - 1) * 100, 1) if len(tax) == 2 else None
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    o = build()
    print(o["change"], o["peak"], o["tax_day"])
    for e in o["events"]:
        print(e["date"], e["brand"], e["move"], e["label"])
