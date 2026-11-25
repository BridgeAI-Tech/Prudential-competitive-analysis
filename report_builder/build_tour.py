"""Narrated guided tour for the Prudential Hong Kong competitive-intelligence report.

Records one clip per step into vercel_prudential_report/private/narration/pru/<step>.mp3 and injects the tour player
into the built report. Unchanged steps are not re-recorded. Steps without a recorded clip fall back to the browser's
own voice with timed captions, so the tour always works. Reuses the player from report_app/build_pa_tour.py.

    python -I report_app/prudential/build_tour.py --dry      # clips to record and the credit cost
    python -I report_app/prudential/build_tour.py            # record with ELEVENLABS_API_KEY, then inject
    python -I report_app/prudential/build_tour.py --key2     # record with ELEVENLABS_API_KEY2, then inject
    python -I report_app/prudential/build_tour.py --inject   # inject only (build.py runs this automatically)

The voice key is read from .env here only and never written into the app. Narration text must not contain personal
contact details, because it is sent to the voice service.
"""
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "report_app"))
import build_pa_tour as pa  # noqa: E402  (player markup and styles)

APP = ROOT / "vercel_prudential_report"
REPORTS = [APP / "private/report.html", ROOT / "Prudential/Prudential_HK_Competitive_Intelligence_Report.html"]
OUT = APP / "private/narration"
PERSONA = "pru"
VOICE = ("Alice", "Xb7hH8MSUJpSbSDYk0k2")  # default voice: British, female
MODEL = "eleven_multilingual_v2"
KBPS = 128
MAX_CREDITS = 15000   # across all keys given (each free key has about 10,000 a month)

