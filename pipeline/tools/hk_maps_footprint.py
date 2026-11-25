"""Physical footprint and location sentiment for the four insurers in Hong Kong, from Google Maps.

Places:  compass/crawler-google-places   - each brand x each of the 18 districts, in English and Chinese, plus
                                           Hong Kong-wide "customer service centre" searches. Gives coordinates,
                                           address, category, rating and review count.
Reviews: compass/Google-Maps-Reviews-Scraper - newest reviews for every in-scope place, 1 Nov 2025 onwards,
                                           without reviewer personal data (personalData=false).

Hong Kong has districts, not provinces: each place is assigned to one of the 18 districts from its address, or the
nearest district centre when the address does not name an area. Only places in Hong Kong (countryCode HK) are kept;
Macau places are left out (outside the scope). Nothing else is dropped: buildings named after a brand (e.g. "AIA Tower") are
kept as "Named building", and businesses that only share a name (e.g. an employment agency called Prudential) are kept as
"Other business with a similar name"; neither is counted as a service point.

    python -I Prudential/ci-monitor/tools/hk_maps_footprint.py              # places + reviews + process
    python -I Prudential/ci-monitor/tools/hk_maps_footprint.py --process    # re-process saved raw data only
Outputs (Prudential/hk_maps/): places_raw.json, reviews_raw.json, footprint.json, HK_physical_footprint.xlsx
APIFY_TOKEN is read from the project .env and sent only in a header.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Prudential" / "hk_maps"
WIN = ("2025-11-01", "2026-10-31")

BRANDS = {
    "Prudential": {"en": "Prudential", "zh": "保誠", "rx": r"prudential|保誠|保诚"},
    "AIA": {"en": "AIA", "zh": "友邦", "rx": r"\bAIA\b|友邦"},
    "Manulife": {"en": "Manulife", "zh": "宏利", "rx": r"manulife|宏利"},
    "AXA": {"en": "AXA", "zh": "安盛", "rx": r"\bAXA\b|安盛"},
}
# 18 districts: English, Chinese, approximate centre (lat, lng), area names that appear in addresses
DISTRICTS = [
    ("Central and Western", "中西區", 22.2830, 114.1500, "central|sheung wan|admiralty|mid-levels|sai ying pun|kennedy town|中環|上環|金鐘|西營盤|堅尼地城"),
    ("Wan Chai", "灣仔區", 22.2780, 114.1760, "wan chai|causeway bay|happy valley|tin hau|灣仔|銅鑼灣|跑馬地|天后"),
    ("Eastern", "東區", 22.2840, 114.2240, "north point|quarry bay|tai koo|taikoo|sai wan ho|shau kei wan|chai wan|fortress hill|北角|鰂魚涌|太古|西灣河|筲箕灣|柴灣"),
    ("Southern", "南區", 22.2470, 114.1580, "aberdeen|wong chuk hang|ap lei chau|pok fu lam|repulse bay|stanley|香港仔|黃竹坑|鴨脷洲|薄扶林|赤柱"),
    ("Yau Tsim Mong", "油尖旺區", 22.3110, 114.1700, "tsim sha tsui|jordan|yau ma tei|mong kok|tai kok tsui|尖沙咀|佐敦|油麻地|旺角|大角咀"),
    ("Sham Shui Po", "深水埗區", 22.3300, 114.1600, "sham shui po|cheung sha wan|lai chi kok|shek kip mei|深水埗|長沙灣|荔枝角|石硤尾"),
    ("Kowloon City", "九龍城區", 22.3280, 114.1910, "kowloon city|hung hom|to kwa wan|kowloon tong|ho man tin|kai tak|九龍城|紅磡|土瓜灣|九龍塘|何文田|啟德"),
    ("Wong Tai Sin", "黃大仙區", 22.3420, 114.1950, "wong tai sin|diamond hill|san po kong|tsz wan shan|黃大仙|鑽石山|新蒲崗|慈雲山"),
    ("Kwun Tong", "觀塘區", 22.3130, 114.2250, "kwun tong|kowloon bay|ngau tau kok|lam tin|yau tong|觀塘|九龍灣|牛頭角|藍田|油塘"),
    ("Kwai Tsing", "葵青區", 22.3570, 114.1250, "kwai chung|kwai fong|kwai hing|tsing yi|葵涌|葵芳|葵興|青衣"),
    ("Tsuen Wan", "荃灣區", 22.3710, 114.1140, "tsuen wan|荃灣"),
    ("Tuen Mun", "屯門區", 22.3910, 113.9730, "tuen mun|屯門"),
    ("Yuen Long", "元朗區", 22.4450, 114.0220, "yuen long|tin shui wai|元朗|天水圍"),
    ("North", "北區", 22.4950, 114.1380, "sheung shui|fanling|上水|粉嶺"),
    ("Tai Po", "大埔區", 22.4500, 114.1650, "tai po|大埔"),
    ("Sha Tin", "沙田區", 22.3830, 114.1880, "sha tin|shatin|ma on shan|fo tan|tai wai|沙田|馬鞍山|火炭|大圍"),
    ("Sai Kung", "西貢區", 22.3300, 114.2600, "sai kung|tseung kwan o|hang hau|po lam|西貢|將軍澳|坑口|寶琳"),
    ("Islands", "離島區", 22.2600, 113.9450, "tung chung|lantau|discovery bay|cheung chau|東涌|大嶼山|愉景灣|長洲"),
]
TOPICS = {
    "Claims": r"claim|reimburse|理賠|索償|賠償",
    "Staff and service": r"staff|service|friendly|helpful|polite|rude|attitude|professional|服務|態度|職員|專業|有禮",
    "Waiting time": r"wait|queue|slow|long time|ticket|等|排隊|好耐|慢",
    "Agents and sales": r"agent|adviser|advisor|sales|pushy|consultant|經紀|代理|推銷|顧問",
    "Policy and payments": r"policy|premium|payment|surrender|refund|cancel|保單|保費|退保|退款|供款",
    "Phone and online": r"phone|hotline|call|app\b|online|website|email|電話|熱線|網上|手機",
    "Location and facilities": r"location|parking|clean|comfortable|environment|lift|環境|地點|乾淨|舒適",
}


def token() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("APIFY_TOKEN="):
            return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("APIFY_TOKEN is not set in .env")


def api(method: str, path: str, payload=None, timeout=60):
    req = urllib.request.Request("https://api.apify.com/v2" + path, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        msg = e.read()[:300].decode("utf-8", "replace")
        sys.exit(f"Apify HTTP {e.code} on {path.split('?')[0]}: {'token rejected - renew APIFY_TOKEN in .env' if e.code == 401 else msg}")


def run_actor(actor: str, run_input: dict, label: str) -> list:
    """Start an actor run, wait for it, return all dataset items (async: big runs exceed the sync limit)."""
    run = api("POST", f"/acts/{actor.replace('/', '~')}/runs", run_input)["data"]
    print(f"{label}: run {run['id']} started")
    while True:
        time.sleep(15)
        run = api("GET", f"/actor-runs/{run['id']}")["data"]
        if run["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        print(f"  {label}: {run['status']} ({(run.get('stats') or {}).get('runTimeSecs', 0):.0f}s)")
    if run["status"] != "SUCCEEDED":
        sys.exit(f"{label}: run ended {run['status']}")
    items, off = [], 0
    while True:
        page = api("GET", f"/datasets/{run['defaultDatasetId']}/items?clean=true&offset={off}&limit=1000", timeout=120)
        items += page if isinstance(page, list) else []
        if not isinstance(page, list) or len(page) < 1000:
            break
        off += 1000
    usage = run.get("usageTotalUsd")
    print(f"{label}: {len(items)} items" + (f", US${usage:.2f}" if usage else ""))
    return items


def collect_extra() -> list:
    """Second, broader pass: service centres, planning centres, branches and the plain brand name, up to 30 places each."""
    searches = []
    for b in BRANDS.values():
        searches += [f"{b['en']} Hong Kong", b["zh"], f"{b['zh']}保險", f"{b['en']} customer service centre",
                     f"{b['zh']}客戶服務中心", f"{b['en']} financial planning centre", f"{b['zh']}理財中心", f"{b['en']} agency office Hong Kong",
                     f"{b['zh']} 分行", f"{b['zh']}保險 辦事處"]
    return run_actor("compass/crawler-google-places", {
        "searchStringsArray": searches, "locationQuery": "Hong Kong", "maxCrawledPlacesPerSearch": 30, "language": "en",
        "skipClosedPlaces": True, "scrapeContacts": False, "maxImages": 0, "scrapePlaceDetailPage": False,
        "scrapeReviewsPersonalData": False, "maxReviews": 0}, "places (extra pass)")


def collect_places() -> list:
    searches = []
    for b in BRANDS.values():
        for en, zh, *_ in DISTRICTS:
            searches += [f"{b['en']} insurance {en} Hong Kong", f"{b['zh']}保險 {zh}"]
        searches += [f"{b['en']} customer service centre Hong Kong", f"{b['zh']} 客戶服務中心 香港"]
    return run_actor("compass/crawler-google-places", {
        "searchStringsArray": searches, "locationQuery": "Hong Kong", "maxCrawledPlacesPerSearch": 15, "language": "en",
        "skipClosedPlaces": True,   # countryCode "hk" is not an allowed value; locationQuery restricts to Hong Kong "scrapeContacts": False, "maxImages": 0, "scrapePlaceDetailPage": False,
        "scrapeReviewsPersonalData": False, "maxReviews": 0}, "places")


def brand_of(title: str) -> str | None:
    for b, d in BRANDS.items():
        if re.search(d["rx"], title or "", re.I):
            return b
    return None


# Not this insurer, or not a place customers use (checked against the 12 Nov 2026 collection)
OTHER = "Other business with a similar name"
SERVICE = ("Customer service centre", "Health and wellness centre", "Office (agency or adviser team)")
NOT_OURS_T = (r"car ?park|停車場|reverse vending|\bRVM\b|coffee|architect|電業|surveyor|employment agency|engineering|護衛|報價|"
              r"insurance co of america|brokerage ltd|carnival|非客服|investment managers|asset management|資產管理|AIA Group|"
              r"prudential corporation asia|manufacturer|lee gardens manulife plaza;|養生庭|compass offices|fitness|\bEPD\b|hotel|outside prudential|prudential centre;|ansen")
NOT_OURS_C = r"停車場|資源回收點|coffee shop|公車站|bus stop|architects|電器舖|surveyor|stock broker|manufacturer|event venue(?!.*hub)"
BUILDING_T = r"\b(tower|building|plaza|place|central|southside|financial centre|business centre|commercial space)\b|大廈|大樓|中心$|匯$|^aia financial centre$"


# Walk-in centres listed on the insurers' own contact pages (12 Nov 2026): a Maps listing at that address is that centre,
# whatever name the listing uses (e.g. Prudential's centre is listed on Google Maps as "Prudential Insurance Building").
OFFICIAL = [
    ("Prudential", r"prudential (insurance )?tower|harbour city", "Customer Service Centre, 8/F Prudential Tower, Harbour City",
     "https://www.prudential.com.hk/en/general/contact/"),
    ("Prudential", r"one island east|18 westlands", "Prudential General Insurance office, 28/F One Island East",
     "https://www.prudential.com.hk/en/general/contact/"),
    ("AIA", r"aia tower.*electric r|183 electric r", "Customer Service Centre, 12/F AIA Tower, North Point",
     "https://www.aia.com.hk/en/help-and-support/contact-us"),
]


def official_of(p: dict, brand: str):
    addr = (p.get("address") or "").lower()
    for b, rx, name, url in OFFICIAL:
        if b == brand and re.search(rx, addr):
            return name, url
    return None


def kind_of(p: dict) -> str:
    """Customer service centre / Health and wellness centre / Office (agency or adviser team) / Named building / OTHER."""
    t = (p.get("title") or "")
    tl = t.lower()
    cats = " ".join([p.get("categoryName") or ""] + (p.get("categories") or [])).lower()
    if re.search(r"vitality hub", tl):
        return "Health and wellness centre"
    if re.fullmatch(r"prudential centre|axa china region (ltd|limited)", tl):
        return "Named building" if "centre" in tl else "Office (agency or adviser team)"
    if re.search(NOT_OURS_T, t, re.I) or re.search(NOT_OURS_C, cats, re.I):
        return OTHER
    if re.search(r"customer service|客戶服務|客服中心|services? (centre|center)|customer (centre|center)|\bcsc\b", tl + " " + cats):
        return "Customer service centre"
    if re.search(r"clinic|medical|醫療|體檢|vitality hub|wellness", tl + " " + cats):
        return "Health and wellness centre"
    if re.search(BUILDING_T, tl) and not re.search(r"insurance|保險|人壽", cats):
        return "Named building"
    if re.search(r"insurance|保險|人壽|理財|退休金|investment|finance|financial|agency|office|辦公室", cats + " " + tl):
        return "Office (agency or adviser team)"
    return OTHER


def district_of(p: dict) -> str:
    addr = " ".join(str(p.get(k) or "") for k in ("address", "neighborhood", "street", "city")).lower()
    for en, zh, lat, lng, rx in DISTRICTS:
        if re.search(rx, addr):
            return en
    loc = p.get("location") or {}
    if loc.get("lat") is None:
        return "Unknown"
    return min(DISTRICTS, key=lambda d: math.hypot(d[2] - loc["lat"], (d[3] - loc["lng"]) * math.cos(math.radians(22.3))))[0]


def tidy_places(raw: list) -> list:
    seen, out = set(), []
    for p in raw:
        pid = p.get("placeId")
        if not pid or pid in seen or (p.get("countryCode") or "").upper() not in ("HK", ""):
            continue
        if p.get("permanentlyClosed"):
            continue
        b = brand_of(p.get("title"))
        if not b:
            continue
        seen.add(pid)
        k = kind_of(p)
        off = official_of(p, b) if k in SERVICE else None
        if off:
            k = "Customer service centre"
        loc = p.get("location") or {}
        out.append({"placeId": pid, "brand": b, "kind": k, "title": p.get("title"), "category": p.get("categoryName"),
                    "address": p.get("address"), "district": district_of(p), "lat": loc.get("lat"), "lng": loc.get("lng"),
                    "rating": p.get("totalScore"), "reviews": p.get("reviewsCount") or 0, "url": p.get("url"),
                    "temporarilyClosed": bool(p.get("temporarilyClosed")),
                    "official_name": off[0] if off else None, "official_url": off[1] if off else None})
    return out


def collect_reviews(places: list) -> list:
    ids = [p["placeId"] for p in places if p["kind"] in SERVICE and p["reviews"]]
    if not ids:
        return []
    return run_actor("compass/Google-Maps-Reviews-Scraper", {
        "placeIds": ids, "maxReviews": 300, "reviewsSort": "newest", "reviewsStartDate": WIN[0], "language": "en",
        "reviewsOrigin": "google", "personalData": False}, "reviews")


def topics(text: str) -> list:
    return [t for t, rx in TOPICS.items() if re.search(rx, text or "", re.I)]


def process(places: list, reviews: list) -> dict:
    by_place = {p["placeId"]: p for p in places}
    revs = []
    for r in reviews:
        d = (r.get("publishedAtDate") or "")[:10]
        p = by_place.get(r.get("placeId"))
        if not p or not d or not (WIN[0] <= d <= WIN[1]) or r.get("stars") is None:
            continue
        text = (r.get("textTranslated") or r.get("text") or "").strip()
        revs.append({"placeId": p["placeId"], "brand": p["brand"], "district": p["district"], "kind": p["kind"], "date": d,
                     "stars": r["stars"], "text": text[:600], "original": (r.get("text") or "")[:600] if r.get("textTranslated") else "",
                     "lang": r.get("originalLanguage") or r.get("language"), "owner_reply": bool(r.get("responseFromOwnerText")),
                     "topics": topics((r.get("text") or "") + " " + text)})
    summary = {}
    for b in BRANDS:
        pts = [p for p in places if p["brand"] == b and p["kind"] in SERVICE]
        rv = [r for r in revs if r["brand"] == b]
        rated = [p for p in pts if p["rating"] and p["reviews"]]
        tot = sum(p["reviews"] for p in rated)
        neg = [r for r in rv if r["stars"] <= 2]
        top = {}
        for r in neg:
            for t in r["topics"]:
                top[t] = top.get(t, 0) + 1
        summary[b] = {
            "points": len(pts), "kinds": {k: sum(1 for p in pts if p["kind"] == k) for k in SERVICE},
            "named_buildings": sorted({p["title"] for p in places if p["brand"] == b and p["kind"] == "Named building"}),
            "districts": sorted({p["district"] for p in pts if p["district"] != "Unknown"}),
            "avg_rating": round(sum(p["rating"] * p["reviews"] for p in rated) / tot, 2) if tot else None, "all_time_reviews": tot,
            "window_reviews": len(rv), "window_avg_stars": round(sum(r["stars"] for r in rv) / len(rv), 2) if rv else None,
            "positive_pct": round(100 * sum(r["stars"] >= 4 for r in rv) / len(rv)) if rv else None,
            "negative_pct": round(100 * len(neg) / len(rv)) if rv else None,
            "owner_reply_pct": round(100 * sum(r["owner_reply"] for r in rv) / len(rv)) if rv else None,
            "negative_topics": dict(sorted(top.items(), key=lambda kv: -kv[1])),
        }
    grid = {d[0]: {b: sum(1 for p in places if p["brand"] == b and p["kind"] in SERVICE and p["district"] == d[0]) for b in BRANDS} for d in DISTRICTS}
    loc = []
    for p in places:
        if p["kind"] not in SERVICE:
            continue
        rv = [r for r in revs if r["placeId"] == p["placeId"]]
        loc.append({**p, "window_reviews": len(rv), "window_avg_stars": round(sum(r["stars"] for r in rv) / len(rv), 2) if rv else None,
                    "negative_pct": round(100 * sum(r["stars"] <= 2 for r in rv) / len(rv)) if rv else None})
    return {"window": WIN, "collected": time.strftime("%d %b %Y"), "summary": summary, "district_grid": grid, "locations": loc,
            "named_buildings": [p for p in places if p["kind"] == "Named building"], "other_same_name": [p for p in places if p["kind"] == OTHER], "all_listings": places, "reviews": revs}


def write_xlsx(fp: dict):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Brand summary"
    ws.append(["Brand", "Service points", "Customer service centres", "Health centres", "Offices (agency or adviser teams)", "Districts covered (of 18)",
               "Avg Google rating", "All-time reviews", "Reviews in window", "Avg stars in window", "% positive (4-5)", "% negative (1-2)", "% with owner reply"])
    for b, s in fp["summary"].items():
        k = s["kinds"]
        ws.append([b, s["points"], k["Customer service centre"], k["Health and wellness centre"], k["Office (agency or adviser team)"], len(s["districts"]),
                   s["avg_rating"], s["all_time_reviews"], s["window_reviews"], s["window_avg_stars"], s["positive_pct"], s["negative_pct"], s["owner_reply_pct"]])
    ws = wb.create_sheet("District grid")
    ws.append(["District"] + list(BRANDS))
    for d, row in fp["district_grid"].items():
        ws.append([d] + [row[b] for b in BRANDS])
    ws = wb.create_sheet("Locations")
    cols = ["brand", "kind", "title", "district", "address", "lat", "lng", "rating", "reviews", "window_reviews", "window_avg_stars", "negative_pct", "url"]
    ws.append(cols)
    for p in fp["locations"]:
        ws.append([p.get(c) for c in cols])
    ws = wb.create_sheet("All listings found")
    ws.append(["brand", "kind", "title", "district", "address", "rating", "reviews", "url"])
    for p in fp["all_listings"]:
        ws.append([p.get(c) for c in ("brand", "kind", "title", "district", "address", "rating", "reviews", "url")])
    ws = wb.create_sheet("Reviews (no personal data)")
    cols = ["brand", "district", "kind", "date", "stars", "topics", "text", "original", "lang", "owner_reply"]
    ws.append(cols)
    for r in fp["reviews"]:
        ws.append([", ".join(r[c]) if c == "topics" else r.get(c) for c in cols])
    wb.save(OUT / "HK_physical_footprint.xlsx")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--process" not in sys.argv:
        if "--extra" in sys.argv:   # add the broader pass to the saved places, then re-collect reviews for the full set
            raw = json.loads((OUT / "places_raw.json").read_text(encoding="utf-8"))
            have = {p.get("placeId") for p in raw}
            raw += [p for p in collect_extra() if p.get("placeId") not in have]
            (OUT / "places_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        elif "--reviews-only" in sys.argv:
            raw = json.loads((OUT / "places_raw.json").read_text(encoding="utf-8"))
        else:
            raw = collect_places()
            (OUT / "places_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        places = tidy_places(raw)
        reviews = collect_reviews(places)
        (OUT / "reviews_raw.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=1), encoding="utf-8")
    raw = json.loads((OUT / "places_raw.json").read_text(encoding="utf-8"))
    places = tidy_places(raw)
    reviews = json.loads((OUT / "reviews_raw.json").read_text(encoding="utf-8")) if (OUT / "reviews_raw.json").exists() else []
    # reviewer identities are never kept, even if a provider returns them
    reviews = [{k: v for k, v in r.items() if k not in ("name", "reviewerId", "reviewerUrl", "reviewerPhotoUrl", "reviewUrl")} for r in reviews]
    fp = process(places, reviews)
    (OUT / "footprint.json").write_text(json.dumps(fp, ensure_ascii=False, indent=1), encoding="utf-8")
    write_xlsx(fp)
    for b, s in fp["summary"].items():
        print(f"{b}: {s['points']} service points in {len(s['districts'])} districts, rating {s['avg_rating']}, "
              f"{s['window_reviews']} reviews in window ({s['negative_pct']}% negative)")


if __name__ == "__main__":
    main()
