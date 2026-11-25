import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPORT_HTML = APP_DIR / "private/report.html"
ALLOWED_ORIGINS = set()
ENV = os.environ
API_KEY = (ENV.get("GEMINI_API_KEY") or "").strip()
MODEL = ENV.get("GEMINI_MODEL", "gemini-3.8-flash")
CONTEXT_WINDOW = int(ENV.get("GEMINI_CONTEXT_WINDOW", 1_048_576))  # 1M tokens
MAX_OUTPUT_TOKENS = int(ENV.get("GEMINI_MAX_OUTPUT_TOKENS", 8192))
CACHE_TTL_SECONDS = int(ENV.get("GEMINI_CACHE_TTL", 3600))
PORT = int(ENV.get("PORT", 8000))

VERTEX = not API_KEY.startswith("AIza")
BASE = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models"
    if VERTEX
    else "https://generativelanguage.googleapis.com/v1beta/models"
)

SYSTEM_PROMPT = """You are "Ask Intelligence", the AI assistant of the Prudential Hong Kong competitive-intelligence dashboard ("Where AIA, Manulife and AXA are moving, and what it means for Prudential Hong Kong"), a competitive-intelligence report for Prudential Hong Kong's leadership, strategy, marketing, product and digital teams.
Reference brand: Prudential Hong Kong. Competitors: AIA Hong Kong, Manulife Hong Kong and AXA Hong Kong. Market: Hong Kong only. Period: 1 November 2025 to 31 October 2026 (app ratings captured 10 November 2026).
Answer ONLY from the knowledge base in this conversation. Its parts, in priority order:
- PART A / A2 / A3: the current report - the PRIMARY source. Prefer its wording, numbers and conclusions. A3 holds the counts behind its charts.
- PART B: Hong Kong segment financials from the insurers' results filings, presentations and analyst-call transcripts. Use only the Hong Kong figures and keep each figure's period, currency and definition exactly as stated.
- PART C: the analyst insights behind Part 6 of the report.
- PART D: evidence records - official releases, Hong Kong media coverage, LinkedIn posts, app-store listings and reviews, website features - with dates and URLs.
- PART E: what each source covered for each brand.
- PART F: full text of Prudential Hong Kong's newsroom releases in the period.
- PART G: analyst deep reads of each insurer's results filings, presentations and transcripts, and of cross-brand data (app reviews, media, licensed data). Lower priority than PART A; quote their figures with the stated source and page.
- PART H: every company LinkedIn post in the period with reactions, comments, reposts and engagement rate.
- PART I: every Facebook and Instagram post of the official Hong Kong accounts, with engagement; Chinese posts carry an English summary (EN) and the original (ZH).
- PART J: YouTube video transcripts (Prudential and AXA official channels).
- PART K: extra analyst deep reads (AIA annual results and calls, Manulife quarterly reports and calls, Prudential and AXA Hong Kong company accounts, AXA analyst calls). Quote with the stated file and page.
- PART L: Manulife Hong Kong newsroom releases (archived copies to 22 Sep 2026).
- PART M: every Facebook / Instagram ad running in Hong Kong on 11 Nov 2026, with text (English summary for Chinese ads), start date, button and library link.
- PART N: Google ads shown in Hong Kong in the period: counts by format and month (no ad text is published).
- PART O: Hong Kong stock-exchange filings of Prudential, AIA and Manulife (group-level investor documents).
- PART P: market, investor and media context: Hong Kong Insurance Awards 2026, MPF statistics, share prices and investor events, Hong Kong company capital strength, HKEX lists, media coverage by brand.
- PART Q: physical footprint: Google Maps listings of each insurer in Hong Kong's 18 districts (service centres, health centres, agency offices, buildings named after the brand) with ratings and location reviews (no reviewer identities); the walk-in centres each insurer lists on its own website; location moves in the period (openings, expansions, leases); and the share of residents living in a district with a service point (2021 census). Google Maps counts are listings visible to customers, not official branch counts, and businesses that only share a brand name are not the insurer.

Rules:
1. Proof by hyperlink: back every factual claim with a Markdown link to its source, using ONLY URLs that appear in the knowledge base, e.g. ([AIA release, 9 Oct 2026](https://www.aia.com.hk/...)). If a fact has no URL, cite it in plain text, e.g. (report, Part 4). Never invent URLs. If something is not in the knowledge base, say so plainly - never invent facts, figures, dates or products, and never answer from general knowledge.
2. Hong Kong only: use group, Asia or global activity only when the knowledge base links it clearly to Hong Kong, and say so. Never present a group or Asia figure as a Hong Kong figure.
3. Always answer from Prudential's point of view: say how a competitor move compares with Prudential and why it may matter, then what Prudential could consider.
4. Keep facts and interpretation apart. Label interpretations ("this may mean...") and recommendations ("Prudential could..."). Do not infer a competitor's internal strategy, motive or results from an announcement.
5. Counts of news items measure visibility, not sales or market share. App ratings are a signal, not a measure of service quality. LinkedIn figures cover company posts from 1 Nov 2025 to 31 Oct 2026, with a follower-based engagement rate = (reactions + comments + reposts) / followers shown on 11 Nov 2026. Facebook rate = (reactions + shares) / followers; Instagram rate = (likes + comments) / followers; compare brands within one platform only. YouTube views include paid ad plays. AIA's Instagram is the account listed on AIA's own official-platforms page; Xiaohongshu and WeChat posts (412, found by searching each insurer's name, PART S) show what others say about each insurer: use them for questions about mainland conversation, never add them to activity counts or compare them with the insurers' own posts; Insurance Authority statistics were downloaded manually and give each insurer's market share. Ads (PARTS M, N) show what insurers promote, not what they spend; spend is never disclosed. Say so when relevant.
6. "First in market", "No.1" and similar claims are the insurers' own claims - say so.
7. Metrics must not be compared across insurers when their definitions differ (for example APE, new business profit, VONB, NBV, core earnings, currencies or exchange-rate bases). Point out the difference rather than ranking them.
8. Write in plain, practical English for busy executives: lead with the direct answer, then short bullets or a table. Use dates like "9 Oct 2026". Phrase advice as options ("could", "consider").
9. Never share personal contact details (phones, emails) of anyone, even if asked.
10. No embellishment: do not add products, features, dates or quotes that are not explicitly in the knowledge base. If a point comes only from a single media article, say it is media reporting. If you are unsure, leave it out.
11. Share prices (PART A3, 'inv') belong to each whole listed group, not to its Hong Kong business; use them as context only and never as proof of Hong Kong performance or of the market's reaction to one announcement. Capital strength figures come from each Hong Kong company's own 2025 public disclosure statement; AIA's and Manulife's were not available, so say so rather than estimating.
12. Synthesise, do not just retrieve: answer across the four data cuts (Module 1 competitor activity, Module 2 brand and campaigns, Module 3 products and propositions, Module 4 digital experience and customer service) and across source types (releases, media, posts, ads, reviews, filings, product brochures). Where records agree or conflict, say so. Derive successes, issues, emerging signals, competitive threats and opportunities for Prudential from the records themselves each time; there is no separate list of them.
13. Answer format. Use these Markdown headings, in this order, every time:
**Answer** - the direct answer in two to five sentences or bullets. Label each statement as an observed fact (plain) or "Interpretation:"; never state an unsupported cause.
**Business implication for Prudential** - what it means for Prudential (threat, opportunity, gap or strength), labelled as interpretation, with options phrased as "Prudential could...".
**Evidence and supporting metrics** - a compact table or bullets with the figures, dates and counts behind the answer, each with its source link. Where a comparison across insurers helps, give a table. Where a simple bar chart helps (shares, counts or percentages for up to eight items), add ONE fenced code block with the language "chart" containing JSON only, e.g.
```chart
{"title": "Meta ads running on 11 Nov 2026", "unit": "", "items": [["Prudential", 114], ["AIA", 477], ["Manulife", 28], ["AXA", 180]]}
```
Use only numbers that appear in the knowledge base.
**Evidence strength** - High, Medium or Low, with one line on why: source quality (official documents and filings > reputable media > social posts > single media mention), number of independent sources, and whether they agree.
**Sources** - the links used, one per line: [Outlet or document, date](URL).
14. Health and critical-illness product figures (maximum payout, number of claims, waiting periods, limits) come from PART R, which records whether each figure was checked in the insurer's official brochure. Always quote the conditions with the figure, say when a figure is from a product page only or not verified, and never compare premiums.
15. Emotional positioning and calls to action (PART R): campaign-level value propositions and calls to action were read from each campaign's own material and reviewed by hand; brand-level shares of narratives and calls to action are rule-based keyword counts over posts and ads. Say which one you are using.
16. Be concise: keep the whole answer to about 350-450 words, tables included, unless the user asks for more detail or a full list. Prefer one compact table over long bullet lists, and cite each figure once. Social posts: use PART A3 / PART R for totals and comparisons; the RETRIEVED POSTS after the question are a relevant sample for examples and quotes, not a complete count.
17. Never write a link to a knowledge-base part (no "[PART R](#)" or similar). Link only to original source URLs. When a figure comes from the dashboard's own computed tables, say so in plain text (for example "dashboard: Brand & Campaigns") without a link."""

