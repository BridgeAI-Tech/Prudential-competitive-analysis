"""Pictures for findings that cite only PDF documents (results reports, filings), 20 Nov 2026.

Reads every link in INSIGHTS from the built report (exact href and link text, e.g. "HY report, p.25"), and for each PDF
link renders the cited page (from "#page=N" or "p.N" in the link text; page 1 otherwise) with PyMuPDF, keeping the top
of the page in a 640x400 JPEG at report_app/prudential/media/moves/doc_<hash>.jpg. Entries are added to
media/moves.json under the exact href, so the dashboard shows them like the page screenshots.
Usage: python -I Prudential/ci-monitor/tools/render_doc_pages.py
"""
import hashlib
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "vercel_prudential_report" / "private" / "report.html"
OUT = ROOT / "report_app" / "prudential" / "media" / "moves"
IDX = OUT.parent / "moves.json"
CACHE = ROOT / "Prudential" / "_report_work" / "pdf_cache"
CACHE.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def links():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page()
        pg.goto(REPORT.as_uri(), wait_until="domcontentloaded", timeout=120000)
        out = pg.evaluate("""INSIGHTS.flatMap(x => [...[x.finding, x.compare, x.means, x.act].join(' ')
            .matchAll(/<a [^>]*href="([^"]+)"[^>]*>([^<]*)</g)].map(m => [m[1], m[2]]))""")
        pg.wait_for_timeout(2000)
        out += pg.evaluate("[...document.querySelectorAll('#swS a[href^=http], #swW a[href^=http], #cogrid a[href^=http], #one a[href^=http]')].map(a => [a.getAttribute('href'), a.textContent])")
        br.close()
    return out


def pdf_bytes(url):
    f = CACHE / (hashlib.sha1(url.split("#")[0].encode()).hexdigest()[:16] + ".pdf")
    if not f.exists():
        req = urllib.request.Request(url.split("#")[0], headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=90).read()
        if not data.startswith(b"%PDF"):
            raise RuntimeError("not a PDF")
        f.write_bytes(data)
        time.sleep(1)
    return f.read_bytes()


def render(data, page):
    import pymupdf
    from PIL import Image
    doc = pymupdf.open(stream=data, filetype="pdf")
    p = doc[min(max(page, 1), doc.page_count) - 1]
    pix = p.get_pixmap(dpi=110)
    im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    w = im.width
    h = int(w * 10 / 16)
    if im.height < h:                              # landscape slide: fit whole page
        im = im.resize((640, int(im.height * 640 / w)))
        canvas = Image.new("RGB", (640, 400), "white")
        canvas.paste(im, (0, max(0, (400 - im.height) // 2)))
        return canvas
    return im.crop((0, 0, w, h)).resize((640, 400))


if __name__ == "__main__":
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    done = 0
    for href, text in links():
        if not re.search(r"\.pdf($|[?#])", href, re.I) or idx.get(href):
            continue
        m = re.search(r"#page=(\d+)", href) or re.search(r"\b(?:p|page|slide)\.?\s*(\d+)", text, re.I)
        page = int(m.group(1)) if m else 1
        try:
            img = render(pdf_bytes(href), page)
            f = "doc_" + hashlib.sha1(href.encode()).hexdigest()[:14] + ".jpg"
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80, optimize=True)
            (OUT / f).write_bytes(buf.getvalue())
            idx[href] = {"file": f, "captured": time.strftime("%d %b %Y"), "via": f"pdf page {page}"}
            done += 1
            print("ok  ", page, href[:100], flush=True)
        except Exception as e:
            print("skip", href[:100], str(e)[:60], flush=True)
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rendered", done)
