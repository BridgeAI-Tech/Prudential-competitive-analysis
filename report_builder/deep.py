"""Deeper, computed findings from the social, ad, video and search data (all numbers derived here, none typed by hand).

Output DEEP = {
  social:  {platform: {brand: {posts, per_month, er, celeb:[n, er], offer:[n, er], wellness:[n, er], formats:{fmt:[n, er]}, top:[{date, er, text, url}]}}},
  li_fmt:  {brand: {fmt: [er, n]}},
  meta_ads:{brand: {active, recent, recent_from, topics:[[topic, n]], months:[[yyyy-mm, n]]}},
  youtube: {brand: {videos, views, top3_share, under1k, median, top:[{title, views}]}},
  gads:    {brand: {total, video, image, text}},
  trends:  {"en"|"zh": {"terms": {brand: term}, "series": {brand: [[yyyy-mm, value]]}, "avg": {brand: value}, "url": str}},
}
"""
import json
import re
import sqlite3
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import linkedin as _li
import social_meta as _sm

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "Prudential" / "ci-monitor" / "data" / "ci.db"
BRANDS = ("Prudential", "AIA", "Manulife", "AXA")
CID = {"PRU_HK": "Prudential", "AIA_HK": "AIA", "MFC_HK": "Manulife", "AXA_HK": "AXA"}
TOPIC = {"Savings and wealth": r"儲蓄|財富|savings|wealth|傳承|legacy|增值",
         "Medical and VHIS": r"醫療|自願醫保|vhis|medical|住院|hospital",
         "Critical illness and cancer": r"危疾|癌|critical illness|cancer",
         "Retirement and annuity": r"退休|年金|retire|annuit",
         "Travel": r"旅遊|travel|旅行",
         "Health and wellness": r"健康|wellness|運動|mental|身心|wellbeing",
         "Offers and prizes": r"優惠|折扣|回贈|禮品|獎賞|抽獎|lucky draw|discount|offer|rebate|送",
         "Children and family": r"子女|兒童|家庭|親子|baby|children|family|parent",
         "Newcomers to Hong Kong": r"新來港|來港|newcomer|人才|talent"}
CELEB = r"陳奕迅|eason|鄭秀文|sammi|劉德華|andy lau|張學友|孫燕姿|stefanie|張敬軒|hins|古天樂|louis koo"
tags = lambda t: [k for k, p in TOPIC.items() if re.search(p, (t or "").lower())]
med = lambda a: round(st.median(a), 3) if a else None


def _social():
    posts, _ = _sm.load()
    out = defaultdict(dict)
    for plat in ("Facebook", "Instagram"):
        for b in BRANDS:
            mine = [p for p in posts if p["platform"] == plat and p["brand"] == b]
            if not mine:
                continue
            rated = [p for p in mine if p["er"] is not None]
            grp = lambda f: (lambda v: [len(v), med([p["er"] for p in v])])([p for p in rated if f(p)])
            fm = {f: grp(lambda p, f=f: p["format"] == f) for f in sorted({p["format"] for p in rated})}
            top = sorted(rated, key=lambda p: -p["er"])[:3]
            out[plat][b] = {"posts": len(mine), "per_month": round(len(mine) / 12, 1), "er": med([p["er"] for p in rated]),
                            "celeb": grp(lambda p: re.search(CELEB, p["text"].lower())),
                            "offer": grp(lambda p: "Offers and prizes" in tags(p["text"])),
                            "wellness": grp(lambda p: "Health and wellness" in tags(p["text"])),
                            "savings": grp(lambda p: "Savings and wealth" in tags(p["text"])),
                            "formats": {k: v for k, v in fm.items() if v[0] >= 5},
                            "top": [{"date": p["date"], "er": p["er"], "text": p["text"][:140], "url": p["url"]} for p in top]}
    return out


