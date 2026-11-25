"""Live browser captures of the pages behind the evidence (InkTank-style "live browser captures" wall, 20 Nov 2026).

Picks, for each insurer, the most recent in-window evidence records per channel (official newsroom / site, Hong Kong media,
app store, HKEX filing pages are skipped as PDFs) and screenshots each public page in headless Chromium (1280x800, top
of the page), saved as 640 px JPEG in report_app/prudential/media/cap_*.jpg and listed in media/captures.json with the
evidence id, so a card can open its evidence record. Polite: one page at a time, robots-respecting public pages only,
no login, no clicking except a cookie banner "accept/close".
Usage: python -I Prudential/ci-monitor/tools/capture_sources.py [per_brand_per_channel=4]
"""
import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
HTML = ROOT / "vercel_prudential_report" / "private" / "report.html"
MEDIA = ROOT / "report_app" / "prudential" / "media"
PER = int(sys.argv[1]) if len(sys.argv) > 1 else 4
CHANNELS = {"Official site": "Websites", "Media": "News", "App store": "App stores"}


def evid():
    h = HTML.read_text(encoding="utf-8")
    return json.loads(re.search(r"const EVID = (\[.*?\]);\n", h, re.S).group(1))


def pick(rows):
    out = []
    for b in ("Prudential", "AIA", "Manulife", "AXA"):
        for plat, ch in CHANNELS.items():
            rs = [r for r in rows if r[2] == b and r[8] == plat and 20251101 <= r[1] <= 20261031 and str(r[10]).startswith("http")
                  and not re.search(r"\.pdf($|\?)|web\.archive\.org|hkexnews", str(r[10]), re.I)]
            rs.sort(key=lambda r: r[1], reverse=True)
            seen = set()
            for r in rs:
                host = re.sub(r"^https?://(www\.)?", "", r[10]).split("/")[0]
                key = (host, r[9][:40])
                if key in seen:
                    continue
                seen.add(key)
                out.append({"id": r[0], "date": r[1], "brand": b, "plat": plat, "channel": ch, "title": r[9], "url": r[10], "source": r[11]})
                if len([x for x in out if x["brand"] == b and x["plat"] == plat]) >= PER:
                    break
    return out


def shoot(items):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    done = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 800}, locale="en-GB",
                             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")
        for n, it in enumerate(items, 1):
            pg = ctx.new_page()
            try:
                pg.goto(it["url"], wait_until="domcontentloaded", timeout=40000)
                pg.wait_for_timeout(3500)
                for sel in ("#onetrust-accept-btn-handler", "button:has-text('Accept')", "button:has-text('Agree')", "button:has-text('I agree')",
                            "button:has-text('同意')", "button:has-text('Close')", "[aria-label='Close']"):
                    try:
                        loc = pg.locator(sel).first
                        if loc.is_visible(timeout=400):
                            loc.click(timeout=1200)
                            pg.wait_for_timeout(600)
                            break
                    except Exception:
                        pass
                title = pg.title() or ""
                if re.search(r"(?i)access denied|forbidden|just a moment|attention required|404|not found|captcha", title):
                    raise RuntimeError("blocked or missing page: " + title[:60])
                # a login wall or a human check shows nothing of the source: skip it (Facebook/LinkedIn redirects, bot checks)
                final = pg.url
                body = (pg.inner_text("body") or "")[:3000]
                if re.search(r"(?i)facebook\.com/login|linkedin\.com/(login|authwall|checkpoint)|accounts\.google", final) or \
                   re.search(r"(?i)confirm you are human|verify you are human|are you a robot|create new account|sign in to continue|log in to continue|unusual traffic", body) or \
                   (re.search(r"(?i)facebook\.com|linkedin\.com|instagram\.com", final) and len(body) < 1500):
                    raise RuntimeError("login wall or human check: " + final[:60])
                it["final_url"] = final
                png = pg.screenshot(type="png")
                im = Image.open(io.BytesIO(png)).convert("RGB").resize((640, 400))
                f = f"cap_{it['brand'].lower()}_{re.sub(r'[^a-z]', '', it['channel'].lower())}_{it['id'][:10]}.jpg"
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=78, optimize=True)
                (MEDIA / f).write_bytes(buf.getvalue())
                done.append({**it, "file": f, "kb": round(len(buf.getvalue()) / 1024, 1), "captured": time.strftime("%d %b %Y")})
                print(f"{n}/{len(items)} ok  {it['brand']:10} {it['channel']:10} {it['url'][:70]}", flush=True)
            except Exception as e:
                print(f"{n}/{len(items)} skip {it['brand']:10} {it['channel']:10} {str(e)[:70]}", flush=True)
            finally:
                pg.close()
            time.sleep(1)
        br.close()
    return done


if __name__ == "__main__":
    items = pick(evid())
    print("candidates:", len(items), flush=True)
    caps = shoot(items)
    (MEDIA / "captures.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("saved", len(caps), dict(Counter((c["brand"], c["channel"]) for c in caps)))
