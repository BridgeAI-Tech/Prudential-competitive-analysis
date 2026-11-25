"""Stage 3: classification & normalisation (rule-based, driven by config/taxonomy.json).

The pipeline only labels and organises evidence; it does not draw conclusions (that is the analytical layer).
"""
from __future__ import annotations

import collections
import html
import re
import unicodedata
from difflib import SequenceMatcher

from common import TAXONOMY

# ------------------------------------------------------------------ noise rules (logged, not silently dropped)
NOISE = [
    ("sports_fixture", re.compile(r"\bvs\.?\b.*\b(match|highlight|round|final|qualif)|scores \||live updates|overview \| wta|tennis open \d{4} scores", re.I)),
    ("job_posting", re.compile(r"\| emploive|\bjob(s)? at\b|we.?re hiring|vacanc|careers?\b|career opportunit|"
                               r"\b(manager|director|principal|officer|analyst|specialist|consultant|lead)\b[^|]{0,60}\s(at|-)\s+(prudential|manulife|aia|axa)|"
                               r"manager in hong kong|^[A-Z][a-z]+ [A-Z][a-z]+ - [^|]*\b(at|-) ", re.I)),
    ("company_profile_page", re.compile(r"number of employees|employee count|headcount data|latest news and updates|products, competitors, financials|^AXA \| Offers$|^AIA International Limited$", re.I)),
    ("name_collision", re.compile(r"architect|seating design|landscape tour|honors & awards|kat o|dajiao", re.I)),  # AIA = American Institute of Architects HK
    ("market_ticker", re.compile(r"at lang & schwarz|stock after-hours|share price (falls|rises)|\(\d{4,5}\.HK\) (closes|opens)", re.I)),
    ("individual_incident", re.compile(r"slapped|brawl|mall spat|apm打|altercation|play area", re.I)),
]
SPONSOR_RX = re.compile(r"tennis open|hong kong open\b|演唱會|concert tour", re.I)
CAMPAIGN_PUBLISHERS = re.compile(r"marketing-interactive|marketech|little black book|\bLBB\b|campaign asia|mumbrella", re.I)
PRODUCT_WORDS = re.compile(r"\bPRU[A-Z][a-z]|\b(plan|insurance|product|cover|coverage|protection|annuity|medical|policy|rider|series|saver)\b|保險|計劃|保障|年金|醫保", re.I)
# Activity overrides - group-level financial results are corporate, not product/campaign activity
RESULTS_RX = re.compile(r"re-?domicil|遷冊|\b(Q[1-4]|first[- ]half|1H|H1|third[- ]quarter|interim|core earnings|new business (value|profit)|VONB)\b|業績|新業務價值|新業務利潤", re.I)


def clean_html(s: str) -> str:
    s = html.unescape(html.unescape(s)).replace("\xa0", " ")
    s = re.sub(r"\b(logo\s+){2,}", "", s, flags=re.I)  # image alt-text residue from news cards
    return re.sub(r"[ \t]+", " ", s).strip()


# URL-level noise (mostly from search-API extracts): listing/index pages, people profiles, off-target sites
URL_NOISE = [
    ("person_profile", re.compile(r"linkedin\.com/in/", re.I)),
    ("index_page", re.compile(r"/(news-?room|media-centre|press-releases?|blog/[a-z]+|blog|tags?/[^/]+|category/[^/]+|important-notice/\d{4}|"
                              r"important-notice|investment-notice/[^/]+|article)/?$|listpage-|/tag/|/archives?/?$", re.I)),
    ("off_target_site", re.compile(r"wikipedia\.org|leasinghub\.com|careers\.|/job/|aiahk\.org|hkexnews\.hk", re.I)),
]
INDEX_TITLES = re.compile(r"^(新聞中心|news ?room|重要通知|newsdetail|news release|press release|flexi notices|.*mediaroom_page.*|"
                          r"betterme blog|.* archives - .*|.* - 香港財經時報 HKBT)(\s*\|.*)?$", re.I)
STALE_YEAR = re.compile(r"\b(20(0\d|1\d|2[0-4]))\b")
FRESH_YEAR = re.compile(r"\b202[5-9]\b")
# official consumer-education content (blogs / knowledge corners) -> M2 customer education, not an M1 development
EDU_URL = re.compile(r"axa\.com\.hk/[a-z-]+/blog/|prudential\.com\.hk/[a-z-]+/knowledge-corner/|aia\.com\.hk/[a-z-]+/.*/(articles?|insights)/|manulife\.com\.hk/.*/(articles?|insights)/", re.I)


