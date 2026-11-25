"""Find the Hong Kong passages in AXA's analyst-call recordings (MP3) with Gemini audio understanding.

Output: Prudential/_report_work/axa_calls_hk.md. The key is read from .env and sent only in a request header (never printed).
Quotes are verbatim from the audio as heard; timestamps are approximate.
"""
import base64
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRU = ROOT / "Prudential"
ENV = dict(re.findall(r"^\s*([A-Z_]+)\s*=\s*\"?([^\"\n]*)\"?", (ROOT / ".env").read_text(encoding="utf-8"), re.M))
KEY = ENV.get("GEMINI_API_KEY", "").strip()
MODEL = ENV.get("GEMINI_MODEL", "gemini-3.8-flash")
URL = (f"https://aiplatform.googleapis.com/v1/publishers/google/models/{MODEL}:generateContent" if not KEY.startswith("AIza")
       else f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent")
FILES = {"AXA analysts presentation, 5 May 2026": "aftBgMBOoF08xrHr_axa_analysts_presentation_20260505.mp3",
         "AXA analysts presentation, 31 Jul 2026 (half-year results)": "V3DXF9U0RR1UZ87I_AXA_Analysts_Presentation_20260731.mp3"}
PROMPT = """This is a recording of an AXA Group investor/analyst call. Listen to the whole recording.
1. In one paragraph, say what the call is (speakers' roles, topic) and how long it is.
2. List EVERY passage that mentions Hong Kong, Macau, the Greater Bay Area, mainland Chinese visitors, the Hong Kong high-net-worth business, the Hong Kong hub or office, Asia (where Hong Kong is discussed), AXA Hong Kong agents, or Hong Kong health insurance.
   For each: approximate timestamp (mm:ss), speaker (name and role if stated), and a VERBATIM quote of what was said (up to 80 words), then one line in plain English on what it means.
3. If Hong Kong is never mentioned, say so clearly.
Do not invent anything; if a word is unclear write [inaudible]. Do not include phone numbers or email addresses."""


def ask(path):
    audio = base64.b64encode(path.read_bytes()).decode()
    body = {"contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "audio/mpeg", "data": audio}}, {"text": PROMPT}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=900))
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])


def main():
    out = ["# AXA analyst calls: Hong Kong passages", "",
           "Machine listening of the two AXA recordings in the project folder. Quotes are verbatim as heard; timestamps approximate. "
           "Use as supporting context; confirm wording against AXA's published materials before quoting in the report.", ""]
    for label, fn in FILES.items():
        p = PRU / fn
        try:
            txt = ask(p)
        except Exception as e:  # report the error type only
            txt = f"(could not process: {type(e).__name__})"
        out += [f"## {label}", f"File: `{fn}`", "", txt.strip(), ""]
        print("done", label, len(txt))
    (PRU / "_report_work" / "axa_calls_hk.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
