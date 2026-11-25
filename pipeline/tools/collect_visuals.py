"""Visual evidence for the dashboard (Sahaj's walkthrough, 17 Nov 2026: "add screenshots and snapshots from source content").

Collects, for each insurer, inside the dashboard window (Nov 2025 - Oct 2026):
  - recent Instagram and Facebook posts (Apify official actors) and Meta Ad Library ads, top items by engagement / recency
  - YouTube video thumbnails (from the collected YouTube records)
  - Xiaohongshu notes and WeChat articles (pilot, from apify_raw/xhs_test.json and wechat_test.json)
  - screenshots of each insurer's home page and a flagship health / critical illness page (headless browser)
Images are downloaded straight away (Meta's image links expire within days), resized to 560 px wide JPEG and saved in
report_app/prudential/media/; the list is report_app/prudential/media/media.json. They are served only behind the
dashboard login. No personal data: posts are the insurers' own; no commenter or author profile data is kept.
Usage: python -I Prudential/ci-monitor/tools/collect_visuals.py [--no-apify] [--no-shots]
"""
import io
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]                   # F:\Australia defence department
PRU = ROOT / "Prudential"
MEDIA = ROOT / "report_app" / "prudential" / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
WIN0, WIN1 = "2025-11-01", "2026-10-31"
SINCE = "2026-06-01"                                          # recent part of the window, for fresh image links
IG = {"Prudential": "prudential.hongkong", "AIA": "aiahongkongmacau", "Manulife": "manulife_hongkong", "AXA": "axahongkong"}
FB = {"Prudential": "https://www.facebook.com/prudentialhk", "AIA": "https://www.facebook.com/AIAHongKong/",
      "AXA": "https://www.facebook.com/AXAHongKong", "Manulife": "https://www.facebook.com/manulifehongkong/"}
ADS = {"Prudential": "191172447574636", "AIA": "233237970068198", "Manulife": "485081128298580", "AXA": "381309905353457"}
HOME = {"Prudential": "https://www.prudential.com.hk/en/", "AIA": "https://www.aia.com.hk/en/", "Manulife": "https://www.manulife.com.hk/en/",
        "AXA": "https://www.axa.com.hk/en"}
PER = 6                                                        # items per brand per channel shown in the gallery
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def token():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*APIFY_(?:API_)?TOKEN\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip("\"'")


def apify(actor, inp, t=500):
    req = urllib.request.Request(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?timeout={t}&clean=true",
                                 data=json.dumps(inp).encode(), headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=t + 60))
    except Exception as e:
        print("  apify failed:", actor, str(e)[:150])
        return []


def save_img(url, name, headers=None):
    """Download, resize to 560 px wide, save as JPEG. Returns the file name or None."""
    from PIL import Image
    if not url:
        return None
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=30).read()
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width > 560:
            im = im.resize((560, round(im.height * 560 / im.width)))
        if im.height > 900:
            im = im.crop((0, 0, im.width, 900))
        f = f"{name}.jpg"
        im.save(MEDIA / f, "JPEG", quality=78, optimize=True)
        return f
    except Exception as e:
        print("  image failed:", name, str(e)[:80])
        return None


def day(s):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    return f"{m[1]}-{m[2]}-{m[3]}" if m else ""


def in_window(d):
    return bool(d) and WIN0 <= d <= WIN1


def clip(t, n=180):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(t or ""))).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


items = []


