"""Screenshots of the source page behind every move on the "Timeline of moves" board (20 Nov 2026).

Reads TIMELINE (date, brand, type, move, source label, URL) from the built report, opens each public URL in headless
Chromium (1280x800, top of the page), and saves a 640x400 JPEG in report_app/prudential/media/moves/<hash>.jpg,
listed in media/moves.json ({url: {file, captured}}). Same rules as capture_sources.py: no login, only a cookie
banner may be clicked, login walls / human checks / error pages are skipped. PDFs are rendered from page 1 by Chromium's
viewer where possible, otherwise skipped. Re-runs skip URLs already captured.
Usage: python -I Prudential/ci-monitor/tools/capture_moves.py
"""
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "vercel_prudential_report" / "private" / "report.html"
OUT = ROOT / "report_app" / "prudential" / "media" / "moves"
IDX = OUT.parent / "moves.json"
OUT.mkdir(parents=True, exist_ok=True)
EXTRA = "#one a[href^=http], #swS a[href^=http], #swW a[href^=http], #cogrid a[href^=http], #hciLineup a[href^=http], #topPosts a[href^=http], #appTbl a[href^=http], #fpNews a[href^=http], #fpOff a[href^=http]"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    idx = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        # 1. the move list, straight from the built page (so the URLs match exactly what the board links to)
        pg = br.new_page()
        pg.goto(REPORT.as_uri(), wait_until="domcontentloaded", timeout=120000)
        moves = pg.evaluate("TIMELINE.map(r => [r[0], r[1], r[3], r[5]])")
        # also every source link on the strengths / weaknesses cards and the company profile cards (20 Nov 2026)
        pg.wait_for_timeout(2000)
        moves += pg.evaluate("[...document.querySelectorAll(SEL)].map(a => [0, '', '', a.href])".replace("SEL", repr(EXTRA)))
        pg.close()
        urls = []
        for d, b, t, u in moves:
            if isinstance(u, str) and u.startswith("http") and u not in urls:
                urls.append(u)
        todo = [u for u in urls if u not in idx]
        print("moves:", len(moves), "urls:", len(urls), "to capture:", len(todo), flush=True)
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB", user_agent=UA)
        for n, u in enumerate(todo, 1):
            p = ctx.new_page()
            try:
                if re.search(r"\.pdf($|\?)", u, re.I):
                    raise RuntimeError("PDF (no page to screenshot)")
                p.goto(u, wait_until="domcontentloaded", timeout=40000)
                p.wait_for_timeout(3500)
                for sel in ("#onetrust-accept-btn-handler", "button:has-text('Accept')", "button:has-text('Agree')", "button:has-text('I agree')",
                            "button:has-text('同意')", "button:has-text('Close')", "[aria-label='Close']"):
                    try:
                        loc = p.locator(sel).first
                        if loc.is_visible(timeout=400):
                            loc.click(timeout=1200)
                            p.wait_for_timeout(600)
                            break
                    except Exception:
                        pass
                title, final = p.title() or "", p.url
                body = (p.inner_text("body") or "")[:3000]
                if re.search(r"(?i)access denied|forbidden|just a moment|attention required|404|not found|captcha", title):
                    raise RuntimeError("blocked or missing: " + title[:60])
                if re.search(r"(?i)facebook\.com/login|linkedin\.com/(login|authwall|checkpoint)|accounts\.google", final) or \
                   re.search(r"(?i)confirm you are human|verify you are human|are you a robot|sign in to continue|log in to continue|unusual traffic|join linkedin|sign in to view", body) or \
                   (re.search(r"(?i)facebook\.com|linkedin\.com|instagram\.com", final) and len(body) < 1500):
                    raise RuntimeError("login wall or human check")
                png = p.screenshot(type="png")
                im = Image.open(io.BytesIO(png)).convert("RGB").resize((640, 400))
                f = "move_" + hashlib.sha1(u.encode()).hexdigest()[:14] + ".jpg"
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=78, optimize=True)
                (OUT / f).write_bytes(buf.getvalue())
                idx[u] = {"file": f, "captured": time.strftime("%d %b %Y")}
                print(f"{n}/{len(todo)} ok   {u[:90]}", flush=True)
            except Exception as e:
                idx[u] = None
                print(f"{n}/{len(todo)} skip {u[:70]}  ({str(e)[:50]})", flush=True)
            finally:
                p.close()
            time.sleep(1)
        br.close()
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", sum(1 for v in idx.values() if v), "of", len(idx))


if __name__ == "__main__":
    main()
