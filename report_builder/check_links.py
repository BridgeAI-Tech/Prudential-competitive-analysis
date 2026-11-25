"""Check every external link in the Prudential report sources (body.html + data.js). Usage: python -I report_app/prudential/check_links.py"""
import concurrent.futures as cf
import re
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
text = (HERE / "body.html").read_text(encoding="utf-8") + (HERE / "data.js").read_text(encoding="utf-8")
# Resolve the string-prefix constants used in data.js (P + "...", A + "..." etc.).
consts = dict(re.findall(r'const (\w+) = "(https://[^"]+)";', text))
urls = set(re.findall(r'https://[^"\'`\s)<>]+', text)) - set(consts.values())
for name, base in consts.items():
    for tail in re.findall(rf'\b{name} \+ "([^"]+)"', text):
        urls.add(base + tail)
urls = sorted(u for u in urls if not u.endswith(("/", "-")) or "/newsroom/" in u or u.count("/") > 3)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "en-GB,en;q=0.9"}
BLOCKS_BOTS = ("linkedin.com", "facebook.com", "ia.org.hk", "youtube.com", "manulife.com", "scmp.com", "thestandard.com.hk")


def check(u):
    try:
        r = requests.get(u, headers=UA, timeout=25, allow_redirects=True)
        return u, r.status_code, r.url
    except Exception as e:  # noqa: BLE001
        return u, type(e).__name__, ""


bad = []
with cf.ThreadPoolExecutor(12) as ex:
    for u, code, final in ex.map(check, urls):
        ok = code == 200
        note = "" if ok else (" (site blocks automated checks)" if any(b in u for b in BLOCKS_BOTS) else "")
        print(f"{code}\t{u}{' -> ' + final if final and final.rstrip('/') != u.rstrip('/') else ''}{note}")
        if not ok and not note:
            bad.append(u)
print(f"\n{len(urls)} links checked, {len(bad)} failing (excluding sites that block automated checks)")
sys.exit(1 if bad else 0)
