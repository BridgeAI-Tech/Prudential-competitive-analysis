"""Facebook and Instagram posts (official HK accounts, collected via Apify) -> per-post rows + brand statistics.

Engagement rate (follower-based, brief v3 s4 M2), one definition per platform, never mixed:
  Facebook  = (reactions + shares) / page followers x 100      (comment counts are missing on most posts in the export, so not used)
  Instagram = (likes + comments) / account followers x 100     (Instagram does not expose shares; posts with hidden likes are excluded)
  Threads   = (likes + replies + reposts + quotes) / account followers x 100   (added 17 Nov 2026; Prudential and AIA have accounts,
              AIA's last post was 30 Jul 2025, so only Prudential has posts in the period; AXA and Manulife have no Threads account)
Followers are the counts shown at capture (11 Nov 2026). Only posts owned by the brand account, dated 1 Nov 2025 - 31 Oct 2026.
"""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "Prudential" / "apify_raw"
TAX = ROOT / "Prudential" / "ci-monitor" / "pipeline" / "config" / "taxonomy.json"
WIN = ("2025-11-01", "2026-10-31")
FB_PAGE = {"prudentialhk": "Prudential", "AIAHongKong": "AIA", "AXAHongKong": "AXA", "manulifehongkong": "Manulife"}
IG_USER = {"prudential.hongkong": "Prudential", "axahongkong": "AXA", "manulife_hongkong": "Manulife", "aiahongkongmacau": "AIA"}  # AIA: listed on AIA's own official-platforms page


def _themes():
    t = json.loads(TAX.read_text(encoding="utf-8"))["themes"]
    return {k: [re.compile(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])") for w in v.get("en", [])] + [re.compile(re.escape(w)) for w in v.get("zh", [])]
            for k, v in t.items()}


