"""Module 2 - post-level social content and engagement.

Sources (each runs only when its access is available; coverage is recorded either way):
  * LinkedIn  - licensed Explorium extract already held in the project folder (*_explorium_data.xlsx).
  * YouTube   - official YouTube Data API v3 (env YOUTUBE_API_KEY).
  * Facebook  - Apify actor apify/facebook-posts-scraper   (env APIFY_TOKEN).
  * Instagram - Apify actor apify/instagram-post-scraper   (env APIFY_TOKEN).
Metrics not exposed by a platform are stored as None (null), never 0.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

from common import COMPANIES, ROOT, clean_text, log, make_record, now_utc

EXPLORIUM_FILES = {
    "Prudential": "Prudential_Hong_Kong_explorium_data.xlsx",
    "AIA": "AIA_Hong_Kong_explorium_data.xlsx",
    "Manulife": "Manulife_Hong_Kong_explorium_data.xlsx",
    "AXA": "AXA_Hong_Kong_explorium_data.xlsx",
}
SOURCE_DIR = ROOT.parent  # F:\Prudential holds the licensed extracts

COVERAGE: list[dict] = []  # platform/account coverage log, exported for the dashboard


def _cov(brand, platform, status, n=0, note=""):
    COVERAGE.append({"brand": brand, "platform": platform, "status": status, "records": n, "note": note,
                     "checked_at": now_utc()})


def _num(v):
    try:
        if v is None or v == "":
            return None
        return int(float(str(v).replace(",", "")))
    except ValueError:
        return None


# ---------------------------------------------------------------- LinkedIn (Explorium extract)
def linkedin_explorium(start, end):
    import openpyxl
    out = []
    for c in COMPANIES:
        f = SOURCE_DIR / EXPLORIUM_FILES[c["brand"]]
        if not f.exists():
            _cov(c["brand"], "linkedin", "unavailable", note="Explorium extract missing")
            continue
        wb = openpyxl.load_workbook(f, read_only=True)
        rows = list(wb["9_Social_Media"].iter_rows(values_only=True))
        cap_date = dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat()
        n = 0
        for i, r in enumerate(rows):
            if not r or not r[1] or str(r[1]).lower().startswith("post"):
                continue
            pub = dt.date.fromisoformat(str(r[1])[:10])
            if not (start <= pub <= end):
                continue
            content = clean_text(r[5])
            # Explorium returns mathematical-bold unicode headings; normalise to plain for matching/display
            import unicodedata
            content_norm = unicodedata.normalize("NFKC", content)
            out.append(make_record(
                brand=c["brand"], record_type="social_post", modules=["M2"],
                title=content_norm[:110] + ("…" if len(content_norm) > 110 else ""),
                original_content=content_norm, publication_date=pub.isoformat(), capture_ts=cap_date,
                source_name="LinkedIn (via Explorium)", source_category="social",
                source_url=c["social"]["linkedin"]["url"], evidence_ref=f"{f.name}#9_Social_Media!row{i + 1}",
                hk_relevance="explicit", hk_relevance_basis="Official HK LinkedIn company page",
                platform="linkedin", content_format="post",
                metrics={"likes": _num(r[3]), "comments": _num(r[4]), "shares": None, "views": None},
                extra={"post_url_available": False,
                       "metric_note": "Explorium extract: likes + comments only (comments often null); no post URL; shares not provided"},
            ))
            n += 1
        _cov(c["brand"], "linkedin", "collected" if n else "no posts in window", n,
             "Licensed Explorium extract; post URLs and shares not provided")
    return out


# ---------------------------------------------------------------- YouTube Data API v3
def youtube_api(start, end):
    key = os.environ.get("YOUTUBE_API_KEY")
    out = []
    for c in COMPANIES:
        yt = c["social"].get("youtube")
        if not yt:
            _cov(c["brand"], "youtube", "no verified account")
            continue
        if not key:
            _cov(c["brand"], "youtube", "pending access", note="Set YOUTUBE_API_KEY (free) to collect")
            continue
        base = "https://www.googleapis.com/youtube/v3"
        ch = requests.get(f"{base}/channels", params={"part": "contentDetails,statistics", "id": yt["channel_id"], "key": key}, timeout=30).json()
        item = ch["items"][0]
        uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
        subs = _num(item["statistics"].get("subscriberCount"))
        ids, token = [], None
        while True:
            pl = requests.get(f"{base}/playlistItems", params={"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "pageToken": token, "key": key}, timeout=30).json()
            stop = False
            for it in pl.get("items", []):
                d = dt.date.fromisoformat(it["contentDetails"]["videoPublishedAt"][:10])
                if d < start:
                    stop = True
                elif d <= end:
                    ids.append(it["contentDetails"]["videoId"])
            token = pl.get("nextPageToken")
            if stop or not token:
                break
        for i in range(0, len(ids), 50):
            vs = requests.get(f"{base}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50]), "key": key}, timeout=30).json()
            for v in vs.get("items", []):
                s, st = v["snippet"], v["statistics"]
                out.append(make_record(
                    brand=c["brand"], record_type="social_post", modules=["M2"], title=clean_text(s["title"]),
                    description=clean_text(s.get("description"))[:1000], original_content=clean_text(s.get("description")),
                    publication_date=s["publishedAt"][:10], source_name="YouTube Data API", source_category="social",
                    source_url=f"https://www.youtube.com/watch?v={v['id']}", evidence_ref=f"youtube:{v['id']}",
                    hk_relevance="explicit", hk_relevance_basis="Official HK YouTube channel", platform="youtube",
                    content_format="video",
                    metrics={"likes": _num(st.get("likeCount")), "comments": _num(st.get("commentCount")),
                             "shares": None, "views": _num(st.get("viewCount")), "followers": subs},
                    extra={"thumbnail": s.get("thumbnails", {}).get("high", {}).get("url"), "duration": v["contentDetails"].get("duration")},
                ))
        _cov(c["brand"], "youtube", "collected", len(ids), "Official API; shares not exposed")
    return out


# ---------------------------------------------------------------- Apify (Facebook / Instagram)
APIFY = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def _apify(actor, payload, token):
    r = requests.post(APIFY.format(actor=actor), params={"token": token}, json=payload, timeout=600)
    r.raise_for_status()
    return r.json()


def apify_social(start, end):
    token = os.environ.get("APIFY_TOKEN")
    out = []
    for c in COMPANIES:
        for platform in ("facebook", "instagram"):
            acct = c["social"].get(platform)
            if not acct:
                _cov(c["brand"], platform, "no verified account",
                     note="Official account not verifiable (site blocked)" if c["brand"] == "Manulife" else "")
                continue
            if not token:
                _cov(c["brand"], platform, "pending access", note="Set APIFY_TOKEN to collect via licensed actor")
                continue
            try:
                if platform == "facebook":
                    items = _apify("apify~facebook-posts-scraper", {"startUrls": [{"url": acct["url"]}], "resultsLimit": 200,
                                                                     "onlyPostsNewerThan": start.isoformat()}, token)
                else:
                    user = acct["url"].rstrip("/").split("/")[-1]
                    items = _apify("apify~instagram-post-scraper", {"username": [user], "resultsLimit": 200,
                                                                     "onlyPostsNewerThan": start.isoformat()}, token)
            except Exception as e:
                _cov(c["brand"], platform, "error", note=str(e)[:200])
                continue
            n = 0
            for it in items:
                ts = it.get("time") or it.get("timestamp") or it.get("date")
                if not ts:
                    continue
                pub = dt.date.fromisoformat(str(ts)[:10])
                if not (start <= pub <= end):
                    continue
                text = clean_text(it.get("text") or it.get("caption") or "")
                if platform == "facebook":
                    m = {"likes": _num(it.get("likes") or it.get("reactionsCount")), "comments": _num(it.get("comments") or it.get("commentsCount")),
                         "shares": _num(it.get("shares") or it.get("sharesCount")), "views": _num(it.get("viewsCount") or it.get("videoViewCount"))}
                else:
                    likes = it.get("likesCount")
                    m = {"likes": None if likes in (None, -1) else _num(likes), "comments": _num(it.get("commentsCount")),
                         "shares": None, "views": _num(it.get("videoPlayCount") or it.get("videoViewCount"))}
                out.append(make_record(
                    brand=c["brand"], record_type="social_post", modules=["M2"], title=text[:110] or "(no caption)",
                    original_content=text, publication_date=pub.isoformat(), source_name=f"{platform.title()} (Apify)",
                    source_category="social", source_url=it.get("url") or it.get("postUrl"), evidence_ref=f"apify:{platform}:{it.get('id') or it.get('postId')}",
                    hk_relevance="explicit", hk_relevance_basis=f"Official HK {platform} account", platform=platform,
                    content_format=(it.get("type") or "post").lower(), metrics=m,
                    extra={"image": it.get("displayUrl") or (it.get("media") or [{}])[0].get("thumbnail") if isinstance(it.get("media"), list) else it.get("displayUrl")},
                ))
                n += 1
            _cov(c["brand"], platform, "collected", n, "Licensed Apify actor")
    return out


def collect(start, end):
    COVERAGE.clear()
    out = []
    for fn in (linkedin_explorium, youtube_api, apify_social):
        try:
            r = fn(start, end)
            log(f"social {fn.__name__}: {len(r)} posts")
            out += r
        except Exception as e:
            log(f"social {fn.__name__} FAILED: {e}")
    # platforms in brief scope with no POC collector
    for c in COMPANIES:
        for p in ("tiktok", "xiaohongshu", "wechat"):
            if c["social"].get(p):
                _cov(c["brand"], p, "account verified - not collected", note="Out of POC collection scope")
            else:
                _cov(c["brand"], p, "no verified account")
    (ROOT / "data" / "raw" / "social_coverage.json").write_text(json.dumps(COVERAGE, indent=1, ensure_ascii=False), encoding="utf-8")
    return out
