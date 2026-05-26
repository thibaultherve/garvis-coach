"""
Reverse-geocode (Nominatim OSM) les hameaux/villages traverses par chaque
parcours pour aider au nommage. Print uniquement, n'ecrit rien.

Usage : python geocode_routes.py [--min-distance 7000]
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import OrderedDict
from pathlib import Path

import gpxpy
import numpy as np
import requests

ROOT = Path(__file__).parent
URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "garvis-coach-geocode/1.0"}
SAMPLE_PTS = 7
SLEEP_S = 1.1   # respect Nominatim 1 req/s


def safe_print(s):
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", errors="replace").decode())


def reverse(lat, lon):
    r = requests.get(URL, params={"format": "json", "lat": lat, "lon": lon,
                                  "zoom": 16, "addressdetails": 1},
                     headers=HEADERS, timeout=15)
    if r.status_code != 200 or not r.text.strip():
        return None
    try:
        return r.json()
    except Exception:
        return None


def hamlet_of(j):
    a = j.get("address", {}) if j else {}
    return (a.get("hamlet") or a.get("village") or a.get("isolated_dwelling")
            or a.get("locality") or a.get("town") or a.get("suburb"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-distance", type=int, default=7000,
                    help="Skip routes shorter than X m (default 7000)")
    args = ap.parse_args()

    gpx_dir = ROOT / "data" / "gpx"
    routes_dir = ROOT / "data" / "routes"

    targets = []
    for jp in sorted(routes_dir.glob("activity_*.json")):
        import json
        with open(jp, encoding="utf-8") as f:
            d = json.load(f)
        if d["distance_m"] >= args.min_distance:
            targets.append(d)

    print(f"{len(targets)} routes a geocoder (>= {args.min_distance}m)\n")

    for r in targets:
        name = r["name"]
        gpx = gpx_dir / f"{name}.gpx"
        if not gpx.exists():
            print(f"  {name}: GPX manquant")
            continue
        with open(gpx, encoding="utf-8") as f:
            g = gpxpy.parse(f)
        pts = [(p.latitude, p.longitude) for trk in g.tracks for seg in trk.segments for p in seg.points]
        if not pts:
            continue
        idx = np.linspace(0, len(pts) - 1, SAMPLE_PTS).astype(int)
        samples = [pts[i] for i in idx]
        seen = OrderedDict()    # garde l'ordre d'apparition
        safe_print(f"\n=== {name}  ({r['distance_m']/1000:.1f}km D+{int(r['elev_gain_m'])}m) ===")
        for lat, lon in samples:
            j = reverse(lat, lon)
            h = hamlet_of(j)
            if h:
                seen[h] = seen.get(h, 0) + 1
            safe_print(f"  {lat:.5f},{lon:.5f}  {h}")
            time.sleep(SLEEP_S)
        order_unique = list(seen.keys())
        safe_print(f"  -> hameaux: {order_unique}")


if __name__ == "__main__":
    main()
