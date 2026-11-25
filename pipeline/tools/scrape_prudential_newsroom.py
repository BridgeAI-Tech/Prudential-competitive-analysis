"""Scrape every article listed on https://www.prudential.com.hk/en/about-us/newsroom/ into an Excel workbook.

Usage:  python tools/scrape_prudential_newsroom.py [--out ../Prudential_HK_newsroom.xlsx] [--limit N]
Uses the pipeline's polite fetch (robots.txt respected, 1.5 s per-host delay, HTML snapshot saved as evidence).
Publication date comes from the newsroom card (DD-MM-YYYY); the article's JSON-LD datePublished is kept separately.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "collectors"))

from bs4 import BeautifulSoup  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from common import Blocked, clean_text, fetch, log, now_utc  # noqa: E402
from newsrooms import extract_article  # noqa: E402

BASE = "https://www.prudential.com.hk"
LIST_URL = BASE + "/en/about-us/newsroom/"
WINDOW = (dt.date(2025, 11, 1), dt.date(2026, 10, 31))
# Media contacts supplied by the user (screenshot of a press-release "Media" block followed by "About Prudential plc").
# Not present on the prudential.com.hk newsroom article pages, so kept as a separate, user-provided sheet.
# Kept out of the public repo: put [["Name", "Phone", "Email"], ...] in media_contacts.local.json next to this file (git-ignored).
_MC = Path(__file__).with_name("media_contacts.local.json")
MEDIA_CONTACTS = [tuple(x) for x in json.loads(_MC.read_text(encoding="utf-8"))] if _MC.exists() else []
MEDIA_SOURCE = "User-provided (press-release 'Media' contact block); not found on prudential.com.hk newsroom pages as of 2026-11-11"


def write_media_contacts(wb):
    if "media_contacts" in wb.sheetnames:
        del wb["media_contacts"]
    m = wb.create_sheet("media_contacts", 1)
    m.append(["Brand", "Contact type", "Name", "Phone", "Email", "Source"])
    for name, phone, email in MEDIA_CONTACTS:
        m.append(["Prudential", "Media", name, phone, email, MEDIA_SOURCE])
    for j, w in enumerate([12, 12, 18, 16, 36, 90], 1):
        c = m.cell(row=1, column=j)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="D7263D")
        m.column_dimensions[get_column_letter(j)].width = w
    for r in m.iter_rows(min_row=2):
        r[4].hyperlink = "mailto:" + r[4].value
        r[4].style = "Hyperlink"

COLUMNS = [
    ("No.", 6), ("Publication date", 13), ("Year", 7), ("Title", 60), ("Article URL", 50), ("Summary (meta description)", 60),
    ("Article text", 80), ("Word count", 10), ("JSON-LD datePublished", 14), ("Chinese version URL", 45),
    ("Image URL", 40), ("In POC window (Nov 25-Oct 26)", 12), ("Fetch status", 12), ("Capture timestamp (UTC)", 22),
    ("Evidence snapshot", 38),
]


def card_title(card) -> str:
    for tag in ("h3", "h2", "h4"):
        h = card.find(tag)
        if h and clean_text(h.get_text(" ")):
            return clean_text(h.get_text(" "))
    img = card.find("img")
    if img and img.get("alt"):
        return clean_text(img["alt"])
    a = card.find("a", href=True)
    return clean_text(a.get_text(" ")) if a else ""


def parse_card_date(s: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except (ValueError, AttributeError):
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "Prudential_HK_newsroom.xlsx"))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    html, list_ref = fetch(LIST_URL)
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article.article-card")
    items, seen = [], set()
    for card in cards:
        link = card.find("a", href=True)
        if not link:
            continue
        url = urljoin(BASE, link["href"].split("?")[0])
        if url in seen:
            continue
        seen.add(url)
        items.append({"url": url, "title": card_title(card), "date": parse_card_date(card.get("data-date", ""))})
    items.sort(key=lambda x: x["date"] or dt.date.min, reverse=True)
    if a.limit:
        items = items[: a.limit]
    log(f"newsroom list: {len(cards)} cards, {len(items)} unique articles")

    rows = []
    for i, it in enumerate(items, 1):
        art, ref, status = {}, None, "ok"
        try:
            ahtml, ref = fetch(it["url"])
            art = extract_article(ahtml)
            s2 = BeautifulSoup(ahtml, "lxml")
            alt = s2.find("link", rel="alternate", hreflang=lambda v: v and v.lower().startswith("zh"))
            art["zh_url"] = alt["href"] if alt and alt.get("href") else it["url"].replace("/en/", "/tc/")
            h1 = s2.find("h1")
            if h1 and clean_text(h1.get_text(" ")) and not it["title"]:
                it["title"] = clean_text(h1.get_text(" "))
        except Blocked as e:
            status = f"blocked: {e}"[:60]
        except Exception as e:  # keep going; record the failure in the sheet
            status = f"error: {e}"[:60]
        body = art.get("body") or ""
        d = it["date"]
        rows.append([
            i, d, d.year if d else None, it["title"], it["url"], art.get("description"), body,
            len(body.split()) if body else 0, art.get("date"), art.get("zh_url"),
            urljoin(BASE, art["image"]) if art.get("image") else None,
            "Yes" if d and WINDOW[0] <= d <= WINDOW[1] else "No", status, now_utc(), ref,
        ])
        if i % 10 == 0:
            log(f"  {i}/{len(items)} fetched")

    wb = Workbook()
    ws = wb.active
    ws.title = "newsroom_articles"
    ws.append([c for c, _ in COLUMNS])
    for r in rows:
        ws.append(r)
    head = PatternFill("solid", fgColor="D7263D")
    for j, (_, w) in enumerate(COLUMNS, 1):
        c = ws.cell(row=1, column=j)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), head
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(j)].width = w
    for r in ws.iter_rows(min_row=2):
        r[1].number_format = "dd-mmm-yyyy"
        for c in r:
            c.alignment = Alignment(wrap_text=c.column in (4, 6), vertical="top")
        r[4].hyperlink = r[4].value
        r[4].style = "Hyperlink"
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = ws.dimensions

    by_year = {}
    for r in rows:
        by_year[r[2]] = by_year.get(r[2], 0) + 1
    s = wb.create_sheet("summary")
    for row in [["Source", LIST_URL], ["List snapshot", list_ref], ["Scraped at (UTC)", now_utc()],
                ["Articles listed", len(items)], ["Fetched OK", sum(1 for r in rows if r[12] == "ok")],
                ["In POC window (1 Nov 2025 - 31 Oct 2026)", sum(1 for r in rows if r[11] == "Yes")], [],
                ["Year", "Articles"]] + [[y, n] for y, n in sorted(by_year.items(), key=lambda x: (x[0] is None, x[0]), reverse=True)]:
        s.append(row)
    s.column_dimensions["A"].width = 42
    s.column_dimensions["B"].width = 70
    for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A8", "B8"):
        s[c].font = Font(bold=True)

    write_media_contacts(wb)
    wb.save(a.out)
    log(f"saved {len(rows)} articles -> {a.out}")


if __name__ == "__main__":
    main()