# Other markets: subject is a non-HK entity (title judged without its trailing " - Publisher" suffix).
# 保誠人壽 = Prudential's Taiwan life entity; 友邦 also means "diplomatic ally" in Taiwanese news.
OTHER_MARKET = re.compile(r"singapore|philippines|\bindia\b|indonesia|malaysia|vietnam|thailand|taiwan|japan|cambodia|sri lanka|"
                          r"台灣|台幣|新台幣|台北|保誠人壽|友邦人壽|新加坡|馬來西亞|印尼|越南|泰國|日本|菲律賓|帛琉|邦交|"
                          r"john hancock|jackson financial|PGIM", re.I)
TW_PUBLISHERS = re.compile(r"自由時報|自由財經|自由軍武|中央社|三立|ETtoday|風傳媒|今周刊|旺得富|換日線|台灣民眾|Yahoo股市|CSR@天下|"
                           r"墨新聞|原住民族|Taiwan News|聯合新聞網|udn|鉅亨|工商時報|中時|TVBS|民視|經濟日報.*(udn|money)", re.I)
HK_TERMS = re.compile(r"hong kong|\bHK\b|香港|港人|GBA|greater bay|大灣區|macau|澳門|港澳", re.I)
BRAND_RX = {"Prudential": re.compile(r"prudential|保誠|\bPRU", re.I), "AIA": re.compile(r"\bAIA|友邦"),
            "Manulife": re.compile(r"manulife|宏利", re.I), "AXA": re.compile(r"\bAXA|安盛", re.I)}
# headline subject is another insurer (our brand only mentioned in passing)
OTHER_SUBJECT = re.compile(r"^\W*(FWD|Sun Life|HSBC Life|HSBC|Chubb|Zurich|BOC Life|Bupa|Generali|FTLife|China Life|YF Life|Allianz|"
                           r"Great Eastern|Blue Cross|Bowtie|Hang Seng|AIA|AXA|Manulife|Prudential|富衛|安達|永明|滙豐|中銀人壽|"
                           r"周大福人壽|富通|萬通|保柏|蘇黎世|忠意|中國人壽|中國太平|國壽|信諾|港交所|HKEX|星展|DBS|友邦|安盛|宏利|保誠)", re.I)
PUB_SUFFIX = re.compile(r"\s+[-|–]\s+[^-|–]{2,60}$")


def noise_reason(rec: dict) -> str | None:
    extra = rec.get("extra") or {}
    vendor = extra.get("exclude_reason")
    if vendor:  # out-of-scope rows from the imported workbooks keep the vendor's documented reason
        return vendor
    t = rec.get("title") or ""
    for name, rx in NOISE:
        if rx.search(t):
            return name
    if rec.get("record_type") in ("announcement", "news_article"):
        core = PUB_SUFFIX.sub("", t)
        if (OTHER_MARKET.search(core) and not HK_TERMS.search(core)) or TW_PUBLISHERS.search(rec.get("source_name") or ""):
            return "other_market"
        if (rec.get("source_category") != "official" and not extra.get("explorium_event")
                and rec.get("brand") in BRAND_RX and not BRAND_RX[rec["brand"]].search(t + " " + (rec.get("description") or "")[:300])):
            return "brand_not_in_headline"
        m = OTHER_SUBJECT.search(core)
        if (m and rec.get("brand") in BRAND_RX and not BRAND_RX[rec["brand"]].search(m.group(1))
                and not BRAND_RX[rec["brand"]].search(core[:60])):
            return "other_brand_subject"
        url = rec.get("source_url") or ""
        for name, rx in URL_NOISE:
            if rx.search(url):
                return name
        if INDEX_TITLES.search(t.strip()):
            return "index_page"
        # an old development re-captured with a new date (e.g. a 2019 award page) is not new activity
        if STALE_YEAR.search(t) and not FRESH_YEAR.search(t):
            return "rediscovered_old_content"
    return None


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").lower()


def _hits(text: str, kws: list[str]) -> int:
    n = 0
    for kw in kws:
        k = kw.lower()
        if re.search(r"[一-鿿]", k):
            n += k in text
        else:
            n += bool(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text))
    return n


