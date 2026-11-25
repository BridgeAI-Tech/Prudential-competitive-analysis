"""Check EVERY link in the built report page (text, tables, charts, evidence records, posts, ads, filings).

Usage: python -I report_app/prudential/check_all_links.py
Sites that refuse automated checks (social platforms, some publishers) are reported separately, not as broken.
Writes Prudential/_report_work/link_check_all.tsv.
"""
import concurrent.futures as cf
import html
import re
import sys
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
page = (ROOT / "Prudential" / "Prudential_HK_Competitive_Intelligence_Report.html").read_text(encoding="utf-8")
page = html.unescape(page.replace("\\/", "/"))
urls = sorted({u.rstrip(".,;)") for u in re.findall(r'https://[^"\'`\s<>\\]+', page)} - {""})
urls = [u for u in urls if not re.search(r"\$\{|cdnjs|fonts\.(googleapis|gstatic)|w3\.org|schema\.org", u) and len(u) > 12
        and not u.endswith(("*", "-", "…")) and "bit.ly" not in u]      # cut-off text inside post captions, not links
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en-GB,en;q=0.9"}
BLOCKS_BOTS = ("linkedin.com", "facebook.com", "instagram.com", "ia.org.hk", "youtube.com", "youtu.be", "manulife.com", "scmp.com",
               "thestandard.com.hk", "threads.com", "xiaohongshu.com", "hkej.com", "hk01.com", "bloomberg.com", "reuters.com", "ft.com", "wsj.com")


def check(u):
    for method in ("head", "get"):
        try:
            r = getattr(requests, method)(u, headers=UA, timeout=30, allow_redirects=True, stream=(method == "get"))
            code = r.status_code
            r.close()
            if code < 400 or method == "get":
                return u, code
        except Exception as e:  # noqa: BLE001
            if method == "get":
                return u, type(e).__name__
    return u, "?"


res = []
with cf.ThreadPoolExecutor(16) as ex:
    for u, code in ex.map(check, urls):
        blocked = any(b in u for b in BLOCKS_BOTS)
        refused = code in (401, 403, 405, 429, 503)          # the server answered but refuses automated clients or rate-limits
        status = ("ok" if isinstance(code, int) and 200 <= code < 400 else
                  "blocks automated checks" if blocked or refused else "BROKEN")
        res.append((u, code, status))
out = ROOT / "Prudential" / "_report_work" / "link_check_all.tsv"
out.write_text("\n".join(f"{s}\t{c}\t{u}" for u, c, s in res), encoding="utf-8")
dead_f = ROOT / "Prudential" / "_report_work" / "dead_links.txt"          # cumulative: the report build leaves these records out
dead = set(dead_f.read_text(encoding="utf-8").split()) if dead_f.exists() else set()
dead |= {u for u, c, st in res if st == "BROKEN" and c in (404, 410, "ConnectionError")}
dead_f.write_text("\n".join(sorted(dead)), encoding="utf-8")
cnt = Counter(s for _, _, s in res)
print(f"{len(res)} distinct links: {dict(cnt)}")
for u, c, s in res:
    if s == "BROKEN":
        print(f"BROKEN\t{c}\t{u}")
sys.exit(1 if cnt.get("BROKEN") else 0)