def _crisis():
    """Posts about the Tai Po Wang Fuk Court fire (26 Nov 2025): first post, money pledged, engagement against each brand's usual post."""
    posts, _ = _sm.load()
    base = {(pl, b): med([p["er"] for p in posts if p["platform"] == pl and p["brand"] == b and p["er"] is not None]) for pl in ("Facebook", "Instagram") for b in BRANDS}
    out = []
    for p in posts:
        if re.search(r"大埔|宏福", p["text"]) and p["er"] is not None:
            out.append({"brand": p["brand"], "platform": p["platform"], "date": p["date"], "er": p["er"], "url": p["url"],
                        "times": round(p["er"] / base[(p["platform"], p["brand"])], 1) if base[(p["platform"], p["brand"])] else None})
    return sorted(out, key=lambda x: (x["date"], x["brand"]))


def _meta_ads():
    raw = _sm.RAW / "fb_ads.json"
    if not raw.exists():
        return {}
    by = defaultdict(list)
    for a in json.loads(raw.read_text(encoding="utf-8")):
        b = _sm.AD_PAGE.get(str(a.get("pageId") or a.get("pageID")))
        if not b:
            continue
        s = a.get("snapshot") or {}
        body = s.get("body")
        body = body.get("text") if isinstance(body, dict) else body
        txt = " ".join(str(x) for x in [body, s.get("title"), s.get("linkDescription")] + [c.get("body") for c in (s.get("cards") or []) if isinstance(c, dict)] if x)
        by[b].append((txt, str(a.get("startDateFormatted") or "")[:7]))
    out = {}
    for b, v in by.items():
        months = Counter(d for _, d in v if d)
        recent = sum(n for m, n in months.items() if m >= "2026-10")
        out[b] = {"active": len(v), "recent": recent, "recent_from": "Oct 2026",
                  "topics": Counter(t for txt, _ in v for t in tags(txt)).most_common(5),
                  "months": sorted(months.items())}
    return out


def _youtube(con):
    out = {}
    for cid, b in CID.items():
        v = con.execute("""select o.title,(select value from observation_metrics m where m.record_id=o.record_id and metric='views')
                           from observations o where o.company_id=? and o.platform='youtube' and o.source_name like '%official%'
                           and publication_date between '2025-11-01' and '2026-10-31'""", (cid,)).fetchall()
        vs = sorted([x for x in v if x[1]], key=lambda x: -x[1])
        tot = sum(x[1] for x in vs)
        if not vs:
            continue
        out[b] = {"videos": len(v), "views": int(tot), "top3_share": round(sum(x[1] for x in vs[:3]) / tot * 100),
                  "under1k": sum(1 for x in vs if x[1] < 1000), "median": int(st.median([x[1] for x in vs])),
                  "top": [{"title": t[:90], "views": int(n)} for t, n in vs[:3]]}
    return out


def _gads(con):
    out = {}
    for cid, b in CID.items():
        r = dict(con.execute("select lower(format),count(*) from ad_library where company_id=? and in_scope=1 and shown_in_window=1 group by 1", (cid,)).fetchall())
        out[b] = {"total": sum(r.values()), "video": r.get("video", 0), "image": r.get("image", 0), "text": r.get("text", 0)}
    return out


def _trends(con):
    rows = con.execute("select period, metric, value, company_id, url from context_stats where source like 'Google Trends%' order by period").fetchall()
    out = {}
    for period, metric, val, cid, url in rows:
        term = metric.split(":", 1)[1].strip()
        lang = "zh" if re.search(r"[一-鿿]", term) else "en"
        b = CID.get(cid)
        if not b:
            continue
        d = out.setdefault(lang, {"terms": {}, "series": defaultdict(list), "url": url})
        d["terms"][b] = term
        d["series"][b].append([period, round(val, 1)])
    for d in out.values():
        d["series"] = dict(d["series"])
        d["avg"] = {b: round(st.mean(v for _, v in s), 1) for b, s in d["series"].items()}
    return out


def build():
    con = sqlite3.connect(DB)
    _, lst = _li.load()
    deep = {"social": _social(), "li_fmt": lst.get("format_er", {}), "meta_ads": _meta_ads(),
            "crisis": _crisis(), "youtube": _youtube(con), "gads": _gads(con), "trends": _trends(con)}
    con.close()
    return deep


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    d = build()
    for k, v in d.items():
        print("==", k, json.dumps(v, ensure_ascii=False)[:900])