def match_dict(text: str, d: dict) -> list[str]:
    return [k for k, v in d.items() if isinstance(v, dict) and _hits(text, v.get("en", []) + v.get("zh", []))]


def activity_type(rec: dict) -> str:
    if rec["record_type"] == "social_post":
        return "social_post"
    if rec["record_type"] in ("app_snapshot",):
        return "app_update"
    if rec["record_type"] == "app_review":
        return "app_review"
    if rec["record_type"] == "web_feature":
        return "digital_capability"
    if rec["record_type"] == "content_article":
        return "customer_education"
    raw_title = rec.get("title") or ""
    title = _norm(raw_title)
    if RESULTS_RX.search(raw_title):
        return "corporate_announcement"
    if SPONSOR_RX.search(raw_title):
        return "sponsorship_community"
    if re.search(r"(brand|advertising|marketing) campaign|品牌宣傳|廣告", raw_title, re.I):
        return "campaign"
    acts = TAXONOMY["activity_types"]
    is_product = bool(PRODUCT_WORDS.search(raw_title))

    def pick(text, allow_launch):
        for a in TAXONOMY["activity_priority"]:
            if a == "product_launch" and not allow_launch:
                continue
            if _hits(text, acts[a]["en"] + acts[a]["zh"]):
                return a
        return None

    a = pick(title, allow_launch=is_product)
    if a in (None, "product_launch", "corporate_announcement", "service_enhancement") and CAMPAIGN_PUBLISHERS.search(
            (rec.get("source_name") or "") + " " + raw_title) and not (a == "product_launch"):
        return "campaign"
    if a:
        return a
    body = _norm((rec.get("description") or "") + " " + (rec.get("original_content") or "")[:600])
    return pick(body, allow_launch=False) or "other"


PRODUCT_NAME_RX = [
    re.compile(r"\b(PRU[A-Za-z]+(?:\s+(?:Hong Kong|[A-Z][A-Za-z+]+)){0,3})"),
    re.compile(r"\b(?:AIA|AXA|Manulife)\s+((?:[A-Z][A-Za-z+]*\s+){0,5}(?:Plan|Insurance|Annuity|Protection|Saver|Series|Medical Insurance)(?:\s+\d+)?)"),
    re.compile(r"(?:launch(?:es|ed)?|unveils|introduces)\s+(?:the\s+|its\s+|new\s+|first-in-market\s+|brand new\s+)*([A-Z][A-Za-z+]+(?:\s+[A-Z][A-Za-z+.]+){0,5})"),
    re.compile(r"[「《]([^」》]{2,20})[」》]"),
]


def product_name(rec: dict) -> str | None:
    t = rec.get("title") or ""
    for rx in PRODUCT_NAME_RX:
        m = rx.search(t)
        if m:
            name = m.group(1).strip(" ,.-")
            name = re.sub(r"^(Unveils|Launches|Launch|Introduces|Debuts|Rolls Out)\s+", "", name)
            name = re.sub(r"\s+(to|for|with|a|an|the|meeting|amid|amidst)$", "", name)
            if len(name) > 3 and not name.lower().startswith(("brand new ai", "new business")):
                return name
    return None


# Module 5 (optional): distribution channels, intermediaries, agency force and talent signals
DIST_RX = re.compile(r"bancassurance|banca|agency|agents?|advisers?|advisors?|broker|distribution|financial (planner|consultant)s?|"
                     r"MDRT|wealth (centre|center|hub)|office|headquarters|recruit|talent|chief distribution|appoint|"
                     r"銀保|代理|經紀|分銷|財務策劃|理財顧問|顧問團隊|總部|樓面|委任|招聘|人才", re.I)
TOOL_RX = re.compile(r"underwrit|AI tool|chatbot|platform|核保|direct billing|partnership", re.I)


