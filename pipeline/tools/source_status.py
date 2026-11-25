"""Status of every URL in 'Prudential_HK_All_Source_URLs_for_Sahaj.docx': fetched or not, how much, where it is used, and why not.
Usage: python -I ci-monitor/tools/source_status.py  ->  Prudential/Source_URL_Status.xlsx
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import docx
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "Prudential_HK_All_Source_URLs_for_Sahaj.docx"
RAW = ROOT / "apify_raw"
con = sqlite3.connect(ROOT / "ci-monitor/data/ci.db")
q = lambda s, *a: con.execute(s, a).fetchall()
W = ("2025-11-01", "2026-10-31")


def jcount(name, key=None, val=None):
    p = RAW / f"{name}.json"
    if not p.exists():
        return None
    items = json.loads(p.read_text(encoding="utf-8"))
    return len([x for x in items if key is None or str(x.get(key, "")).lower() == str(val).lower()])


def news(domain):
    return q(f"select count(*) from observations where source_url like ? and publication_date between '{W[0]}' and '{W[1]}'", f"%{domain}%")[0][0]


FB = {"prudentialhk": "prudentialhk", "aiahongkong": "AIAHongKong", "axahongkong": "AXAHongKong", "manulifehongkong": "manulifehongkong"}
IG = {"prudential.hongkong": "prudential.hongkong", "axahongkong": "axahongkong", "manulife_hongkong": "manulife_hongkong", "aiahongkongmacau": "AIAHongKongMacau"}


def status(url):
    u = url.lower()
    if "facebook.com/ads/library" in u:
        n = jcount("fb_ads")
        return ("Fetched" if n else "Pending", f"{n} ads (Meta Ad Library, Hong Kong)" if n is not None else "Run in progress", "Brand & Campaigns")
    if "facebook.com/search" in u:
        return ("Covered another way", "Facebook search needs a login; the four official pages were fetched in full instead", "Brand & Campaigns")
    m = re.search(r"facebook\.com/([^/?]+)", u)
    if m and m.group(1) in FB:
        n = jcount("fb_posts", "pageName", FB[m.group(1)])
        return ("Fetched", f"{n} page posts (11 months of the window and more), followers", "Brand & Campaigns, Company Profiles")
    if "facebook.com" in u:
        return ("Reference only", "Platform home page, no data of its own", "–")
    m = re.search(r"instagram\.com/([^/?]+)", u)
    if m and m.group(1) in IG:
        name = "ig_posts_aia" if "aia" in m.group(1) else "ig_posts"
        n = jcount(name, "ownerUsername", IG[m.group(1)])
        return ("Fetched" if n else "Pending", f"{n} posts, followers" if n is not None else "Run in progress", "Brand & Campaigns")
    if "instagram.com" in u:
        return ("Reference only", "Platform home page", "–")
    if "threads." in u:
        n = jcount("threads_aia")
        return ("Fetched" if n else "Pending", f"{n} profile record(s)" if n is not None else "Run in progress", "Brand & Campaigns")
    if "youtube.com/results" in u:
        return ("Fetched", "Searched for interviews, podcasts and campaign videos; Hong Kong-relevant results kept", "Brand & Campaigns (YouTube)")
    if "youtube.com" in u and u.rstrip("/") != "https://www.youtube.com":
        b = [k for k in ("prudential", "aia", "manulife", "axa") if k in u]
        cid = {"prudential": "PRU_HK", "aia": "AIA_HK", "manulife": "MFC_HK", "axa": "AXA_HK"}.get(b[0]) if b else None
        n = q("select count(*) from observations where platform='youtube' and company_id=?", cid)[0][0] if cid else 0
        return ("Fetched", f"{n} videos with views, subscribers", "Brand & Campaigns (YouTube)")
    if "linkedin.com/search" in u:
        return ("Covered another way", "LinkedIn search needs a login; the four company pages' posts were fetched in full instead", "Brand & Campaigns")
    if "linkedin.com/company" in u:
        return ("Fetched", "Full-year company posts with reactions, comments, reposts and followers", "Brand & Campaigns")
    if "wechat" in u:
        return ("Not available", "WeChat account content is not publicly accessible; account recorded", "Company Profiles (coverage table)")
    if "xiaohongshu" in u:
        return ("Waiting for login", "Needs a logged-in session; collector ready (ci-monitor/tools/xhs_collect.py)", "Company Profiles (coverage table)")
    if "tiktok" in u:
        return ("Not applicable", "TikTok does not operate in Hong Kong; no Hong Kong accounts or ad data", "Company Profiles (coverage table)")
    if "adstransparency" in u:
        n = q("select count(*) from ad_library")[0][0]
        return ("Fetched", f"{n} Google ad creatives for the four brands (Hong Kong)", "Brand & Campaigns (YouTube and paid ads)")
    if "trends.google" in u:
        n = q("select count(*) from context_stats where source like '%rends%'")[0][0]
        return ("Fetched", f"{n} monthly search-interest rows (English and Chinese brand names)", "Chat knowledge base")
    if "ia.org.hk" in u:
        return ("Blocked", "The Insurance Authority site refuses automated access (HTTP 403). Figures used via the insurers' own filings and news coverage; Q1 and H1 2026 statistics files need a manual download", "Hong Kong market & results")
    if "icb.org.hk" in u:
        return ("Blocked", "The site's robots rules forbid automated access; annual report needs a manual download", "–")
    if "hkfi.org.hk" in u or "mpfa.org.hk" in u:
        n = q("select count(*) from context_stats where source like ?", "%" + ("HKFI" if "hkfi" in u else "MPFA") + "%")[0][0]
        return ("Fetched", f"{n} context figures (latest brief or statistics digest)", "Chat knowledge base")
    if "hkma.gov.hk" in u:
        return ("Fetched (targeted)", "GenA.I. Sandbox++ participant release used", "Digital experience (AI moves)")
    if any(k in u for k in ("data.gov.hk", "censtatd", "consumer.org", "cr.gov.hk")):
        return ("Not needed", "General government portal with no insurer-specific data for this report (Companies Registry searches are paid)", "–")
    if "hkinsurancenews" in u:
        return ("Not available", "Domain does not exist", "–")
    if "news.google.com" in u:
        n = q(f"select count(*) from observations where source_url like '%news.google.com%' and publication_date between '{W[0]}' and '{W[1]}'")[0][0]
        return ("Fetched", f"{n} news items via Google News feeds (brand and month queries)", "Competitor Activity, Evidence explorer")
    if "google.com/search" in u:
        return ("Covered another way", "Google web search pages cannot be fetched automatically under Google's terms; covered by Google News, YouTube search and the insurers' sites", "–")
    for dom in ("insuranceasianews", "insuranceasia.com", "asiainsurancereview", "thestandard", "scmp.com", "rthk"):
        if dom in u:
            return ("Fetched", f"{news(dom)} articles in the window", "Competitor Activity, Evidence explorer")
    if "emma.axa.com.hk" in u:
        return ("Fetched", "App capabilities recorded", "Digital Experience")
    if "apps.apple.com" in u or "play.google.com" in u:
        return ("Fetched", "Store listings, ratings and 12 months of iPhone reviews for every insurer's app", "Digital Experience")
    if "developer.apple" in u or "support.google" in u:
        return ("Reference only", "Help documentation, no data", "–")
    for dom, cid in (("prudential.com.hk", "PRU_HK"), ("aia.com.hk", "AIA_HK"), ("axa.com.hk", "AXA_HK"), ("manulife.com.hk", "MFC_HK")):
        if dom in u:
            n = q(f"select count(*) from observations where company_id=? and source_category='official' and publication_date between '{W[0]}' and '{W[1]}'", cid)[0][0]
            how = "via Internet Archive copies (the live site blocks automated access)" if cid == "MFC_HK" else "official site and newsroom"
            return ("Fetched", f"{n} official releases and pages, {how}", "Competitor Activity, Products, Company Profiles")
    if re.match(r"https://www\.(youtube|linkedin)\.com/?$", u):
        return ("Reference only", "Platform home page", "–")
    return ("Reference only", "Platform or search home page with no data of its own", "–")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = docx.Document(DOC)
    rows, sec = [], ""
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if re.match(r"^\d+\.\s", t) and "http" not in t:
            sec = t
            continue
        for u in re.findall(r"https?://\S+", t):
            label = t.split("\n")[0] if not t.startswith("http") else ""
            rows.append((sec, label, u.rstrip(".,)")))
    seen, out = set(), []
    for sec, label, u in rows:
        if u in seen:
            continue
        seen.add(u)
        out.append((sec, label, u, *status(u)))
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Source status"
    ws.append(["Section in source list", "Label", "URL", "Status", "What was fetched", "Where it is used in the report"])
    fill = {"Fetched": "DCF3E6", "Fetched (targeted)": "DCF3E6", "Covered another way": "E1ECFB", "Pending": "FBEFD6", "Waiting for login": "FBEFD6",
            "Blocked": "F8D7DA", "Not available": "EEEEEE", "Not applicable": "EEEEEE", "Not needed": "EEEEEE", "Reference only": "EEEEEE"}
    for r in out:
        ws.append(r)
        ws.cell(ws.max_row, 4).fill = PatternFill("solid", fgColor=fill.get(r[3], "FFFFFF"))
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEF", (34, 30, 70, 20, 70, 40)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(ROOT / "Source_URL_Status.xlsx")
    from collections import Counter
    print(len(out), "unique URLs:", dict(Counter(r[3] for r in out)))


if __name__ == "__main__":
    main()