# id, element to bring into view (the player opens its view first), player label, caption (the voice reads the same text)
STEPS = [
    ("intro", "#one", "Introduction",
     "Welcome to the Prudential Hong Kong competitive intelligence report. It compares Prudential with its three closest rivals in Hong Kong, "
     "AIA, Manulife and AXA, over twelve months, from November 2025 to October 2026. "
     "This tour walks through every part of the report in order, and explains what each part shows and how to use it. "
     "Use the tour bar to pause, go back, skip ahead, turn captions on or off, change the speed, or close the tour at any time."),
    ("bottom-line", "#one .op-box", "The bottom line",
     "We start with the leadership brief and its bottom line. Prudential is growing profit while its sales shrink. "
     "Profit from new policies rose eight percent in the first half of 2026, and its margin reached fifty-seven percent, but sales fell six percent. "
     "Manulife has pulled ahead on sales by accepting lower margins, and AIA remains the largest and most profitable rival. "
     "Below it, a table compares the four companies at a glance. Each insurer measures new business in its own way, so compare growth, not size. "
     "Every figure links to its source."),
    ("strengths", "#one .grid.g2", "Strongest and weakest points",
     "Next, where Prudential is strongest and weakest. Its strongest points are profit quality, sales through bank partners, which grew forty-eight percent, "
     "and cashless hospital billing across Hong Kong, the Greater Bay Area and Shanghai. "
     "Its weakest points are slower agency growth, a customer app rated about one star in recent reviews, and the smallest Google ad and YouTube reach. "
     "Each point has a Read more button that opens its sources."),
    ("summary", "#es", "Executive summary",
     "The executive summary puts the main story in one line: rivals are racing for wealthy, long-lived customers, and Prudential's edge is healthcare service. "
     "If Prudential does one thing, the report suggests joining that healthcare lead to a longevity and legacy proposition, and making it visible in myPrudential. "
     "Below that are five key findings, a live competitor timeline, and a product and digital comparison. "
     "These panels follow the filter bar, and you can click any tile, line, dot or row to see its sources."),
    ("scorecard", "#sw", "Scorecard",
     "The scorecard sets Prudential's strongest and weakest points side by side, each compared with its rivals and linked to its source. "
     "Under them is a suggested action plan, with timing, an owner and the evidence behind each action, "
     "followed by where each rival is strong and where it is exposed. "
     "Results are measured differently by each insurer, so read the direction, not the size."),
    ("profiles", "#profiles-v", "Company profiles",
     "The company profiles page sets out who each of the four insurers is in Hong Kong, what it sells and how it sells it, "
     "with links to each insurer's own product pages. A coverage table shows how much data this report holds for each one, "
     "so missing data is not mistaken for missing activity."),
    ("results", "#p1 .insight", "Hong Kong results",
     "Part one covers the Hong Kong market and each insurer's results. Demand was strong, with record new life premiums in early 2026. "
     "In August, reports of mainland tax notices on Hong Kong policies hit insurer shares, and some mainland visitors began to pause. "
     "For both Prudential and AIA, local customers drove the growth. "
     "The side-by-side table shows each insurer's sales, new business value and margin. "
     "Manulife grew sales fastest, up forty-five percent in the third quarter, but at a lower margin. "
     "The Insurance Authority's own figures then give each insurer's market share: in the first half of 2026 Prudential held four percent of new business premiums, "
     "rank eight, while Manulife rose to fifteen percent, second only to H S B C Life."),
    ("investors", "#inv", "Shares and capital",
     "Investors and capital. Over the year, Prudential's Hong Kong shares fell about twelve percent, close to the Hang Seng index, while Manulife's rose forty-one percent. "
     "Prudential's Hong Kong life company holds more than twice the capital the regulator requires."),
    ("awards", "#awards", "Industry awards",
     "Prudential won two of the seventeen Hong Kong Insurance Awards in 2026: excellence in digital transformation, and outstanding customer service in life insurance."),
    ("moves", "#tlBoard", "Competitor moves",
     "Part two tracks competitor activity. Counting official releases, articles and media stories together, Prudential had the most Hong Kong items in the period, "
     "narrowly ahead of Manulife and AIA. Prudential led on partnerships and customer education, AIA on product launches, and Manulife on campaigns. "
     "The board shows one column per insurer, newest first. Switch to the timeline or list view, use the type buttons to show only launches, "
     "health network moves, partnerships or campaigns, and click any card to open its source."),
    ("media", "#media", "Media coverage",
     "Media coverage. Prudential, AIA and Manulife each drew a little over a quarter of Hong Kong media stories. AXA drew less. "
     "Close to half of the coverage is in Chinese. Share of coverage measures visibility, not sales or sentiment."),
    ("brand", "#socAll", "Brand and social",
     "Part three covers brand, campaigns and customer messaging. Prudential, AXA and Manulife all built their 2026 campaigns around a celebrity, "
     "and AIA ran a brand film, so a famous face alone no longer sets a brand apart. The bigger difference is the message: "
     "wellness dominates the rivals' posts, yet it draws below-average engagement. "
     "Prudential posts less than its rivals, but each Facebook post gets the highest engagement of the four. "
     "The tables compare every platform, month by month and by theme, plus YouTube and paid ads."),
    ("detail", "#dpGlance", "Social, ads and search",
     "This page goes deeper on social media, ads and search. Two findings stand out. People search for Prudential by its Chinese name far more than its English one. "
     "And most of its Facebook and Instagram ads started only in October 2026, while AIA keeps ads running all year. "
     "Engagement here uses the middle post, so one viral post does not distort the picture. "
     "The page also compares how each insurer responded to the Tai Po fire."),
    ("products", "#p4", "Products",
     "Part four tracks product launches by customer segment. High-net-worth legacy and retirement income were the busiest segments, led by AIA. "
     "Prudential also launched four wealth and legacy plans in the first half, but publicised only one; "
     "its public launches went to young adults, newcomers and short trips to the Greater Bay Area. "
     "A heat map shows which product areas each brand is talked about for. Click a cell to see the items."),
    ("digital", "#apps", "Digital and apps",
     "Part five covers digital experience and customer service. Prudential's newest service, instant doctor booking and pre-authorisation, "
     "runs on a partner's platform rather than in myPrudential, while AIA+ and Manulife's app already bring the medical card, network doctors "
     "and wellness rewards into one place. Of the eighteen written iPhone reviews of myPrudential in the period, eight mention slow loading "
     "and seven mention failed log-ins. A feature table compares what each app offers."),
    ("footprint", "#footprint", "Branches and service centres",
     "Branches and service centres. On Google Maps, Prudential shows five service points in four districts, against sixteen for AIA, "
     "and its locations draw more negative reviews than AIA's or AXA's. AIA and AXA also run wellness or partner health centres; "
     "the district maps show where each insurer can be found."),
    ("insights", "#insights", "Insights",
     "The Insights tab brings the four core modules together: the key insight from each module, then a briefing for leadership: the one move to make, "
     "the question for the leadership team, what not to over-read, and what to watch most closely. Then come the five insights in full. "
     "Each one separates what the sources show from what it may mean, with a confidence level and a Read more list of every source behind it. "
     "There is also a thirty-second briefing you can copy for a meeting."),
    ("explorer", "#explorer", "Evidence",
     "The Evidence tab holds every record behind the dashboard: releases, media stories, posts, ads, stock exchange filings and awards, each with its source link. "
     "Pick a brand to see only that insurer's records, search in English or Chinese, and use the buttons to choose a record type. "
     "Chinese records show an English summary with the original underneath."),
    ("watch", "#watch", "What to watch next and data coverage",
     "Part seven lists what to watch next: AXA's savings product renames from sixteen November, Manulife's new cross-border direct billing with Ant Health "
     "launched on ten November, the next intake of the Gen A I Sandbox, monthly app ratings, and the Insurance Authority's quarterly statistics. "
     "Below it, two tables show how complete the data is for each brand and source, and how the sources were searched. "
     "The notes after them explain the limits of the evidence behind this report."),
    ("filters", ".fbar", "Filters",
     "The filter bar at the top narrows every live panel by period, brand, module, category and platform. Click one brand to see that insurer alone. "
     "Each option shows how many records it leaves, and panels with no data are hidden with a note."),
    ("close", ".fab", "End of the tour",
     "That is the end of the tour. To go further, use Ask Intelligence, at the bottom right: it answers questions from the dashboard's own sources, "
     "and each section has its own Ask about this button. Blue underlined text always links to the source. "
     "You can replay this tour at any time from the Guided tour button at the top."),
]
SAY = [(r"\bAIA\+", "A I A plus"), (r"\bAIA\b", "A I A"), (r"\bAXA\b", "Axa"), (r"\bAIA's\b", "A I A's"), (r"\bAXA's\b", "Axa's"),
       (r"\bmyPrudential\b", "my Prudential")]