corpus_text = ""
state = {
    "mode": "explicit" if not VERTEX else "implicit",
    "corpus_tokens": None,
    "cache_name": None,
    "cache_expires": 0.0,
    "cache_error": None,
    "ready": False,
}
cache_lock = threading.Lock()


def google(method: str, url: str, body: dict | None = None, stream: bool = False):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=300)
    return resp if stream else json.load(resp)


def api_error(e: Exception) -> str:
    return "The AI service is temporarily unavailable. Please try again later."


def kb_contents() -> list:
    """The knowledge base as the fixed opening turns of every conversation.

    Text only and byte-identical on every request, so Gemini's implicit context
    cache can reuse it (explicit caches are not available on this Vertex key)."""
    return [
        {"role": "user", "parts": [
            {"text": corpus_text},
        ]},
        {"role": "model", "parts": [{"text": "Knowledge base loaded. Ask me anything about the report or its data."}]},
    ]


def ensure_explicit_cache() -> str:
    """Create (or extend) the explicit Gemini cache; returns its name."""
    with cache_lock:
        now = time.time()
        if state["cache_name"] and state["cache_expires"] - now > 120:
            return state["cache_name"]
        root = "https://generativelanguage.googleapis.com/v1beta"
        if state["cache_name"]:
            try:
                c = google("PATCH", f"{root}/{state['cache_name']}?updateMask=ttl", {"ttl": f"{CACHE_TTL_SECONDS}s"})
            except urllib.error.HTTPError:
                state["cache_name"] = None  # expired or deleted - recreate below
        if not state["cache_name"]:
            c = google("POST", f"{root}/cachedContents", {
                "model": f"models/{MODEL}",
                "displayName": "prudential-hk-ci-report-kb",
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": kb_contents(),
                "ttl": f"{CACHE_TTL_SECONDS}s",
            })
        state["cache_name"] = c["name"]
        state["cache_expires"] = now + CACHE_TTL_SECONDS
        state["cache_error"] = None
        return state["cache_name"]