def collect_social():
    jobs = {
        "ig": ("apify~instagram-post-scraper", {"username": list(IG.values()), "resultsLimit": 60, "onlyPostsNewerThan": SINCE}),
        "fb": ("apify~facebook-posts-scraper", {"startUrls": [{"url": u} for u in FB.values()], "resultsLimit": 25,
                                                "onlyPostsNewerThan": SINCE, "onlyPostsOlderThan": "2026-11-01"}),
        "ads": ("apify~facebook-ads-scraper", {"startUrls": [{"url": f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=HK&media_type=all&view_all_page_id={p}"}
                                                              for p in ADS.values()], "resultsLimit": 40, "onlyAdsNewerThan": SINCE}),
    }
    raw = {}
    for k in list(jobs):
        f = PRU / "apify_raw" / f"visuals_{k}.json"
        if "--from-raw" in sys.argv and f.exists() and json.loads(f.read_text(encoding="utf-8")):
            raw[k] = json.loads(f.read_text(encoding="utf-8"))
            jobs.pop(k)
    with ThreadPoolExecutor(3) as ex:
        raw.update(dict(zip(jobs, ex.map(lambda j: apify(*j), jobs.values()))))
    if not raw.get("ads"):        # the actor sometimes returns nothing with a date filter: retry as the original run did
        raw["ads"] = apify("apify~facebook-ads-scraper", {"startUrls": [{"url": f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=HK&media_type=all&view_all_page_id={p}"}
                                                                          for p in ADS.values()], "resultsLimit": 160, "activeStatus": "", "includeAboutPage": False})
    for k, v in raw.items():
        (PRU / "apify_raw" / f"visuals_{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        print(k, len(v))
    brand_of_ig = {v.lower(): k for k, v in IG.items()}
    picks = {}
    for p in raw["ig"]:
        b = brand_of_ig.get(str(p.get("ownerUsername") or "").lower())
        d = day(p.get("timestamp"))
        if b and in_window(d) and p.get("displayUrl"):
            picks.setdefault(("instagram", b), []).append({"brand": b, "platform": "Instagram", "date": d, "url": p.get("url"),
                                                           "img": p.get("displayUrl"), "text": clip(p.get("caption")),
                                                           "likes": p.get("likesCount") or 0, "comments": p.get("commentsCount") or 0,
                                                           "kind": "video" if p.get("type") == "Video" else "post", "id": p.get("shortCode") or p.get("id")})
    page_brand = {"prudentialhk": "Prudential", "aiahongkong": "AIA", "axahongkong": "AXA", "manulifehongkong": "Manulife"}
    for p in raw["fb"]:
        b = page_brand.get(str(p.get("pageName") or p.get("inputUrl", "").rstrip("/").split("/")[-1]).lower())
        d = day(p.get("time"))
        img = None
        for m in p.get("media") or []:
            img = (m.get("thumbnail") or (m.get("photo_image") or {}).get("uri") or (m.get("image") or {}).get("uri")) if isinstance(m, dict) else None
            if img:
                break
        if b and in_window(d) and img:
            picks.setdefault(("facebook", b), []).append({"brand": b, "platform": "Facebook", "date": d, "url": p.get("url"), "img": img,
                                                          "text": clip(p.get("text")), "likes": p.get("likes") or 0, "comments": p.get("comments") or 0,
                                                          "kind": "post", "id": p.get("postId")})
    pid_brand = {v: k for k, v in ADS.items()}
    for a in raw["ads"]:
        b = pid_brand.get(str(a.get("pageId") or a.get("pageID") or ""))
        s = a.get("snapshot") or {}
        d = day(a.get("startDateFormatted"))
        img = None
        for im in (s.get("images") or []):
            img = im.get("resizedImageUrl") or im.get("originalImageUrl")
            break
        if not img:
            for c in (s.get("cards") or []):
                img = c.get("resizedImageUrl") or c.get("originalImageUrl") or c.get("videoPreviewImageUrl")
                if img:
                    break
        if not img:
            for v in (s.get("videos") or []):
                img = v.get("videoPreviewImageUrl")
                break
        body = (s.get("body") or {}).get("text") if isinstance(s.get("body"), dict) else s.get("body")
        aid = a.get("adArchiveID") or a.get("adArchiveId")
        if b and in_window(d) and img:
            picks.setdefault(("ad", b), []).append({"brand": b, "platform": "Meta ad", "date": d, "url": f"https://www.facebook.com/ads/library/?id={aid}",
                                                    "img": img, "text": clip(s.get("title") or body), "cta": s.get("ctaText"),
                                                    "platforms": a.get("publisherPlatform"), "kind": "ad", "id": aid, "likes": 0})
    print("eligible:", {f"{c}/{b}": len(v) for (c, b), v in picks.items()})
    for (ch, b), v in picks.items():
        v.sort(key=lambda x: (x["likes"] + 2 * x.get("comments", 0), x["date"]) if ch != "ad" else (x["date"],), reverse=True)
        seen = set()
        for x in v:
            if len([y for y in items if y["brand"] == b and y["platform"] == x["platform"]]) >= PER:
                break
            if x["text"][:60] in seen:
                continue
            seen.add(x["text"][:60])
            f = save_img(x.pop("img"), f"{ch}_{b.lower()}_{re.sub(r'[^A-Za-z0-9]', '', str(x['id']))[:24]}")
            if f:
                items.append({**x, "file": f})


def collect_youtube():
    rows = [json.loads(l) for l in open(PRU / "ci-monitor" / "data" / "raw" / "youtube.jsonl", encoding="utf-8")]
    for b in IG:
        rs = [r for r in rows if r.get("brand") == b and in_window(day(r.get("publication_date")))]
        rs.sort(key=lambda r: ((r.get("metrics") or {}).get("views") or (r.get("metrics") or {}).get("view_count") or 0), reverse=True)
        for r in rs[:PER]:
            m = re.search(r"(?:v=|youtu\.be/|/shorts/)([\w-]{11})", r.get("source_url") or "")
            if not m:
                continue
            f = save_img(f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg", f"youtube_{b.lower()}_{m.group(1)}")
            if f:
                mt = r.get("metrics") or {}
                items.append({"brand": b, "platform": "YouTube", "date": day(r.get("publication_date")), "url": r.get("source_url"),
                              "text": clip(r.get("english_summary") or r.get("title")), "title": clip(r.get("title"), 90),
                              "likes": mt.get("likes") or 0, "views": mt.get("views") or mt.get("view_count") or 0, "kind": "video", "file": f})


def collect_china():
    """Pilot: Xiaohongshu notes and WeChat articles found by keyword (insurers' names); brand content only."""
    kw_brand = {"保诚": "Prudential", "保誠": "Prudential", "友邦": "AIA", "宏利": "Manulife", "安盛": "AXA"}
    for f, plat in (("xhs_test.json", "Xiaohongshu"), ("wechat_test.json", "WeChat")):
        p = PRU / "apify_raw" / f
        if not p.exists():
            continue
        n = {}
        for it in json.loads(p.read_text(encoding="utf-8")):
            text = clip(it.get("title") or it.get("desc"), 120)
            b = next((v for k, v in kw_brand.items() if k in (str(it.get("keyword") or "") + text)), None)
            if not b or n.get(b, 0) >= 3:
                continue
            img = (it.get("images") or [{}])[0].get("url") if plat == "Xiaohongshu" else it.get("thumbUrl")
            if plat == "WeChat" and img and "mmecoa." in img:
                continue
            url = it.get("url") or it.get("doc_url") or ""
            d = day(it.get("timestamp") and time.strftime("%Y-%m-%d", time.gmtime(int(str(it["timestamp"])[:10]))) or it.get("date"))
            fn = save_img(img, f"{plat.lower()}_{b.lower()}_{n.get(b, 0)}", headers={"Referer": "https://www.xiaohongshu.com/"} if plat == "Xiaohongshu" else None)
            if fn:
                items.append({"brand": b, "platform": plat, "date": d, "url": url, "text": text, "kind": "note" if plat == "Xiaohongshu" else "article",
                              "file": fn, "pilot": True, "likes": 0})
                n[b] = n.get(b, 0) + 1


def collect_shots():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    hci = {}
    try:
        lineup = json.loads((PRU / "_report_work" / "health_ci_products.json").read_text(encoding="utf-8"))
        for row in lineup.get("lineup") or lineup.get("products") or []:
            b, u = row.get("brand"), row.get("product_page") or row.get("url")
            if b in HOME and u and b not in hci and re.search(r"(?i)critical|illness|\bci\b", (row.get("category") or "") + (row.get("plan_en") or "")):
                hci[b] = (u, row.get("plan_en") or "Critical illness product page")
    except Exception as e:
        print("  health lineup not read:", e)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB", user_agent=UA["User-Agent"])
        for b, home in HOME.items():
            for kind, (url, title) in (("home", (home, f"{b} Hong Kong home page")), ("health", hci.get(b, (None, None)))):
                if not url:
                    continue
                pg = ctx.new_page()
                try:
                    pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(5000)
                    for sel in ("button:has-text('Accept')", "button:has-text('accept')", "button:has-text('Agree')", "button:has-text('同意')", "#onetrust-accept-btn-handler"):
                        try:
                            if pg.locator(sel).first.is_visible(timeout=600):
                                pg.locator(sel).first.click(timeout=1500)
                                pg.wait_for_timeout(800)
                                break
                        except Exception:
                            pass
                    png = pg.screenshot(type="png")
                    im = Image.open(io.BytesIO(png)).convert("RGB").resize((800, 500))
                    f = f"site_{b.lower()}_{kind}.jpg"
                    im.save(MEDIA / f, "JPEG", quality=80, optimize=True)
                    items.append({"brand": b, "platform": "Website", "date": time.strftime("%Y-%m-%d"), "url": url, "text": title,
                                  "kind": "screenshot", "file": f, "captured": time.strftime("%d %b %Y")})
                    print("  screenshot", b, kind)
                except Exception as e:
                    print("  screenshot failed", b, kind, str(e)[:80])
                finally:
                    pg.close()
        br.close()


if __name__ == "__main__":
    old = MEDIA / "media.json"
    keep = [x for x in (json.loads(old.read_text(encoding="utf-8")) if old.exists() else [])]
    if "--no-apify" not in sys.argv:
        collect_social()
    else:
        items += [x for x in keep if x["platform"] in ("Instagram", "Facebook", "Meta ad")]
    collect_youtube()
    collect_china()
    if "--no-shots" not in sys.argv:
        collect_shots()
    else:
        items += [x for x in keep if x["platform"] == "Website"]
    old.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("saved", len(items), dict(Counter((x["platform"]) for x in items)))
    print("per brand", dict(Counter(x["brand"] for x in items)))