def say(t):
    for a, b in SAY:
        t = re.sub(a, b, t)
    return t


def key_names():
    """Keys to use, in the order given: --key2 / --key3 / --key4 (any combination); default ELEVENLABS_API_KEY.
    When one key is refused or runs out of credits, recording moves on to the next."""
    names = [{"--key2": "ELEVENLABS_API_KEY2", "--key3": "ELEVENLABS_API_KEY3", "--key4": "ELEVENLABS_API_KEY4",
              "--key5": "ELEVENLABS_API_KEY5", "--key6": "ELEVENLABS_API_KEY6"}[a]
             for a in sys.argv if a in ("--key2", "--key3", "--key4", "--key5", "--key6")]
    return names or ["ELEVENLABS_API_KEY"]


def api_key(name):
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return ""


KEYS = []   # remaining (name, key) pairs; the first one is in use


def record(text, dest):
    if not KEYS:
        KEYS.extend((n, api_key(n)) for n in key_names() if api_key(n))
    while KEYS:
        name, key = KEYS[0]
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE[1]}?output_format=mp3_44100_{KBPS}",
                                     data=json.dumps({"text": text, "model_id": MODEL}).encode(),
                                     headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            dest.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            return True
        except urllib.error.HTTPError as e:
            body = e.read()[:300]
            if e.code in (401, 402, 403, 429) or b"quota" in body:
                print(f"  {name} refused {dest.name} ({e.code}): moving to the next key")
                KEYS.pop(0)
                continue
            print(f"  voice service refused {dest.name}: {e.code} {body[:200]!r}")
            return False
    print("  no keys left with credits")
    return False


