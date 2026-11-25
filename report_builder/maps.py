"""Physical footprint and location sentiment (Google Maps) for the report.

Reads Prudential/hk_maps/footprint.json, written by Prudential/ci-monitor/tools/hk_maps_footprint.py. Returns None when
the data has not been collected, so the report shows no empty panel. Adviser and agency listings are counted but not
named in the report (many are named after individual agents); customer service and health centres are named.
Reviews carry no reviewer identity.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = ROOT / "Prudential" / "hk_maps" / "footprint.json"
NAMED = ("Customer service centre", "Health and wellness centre")


def build():
    if not F.exists():
        return None
    fp = json.loads(F.read_text(encoding="utf-8"))
    if not any(s["points"] for s in fp["summary"].values()):
        return None
    locs = []
    for p in fp["locations"]:
        if p.get("lat") is None:
            continue
        locs.append({"b": p["brand"], "k": p["kind"], "n": p["title"] if p["kind"] in NAMED else None, "d": p["district"],
                     "lat": round(p["lat"], 5), "lng": round(p["lng"], 5), "r": p.get("rating"), "rc": p.get("reviews") or 0,
                     "wr": p.get("window_reviews") or 0, "ws": p.get("window_avg_stars"), "neg": p.get("negative_pct"), "u": p.get("url")})
    # review examples: the most recent long-enough review per brand and sentiment, with its location link
    ex = {}
    by_place = {p["placeId"]: p for p in fp["locations"]}
    for r in sorted(fp["reviews"], key=lambda r: r["date"], reverse=True):
        if len(r["text"]) < 60:
            continue
        key = (r["brand"], "neg" if r["stars"] <= 2 else "pos" if r["stars"] >= 4 else None)
        if key[1] and len(ex.setdefault(key, [])) < 2:
            p = by_place.get(r["placeId"], {})
            ex[key].append({"date": r["date"], "stars": r["stars"], "text": re.sub(r"<br\s*/?>", " ", r["text"], flags=re.I)[:280], "district": r["district"], "kind": r["kind"],
                            "translated": bool(r.get("original")), "topics": r["topics"], "u": p.get("url")})
    months = {}
    for r in fp["reviews"]:
        m = months.setdefault(r["date"][:7], {})
        m[r["brand"]] = m.get(r["brand"], 0) + 1
    # official locations, location news and district population (web research; optional file)
    on = {}
    of = F.parent / "official_and_news.json"
    if of.exists():
        on = json.loads(of.read_text(encoding="utf-8"))
    def plain(note):
        """Keep caveats a reader needs; drop collection details (URLs, blocked sites, archive copies)."""
        keep = [s.strip() for s in re.split(r"(?<=[.;])\s+", note or "") if s.strip()
                and not re.search(r"https?://|403|bots?\b|wayback|archive|original url|ticketing|scrap|[\u3400-\u9fff]", s, re.I)]
        return " ".join(keep)
    official = [{**o, "note": plain(o.get("note"))} for o in on.get("official_locations", []) if o.get("source_url")]
    news = sorted([{**n, "note": plain(n.get("note"))} for n in on.get("location_news", [])
                   if n.get("source_url") and "2025-11-01" <= (n.get("date") or "") <= "2026-10-31"], key=lambda n: n["date"], reverse=True)
    pop = (on.get("district_population") or {}).get("by_district") or {}
    reach = None
    if pop and sum(pop.values()):
        tot = sum(pop.values())
        reach = {"total": tot, "source_url": on["district_population"].get("source_url"), "source_title": "2021 Population Census, Census and Statistics Department",
                 "year": on["district_population"].get("year"), "by_brand": {}}
        for b in fp["summary"]:
            ds = {d for d, row in fp["district_grid"].items() if row.get(b)} | {o["district"] for o in official if o["brand"] == b and o.get("district")}
            reach["by_brand"][b] = {"districts": len(ds), "pct": round(100 * sum(pop.get(d, 0) for d in ds) / tot)}
    other = [{"b": p["brand"], "n": p["title"][:80], "d": p["district"], "u": p.get("url")} for p in fp.get("other_same_name", [])
             if not re.search(r"報價|quote", p["title"] or "", re.I)]   # keep business names; skip ad-style listing titles
    return {"collected": fp["collected"], "window": fp["window"], "summary": fp["summary"], "grid": fp["district_grid"], "locs": locs, "other": other,
            "official": official, "news": news, "reach": reach,
            "examples": {f"{b}|{s}": v for (b, s), v in ex.items()}, "months": dict(sorted(months.items()))}


def kb_text(m) -> str:
    """Plain-text part for the chat knowledge base."""
    if not m:
        return ""
    out = [f"Google Maps listings in Hong Kong, collected {m['collected']}; reviews {m['window'][0]} to {m['window'][1]}. "
           "Counts are listings visible on Google Maps (agency teams create many of them), not official branch counts. "
           "Reviews are a self-selected sample; ratings are out of 5."]
    for b, s in m["summary"].items():
        out.append(f"- {b}: {s['points']} service points ({s['kinds']}), in {len(s['districts'])} of 18 districts ({', '.join(s['districts'])}); "
                   f"average Google rating {s['avg_rating']} over {s['all_time_reviews']} all-time reviews; {s['window_reviews']} reviews in the window, "
                   f"average {s['window_avg_stars']} stars, {s['positive_pct']}% positive, {s['negative_pct']}% negative, owner replied to {s['owner_reply_pct']}%; "
                   f"topics in negative reviews: {s['negative_topics']}")
    out.append("Buildings named after each brand (visibility, not service points): " + json.dumps({b: s.get("named_buildings", []) for b, s in m["summary"].items()}, ensure_ascii=False))
    out.append("Other businesses that only share a brand name (not the insurer): " + "; ".join(f"{o['b']}: {o['n']}" for o in m.get("other", [])))
    out.append("Official locations listed on each insurer's own website:")
    out += [f"- [{o['brand']}] {o['name']} ({o.get('type')}) · {o.get('address')} · {o.get('district')} · hours: {o.get('hours') or 'n/a'} · {o['source_url']}" for o in m.get("official", [])]
    out.append("Location moves in the window (openings, expansions, leases, relocations):")
    out += [f"- {n['date']} [{n['brand']}] {n['what']} ({n.get('district') or ''}) {n['source_url']}" for n in m.get("news", [])]
    if m.get("reach"):
        out.append(f"Share of Hong Kong residents living in a district with at least one service point ({m['reach']['source_title']}, {m['reach']['year']}; {m['reach']['source_url']}): "
                   + json.dumps(m["reach"]["by_brand"]))
    out.append("District grid (service points per brand): " + json.dumps(m["grid"], ensure_ascii=False))
    out.append("Named locations (customer service and health centres):")
    out += [f"- [{l['b']}] {l['n']} · {l['d']} · rating {l['r']} ({l['rc']} reviews; {l['wr']} in window, {l['neg']}% negative) · {l['u']}" for l in m["locs"] if l["n"]]
    out.append("Review examples (translated where marked):")
    for k, v in m["examples"].items():
        out += [f"- [{k}] {e['date']} · {e['stars']} stars · {e['district']} {e['kind']} · {'(translated) ' if e['translated'] else ''}{e['text']} · {e['u']}" for e in v]
    return "\n".join(out)
