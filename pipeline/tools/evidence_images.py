"""Pictures for the Evidence library rows (20 Nov 2026).

For every in-window evidence record whose picture we can get without new scraping:
  - Google ads: the stored creative image (ad_library.image_url, tpc.googlesyndication archive)
  - YouTube: the video thumbnail (i.ytimg.com)
  - LinkedIn: the post's first image from the 11 Nov dataset, while the link still works
  - App reviews: one screenshot of the app's store page, shared by all its reviews
Saves 400x225 JPEGs in report_app/prudential/media/evimg/<id>.jpg and media/evimg.json {record id: file}.
Re-runs skip records already done.  Usage: python -I Prudential/ci-monitor/tools/evidence_images.py
"""
import io
import json
import re
import sqlite3
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
PRU = ROOT / "Prudential"
HTML = ROOT / "vercel_prudential_report" / "private" / "report.html"
OUT = ROOT / "report_app" / "prudential" / "media" / "evimg"
IDX = OUT.parent / "evimg.json"
OUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def fname(rid):
    return "ev_" + re.sub(r"[^a-z0-9-]", "_", rid.lower()) + ".jpg"


def thumb(data, contain=False):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width < 60 or im.height < 40:
        raise ValueError("too small")
    tw, th = 400, 225
    if contain:                                   # ad creatives: show the whole ad on white
        im.thumbnail((tw, th))
        c = Image.new("RGB", (tw, th), "white"); c.paste(im, ((tw - im.width) // 2, (th - im.height) // 2)); im = c
    else:
        r = max(tw / im.width, th / im.height)
        im = im.resize((max(tw, round(im.width * r)), max(th, round(im.height * r))))
        l, t = (im.width - tw) // 2, (im.height - th) // 2
        im = im.crop((l, t, l + tw, t + th))
    b = io.BytesIO(); im.save(b, "JPEG", quality=74, optimize=True); return b.getvalue()


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25) as r:
        return r.read(6_000_000)


def job(item):
    rid, src, contain = item
    try:
        (OUT / fname(rid)).write_bytes(thumb(get(src), contain))
        return rid, fname(rid)
    except Exception:
        return rid, None


def app_shots(apps):
    """One screenshot per app store page (headless Chromium, top of the page)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB", user_agent=UA)
        for base in apps:
            p = ctx.new_page()
            try:
                p.goto(base, wait_until="domcontentloaded", timeout=45000); p.wait_for_timeout(4000)
                f = "ev_app_" + re.sub(r"[^a-z0-9]", "_", base.lower())[-40:] + ".jpg"
                (OUT / f).write_bytes(thumb(p.screenshot(type="png")))
                out[base] = f; print("app ok", base[:80], flush=True)
            except Exception as e:
                print("app skip", base[:80], str(e)[:60], flush=True)
            finally:
                p.close()
        br.close()
    return out


if __name__ == "__main__":
    E = json.loads(re.search(r"const EVID = (\[.*?\]);\n", HTML.read_text(encoding="utf-8"), re.S).group(1))
    W = [r for r in E if 20251101 <= r[1] <= 20261031 and str(r[10]).startswith("http")]
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    todo = []
    # Google ads: creative image by Ads Transparency URL
    db = sqlite3.connect(PRU / "ci-monitor" / "data" / "ci.db")
    ad_img = {u: (i or "") for u, i in db.execute("select url, image_url from ad_library")}
    for r in W:
        if r[0] in idx:
            continue
        u = r[10]
        if r[8] == "Google ads" and ad_img.get(u, "").startswith("http"):
            todo.append((r[0], ad_img[u], True))
        elif r[8] == "YouTube":
            m = re.search(r"[?&]v=([\w-]{6,})|youtu\.be/([\w-]{6,})|/shorts/([\w-]{6,})", u)
            if m:
                todo.append((r[0], f"https://i.ytimg.com/vi/{next(g for g in m.groups() if g)}/hqdefault.jpg", False))
    # LinkedIn: first post image (or article image) from the 11 Nov dataset
    try:
        import openpyxl
        wb = openpyxl.load_workbook(next(PRU.glob("dataset_linkedin-company-posts_*.xlsx")), read_only=True)
        ws = wb.active; rows = ws.iter_rows(values_only=True); hdr = list(next(rows))
        col = {h: i for i, h in enumerate(hdr) if h}
        urlc = next((col[h] for h in ("url", "postUrl", "post_url", "linkedinUrl") if h in col), None)
        li_img = {}
        for row in rows:
            u = row[urlc] if urlc is not None else None
            img = next((row[col[h]] for h in ("postImages/0/url", "article/image/url", "document/coverPages/0/imageUrls/0") if h in col and row[col[h]]), None)
            if u and img:
                li_img[str(u).split("?")[0]] = img
        for r in W:
            if r[8] == "LinkedIn" and r[0] not in idx and r[10].split("?")[0] in li_img:
                todo.append((r[0], li_img[r[10].split("?")[0]], False))
    except Exception as e:
        print("linkedin dataset:", str(e)[:80])
    print("to fetch:", len(todo), dict(__import__("collections").Counter(t[0].split("-")[0] for t in todo)), flush=True)
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for rid, f in ex.map(job, todo):
            idx[rid] = f; n += 1
            if n % 200 == 0:
                IDX.write_text(json.dumps(idx), encoding="utf-8"); print(n, "/", len(todo), "ok:", sum(1 for v in idx.values() if v), flush=True)
    # app reviews: one store-page screenshot per app
    apps = sorted({r[10].split("&")[0] if "play.google" in r[10] else r[10].split("?")[0] for r in W if r[8] == "App store"})
    shots = app_shots([a for a in apps])
    for r in W:
        if r[8] == "App store":
            base = r[10].split("&")[0] if "play.google" in r[10] else r[10].split("?")[0]
            if shots.get(base):
                idx[r[0]] = shots[base]
    IDX.write_text(json.dumps(idx), encoding="utf-8")
    import collections
    print("done; with picture:", sum(1 for v in idx.values() if v), "of", len(idx),
          dict(collections.Counter(k.split("-")[0] for k, v in idx.items() if v)))