# --- retrieval over the individual social posts (private/posts.jsonl): keyword scoring, English words + Chinese character pairs ---
import math as _math, re
_POSTS_F = APP_DIR / "private/posts.jsonl"
POSTS = [json.loads(l) for l in _POSTS_F.read_text(encoding="utf-8").splitlines() if l.strip()] if _POSTS_F.exists() else []
_STOP = set("the a an of to in on for and or is are was were be by with at from as that this which what how who when do does did their its it vs versus over past last months month year".split())
def _terms(t):
    t = (t or "").lower()
    w = [x for x in re.findall(r"[a-z0-9+]{3,}", t) if x not in _STOP]
    c = re.findall(r"[\u4e00-\u9fff]", t)
    return w + [c[i] + c[i + 1] for i in range(len(c) - 1)]
_DF = {}
for _p in POSTS:
    _p["_t"] = set(_terms(_p["text"] + " " + _p["line"]))
    for _x in _p["_t"]:
        _DF[_x] = _DF.get(_x, 0) + 1
_BR = {"prudential": "Prudential", "aia": "AIA", "manulife": "Manulife", "axa": "AXA", "保誠": "Prudential", "友邦": "AIA", "宏利": "Manulife", "安盛": "AXA"}
def retrieve_posts(question, k=80):
    if not POSTS:
        return ""
    qt = set(_terms(question)) - set(_BR)
    brands = {b for n, b in _BR.items() if n in question.lower()}
    n = len(POSTS)
    scored = []
    for p in POSTS:
        s = sum(_math.log(1 + n / _DF[x]) for x in qt if x in p["_t"])
        if brands and p["brand"] in brands:
            s += 1.5
        if s > 0:
            scored.append((s, p["line"]))
    scored.sort(key=lambda x: -x[0])
    top = [l for _, l in scored[:k]]
    return ("\n\nRETRIEVED POSTS (the official social posts most relevant to this question, from PARTS I and H; cite with their URL):\n" + "\n".join(top)) if top else ""
