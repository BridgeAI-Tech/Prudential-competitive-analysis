"""Company LinkedIn posts (full-year export) -> per-post rows + brand statistics for the dashboard.

Engagement rate follows brief v3 s4 M2: (reactions + comments + shares) / followers x 100, labelled follower-based.
Followers are the count shown on each page at capture (11 Nov 2026); one denominator per brand for the whole year.
Usage: imported by build.py (load()), or run directly to print a summary.
"""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Prudential" / "dataset_linkedin-company-posts_2026-11-11_06-23-48-682.xlsx"
TAX = ROOT / "Prudential" / "ci-monitor" / "pipeline" / "config" / "taxonomy.json"
PAGES = {"prudential-hong-kong-limited": "Prudential", "aia-hong-kong-&-macau": "AIA",
         "manulife-hong-kong-and-macau": "Manulife", "axahongkong": "AXA"}
WIN = ("2025-11-01", "2026-10-31")


def _themes():
    t = json.loads(TAX.read_text(encoding="utf-8"))["themes"]
    out = {}
    for k, v in t.items():
        pats = [re.compile(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])") for w in v.get("en", [])] + [re.compile(re.escape(w)) for w in v.get("zh", [])]
        out[k] = (v["label"], pats)
    return out


def load():
    import openpyxl
    wb = openpyxl.load_workbook(SRC, read_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    head = [str(h) for h in rows[0]]
    themes = _themes()
    posts, followers = [], {}
    for r in rows[1:]:
        d = dict(zip(head, r))
        brand = PAGES.get(d.get("author/universalName"))
        if not brand or d.get("repostedBy/name"):           # brand-authored originals only; reposts of others are excluded
            continue
        m = re.match(r"([\d,]+) followers", str(d.get("author/info") or ""))
        if m:
            followers[brand] = int(m.group(1).replace(",", ""))
        date = str(d.get("postedAt/date") or "")[:10]
        if not (WIN[0] <= date <= WIN[1]):
            continue
        text = str(d.get("content") or "")
        low = text.lower()
        tags = [k for k, (_, pats) in themes.items() if any(p.search(low) for p in pats)]
        fmt = ("Video" if d.get("postVideo/videoUrl") else "Document" if any(k.startswith("document/") and d.get(k) for k in d)
               else "Article link" if d.get("article/link") else "Image" if d.get("postImages/0/url") else "Text")
        num = lambda k: int(d.get(k) or 0)
        posts.append({"brand": brand, "date": date, "url": d.get("linkedinUrl"), "text": re.sub(r"\s+", " ", text).strip(),
                      "likes": num("engagement/likes"), "comments": num("engagement/comments"), "shares": num("engagement/shares"),
                      "format": fmt, "themes": tags})
    for p in posts:
        f = followers.get(p["brand"])
        p["er"] = round((p["likes"] + p["comments"] + p["shares"]) / f * 100, 3) if f else None
    stats = {"followers": followers, "captured": "11 Nov 2026", "window": WIN, "brand": {}, "theme_er": defaultdict(dict),
             "format_er": defaultdict(dict), "theme_labels": {k: v[0] for k, v in themes.items()}}
    for b in PAGES.values():
        mine = [p for p in posts if p["brand"] == b]
        if not mine:
            continue
        ers = [p["er"] for p in mine if p["er"] is not None]
        stats["brand"][b] = {"posts": len(mine), "followers": followers.get(b),
                             "median_er": round(st.median(ers), 3) if ers else None, "mean_er": round(st.mean(ers), 3) if ers else None,
                             "median_reactions": st.median(p["likes"] for p in mine), "total_shares": sum(p["shares"] for p in mine),
                             "themes": dict(Counter(t for p in mine for t in p["themes"])), "formats": dict(Counter(p["format"] for p in mine)),
                             "months": dict(Counter(p["date"][:7] for p in mine))}
        for k in themes:
            sub = [p["er"] for p in mine if k in p["themes"] and p["er"] is not None]
            if len(sub) >= 3:                                  # small samples are not shown as rates
                stats["theme_er"][b][k] = [round(st.median(sub), 3), len(sub)]
        for fmt, n in Counter(p["format"] for p in mine).items():
            sub = [p["er"] for p in mine if p["format"] == fmt and p["er"] is not None]
            if len(sub) >= 3:
                stats["format_er"][b][fmt] = [round(st.median(sub), 3), len(sub)]
    return posts, stats


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    posts, s = load()
    print("posts in window:", len(posts), "followers:", s["followers"])
    for b, v in s["brand"].items():
        print(f"\n{b}: {v['posts']} posts, median ER {v['median_er']}%, mean {v['mean_er']}%, median reactions {v['median_reactions']}, shares {v['total_shares']}")
        print("  formats", v["formats"])
        print("  themes", sorted(v["themes"].items(), key=lambda kv: -kv[1])[:6])
        print("  theme ER", {k: x for k, x in sorted(s["theme_er"][b].items(), key=lambda kv: -kv[1][0])})
    top = sorted(posts, key=lambda p: -(p["er"] or 0))[:12]
    for p in top:
        print(f"  TOP {p['brand']:10} {p['date']} ER {p['er']}% {p['likes']}r/{p['comments']}c/{p['shares']}s {p['format']:8} {p['text'][:90]}")
