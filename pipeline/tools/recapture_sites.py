"""Recapture the insurer website screenshots in the gallery without cookie banners (20 Nov 2026).
Rewrites report_app/prudential/media/site_<brand>_<home|health>.jpg (800x500) for the given brands; no clicks, banners and
other fixed overlays at the bottom of the screen are hidden with CSS before the screenshot.
Usage: python -I Prudential/ci-monitor/tools/recapture_sites.py prudential aia axa"""
import io
import json
import sys
import time
from pathlib import Path

M = Path(__file__).resolve().parents[3] / "report_app" / "prudential" / "media"
HIDE = """[...document.querySelectorAll('body *')].filter(e => { const s = getComputedStyle(e);
  return ((s.position === 'fixed' || s.position === 'sticky') && e.getBoundingClientRect().top > innerHeight * 0.55)
    || /cookie|onetrust|consent|gdpr/i.test((e.id || '') + ' ' + (typeof e.className === 'string' ? e.className : '')); })
  .forEach(e => e.style.setProperty('display', 'none', 'important'));"""

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    from PIL import Image
    want = set(a.lower() for a in sys.argv[1:])
    media = json.loads((M / "media.json").read_text(encoding="utf-8"))
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB",
                             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
        for x in media:
            if x.get("platform") != "Website" or x["brand"].lower() not in want:
                continue
            p = ctx.new_page()
            try:
                p.goto(x["url"], wait_until="domcontentloaded", timeout=45000)
                p.wait_for_timeout(5000)
                p.evaluate(HIDE)
                p.wait_for_timeout(500)
                im = Image.open(io.BytesIO(p.screenshot(type="png"))).convert("RGB").resize((800, 500))
                im.save(M / x["file"], "JPEG", quality=82, optimize=True)
                x["captured"] = time.strftime("%d %b %Y")
                print("ok  ", x["file"], flush=True)
            except Exception as e:
                print("skip", x["file"], str(e)[:80], flush=True)
            finally:
                p.close()
        br.close()
    (M / "media.json").write_text(json.dumps(media, ensure_ascii=False, indent=1), encoding="utf-8")
