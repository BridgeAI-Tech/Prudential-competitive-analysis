"""Extract the public information from Manulife results-webcast pages (gowebcasting.com) and other pages into Excel.

Usage:  python tools/scrape_manulife_webcasts.py URL [URL ...] [--out ../Manulife_results_webcasts.xlsx]
Tracking parameters (adobe_mc etc.) are stripped and duplicate URLs collapsed. Uses the pipeline's polite fetch
(robots.txt respected, per-host delay, HTML snapshot saved as evidence). Registration-gated webcast content
(audio/video, slides, Q&A) is NOT accessed - the registration form is never submitted.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from bs4 import BeautifulSoup  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from common import Blocked, clean_text, fetch, log, now_utc  # noqa: E402

GREEN = PatternFill("solid", fgColor="1BAF7A")


def clean_url(u: str) -> str:
    p = urlsplit(u.strip())
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def text(el) -> str:
    return clean_text(el.get_text(" ")) if el else ""


def parse_webcast(html: str) -> tuple[dict, list[dict]]:
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    sub = s.select_one("#theme-subheader")
    title = text(sub.find("h1")) if sub else text(s.find("h1"))
    when = text(sub.find("h2")) if sub else ""
    intro = s.select_one("#player-event-intro")
    paras = [text(p) for p in intro.find_all("p") if not p.find_parent(class_="section")] if intro else []
    about = " ".join(p for p in paras if p and not p.startswith("Not all offerings"))
    speakers = []
    for sec in s.select(".section"):
        name = text(sec.select_one(".section-info-title"))
        if not name:
            continue
        desc = sec.select_one(".section-info-description")
        bio = "\n".join(text(p) for p in desc.find_all("p")) if desc else ""
        img = sec.select_one(".section-photo img")
        speakers.append({"name": name, "title": text(sec.select_one(".section-info-subtitle")), "bio": bio.strip(),
                         "photo": img.get("src", "").strip() if img else None})
    form = s.select_one("#register-form")
    fields = []
    if form:
        names = {"email": "Email", "first_name": "First name", "last_name": "Last name", "company": "Company"}
        for el in form.find_all(["input", "select"]):
            n = el.get("name") or ""
            if el.name == "select":
                opts = [text(o) for o in el.find_all("option") if text(o) and text(o).lower() != "select one"]
                fields.append(f"Occupation ({' / '.join(opts)})")
            elif n in names:
                fields.append(names[n])
            elif el.get("type") == "checkbox":
                lab = form.find("label")
                fields.append("Checkbox: " + (text(lab).lstrip("* ") if lab else n))
    tick = re.search(r"trade as (.+?)(?:\.|$)", about)
    scale = re.search(r"At the end of (\d{4}), we had (.+?)(?:\.|$)", about)
    ev = {"title": title, "date_time": when, "about": about, "tickers": tick.group(1) if tick else None,
          "scale": f"End of {scale.group(1)}: {scale.group(2)}" if scale else None,
          "registration_required": bool(form), "registration_fields": ", ".join(fields) or None}
    return ev, speakers


def parse_generic(html: str) -> dict:
    s = BeautifulSoup(html, "lxml")
    for t in s(["script", "style", "noscript", "nav", "footer", "header"]):
        t.decompose()
    return {"title": text(s.find("title")) or text(s.find("h1")), "about": text(s.body)[:30000] if s.body else ""}


def style(ws, widths):
    for j, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=j)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), GREEN
        ws.column_dimensions[get_column_letter(j)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", default=str(ROOT.parent / "Manulife_results_webcasts.xlsx"))
    a = ap.parse_args()
    urls = list(dict.fromkeys(clean_url(u) for u in a.urls))
    log(f"{len(a.urls)} URLs supplied -> {len(urls)} unique after removing tracking parameters")

    events, speakers, other, access = [], [], [], []
    for u in urls:
        status, ref = "ok", None
        try:
            html, ref = fetch(u, timeout=40)
        except Blocked as e:
            status = f"blocked - {e}"
        except Exception as e:
            status = f"error - {type(e).__name__}: {e}"
        access.append([u, status[:300], ref, now_utc()])
        log(f"{status[:60]:60} {u}")
        if status != "ok":
            continue
        if "gowebcasting.com" in u:
            ev, sp = parse_webcast(html)
            m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", u)
            ev.update({"event_date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None, "url": u, "evidence": ref})
            events.append(ev)
            for x in sp:
                speakers.append([ev["event_date"], ev["title"], x["name"], x["title"], x["bio"], x["photo"]])
        else:
            g = parse_generic(html)
            other.append([u, g["title"], g["about"], ref])

    events.sort(key=lambda e: e["event_date"] or "", reverse=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "events"
    ws.append(["Event date", "Event", "Date / time (as shown)", "Webcast URL", "Tickers", "Company scale (as stated)",
               "Company description", "Registration required", "Registration fields", "Evidence snapshot"])
    for e in events:
        ws.append([e["event_date"], e["title"], e["date_time"], e["url"], e["tickers"], e["scale"], e["about"],
                   "Yes - webcast audio/slides/Q&A not accessed" if e["registration_required"] else "No",
                   e["registration_fields"], e["evidence"]])
    style(ws, [12, 36, 34, 60, 40, 50, 90, 26, 40, 40])
    for r in ws.iter_rows(min_row=2):
        r[3].hyperlink, r[3].style = r[3].value, "Hyperlink"

    s2 = wb.create_sheet("speakers")
    s2.append(["Event date", "Event", "Speaker", "Title", "Biography (as shown)", "Photo URL"])
    for r in sorted(speakers, key=lambda x: x[0] or "", reverse=True):
        s2.append(r)
    style(s2, [12, 34, 22, 26, 110, 40])

    # speaker line-up across quarters (who presented when)
    names = list(dict.fromkeys(r[2] for r in speakers))
    s3 = wb.create_sheet("speaker_lineup")
    s3.append(["Speaker", "Title(s)"] + [f"{e['event_date']} {e['title']}" for e in events])
    for n in names:
        titles = sorted({r[3] for r in speakers if r[2] == n})
        s3.append([n, " / ".join(titles)] + ["Yes" if any(r[2] == n and r[0] == e["event_date"] for r in speakers) else ""
                                             for e in events])
    style(s3, [24, 30] + [22] * len(events))

    if other:
        s4 = wb.create_sheet("other_pages")
        s4.append(["URL", "Page title", "Page text", "Evidence snapshot"])
        for r in other:
            s4.append(r)
        style(s4, [60, 40, 120, 40])

    s5 = wb.create_sheet("access_log")
    s5.append(["URL (tracking parameters removed)", "Status", "Evidence snapshot", "Fetched at (UTC)"])
    for r in access:
        s5.append(r)
    style(s5, [90, 70, 40, 24])

    wb.save(a.out)
    log(f"saved {len(events)} webcasts, {len(speakers)} speaker entries, {len(other)} other pages -> {a.out}")


if __name__ == "__main__":
    main()