def classify(rec: dict) -> dict:
    for k in ("title", "description", "original_content"):
        if rec.get(k):
            rec[k] = clean_html(rec[k])
    if rec["record_type"] in ("announcement", "news_article") and EDU_URL.search(rec.get("source_url") or ""):
        rec["record_type"] = "content_article"
        rec["content_format"] = "blog_article"
    text =_norm(" ".join([rec.get("title") or "", rec.get("description") or "", (rec.get("original_content") or "")[:1500]]))
    title_desc = _norm((rec.get("title") or "") + " " + (rec.get("description") or ""))
    rec["activity_type"] = rec.get("activity_type") if rec["record_type"] in ("web_feature",) else activity_type(rec)
    fb = (rec.get("extra") or {}).get("vendor_activity_fallback")
    if rec["activity_type"] == "other" and fb:  # classifier found nothing: fall back to the source's own label (kept auditable)
        rec["activity_type"] = fb
        rec["extra"]["activity_basis"] = "source label (rule-based classifier found no match)"
    # product categories: from title/description (and body for official releases)
    basis = text if rec.get("source_category") == "official" or rec["record_type"] == "social_post" else title_desc
    cats = match_dict(basis, TAXONOMY["product_categories"])
    themes = match_dict(text if rec["record_type"] != "news_article" else title_desc, TAXONOMY["themes"])
    caps = []
    if rec["record_type"] in ("app_snapshot", "announcement", "news_article"):
        caps = match_dict(_norm((rec.get("original_content") or "") + " " + (rec.get("description") or "") + " " + (rec.get("title") or "")),
                          TAXONOMY["digital_capabilities"]) if rec["record_type"] == "app_snapshot" else []
    if rec["record_type"] == "web_feature":
        caps = [rec["extra"]["capability"]]
    rec["tags"] = {"product_category": cats, "theme": themes, "digital_capability": caps}

    mods = set(rec.get("modules") or [])
    if rec["record_type"] == "content_article":
        mods = {"M2"}
    a = rec["activity_type"]
    is_tool = bool(TOOL_RX.search(rec.get("title") or ""))  # internal/digital tools are M4, not insurance products
    if a in ("product_launch", "product_enhancement") and cats and not is_tool:
        mods.add("M3")
        rec["product_name"] = rec.get("product_name") or product_name(rec)
    if is_tool:
        mods.add("M4")
    if a in ("campaign",) or rec["record_type"] == "social_post":
        mods.add("M2")
    if a == "service_enhancement" or "digital_innovation" in themes and rec["record_type"] in ("announcement", "news_article"):
        mods.add("M4")
    if rec["record_type"] in ("announcement", "news_article") and DIST_RX.search(rec.get("title") or "")             and a in ("partnership", "corporate_announcement", "award_recognition", "product_enhancement", "service_enhancement"):
        mods.add("M5")
    rec["modules"] = sorted(mods)

    # English summary: English source -> description/lead; Chinese -> left for translation step (flagged)
    if rec["language"] == "en":
        lead = rec.get("description") or (rec.get("original_content") or "")[:400]
        rec["english_summary"] = rec.get("english_summary") or (lead[:400] if lead else rec.get("title"))
    rec["translation_status"] = "not_required" if rec["language"] == "en" else ("done" if rec.get("english_summary") else "pending")
    return rec


# ------------------------------------------------------------------ duplicate / syndication clustering
def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    ta, tb = set(re.findall(r"[a-z0-9]+|[一-鿿]", a)), set(re.findall(r"[a-z0-9]+|[一-鿿]", b))
    jac = len(ta & tb) / max(1, len(ta | tb))
    return max(jac, SequenceMatcher(None, a, b).ratio())


STOP_PROPER = {"prudential", "aia", "axa", "manulife", "hong", "kong", "hk", "the", "and", "with", "new", "launches", "group",
               "limited", "macau", "insurance", "its", "for", "a", "an", "of", "in", "to", "on", "at", "first", "asia", "china",
               "chinese", "mainland", "international", "company", "plan", "ai", "q1", "q2", "q3", "q4", "2025", "2026", "yahoo",
               "finance", "news", "update", "says", "how", "why", "what", "inside", "selected", "among", "batch", "sign", "signs"}


GENERIC = {"expands", "expanded", "partnership", "partners", "partner", "launch", "launched", "wins", "win", "award", "awards",
           "strategic", "long-term", "health", "medical", "digital", "customers", "customer", "market", "business", "life",
           "services", "service", "announces", "joins", "unveils", "introduces", "protection", "retirement", "wealth", "survey",
           "study", "report", "growth", "rise", "rises", "falls", "profit", "earnings", "new", "brand", "community", "plans"}


def proper_tokens(title: str) -> set[str]:
    toks = re.findall(r"[A-Z][A-Za-z+.&'-]{2,}|\d{2,}[,.]?\d*", unicodedata.normalize("NFKC", title or ""))
    return {t.lower().strip(".,'") for t in toks if t.lower().strip(".,'") not in STOP_PROPER}


