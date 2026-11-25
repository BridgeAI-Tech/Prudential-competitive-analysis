"""Shared helpers: config loading, polite HTTP with robots.txt checks, evidence capture, record schema."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "pipeline" / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"            # collector outputs (jsonl)
EVIDENCE = DATA / "evidence"  # raw page snapshots referenced by evidence_ref

USER_AGENT = "CI-Monitor-POC/0.1 (+competitive-intelligence research; respects robots.txt)"
HTTP_DELAY_S = 1.5

for p in (RAW, EVIDENCE):
    p.mkdir(parents=True, exist_ok=True)


def load_json(name: str):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


COMPANIES = load_json("companies.json")["companies"]
TAXONOMY = load_json("taxonomy.json")
BRAND_TO_ID = {c["brand"]: c["company_id"] for c in COMPANIES}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def window(days: int = 90, end: dt.date | None = None) -> tuple[dt.date, dt.date]:
    end = end or dt.date.today()
    return end - dt.timedelta(days=days), end


# ---------------------------------------------------------------- HTTP
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-HK,en;q=0.9,zh-HK;q=0.8"})
_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def robots_allowed(url: str) -> bool:
    host = urlparse(url).scheme + "://" + urlparse(url).netloc
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _session.get(host + "/robots.txt", timeout=20)
            if r.status_code in (401, 403):
                rp = None  # robots unreadable because access denied -> treat as disallowed
            elif r.status_code >= 400:
                rp.parse([])  # no robots file -> allowed
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None
        _robots[host] = rp
    rp = _robots[host]
    return False if rp is None else rp.can_fetch(USER_AGENT, url)


class Blocked(Exception):
    pass


def fetch(url: str, *, check_robots: bool = True, params=None, timeout: int = 30, save_evidence: bool = True):
    """GET with robots check, per-host delay and evidence snapshot. Returns (text, evidence_ref)."""
    if check_robots and not robots_allowed(url):
        raise Blocked(f"robots.txt disallows or denies access: {url}")
    host = urlparse(url).netloc
    wait = HTTP_DELAY_S - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            _last_hit[host] = time.time()
            if r.status_code in (401, 403):
                raise Blocked(f"HTTP {r.status_code}: {url}")
            if r.status_code == 404:
                raise Blocked(f"HTTP 404: {url}")
            r.raise_for_status()
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
            ref = None
            if save_evidence:
                ref = save_snapshot(r.url, r.text)
            return r.text, ref
        except Blocked:
            raise
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def save_snapshot(url: str, text: str) -> str:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    day = dt.date.today().isoformat()
    path = EVIDENCE / day / f"{h}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path.relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------- records
RECORD_FIELDS = [
    "record_id", "company_id", "brand", "record_type", "modules", "activity_type", "title", "description",
    "original_content", "language", "english_summary", "publication_date", "capture_ts", "source_name",
    "source_category", "source_url", "evidence_ref", "hk_relevance", "hk_relevance_basis", "platform",
    "content_format", "product_name", "campaign_name", "metrics", "extra",
]


def record_id(*parts: str) -> str:
    return hashlib.sha1("|".join(p or "" for p in parts).encode("utf-8")).hexdigest()[:16]


def make_record(**kw) -> dict:
    rec = {f: None for f in RECORD_FIELDS}
    rec.update(kw)
    rec["capture_ts"] = rec["capture_ts"] or now_utc()
    rec["metrics"] = rec["metrics"] or {}
    rec["extra"] = rec["extra"] or {}
    rec["modules"] = rec["modules"] or []
    if rec["company_id"] is None and rec["brand"]:
        rec["company_id"] = BRAND_TO_ID.get(rec["brand"])
    if not rec["record_id"]:
        rec["record_id"] = record_id(rec["record_type"], rec["source_url"], rec["title"], rec["publication_date"])
    if rec["language"] is None:
        rec["language"] = detect_lang((rec["title"] or "") + " " + (rec["original_content"] or "")[:500])
    return rec


def detect_lang(text: str) -> str:
    cjk = len(re.findall(r"[一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk and cjk * 3 >= latin:
        return "zh"
    return "en"


def write_jsonl(name: str, records: list[dict]) -> Path:
    path = RAW / f"{name}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def clean_text(s: str | None) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def log(msg: str):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)
