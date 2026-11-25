"""Module 4.2 - mobile apps: Apple iTunes Lookup API + public review RSS (HK storefront), Google Play listing.

Ratings/versions are point-in-time snapshots (capture date recorded). Historical rating trends are NOT
available retroactively; they accumulate from repeated runs.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from bs4 import BeautifulSoup

from common import COMPANIES, clean_text, fetch, log, make_record


def ios_snapshot(company, app):
    txt, ref = fetch(f"https://itunes.apple.com/lookup?id={app['ios_id']}&country=hk", check_robots=False)
    res = json.loads(txt).get("results", [])
    if not res:
        return None
    a = res[0]
    return make_record(
        brand=company["brand"], record_type="app_snapshot", modules=["M4"], activity_type="app_update",
        title=f"{a['trackName']} (iOS) v{a.get('version')}",
        description=clean_text(a.get("releaseNotes")) or None,
        original_content=a.get("description"),
        publication_date=(a.get("currentVersionReleaseDate") or "")[:10] or None,
        source_name="Apple App Store (HK)", source_category="app_store", source_url=a.get("trackViewUrl"),
        evidence_ref=ref, hk_relevance="explicit", hk_relevance_basis="HK App Store storefront; HK publisher",
        platform="ios", content_format="app_listing", product_name=app["name"],
        metrics={"rating": a.get("averageUserRatingForCurrentVersion") or a.get("averageUserRating"),
                 "rating_all_versions": a.get("averageUserRating"), "rating_count": a.get("userRatingCount")},
        extra={"app_name": app["name"], "app_role": app["role"], "version": a.get("version"),
               "seller": a.get("sellerName"), "first_release": (a.get("releaseDate") or "")[:10],
               "min_os": a.get("minimumOsVersion"), "size_bytes": a.get("fileSizeBytes"),
               "genre": a.get("primaryGenreName"), "store_id": app["ios_id"]},
    )


def ios_reviews(company, app, start, end, pages=10):
    out = []
    for p in range(1, pages + 1):
        url = f"https://itunes.apple.com/hk/rss/customerreviews/page={p}/id={app['ios_id']}/sortby=mostrecent/json"
        try:
            txt, ref = fetch(url, check_robots=False)
        except Exception as e:
            log(f"  reviews {app['name']} p{p}: {e}")
            break
        entries = json.loads(txt).get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        entries = [e for e in entries if "im:rating" in e]
        if not entries:
            break
        for e in entries:
            d = e["updated"]["label"][:10]
            pub = dt.date.fromisoformat(d)
            if not (start <= pub <= end):
                continue
            out.append(make_record(
                brand=company["brand"], record_type="app_review", modules=["M4"],
                title=clean_text(e["title"]["label"]), original_content=clean_text(e["content"]["label"]),
                publication_date=d, source_name="Apple App Store (HK) reviews", source_category="app_store",
                source_url=f"https://apps.apple.com/hk/app/id{app['ios_id']}?see-all=reviews",
                evidence_ref=ref, hk_relevance="explicit", hk_relevance_basis="HK storefront review",
                platform="ios", content_format="review", product_name=app["name"],
                record_id=None, metrics={"rating": int(e["im:rating"]["label"])},
                extra={"app_name": app["name"], "review_id": e["id"]["label"], "version": e.get("im:version", {}).get("label")},
            ))
    return out


def play_snapshot(company, app):
    url = f"https://play.google.com/store/apps/details?id={app['android_id']}&hl=en&gl=HK"
    html, ref = fetch(url, check_robots=False)
    soup = BeautifulSoup(html, "lxml")
    title = clean_text((soup.find("h1") or soup.find("title")).get_text())
    m = re.search(r"Updated on</div><div[^>]*>([^<]+)", html)
    upd = None
    if m:
        try:
            upd = dt.datetime.strptime(m.group(1).strip(), "%b %d, %Y").date().isoformat()
        except ValueError:
            pass
    rating = re.search(r'aria-label="Rated ([\d.]+) stars', html)
    reviews = re.search(r'>([\d.,]+[KM]?)\s*reviews<', html)
    downloads = re.search(r'<div class="ClM7O">([\d.,]+[KMB]?\+)</div><div class="g1rdde">Downloads', html)
    desc = soup.find("meta", attrs={"name": "description"})
    return make_record(
        brand=company["brand"], record_type="app_snapshot", modules=["M4"], activity_type="app_update",
        title=f"{title} (Android)", description=None,
        original_content=desc["content"] if desc else None, publication_date=upd,
        source_name="Google Play (HK)", source_category="app_store", source_url=url, evidence_ref=ref,
        hk_relevance="explicit", hk_relevance_basis="HK Play listing (gl=HK)", platform="android",
        content_format="app_listing", product_name=app["name"],
        metrics={"rating": float(rating.group(1)) if rating else None,
                 "rating_count_text": reviews.group(1) if reviews else None,
                 "downloads_band": downloads.group(1) if downloads else None},
        extra={"app_name": app["name"], "app_role": app["role"], "store_id": app["android_id"]},
    )


def collect(start, end) -> list[dict]:
    out = []
    for c in COMPANIES:
        for app in c.get("apps", []):
            try:
                s = ios_snapshot(c, app)
                if s:
                    out.append(s)
                if app["role"] == "customer":
                    out += ios_reviews(c, app, start, end)
            except Exception as e:
                log(f"  iOS {app['name']}: {e}")
            if app.get("android_id"):
                try:
                    out.append(play_snapshot(c, app))
                except Exception as e:
                    log(f"  Play {app['name']}: {e}")
        log(f"apps {c['brand']}: done")
    return out