DF: collections.Counter = collections.Counter()  # token document frequency across titles (set in cluster())


def cjk_bigrams(s: str) -> set[str]:
    c = "".join(re.findall(r"[一-鿿]", s or ""))
    return {c[i:i + 2] for i in range(len(c) - 1)}


BOILERPLATE = re.compile(r"\b(prudential|aia|axa|manulife|hong kong|macau|and macau|limited|ltd|hk|group|insurance company)\b|"
                         r"保誠|友邦|安盛|宏利|香港|澳門|保險", re.I)
WIRE_TOKENS = {"media", "outreach", "newswire", "prnewswire", "pr", "south", "morning", "post", "times", "business", "manila",
               "malaysian", "reserve", "journal", "daily", "online", "standard", "review", "network", "canada", "canadian",
               "insurer", "insurers", "exclusive", "announces", "appoints", "veteran"}


def core_title(t: str) -> str:
    """Title without publisher suffix and brand/HK boilerplate - what the headline is actually about."""
    t = PUB_SUFFIX.sub("", PUB_SUFFIX.sub("", t or ""))
    t = re.sub(r"#\S+", " ", t)
    return re.sub(r"\s+", " ", BOILERPLATE.sub(" ", t)).strip()


def same_event(a: dict, b: dict, days_apart: int) -> bool:
    ta, tb = core_title(a["title"]), core_title(b["title"])
    if len(ta) >= 12 and len(tb) >= 12 and _sim(ta, tb) >= 0.6:
        return True
    shared = (proper_tokens(ta) & proper_tokens(tb)) - GENERIC - WIRE_TOKENS
    if len(shared) >= 2:
        return True
    # one rare shared name (e.g. BytePlus, IGC, Swire) within 3 days links EN/ZH coverage of the same event
    if days_apart <= 3 and any(DF[t] <= 8 and len(t) >= 3 and not t.isdigit() for t in shared):
        return True
    ba, bb = cjk_bigrams(a["title"]), cjk_bigrams(b["title"])
    if days_apart <= 3 and ba and bb and len(ba & bb) / len(ba | bb) >= 0.22:
        return True
    return False


LANG_SEG = re.compile(r"/(en|en-hk|zh|zh-hk|zh-hant|zh-tw|tc|sc|cn|hk-en|hk-zh)(?=/)", re.I)


def url_key(u: str | None) -> str:
    """Language-neutral URL: /en/... and /zh-hk/... versions of the same official release collapse to one event."""
    u = (u or "").split("?")[0].split("#")[0].rstrip("/").lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    return LANG_SEG.sub("", u)


def cluster(records: list[dict], days: int = 10, thresh: float = 0.55) -> None:
    """Assign cluster_id; the official (else earliest) instance is primary. Other instances stay as corroborating sources."""
    import datetime as dt
    items = [r for r in records if r["record_type"] in ("announcement", "news_article")]
    items.sort(key=lambda r: (r["brand"], r["publication_date"] or ""))
    DF.clear()
    for r in items:
        DF.update(proper_tokens(r["title"]))
    clusters: list[list[dict]] = []
    for r in items:
        placed = False
        for c in clusters:
            head = c[0]
            if head["brand"] != r["brand"]:
                continue
            d0 = dt.date.fromisoformat(head["publication_date"])
            d1 = dt.date.fromisoformat(r["publication_date"])
            same_url = any(url_key(x["source_url"]) == url_key(r["source_url"]) for x in c)
            if same_url or (abs((d1 - d0).days) <= days and any(
                    same_event(r, x, abs((d1 - dt.date.fromisoformat(x["publication_date"])).days)) for x in c)):
                c.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])
    for c in clusters:
        c.sort(key=lambda x: (x["source_category"] != "official", x["publication_date"], x["record_type"] != "announcement"))
        cid = c[0]["record_id"]
        for i, x in enumerate(c):
            x["cluster_id"] = cid
            x["is_primary"] = i == 0
            x["cluster_size"] = len(c)
            x["cluster_sources"] = len({y["source_name"] for y in c})
    for r in records:
        r.setdefault("cluster_id", r["record_id"])
        r.setdefault("is_primary", True)
        r.setdefault("cluster_size", 1)
        r.setdefault("cluster_sources", 1)
