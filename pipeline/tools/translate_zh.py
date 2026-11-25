"""English summaries for Chinese-language records (brief s1 / s9: retain the original, add an English translation or summary).

Covers: observations with language='zh' in ci.db, and Chinese Facebook / Instagram posts (apify_raw).
Output cache: Prudential/_report_work/translations.json  {key: {"en": summary, "src": "observation"|"social"}}
  key = record_id for observations, post URL for social posts. Re-runs only translate what is missing.
Then writes english_summary + translation_status='machine_summary' back to ci.db.
The API key is read from .env and only sent in a request header; it is never printed or logged.
"""
import json
import re
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRU = ROOT / "Prudential"
DB = PRU / "ci-monitor" / "data" / "ci.db"
OUT = PRU / "_report_work" / "translations.json"
sys.path.insert(0, str(ROOT / "report_app" / "prudential"))

ENV = dict(re.findall(r"^\s*([A-Z_]+)\s*=\s*\"?([^\"\n]*)\"?", (ROOT / ".env").read_text(encoding="utf-8"), re.M))
KEY = ENV.get("GEMINI_API_KEY", "").strip()
MODEL = ENV.get("GEMINI_MODEL", "gemini-3.8-flash")
URL = (f"https://aiplatform.googleapis.com/v1/publishers/google/models/{MODEL}:generateContent" if not KEY.startswith("AIza")
       else f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")
CJK = re.compile(r"[一-鿿]")
PROMPT = """You translate Hong Kong insurance-industry content (Traditional Chinese / Cantonese) into plain English for an English-speaking executive.
For each item return ONE English sentence or two (max 45 words) that faithfully summarises what the item says. Keep names of products, campaigns, people and amounts exactly (give the Chinese product name in brackets after an English rendering when it is a product or campaign name). Do not add facts, opinions or marketing language. Do not include phone numbers or email addresses.
Return JSON: {"items": [{"id": "...", "en": "..."}]} with every id from the input."""


def call(batch):
    body = {"contents": [{"role": "user", "parts": [{"text": PROMPT + "\n\nINPUT:\n" + json.dumps(batch, ensure_ascii=False)}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json", "maxOutputTokens": 8192}}
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=180))
            txt = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
            return {x["id"]: x["en"].strip() for x in json.loads(txt)["items"] if x.get("en")}
        except Exception as e:  # noqa: BLE001 - retry, report type only (never the request)
            err = type(e).__name__
            time.sleep(5 * (attempt + 1))
    print("  batch failed:", err, flush=True)
    return {}


def main():
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = []
    con = sqlite3.connect(DB)
    for rid, title, desc, orig in con.execute("select record_id, title, description, original_content from observations where language='zh'"):
        if rid not in cache:
            text = " | ".join(x for x in (title, desc, orig) if x)
            todo.append({"id": rid, "src": "observation", "text": re.sub(r"\s+", " ", text)[:900]})
    import social_meta as sm
    posts, _ = sm.load()
    for p in posts:
        if p["url"] and p["url"] not in cache and CJK.search(p["text"] or ""):
            todo.append({"id": p["url"], "src": "social", "text": p["text"][:900]})
    import linkedin as li
    lip, _ = li.load()
    for p in lip:
        if p["url"] and p["url"] not in cache and CJK.search(p["text"] or ""):
            todo.append({"id": p["url"], "src": "social", "text": p["text"][:900]})
    print(f"to translate: {len(todo)} (cached {len(cache)})", flush=True)
    size = 25 if len(todo) > 300 else 10          # smaller batches on re-runs (long replies can be cut off)
    batches = [todo[i:i + size] for i in range(0, len(todo), size)]
    src = {t["id"]: t["src"] for t in todo}
    done = 0
    with ThreadPoolExecutor(6) as ex:
        for res in ex.map(lambda b: call([{"id": t["id"], "text": t["text"]} for t in b]), batches):
            for k, v in res.items():
                if k in src:
                    cache[k] = {"en": v, "src": src[k]}
            done += 1
            if done % 10 == 0:
                OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
                print(f"  {done}/{len(batches)} batches", flush=True)
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    n = 0
    for k, v in cache.items():
        if v.get("src", "observation") == "observation":   # older cache entries carry no "src"; a non-record key updates nothing
            n += con.execute("update observations set english_summary=?, translation_status='machine_summary' where record_id=? and language='zh'",
                             (v["en"], k)).rowcount
    con.commit()
    left = con.execute("select count(*) from observations where language='zh' and translation_status='pending'").fetchone()[0]
    print(f"cache {len(cache)}; observations updated {n}; still pending {left}")


if __name__ == "__main__":
    main()