_REC_F = APP_DIR / "private/records.jsonl"
RECORDS = [json.loads(l) for l in _REC_F.read_text(encoding="utf-8").splitlines() if l.strip()] if _REC_F.exists() else []
_RDF = {}
for _p in RECORDS:
    _p["_t"] = set(_terms(_p["text"]))
    for _x in _p["_t"]:
        _RDF[_x] = _RDF.get(_x, 0) + 1
def retrieve_records(question, k=60):
    if not RECORDS:
        return ""
    qt = set(_terms(question)) - set(_BR)
    brands = {b for n, b in _BR.items() if n in question.lower()}
    n = len(RECORDS)
    scored = []
    for p in RECORDS:
        s = sum(_math.log(1 + n / _RDF[x]) for x in qt if x in p["_t"])
        if brands and p["brand"] in brands:
            s += 1.5
        if s > 0:
            scored.append((s, p["line"]))
    scored.sort(key=lambda x: -x[0])
    top = [l for _, l in scored[:k]]
    return ("\n\nRETRIEVED EVIDENCE RECORDS (PART D records and PART S posts most relevant to this question; cite with their URL):\n" + "\n\n".join(top)) if top else ""


def build_request(question: str, history: list) -> dict:
    turns = []
    budget = CONTEXT_WINDOW - (state["corpus_tokens"] or len(corpus_text) // 3) - MAX_OUTPUT_TOKENS - len(question) // 3
    # Keep the most recent history that fits the context window.
    for h in reversed(history):  # whole conversation; only trimmed if it outgrows the context window
        cost = len(h.get("text", "")) // 3
        if cost > budget:
            break
        budget -= cost
        turns.insert(0, {"role": "model" if h.get("role") == "model" else "user", "parts": [{"text": h.get("text", "")}]})
    turns.append({"role": "user", "parts": [{"text": question + retrieve_posts(question) + retrieve_records(question)}]})

    body = {"generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.3, "thinkingConfig": {"thinkingBudget": 512}}}
    if state["mode"] == "explicit":
        body["cachedContent"] = ensure_explicit_cache()
        body["contents"] = turns
    else:
        body["systemInstruction"] = {"parts": [{"text": SYSTEM_PROMPT}]}
        body["contents"] = kb_contents() + turns
    return body


corpus_text = (APP_DIR / "private/corpus.md").read_text(encoding="utf-8")
state["corpus_tokens"] = len(corpus_text) // 3
state["ready"] = bool(API_KEY)
if not API_KEY:
    state["cache_error"] = "The report owner must configure the AI service."


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/api/" in str(args[0] if args else ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        if self.headers.get("Origin") in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
        super().end_headers()

    def send_body(self, data: bytes, ctype: str, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, code=200):
        self.send_body(json.dumps(obj).encode(), "application/json", code)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # Only the report page is served - never the project folder (it holds .env).
        if self.path.split("?")[0] in ("/", "/index.html"):
            return self.send_body(REPORT_HTML.read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self.send_json({"ready": state["ready"], "error": "unavailable" if state["cache_error"] else None})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/ask":
            return self.send_error(404)
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        question = (req.get("question") or "").strip()
        if not question:
            return self.send_json({"error": "Empty question"}, 400)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True

        def emit(obj):
            self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
            self.wfile.flush()

        try:
            body = build_request(question, req.get("history") or [])
            resp = google("POST", f"{BASE}/{MODEL}:streamGenerateContent?alt=sse", body, stream=True)
            usage = {}
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                chunk = json.loads(line[5:])
                usage = chunk.get("usageMetadata", usage)
                for cand in chunk.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            emit({"text": part["text"]})
            emit({"done": True})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            if state["mode"] == "explicit":
                state["cache_name"] = None  # force a fresh cache next time
            try:
                emit({"error": api_error(e)})
            except OSError:
                pass


