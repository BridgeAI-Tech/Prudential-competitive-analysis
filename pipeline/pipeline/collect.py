"""Stage 1+2: source collection and extraction. Writes data/raw/<collector>.jsonl.

Usage:  python pipeline/collect.py [--only newsrooms,apps] [--start 2025-11-01] [--end 2026-10-31]
Default period = client config period_start/period_end (static 12-month window per brief v1).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "collectors"))

from common import RAW, load_json, log, write_jsonl  # noqa: E402
import apps, digital_features, excel_imports, google_news, newsrooms, seed_extracts, social  # noqa: E402
import ads_transparency, context_stats, manulife_archive, media_feeds, official_pages, youtube_public  # noqa: E402

COLLECTORS = {
    "newsrooms": newsrooms.collect,
    "excel_imports": excel_imports.collect,
    "google_news": google_news.collect,
    "seed_extracts": seed_extracts.collect,
    "social": social.collect,
    "apps": apps.collect,
    "digital_features": digital_features.collect,
    # added 11 Nov 2026 (each also runs standalone: python -I pipeline/collectors/<name>.py)
    "manulife_archive": manulife_archive.collect,   # Internet Archive copies of the 403-blocked Manulife newsroom
    "official_pages": official_pages.collect,       # official-platform directories, Emma page, Chinese newsrooms
    "media_feeds": media_feeds.collect,             # InsuranceAsia News/insuranceasia.com, SCMP/RTHK RSS, extra Google News
    "youtube": youtube_public.collect,              # yt-dlp public metadata, 4 official channels + HK-media search
    "ad_library": ads_transparency.collect,         # Google Ads Transparency Center (HK), Playwright
    "context_stats": context_stats.collect,         # HKFI / MPFA / Google Trends context (not observations)
}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    cfg = load_json("client_prudential.json")
    ap.add_argument("--start", default=cfg["period_start"])
    ap.add_argument("--end", default=cfg["period_end"])
    a = ap.parse_args()
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    log(f"window {start} .. {end}")
    run = [k for k in COLLECTORS if not a.only or k in a.only.split(",")]
    status = {}
    for k in run:
        try:
            recs = COLLECTORS[k](start, end)
            write_jsonl(k, recs)
            status[k] = {"records": len(recs), "ok": True}
        except Exception as e:  # one collector failing must not stop the run
            log(f"{k} FAILED: {e}")
            status[k] = {"records": 0, "ok": False, "error": str(e)[:300]}
    prev = RAW / "_run_status.json"
    allstat = json.loads(prev.read_text()) if prev.exists() else {}
    allstat.update({k: {**v, "window": [str(start), str(end)], "run_at": dt.datetime.now().isoformat(timespec="seconds")} for k, v in status.items()})
    prev.write_text(json.dumps(allstat, indent=1))
    log(json.dumps(status))