def load():
    themes = _themes()
    tag = lambda text: [k for k, pats in themes.items() if any(p.search(text.lower()) for p in pats)]
    posts, followers = [], {"Facebook": {}, "Instagram": {}, "Threads": {}}
    for x in json.loads((RAW / "fb_pages.json").read_text(encoding="utf-8")):
        b = FB_PAGE.get(str(x.get("pageUrl", "")).rstrip("/").split("/")[-1])
        if b and x.get("followers"):
            followers["Facebook"][b] = int(x["followers"])
    for x in [y for f in ("ig_profiles.json", "ig_profile_aia.json") if (RAW / f).exists() for y in json.loads((RAW / f).read_text(encoding="utf-8"))]:
        b = IG_USER.get(str(x.get("username") or "").lower())
        if b and x.get("followersCount"):
            followers["Instagram"][b] = int(x["followersCount"])
    for x in json.loads((RAW / "fb_posts.json").read_text(encoding="utf-8")):
        b = FB_PAGE.get(x.get("pageName"))
        date = str(x.get("time") or "")[:10]
        if not b or not (WIN[0] <= date <= WIN[1]):
            continue
        text = re.sub(r"\s+", " ", str(x.get("text") or "")).strip()
        video = any(isinstance(m, dict) and m.get("__typename") == "Video" for m in (x.get("media") or []))
        f = followers["Facebook"].get(b)
        r, sh = int(x.get("likes") or 0), int(x.get("shares") or 0)
        posts.append({"platform": "Facebook", "brand": b, "date": date, "url": x.get("url"), "text": text, "format": "Video" if video else "Post",
                      "reactions": r, "comments": x.get("comments"), "shares": sh, "er": round((r + sh) / f * 100, 3) if f else None, "themes": tag(text)})
    for x in [y for f in ("ig_posts.json", "ig_posts_aia.json") if (RAW / f).exists() for y in json.loads((RAW / f).read_text(encoding="utf-8"))]:
        b = IG_USER.get(str(x.get("ownerUsername") or "").lower())                   # collaboration posts owned by partner accounts are excluded
        date = str(x.get("timestamp") or "")[:10]
        if not b or not (WIN[0] <= date <= WIN[1]):
            continue
        text = re.sub(r"\s+", " ", str(x.get("caption") or "")).strip()
        likes, com = x.get("likesCount"), int(x.get("commentsCount") or 0)
        f = followers["Instagram"].get(b)
        ok = likes is not None and likes >= 0 and f
        posts.append({"platform": "Instagram", "brand": b, "date": date, "url": x.get("url"), "text": text,
                      "format": {"Sidecar": "Carousel"}.get(x.get("type"), x.get("type") or "Post"),
                      "reactions": likes if likes is not None and likes >= 0 else None, "comments": com, "shares": None,
                      "views": x.get("videoViewCount"), "er": round((likes + com) / f * 100, 3) if ok else None, "themes": tag(text)})
    # Threads: account usernames are the Instagram ones; profiles checked for all four brands (threads_profiles.json)
    if (RAW / "threads_profiles.json").exists():
        for x in json.loads((RAW / "threads_profiles.json").read_text(encoding="utf-8")):
            b = IG_USER.get(str(x.get("username") or "").lower())
            if b and x.get("follower_count"):
                followers["Threads"][b] = int(x["follower_count"])
    for x in [y for f in ("threads_posts_pru.json", "threads_posts.json") if (RAW / f).exists() for y in json.loads((RAW / f).read_text(encoding="utf-8"))]:
        b = IG_USER.get(str(x.get("username") or "").lower())
        date = str(x.get("created_at") or "")[:10]
        if not b or not (WIN[0] <= date <= WIN[1]) or str(x.get("is_repost")) == "True" or str(x.get("is_reply")) == "True":
            continue
        text = re.sub(r"\s+", " ", str(x.get("text_content") or "")).strip()
        n = lambda k: int(float(x.get(k) or 0))
        f = followers["Threads"].get(b)
        likes, rep, rp, qt = n("like_count"), n("reply_count"), n("repost_count"), n("quote_count")
        posts.append({"platform": "Threads", "brand": b, "date": date, "url": x.get("post_url"), "text": text,
                      "format": {"video": "Video", "image": "Image", "photo": "Image", "carousel": "Carousel"}.get(str(x.get("media_type") or "").lower(), "Text"),
                      "reactions": likes, "comments": rep, "shares": rp + qt, "views": n("view_count") if str(x.get("view_count_status")) == "available" else None,
                      "er": round((likes + rep + rp + qt) / f * 100, 3) if f else None, "themes": tag(text)})
    stats = {"followers": followers, "brand": defaultdict(dict)}
    for plat in ("Facebook", "Instagram", "Threads"):
        for b in ("Prudential", "AIA", "Manulife", "AXA"):
            mine = [p for p in posts if p["platform"] == plat and p["brand"] == b]
            if not mine:
                continue
            ers = [p["er"] for p in mine if p["er"] is not None]
            stats["brand"][plat][b] = {"posts": len(mine), "followers": followers[plat].get(b),
                                       "median_er": round(st.median(ers), 3) if ers else None,
                                       "median_reactions": st.median([p["reactions"] for p in mine if p["reactions"] is not None] or [0]),
                                       "formats": dict(Counter(p["format"] for p in mine)), "themes": dict(Counter(t for p in mine for t in p["themes"]))}
    return posts, stats



AD_PAGE = {"191172447574636": "Prudential", "233237970068198": "AIA", "381309905353457": "AXA", "485081128298580": "Manulife"}


def load_ads():
    p = RAW / "fb_ads.json"
    out = {}
    if not p.exists():
        return out
    for x in json.loads(p.read_text(encoding="utf-8")):
        b = AD_PAGE.get(str(x.get("pageId") or x.get("pageID")))
        if not b:
            continue
        o = out.setdefault(b, {"active": 0, "formats": Counter(), "platforms": Counter(), "cta": Counter(), "earliest": None})
        o["active"] += 1
        snap = x.get("snapshot") or {}
        o["formats"][(snap.get("displayFormat") or "other").title()] += 1
        for pl in x.get("publisherPlatform") or []:
            o["platforms"][pl.title()] += 1
        if snap.get("ctaText"):
            o["cta"][snap["ctaText"]] += 1
        d = str(x.get("startDateFormatted") or "")[:10]
        if d and (o["earliest"] is None or d < o["earliest"]):
            o["earliest"] = d
    return {b: {"active": v["active"], "formats": dict(v["formats"]), "platforms": dict(v["platforms"]),
                "cta": dict(v["cta"].most_common(3)), "earliest": v["earliest"], "captured": "11 Nov 2026"} for b, v in out.items()}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    posts, s = load()
    print(len(posts), "posts; followers", s["followers"])
    for plat, d in s["brand"].items():
        for b, v in d.items():
            print(f"{plat:9} {b:10} posts {v['posts']:3}  followers {v['followers']}  median ER {v['median_er']}%  median reactions {v['median_reactions']}  {v['formats']}")
