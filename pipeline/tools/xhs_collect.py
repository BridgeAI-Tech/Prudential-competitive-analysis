"""Xiaohongshu (RED) official-account notes for the four HK insurers, collected in a visible Chrome window after the user logs in.

Scope and safeguards (brief v3 s5.3; site terms):
- Only the insurers' official public accounts; no commenter or personal data is stored.
- A separate Chrome profile (Prudential/_xhs_browser_profile, local only, never deployed) holds the user's login.
- Slow pace (3-7 s between notes, max 120 notes per account); hard stop on any verification/CAPTCHA page.
Usage: python -I ci-monitor/tools/xhs_collect.py
Output: Prudential/xhs_notes.json and Prudential/xhs_notes.xlsx
"""
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]            # .../Prudential
PROFILE = ROOT / "_xhs_browser_profile"
OUT = ROOT / "xhs_notes.json"
WIN = ("2025-11-01", "2026-10-31")
TARGETS = [  # brand, Xiaohongshu ID (red id), known profile id
    ("Prudential", "11604322316", None),
    ("AIA", "1925810064", None),
    ("AXA", None, "64609d2c00000000100242d5"),
]
MAX_NOTES = 120
log = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


class Stop(Exception):
    pass


def check_block(page):
    u = page.url.lower()
    if "captcha" in u or "verify" in u or "website-login" in u:
        raise Stop(f"verification page shown ({page.url}); stopping as agreed")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    captured = {"me": None, "users": [], "posted": []}
    results = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   viewport={"width": 1280, "height": 860}, locale="zh-HK")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_response(r):
            u = r.url
            try:
                if "/api/sns/web/v2/user/me" in u:
                    captured["me"] = r.json().get("data")
                elif "/search/usersearch" in u:
                    captured["users"] += (r.json().get("data") or {}).get("users", [])
                elif "/user_posted" in u:
                    captured["posted"].append(r.json().get("data") or {})
            except Exception:  # noqa: BLE001 - non-JSON or aborted responses are ignored
                pass
        page.on("response", on_response)

        page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
        log("A Chrome window is open. Please log in to Xiaohongshu there (QR code or phone). Waiting up to 30 minutes...")
        t0 = time.time()
        while True:
            me = captured["me"]
            if me and me.get("guest") is False and me.get("user_id"):   # guests also get a session cookie, so only the API's guest flag counts
                log("Logged in. Starting collection.")
                break
            if time.time() - t0 > 1800:
                log("No login within 30 minutes; closing without collecting.")
                ctx.close(); return
            page.wait_for_timeout(3000)
            if int(time.time() - t0) % 21 < 3:
                try:
                    page.reload(wait_until="domcontentloaded")  # refresh so the login state is re-read
                except Exception:  # noqa: BLE001
                    pass

        try:
            for brand, red_id, uid in TARGETS:
                if brand in results and results[brand].get("done"):
                    log(f"{brand}: already collected, skipping"); continue
                if not uid:
                    captured["users"].clear()
                    page.goto(f"https://www.xiaohongshu.com/search_result?keyword={red_id}&source=web_search_result_notes&type=51",
                              wait_until="domcontentloaded")
                    page.wait_for_timeout(5000); check_block(page)
                    hit = [u for u in captured["users"] if str(u.get("red_id")) == red_id]
                    if not hit:                                       # open the "users" tab if the search defaulted to notes
                        for label in ("用户", "用戶", "Users"):
                            loc = page.get_by_text(label, exact=True)
                            if loc.count():
                                try:
                                    loc.first.click(timeout=8000)
                                except Exception:  # noqa: BLE001 - a login pop-up covers the page
                                    raise Stop("a login pop-up is covering the page; please log in and re-run")
                                page.wait_for_timeout(4000); break
                        hit = [u for u in captured["users"] if str(u.get("red_id")) == red_id]
                    if not hit:
                        log(f"{brand}: account with ID {red_id} not found in search; skipping"); results[brand] = {"error": "not found"}; continue
                    uid = hit[0].get("id") or hit[0].get("user_id")
                    log(f"{brand}: found account '{hit[0].get('name')}' ({uid})")
                captured["posted"].clear()
                page.goto(f"https://www.xiaohongshu.com/user/profile/{uid}", wait_until="domcontentloaded")
                page.wait_for_timeout(5000); check_block(page)
                nick = page.evaluate("() => { try { return window.__INITIAL_STATE__.user.userPageData._value.basicInfo.nickname } catch(e) { return null } }")
                fans = page.evaluate("() => { try { return JSON.stringify(window.__INITIAL_STATE__.user.userPageData._value.interactions) } catch(e) { return null } }")
                # notes on the first screen come from the page state; later pages from the user_posted API while scrolling
                first = page.evaluate("""() => { try { const n = window.__INITIAL_STATE__.user.notes._value[0] || [];
                    return n.map(x => ({id: x.id || x.noteCard.noteId, token: x.xsecToken || x.noteCard.xsecToken, title: x.noteCard.displayTitle})) } catch(e) { return [] } }""")
                notes = {n["id"]: n for n in first if n.get("id")}
                for _ in range(12):
                    page.mouse.wheel(0, 2500); page.wait_for_timeout(random.randint(1800, 3000)); check_block(page)
                    for d in captured["posted"]:
                        for n in d.get("notes", []):
                            notes.setdefault(n["note_id"], {"id": n["note_id"], "token": n.get("xsec_token"), "title": n.get("display_title")})
                    if len(notes) >= MAX_NOTES or (captured["posted"] and not captured["posted"][-1].get("has_more", True)):
                        break
                log(f"{brand}: {len(notes)} notes listed on profile '{nick}'")
                rows, older = [], 0
                for n in list(notes.values())[:MAX_NOTES]:
                    page.goto(f"https://www.xiaohongshu.com/explore/{n['id']}?xsec_token={n.get('token') or ''}&xsec_source=pc_user",
                              wait_until="domcontentloaded")
                    page.wait_for_timeout(random.randint(3000, 7000)); check_block(page)
                    d = page.evaluate(f"""() => {{ try {{ const m = window.__INITIAL_STATE__.note.noteDetailMap; const x = (m['{n['id']}'] || Object.values(m)[0]).note;
                        const i = x.interactInfo || {{}};
                        return {{title: x.title, desc: x.desc, time: x.time, type: x.type, liked: i.likedCount, collected: i.collectedCount,
                                 comments: i.commentCount, shared: i.shareCount, tags: (x.tagList || []).map(t => t.name)}} }} catch(e) {{ return null }} }}""")
                    if not d or not d.get("time"):
                        continue
                    date = datetime.fromtimestamp(d["time"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    if date < WIN[0]:
                        older += 1
                        if older >= 3:                                    # pinned notes can be older; stop after three in a row
                            break
                        continue
                    older = 0
                    if date > WIN[1]:
                        continue
                    rows.append({"brand": brand, "date": date, "url": f"https://www.xiaohongshu.com/explore/{n['id']}", "type": d.get("type"),
                                 "title": d.get("title") or n.get("title"), "text": (d.get("desc") or "")[:2000], "tags": d.get("tags"),
                                 "likes": d.get("liked"), "saves": d.get("collected"), "comments": d.get("comments"), "shares": d.get("shared")})
                    log(f"  {brand} {date} {str(d.get('title'))[:40]} likes={d.get('liked')}")
                results[brand] = {"done": True, "account": nick, "user_id": uid, "red_id": red_id, "interactions": fans,
                                  "captured": datetime.now(timezone.utc).isoformat(timespec="seconds"), "notes": rows}
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                log(f"{brand}: saved {len(rows)} notes in the window")
                page.wait_for_timeout(random.randint(5000, 9000))
        except Stop as e:
            log("STOPPED:", e)
        finally:
            OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            ctx.close()
    try:
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "notes"
        cols = ["brand", "date", "type", "title", "likes", "saves", "comments", "shares", "url", "tags", "text"]
        ws.append(cols)
        for b, v in results.items():
            for r in v.get("notes", []):
                ws.append([", ".join(r[c]) if isinstance(r.get(c), list) else r.get(c) for c in cols])
        wb.save(ROOT / "xhs_notes.xlsx")
    except Exception as e:  # noqa: BLE001
        log("xlsx not written:", e)
    log("Finished:", {b: len(v.get("notes", [])) for b, v in results.items()})


if __name__ == "__main__":
    main()
