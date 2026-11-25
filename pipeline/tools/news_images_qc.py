"""Quality check of the news lead images (20 Nov 2026): marks pictures that are not photos (text cards, logos, blank
banners) so the dashboard leaves them out. Writes "ok": true/false into media/news_images.json.
Rule: a photo has colour and tonal variety; a text card or logo is mostly one flat background colour.
Usage: python -I Prudential/ci-monitor/tools/news_images_qc.py"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageStat

sys.stdout.reconfigure(encoding="utf-8")
M = Path(__file__).resolve().parents[3] / "report_app" / "prudential" / "media"
idx = json.loads((M / "news_images.json").read_text(encoding="utf-8"))
bad = 0
for k, v in idx.items():
    if not v:
        continue
    im = Image.open(M / v["file"]).convert("RGB").resize((80, 45))
    px = list(im.getdata())
    q = {}
    for p in px:                                   # share of the single most common (quantised) colour
        c = (p[0] // 24, p[1] // 24, p[2] // 24)
        q[c] = q.get(c, 0) + 1
    flat = max(q.values()) / len(px)
    sd = sum(ImageStat.Stat(im.convert("L")).stddev)
    host = v["url"].split("/")[2] if "//" in v["url"] else ""
    ok = flat < 0.45 and sd > 28 and "xhcins.com" not in host
    v["ok"] = ok
    bad += not ok
(M / "news_images.json").write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
print("checked", sum(1 for v in idx.values() if v), "left out", bad)
