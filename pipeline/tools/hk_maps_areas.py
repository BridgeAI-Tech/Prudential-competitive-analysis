"""Area-by-area Google Maps pass (Apify compass/google-maps-extractor) to widen the footprint collected by hk_maps_footprint.py.

Each run searches one circle (centre + radius) around a Hong Kong business or MTR hub for every brand's English and Chinese
names, so results are local to that area instead of Hong Kong-wide. New places are merged into Prudential/hk_maps/places_raw.json
(deduplicated by placeId); then run hk_maps_footprint.py --reviews-only to classify and collect reviews.

    python -I Prudential/ci-monitor/tools/hk_maps_areas.py
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import hk_maps_footprint as h

AREAS = [  # name, lat, lng, radius km
    ("Central / Admiralty", 22.2805, 114.1600, 1.5), ("Sheung Wan", 22.2865, 114.1500, 1.0), ("Wan Chai", 22.2775, 114.1730, 1.2),
    ("Causeway Bay", 22.2800, 114.1850, 1.0), ("North Point / Fortress Hill", 22.2900, 114.1980, 1.2), ("Quarry Bay / Taikoo", 22.2860, 114.2140, 1.5),
    ("Chai Wan / Shau Kei Wan", 22.2700, 114.2330, 2.0), ("Aberdeen / Wong Chuk Hang", 22.2480, 114.1650, 2.0), ("Tsim Sha Tsui", 22.2980, 114.1720, 1.2),
    ("Jordan / Yau Ma Tei", 22.3080, 114.1710, 1.0), ("Mong Kok / Prince Edward", 22.3200, 114.1690, 1.2), ("Sham Shui Po / Cheung Sha Wan", 22.3330, 114.1560, 1.8),
    ("Kowloon Tong / Kowloon City", 22.3290, 114.1880, 1.8), ("Hung Hom / Kai Tak", 22.3060, 114.1930, 1.8), ("Kowloon Bay", 22.3240, 114.2130, 1.2),
    ("Kwun Tong", 22.3110, 114.2250, 1.2), ("Wong Tai Sin / Diamond Hill", 22.3420, 114.1990, 1.8), ("Tseung Kwan O", 22.3080, 114.2600, 2.5),
    ("Sha Tin / Tai Wai", 22.3800, 114.1880, 2.5), ("Ma On Shan", 22.4250, 114.2320, 2.0), ("Tai Po", 22.4480, 114.1680, 2.5),
    ("Sheung Shui / Fanling", 22.5000, 114.1300, 3.0), ("Tsuen Wan", 22.3710, 114.1140, 1.8), ("Kwai Chung / Tsing Yi", 22.3600, 114.1150, 2.5),
    ("Tuen Mun", 22.3920, 113.9760, 3.0), ("Yuen Long / Tin Shui Wai", 22.4450, 114.0220, 3.5), ("Tung Chung", 22.2890, 113.9420, 2.5),
]
TERMS = [t for b in h.BRANDS.values() for t in (b["en"], f"{b['en']} insurance", b["zh"], f"{b['zh']}保險")]


def one(area):
    name, lat, lng, km = area
    try:
        items = h.run_actor("compass/google-maps-extractor", {
            "searchStringsArray": TERMS, "maxCrawledPlacesPerSearch": 20, "language": "en", "skipClosedPlaces": True,
            "customGeolocation": {"type": "Point", "coordinates": [lng, lat], "radiusKm": km}}, f"area {name}")
    except SystemExit as e:
        print(f"area {name}: failed ({e})")
        return []
    for it in items:
        it["_area"] = name
    return items


def main():
    f = h.OUT / "places_raw.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    have = {p.get("placeId") for p in raw}
    with ThreadPoolExecutor(6) as ex:
        found = [p for batch in ex.map(one, AREAS) for p in batch]
    new = []
    for p in found:
        if p.get("placeId") and p["placeId"] not in have:
            have.add(p["placeId"])
            new.append(p)
    raw += new
    f.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    branded = [p for p in new if h.brand_of(p.get("title"))]
    print(f"area pass: {len(found)} results, {len(new)} new places, {len(branded)} carry a brand name; total saved {len(raw)}")


if __name__ == "__main__":
    main()
