"""Insurer-level market share from the Insurance Authority's quarterly provisional statistics (long term business).

Input: the IA's own Excel files, downloaded manually from
  https://www.ia.org.hk/en/infocenter/statistics/market_7_2025.html and market_7_2026.html
  into Prudential/IA/ (1q25long.xlsx ... 2q2026.xlsx). Figures are year-to-date (cumulative) in HK$'000.
Table L1 = direct individual long-term NEW business by insurer (participating, other non-linked, linked; single and annualised premiums).

Two measures, both reconciled to IA / press figures (H1 2026: HSBC Life 66.8bn and 25.3bn, The Standard 23 Oct 2026):
  new business premiums (IA "office premiums")  = single + annualised premiums
  annualised new premiums (APE basis)          = annualised premiums + 10% of single premiums
Brands are the sum of their IA-authorized entities (List of Insurers sheet).
Output: Prudential/_report_work/ia_market_share.json
"""
import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
IA = ROOT / "Prudential" / "IA"
OUT = ROOT / "Prudential" / "_report_work" / "ia_market_share.json"
FILES = [("2025-Q1", "Jan–Mar 2025", "1q25long.xlsx"), ("2025-H1", "Jan–Jun 2025", "2q25long.xlsx"), ("2025-9M", "Jan–Sep 2025", "3q25long.xlsx"),
         ("2025-FY", "Jan–Dec 2025", "4q25long.xlsx"), ("2026-Q1", "Jan–Mar 2026", "1q26_long.xlsx"), ("2026-H1", "Jan–Jun 2026", "2q2026.xlsx")]
SRC = {"2025-Q1": "market_7_2025.html", "2025-H1": "market_7_2025.html", "2025-9M": "market_7_2025.html", "2025-FY": "market_7_2025.html",
       "2026-Q1": "market_7_2026.html", "2026-H1": "market_7_2026.html"}
BRAND_RX = {"Prudential": re.compile(r"^Prudential \(HK\)"), "AIA": re.compile(r"^AIA\b"), "Manulife": re.compile(r"^Manulife"),
            "AXA": re.compile(r"^AXA\b")}


def num(v):
    return float(v) if isinstance(v, (int, float)) else 0.0


def read(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = next(s for s in wb.worksheets if s.title.strip() == "Table L1")
    rows = {}
    for r in ws.iter_rows(values_only=True):
        name = str(r[0]).strip() if r[0] else ""
        if not name or name.startswith(("Name of", "香港")) or not any(isinstance(v, (int, float)) for v in r[2:10]):
            continue
        part_s, part_a, oth_s, oth_a, lnk_s, lnk_a, tot_s, tot_a = (num(v) for v in r[2:10])
        rows[name] = {"single": tot_s, "annualised": tot_a, "par_single": part_s, "par_annualised": part_a}
    return rows


def measures(x):
    return {"nbp": (x["single"] + x["annualised"]) / 1e6, "ape": (x["annualised"] + 0.1 * x["single"]) / 1e6,
            "par_share_of_nbp": ((x["par_single"] + x["par_annualised"]) / (x["single"] + x["annualised"])) if (x["single"] + x["annualised"]) else None}


out = {"_definition": __doc__.split("Output:")[0].strip(), "periods": []}
for key, label, fn in FILES:
    rows = read(IA / fn)
    total = next(v for k, v in rows.items() if k.lower().startswith("market total"))
    ins = {k: v for k, v in rows.items() if not k.lower().startswith("market total")}
    # rank every insurer (entity level) and every brand group
    groups = {}
    for name, v in ins.items():
        b = next((b for b, rx in BRAND_RX.items() if rx.search(name)), None)
        g = b or name
        acc = groups.setdefault(g, {"single": 0, "annualised": 0, "par_single": 0, "par_annualised": 0, "entities": []})
        for f in ("single", "annualised", "par_single", "par_annualised"):
            acc[f] += v[f]
        if b:
            acc["entities"].append(name)
    mt = measures(total)
    ranked_nbp = sorted(groups, key=lambda g: -measures(groups[g])["nbp"])
    ranked_ape = sorted(groups, key=lambda g: -measures(groups[g])["ape"])
    per = {"key": key, "label": label, "file": fn, "page": "https://www.ia.org.hk/en/infocenter/statistics/" + SRC[key],
           "file_url": "https://www.ia.org.hk/en/infocenter/statistics/files/" + fn,
           "market": {"nbp_bn": round(mt["nbp"], 1), "ape_bn": round(mt["ape"], 1)}, "brands": {},
           "top5_nbp": [[g, round(measures(groups[g])["nbp"] / mt["nbp"] * 100, 1)] for g in ranked_nbp[:5]]}
    for b in BRAND_RX:
        m = measures(groups[b])
        per["brands"][b] = {"entities": groups[b]["entities"], "nbp_bn": round(m["nbp"], 2), "ape_bn": round(m["ape"], 2),
                            "nbp_share": round(m["nbp"] / mt["nbp"] * 100, 1), "ape_share": round(m["ape"] / mt["ape"] * 100, 1),
                            "nbp_rank": ranked_nbp.index(b) + 1, "ape_rank": ranked_ape.index(b) + 1,
                            "par_pct": round(m["par_share_of_nbp"] * 100) if m["par_share_of_nbp"] is not None else None}
    out["periods"].append(per)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for p in out["periods"]:
    print(p["label"], "| market NBP", p["market"]["nbp_bn"], "bn APE", p["market"]["ape_bn"], "| top5", p["top5_nbp"])
    for b, v in p["brands"].items():
        print(f"   {b:10} NBP {v['nbp_bn']:7.2f}bn {v['nbp_share']:5.1f}% #{v['nbp_rank']:<2} | APE {v['ape_bn']:6.2f}bn {v['ape_share']:5.1f}% #{v['ape_rank']:<2} | par {v['par_pct']}% | {v['entities']}")
