"""Mainland social conversation (Xiaohongshu and WeChat), 20 Nov 2026.

Source: Apify search pilot (Prudential/apify_raw/cn_social_hk_sample.json, 1,299 posts found by searching each insurer's
name). Kept: posts dated 1 Nov 2025 - 31 Oct 2026, about Hong Kong, naming their insurer (456), then classified post by
post (apify_raw/cn_class_a.json + cn_class_b.json) - only posts substantially ABOUT the insurer are used (412).
Search-based: this measures what others say about each insurer, not the insurer's own activity, so it is shown in its
own section and is not added to the activity counts.
build() -> (rows, stats, insight_html, kb_text)
"""
import collections
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "Prudential" / "apify_raw"
BRANDS = ["Prudential", "AIA", "Manulife", "AXA"]
TOPIC = {"company_news": "Company news", "products": "Products and plans", "events_brand": "Events and brand", "claims_service": "Claims and service",
         "dividends_returns": "Dividends and returns", "comparison": "Comparisons between insurers", "recruitment_agents": "Agent recruitment", "other": "Other"}
SPEAK = {"agent_or_broker": "Agents and brokers", "media_or_kol": "Media and finance bloggers", "insurer_official": "The insurer itself", "customer": "Customers", "unknown": "Unclear"}


def rid_of(x):
    return ("XHS-" if x["platform"] == "Xiaohongshu" else "WCH-") + hashlib.sha1(x["url"].encode()).hexdigest()[:12]


def build():
    raw = {rid_of(x): x for x in json.loads((RAW / "cn_social_hk_sample.json").read_text(encoding="utf-8"))}
    cls = json.loads((RAW / "cn_class_a.json").read_text(encoding="utf-8")) + json.loads((RAW / "cn_class_b.json").read_text(encoding="utf-8"))
    imgs = json.loads((HERE / "media" / "cnsoc.json").read_text(encoding="utf-8")) if (HERE / "media" / "cnsoc.json").exists() else {}
    rows = []
    for c in cls:
        if not c.get("relevant") or c["id"] not in raw:
            continue
        x = raw[c["id"]]
        f = imgs.get(c["id"])
        tidy = lambda t: re.sub(r"\bguarantee(d|s)?\b", "fixed", str(t).replace("—", "-"), flags=re.I)   # house style: no em dash, no "guarantee" wording
        rows.append([c["id"], x["platform"], x["brand"], int(x["date"].replace("-", "")), x.get("likes") or 0, tidy(x["title"][:160]),
                     tidy(c["summary_en"]), c["topic"], c["speaker"], c["tone"], tidy(c.get("plan", "")), re.sub(r"^http://", "https://", x["url"]), f if f and (HERE / "media" / "cnsoc" / f).exists() else ""])
    rows.sort(key=lambda r: (-r[3], -r[4]))
    n = len(rows)
    by = {b: [r for r in rows if r[2] == b] for b in BRANDS}
    st = {"n": n, "fetched": 1299, "window_hk": 582, "named": 456,
          "brand": {b: len(by[b]) for b in BRANDS},
          "platform": {p: {b: sum(r[1] == p for r in by[b]) for b in BRANDS} for p in ("Xiaohongshu", "WeChat")},
          "topic": {t: {b: sum(r[7] == t for r in by[b]) for b in BRANDS} for t in TOPIC if any(r[7] == t for r in rows)},
          "speaker": {s: {b: sum(r[8] == s for r in by[b]) for b in BRANDS} for s in SPEAK if any(r[8] == s for r in rows)},
          "tone": {t: {b: sum(r[9] == t for r in by[b]) for b in BRANDS} for t in ("positive", "neutral", "negative")}}
    pct = lambda a, b: round(100 * a / b) if b else 0
    third = {b: sum(r[8] in ("agent_or_broker", "media_or_kol") for r in by[b]) for b in BRANDS}
    own_all = sum(r[8] == "insurer_official" for r in rows)
    pru_own = sum(r[8] == "insurer_official" for r in by["Prudential"])
    comp = st["topic"].get("comparison", {})
    axa_sl = sum(("盛利" in r[5] + r[10]) or "sing lei" in r[10].lower() or "sheng li" in r[10].lower() for r in by["AXA"])
    pru_claims = st["topic"].get("claims_service", {}).get("Prudential", 0)
    pru_neg = [r for r in by["Prudential"] if r[9] == "negative"]
    pru_neg_claims = sum(r[7] == "claims_service" for r in pru_neg)
    lead = max(BRANDS, key=lambda b: st["brand"][b])
    insight = (f"<b>{lead} leads the mainland conversation</b>: {st['brand'][lead]} of the {n} posts about the four insurers "
               f"({pct(st['brand'][lead], n)}%), {pct(third[lead], st['brand'][lead])}% of them from agents, brokers and finance bloggers, "
               f"and it is the insurer others are measured against ({comp.get(lead, 0)} comparison posts, against {comp.get('Prudential', 0)} for Prudential). "
               f"Prudential is second ({st['brand']['Prudential']} posts, {pct(st['brand']['Prudential'], n)}%) and the most active in its own voice "
               f"({pru_own} of the {own_all} posts by the insurers themselves), with the most Xiaohongshu posts ({st['platform']['Xiaohongshu']['Prudential']}). "
               f"<b>Prudential's conversation leans on claims and service</b> ({pru_claims} posts, the most of the four), and {pru_neg_claims} of its "
               f"{len(pru_neg)} negative posts are claim disputes. AXA's talk centres on one savings plan, 盛利 II ({axa_sl} of its {st['brand']['AXA']} posts).")
    kb = [f"Source: Xiaohongshu and WeChat posts found by searching each insurer's name (collected 19 Nov 2026). Fetched {st['fetched']}; "
          f"{st['window_hk']} in the period and about Hong Kong; {st['named']} name their insurer; {n} are substantially about the insurer (classified post by post). "
          "SEARCH-BASED: what agents, brokers, media, bloggers, customers and the insurers say about each insurer - not the insurers' own activity; "
          "not part of the activity counts. Personal names are not stored.",
          "KEY INSIGHT: " + insight.replace("<b>", "").replace("</b>", ""),
          "Posts per insurer: " + ", ".join(f"{b} {st['brand'][b]} ({pct(st['brand'][b], n)}%)" for b in BRANDS),
          "By platform: " + "; ".join(f"{p}: " + ", ".join(f"{b} {v}" for b, v in d.items()) for p, d in st["platform"].items()),
          "By topic: " + "; ".join(f"{TOPIC[t]}: " + ", ".join(f"{b} {v}" for b, v in d.items()) for t, d in st["topic"].items()),
          "Who is talking: " + "; ".join(f"{SPEAK[s]}: " + ", ".join(f"{b} {v}" for b, v in d.items()) for s, d in st["speaker"].items()),
          "Tone: " + "; ".join(f"{t}: " + ", ".join(f"{b} {v}" for b, v in d.items()) for t, d in st["tone"].items()),
          "", "Posts (date | insurer | platform | topic | who | tone | likes | English summary | plan | URL):"]
    for r in rows:
        kb.append(f"{r[3]} | {r[2]} | {r[1]} | {TOPIC[r[7]]} | {SPEAK[r[8]]} | {r[9]} | {r[4]} likes | {r[6]}{(' | plan: ' + r[10]) if r[10] else ''} | {r[11]}")
    return rows, st, insight, "\n".join(kb)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rows, st, ins, kb = build()
    print(len(rows), st["brand"]); print(ins); print(len(kb), "chars of KB text")
