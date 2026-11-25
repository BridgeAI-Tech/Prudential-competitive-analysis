"""Facebook and Instagram data for the client-validated HK accounts (brief v3 s5.3), via Apify's official actors.

The token is read from the project .env (APIFY_TOKEN) and sent only in the Authorization header; it is never printed or saved.
Output: Prudential/apify_raw/<job>.json (raw dataset items) and a run summary on screen.
Usage: python -I ci-monitor/tools/apify_social.py [job ...]     (jobs: fb_posts fb_pages ig_posts ig_profiles; default all)
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[3]                 # project root (holds .env)
OUT = ROOT / "Prudential" / "apify_raw"
API = "https://api.apify.com/v2"
SINCE, UNTIL = "2025-11-01", "2026-10-31"
FB = {"Prudential": "https://www.facebook.com/prudentialhk", "AIA": "https://www.facebook.com/AIAHongKong/",
      "AXA": "https://www.facebook.com/AXAHongKong", "Manulife": "https://www.facebook.com/manulifehongkong/"}
IG = {"Prudential": "prudential.hongkong", "AXA": "axahongkong", "Manulife": "manulife_hongkong"}   # no AIA Instagram in the client's list
JOBS = {
    "fb_posts": ("apify~facebook-posts-scraper", {"startUrls": [{"url": u} for u in FB.values()], "resultsLimit": 400,
                                                  "onlyPostsNewerThan": SINCE, "onlyPostsOlderThan": "2026-11-01"}),
    "fb_pages": ("apify~facebook-pages-scraper", {"startUrls": [{"url": u} for u in FB.values()]}),
    "ig_posts": ("apify~instagram-post-scraper", {"username": list(IG.values()), "resultsLimit": 400, "onlyPostsNewerThan": SINCE}),
    "ig_profiles": ("apify~instagram-profile-scraper", {"usernames": list(IG.values())}),
    # From the source list for Sahaj (11 Nov 2026): AIA's Instagram (listed on AIA's own official-platforms page, not in the client-validated table)
    "ig_posts_aia": ("apify~instagram-post-scraper", {"username": ["AIAHongKongMacau"], "resultsLimit": 400, "onlyPostsNewerThan": SINCE}),
    "ig_profile_aia": ("apify~instagram-profile-scraper", {"usernames": ["AIAHongKongMacau"]}),
    "threads_aia": ("apify~threads-profile-api-scraper", {"usernames": ["aiahongkongmacau"]}),
    # 17 Nov 2026: Threads posts. Threads accounts share the Instagram username, so the other three brands' handles are checked too.
    "threads_profiles": ("apify~threads-profile-api-scraper", {"usernames": ["aiahongkongmacau", "prudential.hongkong", "axahongkong", "manulife_hongkong"]}),
    "threads_posts": ("futurizerush~threads-user-posts-scraper", {"usernames": ["aiahongkongmacau"], "maxPosts": 400}),
    "threads_posts_pru": ("futurizerush~threads-user-posts-scraper", {"usernames": ["prudential.hongkong"], "maxPosts": 600}),
    # Meta Ad Library, Hong Kong, by Ad Library page id (Prudential, AXA, Manulife, AIA)
    "fb_ads": ("apify~facebook-ads-scraper", {"startUrls": [{"url": f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=HK&media_type=all&view_all_page_id={pid}"}
                                                             for pid in ("191172447574636", "381309905353457", "485081128298580", "233237970068198")],
                                              "resultsLimit": 600, "activeStatus": "", "onlyAdsNewerThan": SINCE, "includeAboutPage": True}),
}


def token():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*APIFY_TOKEN\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    sys.exit("APIFY_TOKEN not found in .env")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    H = {"Authorization": f"Bearer {token()}"}
    me = requests.get(f"{API}/users/me", headers=H, timeout=30)
    if me.status_code != 200:
        sys.exit(f"Apify rejected the token (HTTP {me.status_code})")
    plan = me.json()["data"].get("plan", {})
    print("Apify account plan:", plan.get("id") or "n/a")
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or list(JOBS)
    runs = {}
    for job in wanted:
        actor, inp = JOBS[job]
        r = requests.post(f"{API}/acts/{actor}/runs", headers=H, json=inp, timeout=60)
        if r.status_code not in (200, 201):
            print(f"{job}: could not start ({r.status_code}) {r.text[:200]}"); continue
        runs[job] = r.json()["data"]["id"]
        print(f"{job}: started {actor}")
    pending = dict(runs)
    t0 = time.time()
    while pending and time.time() - t0 < 3000:
        time.sleep(20)
        for job, rid in list(pending.items()):
            d = requests.get(f"{API}/actor-runs/{rid}", headers=H, timeout=30).json()["data"]
            if d["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                items = requests.get(f"{API}/datasets/{d['defaultDatasetId']}/items", headers=H,
                                     params={"clean": "true", "format": "json"}, timeout=120).json()
                (OUT / f"{job}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
                cost = (d.get("usageTotalUsd") or 0)
                print(f"{job}: {d['status']} · {len(items)} items · about US${cost:.2f} · {round(time.time() - t0)}s")
                del pending[job]
    for job in pending:
        print(f"{job}: still running after 50 minutes; re-run later to fetch")


if __name__ == "__main__":
    main()
