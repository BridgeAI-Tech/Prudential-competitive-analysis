"""Module 2 - YouTube videos from the four official HK channels + HK-business search hits, via yt-dlp public metadata.

No API key and no login: yt-dlp reads the same public watch/channel pages a browser gets (metadata only, never downloads
media). Polite: >= 1 s between requests (yt-dlp sleep_interval_requests) plus a pause between videos.

Output (same record format as every other collector):
  data/raw/youtube.jsonl              record_type social_post, platform youtube, source_category social
  data/raw/youtube_channels.json      channel context (subscriber count at capture) -> table channel_context
  data/raw/youtube_coverage.json      per-brand coverage rows (merged into source_coverage by build.py)
  data/evidence/youtube/<id>.json     trimmed metadata snapshot per video (evidence_ref)

Usage:  python -I pipeline/collectors/youtube_public.py [--start 2025-11-01] [--end 2026-10-31] [--no-search]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import COMPANIES, EVIDENCE, RAW, ROOT, clean_text, load_json, log, make_record, now_utc, write_jsonl  # noqa: E402

CHANNELS = {  # verified official HK (& Macau) channels - see Prudential/Pending_Data_Links.md section A1
    "Prudential": "UC0FcaFJVwvfwIRgPJjFJaKQ",
    "AIA": "UC5hdg0RQiTsLvYNPlsCZ0kg",
    "Manulife": "UCqJZ7uH55xMJZxssgA-uUOg",
    "AXA": "UCLgUnRTPsfhvMd1-PWTlepA",
}
TABS = ("videos", "shorts", "streams")
SEARCH_TERMS = ("interview", "podcast", "campaign 2026")
SEARCH_DEPTH = 40
# Third-party channels accepted for search hits: Hong Kong media, HK ad archives and regional business/insurance media.
# Fan/vlog channels, other-market brand channels and group/global channels are not accepted (not HK-business evidence).
MEDIA_CHANNELS = {
    "UC4SUWizzKc1tptprBkWjX2Q": "South China Morning Post", "UC2_cdoK4AVOB9kb2ZO4f-XQ": "SCMP Archive",
    "UCIALMKvObZNtJ6AmdCLP7Lg": "Bloomberg Television", "UCUMZ7gohGI9HcU9VNsr2FJQ": "Bloomberg Originals",
    "UCF8HUTbUwPKh2Q-KpGOCVGw": "CNBC International", "UC83jt4dlz1Gjl58fzQrrKZg": "CNA",
    "UC_Lnb8ZHqqgLbp-7hltuT9w": "CNA Insider", "UC-Pq5M-yE8caR28E-VLK5JA": "CGTN BIZ",
    "UCmlSahGWbJTR4PlsMdIT16Q": "Marketing Interactive", "UCM69PTbVF0owexw-RY7E_jA": "Insurance Asia Awards",
    "UCoxZ0g7WomFdjbW8TFiuZkw": "Asia and Middle East Insurance Review", "UCBDGANnytQYn4kXtZQbOI-A": "TPB HK CM (HK TV ad archive)",
    "UC5l18oylJ8o7ihugk4F-3nw": "Pulse HK News", "UCLvd1wGYaWUQpdSL3sxR5ww": "HKTDC", "UCnr0bZa37egykvChQVn-_og": "Invest Hong Kong",
}
BRAND_RX = {"Prudential": re.compile(r"prudential|保誠|保诚|\bPRU", re.I), "AIA": re.compile(r"\bAIA\b|友邦"),
            "Manulife": re.compile(r"manulife|宏利", re.I), "AXA": re.compile(r"\bAXA\b|安盛", re.I)}
HK_RX = re.compile(r"hong ?kong|\bHK\b|香港|港澳|澳門|macau|大灣區|greater bay", re.I)
OTHER_MKT = re.compile(r"malaysia|singapore|thailand|indonesia|philippines|vietnam|sri lanka|india|taiwan|tata aia|prudential financial|AIA Investment Management|Private Limited", re.I)

YDL_OPTS = {"skip_download": True, "quiet": True, "no_warnings": True, "sleep_interval_requests": 1.0,
            "extractor_args": {"youtube": {"skip": ["translated_subs"]}}, "noplaylist": True}
PAUSE_S = 1.5
COVERAGE: list[dict] = []


def _cov(brand, status, n=0, note=""):
    COVERAGE.append({"brand": brand, "platform": "youtube", "source": "YouTube", "status": status, "records": n, "note": note,
                     "checked_at": now_utc()})


def _ydl(flat: bool):
    import yt_dlp
    o = dict(YDL_OPTS)
    if flat:
        o["extract_flat"] = "in_playlist"
    return yt_dlp.YoutubeDL(o)


def _date(info) -> dt.date | None:
    if info.get("upload_date"):
        return dt.datetime.strptime(info["upload_date"], "%Y%m%d").date()
    ts = info.get("timestamp") or info.get("release_timestamp")
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date() if ts else None


def _snapshot(info) -> str:
    keep = ("id", "title", "description", "upload_date", "timestamp", "release_timestamp", "duration", "duration_string",
            "view_count", "like_count", "comment_count", "channel", "channel_id", "channel_follower_count", "uploader_id",
            "webpage_url", "categories", "tags", "language", "live_status", "media_type", "was_live")
    p = EVIDENCE / "youtube" / f"{info['id']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({**{k: info.get(k) for k in keep}, "captured_at": now_utc()}, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p.relative_to(ROOT)).replace("\\", "/")


def _video(ydl, vid: str):
    try:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    except Exception as e:  # private / members-only / removed
        log(f"  yt {vid}: {str(e)[:120]}")
        return None
    finally:
        time.sleep(PAUSE_S)
    return ydl.sanitize_info(info)


def _num(v):
    return int(v) if isinstance(v, (int, float)) else None


def _record(brand, info, fmt, followers, basis, source_name, via):
    cap = now_utc()
    desc = clean_text(info.get("description"))
    url = f"https://www.youtube.com/shorts/{info['id']}" if fmt == "short" else f"https://www.youtube.com/watch?v={info['id']}"
    return make_record(
        brand=brand, record_type="social_post", modules=["M2"], title=clean_text(info.get("title")),
        description=desc[:1000] or None, original_content=desc or None, publication_date=_date(info).isoformat(), capture_ts=cap,
        source_name=source_name, source_category="social", source_url=url, evidence_ref=_snapshot(info),
        hk_relevance="explicit", hk_relevance_basis=basis, platform="youtube", content_format=fmt,
        metrics={"views": _num(info.get("view_count")), "likes": _num(info.get("like_count")),
                 "comments": _num(info.get("comment_count")), "shares": None, "followers": followers},
        extra={"video_id": info["id"], "channel": info.get("channel"), "channel_id": info.get("channel_id"),
               "duration_s": _num(info.get("duration")), "duration": info.get("duration_string"),
               "upload_timestamp": info.get("timestamp"), "live_status": info.get("live_status"), "collected_via": via,
               "metric_note": "views/likes = platform-reported public counts at capture (likes hidden -> null); views include paid ad plays; comment count not exposed in public watch-page metadata (null); shares not exposed"},
    )


def channel_videos(start, end, seen: set) -> tuple[list[dict], list[dict]]:
    out, chans = [], []
    for brand, cid in CHANNELS.items():
        followers, title, n = None, None, 0
        with _ydl(flat=True) as flat, _ydl(flat=False) as full:
            for tab in TABS:
                try:
                    lst = flat.extract_info(f"https://www.youtube.com/channel/{cid}/{tab}", download=False)
                except Exception as e:
                    if "does not have" not in str(e):
                        log(f"  yt {brand}/{tab}: {str(e)[:120]}")
                    continue
                followers = followers or _num(lst.get("channel_follower_count"))
                title = title or re.sub(r"\s+-\s+\w+$", "", lst.get("title") or "")
                old_run = 0
                for e in lst.get("entries") or []:
                    vid = e.get("id")
                    if not vid or vid in seen:
                        continue
                    info = _video(full, vid)
                    if not info or not _date(info):
                        continue
                    d = _date(info)
                    if d < start:
                        old_run += 1
                        if old_run >= 3:  # tabs are newest-first; three in a row before the window -> done
                            break
                        continue
                    old_run = 0
                    if d > end:
                        continue
                    seen.add(vid)
                    fmt = "short" if tab == "shorts" else "live" if tab == "streams" else "video"
                    out.append(_record(brand, info, fmt, followers, "Official HK (& Macau) YouTube channel",
                                       "YouTube (official channel)", f"channel:{tab}"))
                    n += 1
                log(f"yt {brand}/{tab}: {n} in window so far")
        chans.append({"brand": brand, "platform": "youtube", "channel_id": cid, "channel_title": title,
                      "url": f"https://www.youtube.com/channel/{cid}", "followers": followers,
                      "followers_definition": "subscriber count shown publicly at capture (rounded by YouTube)", "captured_at": now_utc(),
                      "videos_in_window": n})
        _cov(brand, "collected" if n else "none in window", n,
             f"Official channel {cid} via yt-dlp public metadata (no API key); views/likes/comments at capture; subscribers {followers}")
    return out, chans


def search_videos(start, end, seen: set) -> list[dict]:
    out = []
    with _ydl(flat=True) as flat, _ydl(flat=False) as full:
        for brand in CHANNELS:
            n = 0
            for term in SEARCH_TERMS:
                q = f"{brand} Hong Kong {term}"
                try:
                    res = flat.extract_info(f"ytsearch{SEARCH_DEPTH}:{q}", download=False)
                except Exception as e:
                    log(f"  yt search {q}: {str(e)[:120]}")
                    continue
                time.sleep(PAUSE_S)
                for e in res.get("entries") or []:
                    vid, ch, t = e.get("id"), e.get("channel_id"), e.get("title") or ""
                    if not vid or vid in seen or ch not in MEDIA_CHANNELS:
                        continue  # official-channel hits are already covered by channel_videos(); others not HK media
                    if not BRAND_RX[brand].search(t) or OTHER_MKT.search(t):
                        continue
                    info = _video(full, vid)
                    if not info or not _date(info) or not (start <= _date(info) <= end):
                        continue
                    text = (info.get("title") or "") + " " + (info.get("description") or "")[:1500]
                    if not (BRAND_RX[brand].search(text) and HK_RX.search(text)):
                        continue
                    seen.add(vid)
                    rec = _record(brand, info, "video", None, f"HK/regional media channel ({MEDIA_CHANNELS[ch]}); brand and Hong Kong named in title/description",
                                  f"YouTube ({MEDIA_CHANNELS[ch]})", f"search:{q}")
                    rec["source_category"] = "social"
                    rec["extra"]["search_query"] = q
                    out.append(rec)
                    n += 1
            log(f"yt search {brand}: {n} third-party HK-media videos in window")
    return out


def collect(start: dt.date, end: dt.date, search: bool = True) -> list[dict]:
    COVERAGE.clear()
    seen: set = set()
    recs, chans = channel_videos(start, end, seen)
    if search:
        s = search_videos(start, end, seen)
        recs += s
        for b in CHANNELS:
            k = sum(1 for r in s if r["brand"] == b)
            COVERAGE.append({"brand": b, "platform": "youtube_search", "source": "YouTube search (HK media)", "status": "collected" if k else "none in window",
                             "records": k, "note": "12 searches (interview/podcast/campaign 2026 per brand); kept only HK/regional media channels naming brand + HK",
                             "checked_at": now_utc()})
    (RAW / "youtube_channels.json").write_text(json.dumps(chans, ensure_ascii=False, indent=1), encoding="utf-8")
    (RAW / "youtube_coverage.json").write_text(json.dumps(COVERAGE, ensure_ascii=False, indent=1), encoding="utf-8")
    return recs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_json("client_prudential.json")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    ap.add_argument("--no-search", action="store_true")
    a = ap.parse_args()
    recs = collect(dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end), search=not a.no_search)
    write_jsonl("youtube", recs)
    log(f"youtube: {len(recs)} records -> {RAW / 'youtube.jsonl'}")