def player():
    p = pa.PLAYER
    for a, b in [('($("#who") || {}).value || "nova"', '"pru"'), ('"pa-tour-', '"pru-tour-'),
                 ("the company, the person and the Palo Alto plays", "Prudential's position, its rivals' moves and what to do next"),
                 ("narration/<persona>/<step>.mp3, built by report_app/build_pa_tour.py", "narration/pru/<step>.mp3, built by report_app/prudential/build_tour.py"),
                 # this report has views: open the step's view before scrolling to it
                 ("clearHi(); const el = document.querySelector(S.to);",
                  "clearHi(); let el = document.querySelector(S.to); if (el && typeof viewOf === \"function\" && typeof showView === \"function\") { const v = viewOf(el); if (v && !document.getElementById(v).classList.contains(\"on\")) showView(v, null, false); el = document.querySelector(S.to); }")]:
        assert a in p, a
        p = p.replace(a, b)
    return p


def inject():
    rows = []
    for sid, to, label, text in STEPS:
        f = OUT / PERSONA / f"{sid}.mp3"
        rows.append({"id": sid, "tab": None, "to": to, "label": label, "text": text,
                     "sec": round(f.stat().st_size * 8 / (KBPS * 1000), 1) if f.exists() else None})
    data = {PERSONA: {"mins": max(1, round(sum(r["sec"] or len(r["text"]) / 15 for r in rows) / 60)), "steps": rows}}
    block = player().replace("__TOUR_DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    # the "9 of 16" label already shows the position; a half-filled line read as a fault
    block = block.replace("<!-- tour:end -->", "<style>#tourBar .tbar { display: none; }</style>\n<!-- tour:end -->", 1)
    btn = '<button type="button" class="btn" id="tourBtn" title="Narrated tour of this report">▶ <span class="lbl">Guided tour</span></button>\n  '
    for report in REPORTS:
        if not report.exists():
            continue
        s = report.read_text(encoding="utf-8")
        s = re.sub(r"<!-- tour:start -->.*?<!-- tour:end -->\n", "", s, flags=re.S)
        anchor = '<button class="fab" data-open-chat'
        assert s.count(anchor) == 1
        s = s.replace(anchor, block + anchor)
        if 'id="tourBtn"' not in s:
            ask = '<button class="btn primary" data-open-chat>✦ Ask Intelligence</button>'
            assert s.count(ask) >= 1
            s = s.replace(ask, btn + ask, 1)
        report.write_text(s, encoding="utf-8", newline="")
    have = sum(1 for r in rows if r["sec"])
    print(f"tour injected: {len(rows)} steps, ~{data[PERSONA]['mins']} min, {have} with recorded voice")


def build(dry=False, inject_only=False):
    mpath = OUT / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    todo = []
    for sid, _to, _label, text in STEPS:
        spoken = say(text)
        h = hashlib.sha256(f"{VOICE[1]}|{MODEL}|{spoken}".encode()).hexdigest()[:16]
        f = OUT / PERSONA / f"{sid}.mp3"
        if manifest.get(f"{PERSONA}/{sid}") != h or not f.exists():
            todo.append((sid, spoken, h, f))
    cost = sum(len(t[1]) for t in todo)
    print(f"{len(todo)} clip(s) to record, about {cost:,} credits")
    if dry:
        for sid, sp, *_ in todo:
            print(f"  {sid}: {len(sp)} chars")
        return
    if todo and not inject_only:
        if cost > MAX_CREDITS:
            sys.exit(f"Refusing: {cost:,} credits is over the {MAX_CREDITS:,} limit")
        for sid, spoken, h, f in todo:
            f.parent.mkdir(parents=True, exist_ok=True)
            if not record(spoken, f):
                break  # e.g. out of credits: clips recorded so far are kept; the rest use the browser voice
            manifest[f"{PERSONA}/{sid}"] = h
            mpath.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
            print(f"  recorded {sid} ({f.stat().st_size // 1024} KB)")
    inject()


if __name__ == "__main__":
    build("--dry" in sys.argv, "--inject" in sys.argv)
