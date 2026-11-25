"""Lead images for the news and newsroom records (20 Nov 2026).

For every in-window evidence record from news media or an official newsroom, reads the article page's own preview image
(og:image / twitter:image / first large <img>), downloads it and saves a 400x225 JPEG thumbnail in
report_app/prudential/media/news/<record id>.jpg, listed in media/news_images.json ({id: {file, url, img}}).
Polite: 6 workers, 20 s timeout, public pages only; if the live page is gone, the Internet Archive copy is tried.
Re-runs skip records already done.  Usage: python -I Prudential/ci-monitor/tools/news_images.py
"""
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
HTML = ROOT / "vercel_prudential_report" / "private" / "report.html"
OUT = ROOT / "report_app" / "prudential" / "media" / "news"
IDX = OUT.parent / "news_images.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
OUT.mkdir(parents=True, exist_ok=True)


def get(url, n=3_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9,zh-HK;q=0.8"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.geturl(), r.headers.get("Content-Type", ""), r.read(n)


def find_img(page_url, html):
    for pat in (r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["\'][^>]*content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']',
                r'<link[^>]+rel=["\']image_src["\'][^>]*href=["\']([^"\']+)'):
        m = re.search(pat, html, re.I)
        if m:
            return urllib.parse.urljoin(page_url, unescape(m.group(1).strip()))
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+\.(?:jpe?g|png|webp)[^"\']*)["\']', html, re.I):
        s = m.group(1)
        if not re.search(r"logo|icon|sprite|avatar|banner-ad|pixel|1x1", s, re.I):
            return urllib.parse.urljoin(page_url, unescape(s))
    return None


def thumb(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width < 200 or im.height < 110:
        raise ValueError("image too small")
    tw, th = 400, 225
    r = max(tw / im.width, th / im.height)
    im = im.resize((max(tw, round(im.width * r)), max(th, round(im.height * r))))
    left, top = (im.width - tw) // 2, max(0, (im.height - th) // 3)
    buf = io.BytesIO()
    im.crop((left, top, left + tw, top + th)).save(buf, "JPEG", quality=72, optimize=True)
    return buf.getvalue()


def one(r):
    rid, url = r[0], r[10]
    for page in (url, f"https://web.archive.org/web/2026/{url}"):
        try:
            final, ct, body = get(page)
            if "html" not in ct.lower():
                continue
            img = find_img(final, body.decode("utf-8", "replace"))
            if not img:
                continue
            _, ict, data = get(img, 8_000_000)
            (OUT / f"{rid}.jpg").write_bytes(thumb(data))
            return rid, {"file": f"news/{rid}.jpg", "url": url, "img": img}
        except Exception:
            continue
    return rid, None


if __name__ == "__main__":
    h = HTML.read_text(encoding="utf-8")
    E = json.loads(re.search(r"const EVID = (\[.*?\]);\n", h, re.S).group(1))
    rows = [r for r in E if r[8] in ("Media", "Official site") and 20251101 <= r[1] <= 20261031 and str(r[10]).startswith("http")
            and not re.search(r"\.pdf($|\?)", r[10], re.I)]
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    todo = [r for r in rows if r[0] not in idx]
    print("records:", len(rows), "to do:", len(todo), flush=True)
    done = 0
    with ThreadPoolExecutor(6) as ex:
        for rid, v in ex.map(one, todo):
            done += 1
            idx[rid] = v
            if done % 50 == 0:
                IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
                print(done, "/", len(todo), "images:", sum(1 for x in idx.values() if x), flush=True)
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=0), encoding="utf-8")
    print("done; with image:", sum(1 for x in idx.values() if x), "of", len(idx))
