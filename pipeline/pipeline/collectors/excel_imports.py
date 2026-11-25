"""Import every Excel extract held in the project folder (F:\\Prudential\\*.xlsx).

Observation records (returned, written to data/raw/excel_imports.jsonl):
  * Exa_news_data.xlsx / Google_News_news_data.xlsx / Tavily_news_data.xlsx  (sheet all_records)
      Normalised news & announcement extracts (run 2026-11-10). Rows flagged in_scope=True become observations;
      every other row is retained as an excluded record with the vendor's reason (never silently dropped).
  * <Brand>_Hong_Kong_explorium_data.xlsx  (sheet 13_News_Events)  - awards, launches, partnerships, offices.

Context files (written to data/raw/, exported to the dashboard by build.py):
  * company_context.json  - Explorium firmographics, workforce mix, employer ratings, technographics, intent topics.
  * source_inventory.json - Source_Validation_v0.1.xlsx (sources, apps, social accounts, metric availability).
  * data_inventory.json   - one row per workbook/sheet: rows read, rows used, how it is used, and why not if excluded.

Vendor labels (activity type, themes, product category, duplicate group) are kept in `extra` for audit; the
pipeline's own taxonomy (classify.py) stays authoritative so every source is labelled consistently.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

from common import COMPANIES, RAW, ROOT, clean_text, log, make_record

SRC = ROOT.parent
NEWS_FILES = ["Exa_news_data.xlsx", "Google_News_news_data.xlsx", "Tavily_news_data.xlsx"]
EXPLORIUM = {c["brand"]: f"{c['display_name'].replace(' ', '_')}_explorium_data.xlsx" for c in COMPANIES}
BY_BRAND = {c["brand"]: c for c in COMPANIES}

HK_RX = re.compile(r"hong kong|\bHK\b|香港|GBA|greater bay|大灣區|macau|澳門", re.I)
# Hong Kong publishers: coverage by these outlets is itself an explicit HK basis
HK_PUBLISHERS = re.compile(
    r"星島|明報|經濟日報|信報|東方日報|香港01|HK01|頭條|am730|文匯|大公|商報|on\.cc|東網|RTHK|香港電台|The Standard|thestandard|"
    r"SCMP|South China Morning Post|晴報|經濟通|etnet|巴士的報|橙新聞|點新聞|now 新聞|now新聞|TVB|無綫|i-CABLE|有線|Sky Post|"
    r"hket|mingpao|singtao|hkej|stheadline|hk\.on\.cc|bastillepost|aastocks|阿思達克|infocast|信析|AM730|Hong Kong Business|"
    r"hongkongbusiness|insurancebusinessmag|hkinsurancenews", re.I)

# vendor activity labels -> pipeline taxonomy (used only when the rule-based classifier finds nothing)
VENDOR_ACTIVITY = {
    "product_launch": "product_launch", "product_enhancement": "product_enhancement", "partnership": "partnership",
    "campaign": "campaign", "sponsorship": "sponsorship_community", "health_wellness_initiative": "campaign",
    "service_enhancement": "service_enhancement", "corporate_announcement": "corporate_announcement",
    "regulatory_matter": "corporate_announcement", "research_report": "corporate_announcement",
}
EXPLORIUM_ACTIVITY = {"new_product": "product_launch", "company_award": "award_recognition",
                      "new_partnership": "partnership", "new_office": "corporate_announcement"}

INVENTORY: list[dict] = []


def _inv(file, sheet, rows, used, use, note=""):
    INVENTORY.append({"file": file, "sheet": sheet, "rows": rows, "used": used, "use": use, "note": note})


def _sheet(path: Path, name: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    if name not in wb.sheetnames:
        return []
    rows = list(wb[name].iter_rows(values_only=True))
    if not rows or rows[0] == ("No data available",):
        return []
    hdr = [str(h) if h is not None else f"col{i}" for i, h in enumerate(rows[0])]
    return [dict(zip(hdr, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]


def _date(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.date().isoformat() if isinstance(v, dt.datetime) else v.isoformat()
    try:
        return dt.date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        return None


def _split(v) -> list[str]:
    return [x.strip() for x in str(v or "").split("|") if x.strip()]


def _truthy(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def _cap_ts(row, path: Path) -> str:
    v = row.get("capture_timestamp")
    if v:
        return str(v).replace("Z", "+00:00")
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ 1. normalised news workbooks
def _exclusion_reason(r: dict, start, end) -> str | None:
    pub = _date(r.get("publication_date"))
    if not pub:
        return "vendor_undated"
    if not (start.isoformat() <= pub <= end.isoformat()):
        return "vendor_out_of_window"
    if _truthy(r.get("excluded_entity_flag")):
        return "vendor_excluded_entity"
    if not _truthy(r.get("brand_match")):
        return "vendor_brand_not_in_text"
    if str(r.get("hk_relevance") or "").lower() == "low":
        return "vendor_low_hk_relevance"
    if not _truthy(r.get("in_scope")):
        return "vendor_out_of_scope"
    return None


def news_workbooks(start, end) -> list[dict]:
    out = []
    for name in NEWS_FILES:
        path = SRC / name
        if not path.exists():
            _inv(name, "all_records", 0, 0, "missing", "file not found")
            continue
        rows = _sheet(path, "all_records") or _sheet(path, "in_scope")
        used = excl = 0
        for n, r in enumerate(rows, start=2):
            brand = r.get("brand")
            if brand not in BY_BRAND or not r.get("source_url") or not r.get("title"):
                continue
            c = BY_BRAND[brand]
            url = str(r["source_url"]).strip()
            domain = urlparse(url).netloc.lower()
            official = r.get("source_category") == "official" or any(domain.endswith(d) for d in c["domains"])
            title = clean_text(r["title"])
            summary = clean_text(r.get("english_summary"))
            desc = clean_text(r.get("description"))
            publisher = r.get("source_name") or domain
            vendor_hk = str(r.get("hk_relevance") or "")
            text = f"{title} {desc[:600]}"
            if official:
                hk, basis = "explicit", "Official HK domain" if any(domain.endswith(d) for d in c["domains"]) else f"Official source; vendor HK basis: {r.get('hk_relevance_basis')}"
            elif vendor_hk.lower() == "high" or HK_RX.search(text):
                hk, basis = "explicit", f"Vendor: {r.get('hk_relevance_basis') or 'HK terms'}" if vendor_hk.lower() == "high" else "Hong Kong term in headline/summary"
            elif HK_PUBLISHERS.search(f"{publisher} {domain}"):
                hk, basis = "explicit", f"Hong Kong publisher ({publisher})"
            else:
                hk, basis = "unconfirmed", f"Vendor: {vendor_hk} - {r.get('hk_relevance_basis') or 'not explicit'}"
            lang = str(r.get("language") or "")
            others = _split(r.get("other_source_urls"))
            rec = make_record(
                record_id="X" + str(r.get("record_id") or n),
                brand=brand, record_type="announcement" if official else "news_article", modules=["M1"],
                title=title, description=(desc or summary)[:500] or None, original_content=clean_text(r.get("original_content")) or None,
                language=lang if lang in ("en", "zh") else None,
                english_summary=summary if summary and lang == "en" else (summary if summary and summary != title else None),
                publication_date=_date(r.get("publication_date")), capture_ts=_cap_ts(r, path),
                source_name=str(publisher), source_category="official" if official else "media", source_url=url,
                evidence_ref=f"{name}#all_records!row{n}" + (f" | {r['evidence_ref']}" if r.get("evidence_ref") else ""),
                hk_relevance=hk, hk_relevance_basis=basis,
                platform="website" if official else "news", content_format="press_release" if official else "article",
                extra={"import": name, "tool": r.get("tool"), "query": r.get("query"), "query_theme": r.get("query_theme"),
                       "vendor_record_id": r.get("record_id"), "vendor_activity_type": r.get("activity_type"),
                       "vendor_activity_fallback": VENDOR_ACTIVITY.get(str(r.get("activity_type"))),
                       "vendor_product_category": _split(r.get("product_category")), "vendor_themes": _split(r.get("themes")),
                       "vendor_modules": _split(r.get("module")), "vendor_duplicate_group": r.get("duplicate_group_id"),
                       "url_is_google_redirect": _truthy(r.get("url_is_google_redirect")),
                       "evidence_urls": others[:6], "brands_mentioned": _split(r.get("brands_mentioned"))},
            )
            reason = _exclusion_reason(r, start, end)
            if reason:
                rec["extra"]["exclude_reason"] = reason
                excl += 1
            else:
                used += 1
            out.append(rec)
        _inv(name, "all_records", len(rows), used, "M1-M5 observations (news & announcements)",
             f"{excl} rows kept as excluded records with vendor reason (out of window, low HK relevance, brand not in text, excluded entity)")
        for s in ("in_scope", "brand_summary"):
            k = len(_sheet(path, s))
            _inv(name, s, k, 0, "cross-check only", "in_scope = subset of all_records (in_scope=True); brand_summary = vendor counts" if s == "in_scope" else "vendor counts per brand (reconciled against imported rows)")
        log(f"excel {name}: {used} in scope, {excl} excluded")
    return out


# ------------------------------------------------------------------ 2. Explorium news events
def explorium_events(start, end) -> list[dict]:
    out = []
    for brand, fname in EXPLORIUM.items():
        path = SRC / fname
        if not path.exists():
            continue
        c = BY_BRAND[brand]
        rows = _sheet(path, "13_News_Events")
        used = 0
        for n, r in enumerate(rows, start=2):
            try:
                d = json.loads(r.get("data") or "{}")
            except json.JSONDecodeError:
                d = {}
            pub = _date(r.get("event_time"))
            link = d.get("link")
            if not (pub and link):
                continue
            ev = r.get("event_name")
            if ev == "company_award":
                title = f"{c['display_name']}: {d.get('award_name', 'award')} ({d.get('awarding_body', 'n/a')})"
                body = d.get("award_reason")
            elif ev == "new_partnership":
                title = d.get("title") or f"{c['display_name']} partners with {d.get('partner_company', 'n/a')}"
                body = f"Partner: {d.get('partner_company')}. Purpose: {d.get('purpose_of_partnership')}"
            elif ev == "new_office":
                title = d.get("title") or f"{c['display_name']} new office: {d.get('office_location')}"
                body = f"{d.get('purpose_of_new_office')} at {d.get('office_location')}"
            else:
                title = d.get("title") or f"{c['display_name']} launches {d.get('product_name')}"
                body = f"{d.get('product_name')}: {d.get('product_description')}"
            import unicodedata
            title = unicodedata.normalize("NFKC", clean_text(title))
            snippet = unicodedata.normalize("NFKC", clean_text(d.get("snippet")))
            domain = urlparse(link).netloc.lower()
            official = any(domain.endswith(x) for x in c["domains"])
            is_li = "linkedin.com" in domain
            rec = make_record(
                brand=brand, record_type="announcement" if (official or is_li) else "news_article", modules=["M1"],
                title=title, description=clean_text(body)[:500], original_content=(clean_text(body) + " " + snippet).strip(),
                publication_date=pub, capture_ts=dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat(),
                source_name="LinkedIn company page (via Explorium)" if is_li else domain,
                source_category="official" if (official or is_li) else "media", source_url=link,
                evidence_ref=f"{fname}#13_News_Events!row{n}",
                hk_relevance="explicit", hk_relevance_basis="Explorium event linked to the HK entity" + (" (official HK LinkedIn page)" if is_li else ""),
                platform="linkedin" if is_li else ("website" if official else "news"),
                content_format="post" if is_li else "article",
                product_name=d.get("product_name") if ev == "new_product" else None,
                extra={"import": fname, "explorium_event": ev, "vendor_activity_fallback": EXPLORIUM_ACTIVITY.get(ev),
                       "partner_company": d.get("partner_company"), "awarding_body": d.get("awarding_body")},
            )
            if not (start.isoformat() <= pub <= end.isoformat()):
                rec["extra"]["exclude_reason"] = "vendor_out_of_window"
            else:
                used += 1
            out.append(rec)
        _inv(fname, "13_News_Events", len(rows), used, "M1 observations (awards, launches, partnerships, offices)")
    return out


# ------------------------------------------------------------------ 3. company context (Explorium) - Module 5 context
def _num(v):
    try:
        return float(str(v).replace(",", "").split("/")[0].strip())
    except (TypeError, ValueError):
        return None


def company_context() -> dict:
    ctx = {}
    for brand, fname in EXPLORIUM.items():
        path = SRC / fname
        if not path.exists():
            continue
        firm = (_sheet(path, "1_Firmographics") or [{}])[0]
        wf = (_sheet(path, "6_Workforce_Trends") or [{}])[0]
        rat = (_sheet(path, "7_Company_Ratings") or [{}])[0]
        tech = (_sheet(path, "4_Technographics") or [{}])[0]
        intent = sorted(_sheet(path, "11_intent_score"), key=lambda x: -(x.get("Composite Score") or 0))
        roles = {}
        for k, v in wf.items():
            m = re.match(r"Perc (.+) Roles", k)
            if m and _num(v) is not None:
                roles[m.group(1)] = {"pct": _num(v), "change": _num(wf.get(f"Change In {m.group(1)} Roles"))}
        ratings = {k.replace("Ratings ", ""): {"value": _num(v), "scale": str(v).split("/")[-1].strip() if "/" in str(v) else None}
                   for k, v in rat.items() if k.startswith("Ratings ") and v not in (None, "") and k != "Ratings All Reviews Count"}
        # intent topics: keep insurance/finance/health/digital-relevant topics; generic IT noise is shown separately
        rel = re.compile(r"insur|health|medic|wellness|retire|wealth|claim|customer|digital|mobile app|ai\b|artificial|chatbot|"
                         r"marketing|advertis|crm|cloud|data|cyber|fintech|payment|underwrit|financial", re.I)
        ctx[brand] = {
            "firmographics": {"name": firm.get("Name"), "domain": firm.get("Company Domain"), "employees": firm.get("Number Of Employees Range"),
                              "revenue": firm.get("Yearly Revenue Range"), "naics": firm.get("Naics Description"),
                              "linkedin": firm.get("Linkedin Profile"), "description": clean_text(firm.get("Business Description"))[:600]},
            "workforce": {"quarter": _date(wf.get("Quarters")), "profiles": _num(wf.get("Profiles Found Per Quarter")), "roles": roles},
            "employer_ratings": {"source_name": rat.get("Company Name"), "reviews": _num(rat.get("Total Reviews Count")), "ratings": ratings},
            "tech_stack": {k: [t.strip() for t in str(v).split(",") if t.strip()] for k, v in tech.items()
                           if v not in (None, "") and k != "Full Tech Stack"},
            "intent_topics": [{"topic": t["Topic"], "score": t.get("Composite Score")} for t in intent
                              if rel.search(str(t.get("Topic"))) and not re.match(r"(hardware|media & advertising|personal computer|construction|social):", str(t.get("Topic")))][:15],
            "intent_topics_total": len(intent),
            "linkedin_posts": max(0, len(_sheet(path, "9_Social_Media")) - 1),
            "evidence_ref": fname,
            "captured": dt.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(),
        }
        for sheet, use, note in [
            ("1_Firmographics", "Company Master context (M5)", "headcount/revenue bands are vendor estimates"),
            ("6_Workforce_Trends", "M5 talent: workforce mix by function (latest quarter)", "LinkedIn-profile based; indicative only"),
            ("7_Company_Ratings", "M5 talent: employer ratings", "employee-review site aggregate; context only"),
            ("4_Technographics", "M4/M5 context: detected technology stack", "detected, not confirmed in use"),
            ("11_intent_score", "M5 context: research-intent topics", "B2B intent signal; insurance-relevant topics shown"),
            ("9_Social_Media", "M2 LinkedIn posts (social collector)", "likes + some comments; no post URLs/shares/followers"),
            ("13_News_Events", "M1 observations", ""),
            ("2_Company_Hierarchy", "not used", "entity mismatch (e.g. parent mapped to Prudential Financial / Worsley Investors)"),
            ("2_Subsidiaries", "not used", "entity mismatch (e.g. 'trip', 'hk express' listed under AXA HK)"),
            ("3_Funding_Overview", "not used", "funding data not relevant to established insurers"),
            ("5_Webstack", "not used", "duplicates technographics"),
            ("10_Intent_Topics", "not used", "header row only (no intent level)"),
        ]:
            if sheet in ("13_News_Events",):
                continue
            k = len(_sheet(path, sheet))
            _inv(fname, sheet, k, k if not use.startswith("not used") else 0, use, note)
    return ctx


# ------------------------------------------------------------------ 4. source validation + other workbooks
def source_inventory() -> dict:
    path = SRC / "Source_Validation_v0.1.xlsx"
    if not path.exists():
        return {}
    inv = {}
    for sheet, key in [("Source_Inventory", "sources"), ("App_Inventory", "apps"), ("Social_Accounts", "social_accounts"),
                       ("Metric_Availability", "metric_availability"), ("Existing_Data", "existing_data")]:
        rows = _sheet(path, sheet)
        inv[key] = [{k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v) for k, v in r.items()} for r in rows]
        _inv(path.name, sheet, len(rows), len(rows), "Technical documentation: source inventory & validation (Coverage tab)")
    return inv


def other_workbooks():
    legacy = {"news_announcements_data.xlsx": "M1 observations (seed_extracts collector; legacy Exa/Tavily/Google combined)",
              "exa_data.xlsx": "M1 observations (seed_extracts collector; legacy Exa extract, de-duplicated by URL)",
              "tavily_data.xlsx": "M1 observations (seed_extracts collector; legacy Tavily extract, de-duplicated by URL)",
              "google_news_rss_data.xlsx": "M1 observations (seed_extracts collector; legacy Google News RSS, de-duplicated by URL)"}
    for f, use in legacy.items():
        p = SRC / f
        if p.exists():
            wb = openpyxl.load_workbook(p, read_only=True)
            _inv(f, wb.sheetnames[0], max(0, wb.worksheets[0].max_row - 1), None, use,
                 "kept only if dated in window, brand named in headline, real article URL; vendor event_type discarded")
    p = SRC / "predictleads_data.xlsx"
    if p.exists():
        wb = openpyxl.load_workbook(p, read_only=True)
        for ws in wb.worksheets:
            _inv(p.name, ws.title, max(0, ws.max_row - 1), 0, "not used",
                 "returned finmo.net and dca-architects.com (Singapore) - not the four insurers; excluded")
    p = SRC / "prudential_hk_input.xlsx"
    if p.exists():
        rows = _sheet(p, "Companies")
        ok = all(any(r.get("domain") in c["domains"] for c in COMPANIES) for r in rows)
        _inv(p.name, "Companies", len(rows), len(rows), "Company Master cross-check",
             "domains match companies.json" if ok else "domain mismatch vs companies.json - review")


def collect(start, end) -> list[dict]:
    INVENTORY.clear()
    out = news_workbooks(start, end) + explorium_events(start, end)
    ctx = company_context()
    inv = source_inventory()
    other_workbooks()
    (RAW / "company_context.json").write_text(json.dumps(ctx, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (RAW / "source_inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (RAW / "data_inventory.json").write_text(json.dumps(INVENTORY, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"excel imports: {sum(1 for r in out if not r['extra'].get('exclude_reason'))} in scope, "
        f"{sum(1 for r in out if r['extra'].get('exclude_reason'))} excluded; context for {len(ctx)} brands")
    return out
