"""
discover_climbs.py — decouvre toutes les cotes du reseau OSM autour d'un centre.

Pipeline:
  1. Overpass API: fetch ways (highway in path|track|...|tertiary|residential)
     dans bbox(centre, radius). Cache JSON.
  2. Pour chaque way, resample geometrie tous les ~25 m.
  3. OpenTopoData EU-DEM 25m (batch 100, 1 req/s, fallback SRTM 30m).
     Cache incremental (key = lat,lon round 5 dec ~1m).
  4. Reutilise les helpers de analyze_routes.py (compute_slope,
     find_notable_climbs, smooth, ...) sur le profil altitude.
  5. Dedup spatial des cotes par midpoint (clustering haversine <60m).
  6. Outputs:
       data/climbs/catalog.csv
       data/climbs/catalog.geojson
       data/climbs/map.html  (Leaflet self-contained, double-clic -> browser)
       data/climbs/gpx/<id>_<slug>.gpx (1 par cote, droppable Garmin/Komoot)

Usage:
  python discover_climbs.py detect [--center 48.3788,0.6384] [--radius 15]
                                   [--min-length 200] [--min-gain 15]
                                   [--min-slope 3] [--sample-step 25]
  python discover_climbs.py filter --min-length 500 --slope-min 5 --slope-max 8
  python discover_climbs.py export-gpx --id 12
  python discover_climbs.py map
  python discover_climbs.py validate    # compare contre data/routes/cote_*

Notes:
  - DEM EU-DEM 25m: precis pour France, validation pro. Fallback SRTM 30m.
  - Rate limit OpenTopoData public: 1 req/s, 100 pts/req, 1000 calls/jour/IP.
    Run initial typique 15 km radius: ~10-20 min, puis cache HIT.
  - Idempotent: re-run = lit cache, ne refait pas le reseau.
  - Upgrade IGN 5m possible si SRTM/EU-DEM 25m insuffisant (TODO).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

# Reuse analysis helpers from analyze_routes.py
from analyze_routes import (
    SAMPLE_M,
    SLOPE_WINDOW_M,
    SMOOTH_WINDOW_M,
    compute_slope,
    cumulative_distance,
    find_notable_climbs,
    haversine_m,
    resample,
    smooth,
)

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "data" / "climbs"
CACHE_DIR = OUT_DIR / "cache"
DISCOVERED_DIR = OUT_DIR / "discovered"
GPX_DIR = OUT_DIR / "gpx"
for d in (OUT_DIR, CACHE_DIR, DISCOVERED_DIR, GPX_DIR):
    d.mkdir(parents=True, exist_ok=True)

CATALOG_CSV = OUT_DIR / "catalog.csv"
CATALOG_GEOJSON = OUT_DIR / "catalog.geojson"
MAP_HTML = OUT_DIR / "map.html"
ELEV_CACHE = CACHE_DIR / "elevations.json"

# --- Defaults (override via CLI args or env) ------------------------------
DEFAULT_CENTER = (48.3788, 0.6384)   # example center (override with --center lat,lon)
DEFAULT_RADIUS_KM = 15
DEFAULT_SAMPLE_M = 25                # resample step pour limiter API calls
DEFAULT_MIN_LENGTH = 200             # m
DEFAULT_MIN_GAIN = 15                # m
DEFAULT_MIN_AVG_SLOPE = 3.0          # %
DEDUP_MIDPOINT_M = 60                # cluster cotes par midpoint < 60m

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPENTOPO_URL = "https://api.opentopodata.org/v1"
OPENTOPO_DATASETS = ["eudem25m", "srtm30m"]    # fallback chain

HIGHWAY_FILTER = r"^(path|track|footway|bridleway|cycleway|unclassified|tertiary|residential|service)$"

UA = "garvis-coach-discover-climbs/1.0"


# ============================================================================
# Overpass: fetch ways dans bbox
# ============================================================================

def overpass_query(center: tuple[float, float], radius_m: int) -> str:
    lat, lon = center
    return f"""
[out:json][timeout:180];
(
  way[highway~"{HIGHWAY_FILTER}"](around:{radius_m},{lat},{lon});
);
out geom;
"""


def fetch_ways(center, radius_km, force=False) -> list[dict]:
    """Retourne liste de ways {id, tags, geometry: [(lat, lon), ...]}.

    Cache: data/climbs/cache/overpass_<bbox_hash>.json (idempotent).
    """
    radius_m = int(radius_km * 1000)
    key = hashlib.md5(f"{center}_{radius_m}".encode()).hexdigest()[:12]
    cache_path = CACHE_DIR / f"overpass_{key}.json"

    if cache_path.exists() and not force:
        print(f"  [cache HIT] overpass {cache_path.name} -> ", end="")
        with open(cache_path, encoding="utf-8") as f:
            ways = json.load(f)
        print(f"{len(ways)} ways")
        return ways

    print(f"  [overpass] querying {radius_km}km around {center}...")
    q = overpass_query(center, radius_m)
    r = requests.post(OVERPASS_URL, data={"data": q},
                      headers={"User-Agent": UA}, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"Overpass HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    ways = []
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom = [(p["lat"], p["lon"]) for p in el.get("geometry", [])]
        if len(geom) < 2:
            continue
        ways.append({
            "id": el["id"],
            "tags": el.get("tags", {}),
            "geometry": geom,
        })
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(ways, f)
    print(f"  [overpass] {len(ways)} ways saved -> {cache_path.name}")
    return ways


# ============================================================================
# Resample geometry along way
# ============================================================================

def resample_way(geometry: list[tuple[float, float]], step_m: float) -> list[tuple[float, float]]:
    """Sample (lat, lon) tous les step_m le long de la polyline."""
    lats = np.array([p[0] for p in geometry])
    lons = np.array([p[1] for p in geometry])
    cum = cumulative_distance(lats, lons)
    total = float(cum[-1])
    if total < step_m:
        return [(float(lats[0]), float(lons[0])), (float(lats[-1]), float(lons[-1]))]
    n = max(2, int(total / step_m) + 1)
    new_d = np.linspace(0, total, n)
    new_lat = np.interp(new_d, cum, lats)
    new_lon = np.interp(new_d, cum, lons)
    return list(zip(new_lat.tolist(), new_lon.tolist()))


# ============================================================================
# Elevation: OpenTopoData batch + cache
# ============================================================================

def load_elev_cache() -> dict:
    if ELEV_CACHE.exists():
        with open(ELEV_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_elev_cache(cache: dict):
    tmp = ELEV_CACHE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    tmp.replace(ELEV_CACHE)


def cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 5)},{round(lon, 5)}"


def fetch_elevation_batch(points: list[tuple[float, float]], dataset: str) -> list[float | None]:
    """Call OpenTopoData pour batch <= 100. Retourne liste meme taille."""
    if not points:
        return []
    locs = "|".join(f"{lat},{lon}" for lat, lon in points)
    r = requests.get(f"{OPENTOPO_URL}/{dataset}",
                     params={"locations": locs},
                     headers={"User-Agent": UA}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"OpenTopoData {dataset} HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") != "OK":
        raise RuntimeError(f"OpenTopoData {dataset} status: {data.get('status')} {data.get('error', '')}")
    return [res.get("elevation") for res in data.get("results", [])]


def fetch_elevations(points: Iterable[tuple[float, float]],
                     primary: str = "eudem25m",
                     fallback: str = "srtm30m") -> dict:
    """Resout l'altitude pour chaque (lat, lon). Cache disque incremental.

    Strategie: tente primary (EU-DEM 25m); sur None, retombe sur fallback.
    """
    cache = load_elev_cache()
    points = list(points)
    # Dedup + filtre cache
    unique = []
    seen = set()
    for lat, lon in points:
        k = cache_key(lat, lon)
        if k in cache or k in seen:
            continue
        seen.add(k)
        unique.append((lat, lon))

    print(f"  [elev] {len(points)} pts requested, {len(unique)} new (after cache + dedup)")
    if not unique:
        return {cache_key(*p): cache.get(cache_key(*p)) for p in points}

    BATCH = 100
    SLEEP = 1.05    # respect public rate limit 1 req/s
    n_batches = (len(unique) + BATCH - 1) // BATCH
    t0 = time.time()
    for i in range(0, len(unique), BATCH):
        batch = unique[i:i + BATCH]
        # Tente primary
        try:
            elevs = fetch_elevation_batch(batch, primary)
        except Exception as e:
            print(f"    [warn] {primary} batch {i//BATCH+1} failed: {e}, retry {fallback}")
            try:
                elevs = fetch_elevation_batch(batch, fallback)
            except Exception as e2:
                print(f"    [error] {fallback} also failed: {e2}, skip batch")
                elevs = [None] * len(batch)
        # Si EU-DEM renvoie des None (hors couverture), retry par point en SRTM
        none_idx = [j for j, e in enumerate(elevs) if e is None]
        if none_idx and primary != fallback:
            try:
                fb_elevs = fetch_elevation_batch([batch[j] for j in none_idx], fallback)
                for j, e in zip(none_idx, fb_elevs):
                    elevs[j] = e
            except Exception:
                pass
        for (lat, lon), e in zip(batch, elevs):
            cache[cache_key(lat, lon)] = e
        # Save toutes les 10 batches (resilience aux interruptions)
        if (i // BATCH) % 10 == 9:
            save_elev_cache(cache)
            elapsed = time.time() - t0
            done = (i + BATCH) / len(unique)
            eta = elapsed / max(done, 0.001) * (1 - done)
            print(f"    [progress] {i+BATCH}/{len(unique)} ({done*100:.0f}%) "
                  f"elapsed={elapsed:.0f}s eta={eta:.0f}s")
        time.sleep(SLEEP)
    save_elev_cache(cache)
    print(f"  [elev] done in {time.time()-t0:.0f}s, cache size = {len(cache)}")
    return {cache_key(lat, lon): cache.get(cache_key(lat, lon)) for lat, lon in points}


# ============================================================================
# Detection: par way -> liste de cotes
# ============================================================================

def detect_climbs_in_way(way: dict, sampled: list[tuple[float, float]],
                         elevs_dict: dict, params: dict) -> list[dict]:
    """Applique le pipeline de analyze_routes.py sur un way."""
    if len(sampled) < 3:
        return []
    lats = np.array([p[0] for p in sampled])
    lons = np.array([p[1] for p in sampled])
    elev = np.array([elevs_dict.get(cache_key(la, lo)) for la, lo in sampled])
    # Si trous d'elevation, interp lineaire (sur indices des valides)
    valid = ~np.array([e is None for e in elev])
    if valid.sum() < 3:
        return []
    if not valid.all():
        idx_all = np.arange(len(elev))
        elev = np.interp(idx_all, idx_all[valid], elev[valid].astype(float))
    else:
        elev = elev.astype(float)

    cum_raw = cumulative_distance(lats, lons)
    if cum_raw[-1] < params["min_length"]:
        return []
    # Re-resample uniformement a SAMPLE_M=10 (les helpers attendent ca)
    distances, elevs_interp = resample(cum_raw, elev, step_m=SAMPLE_M)
    elevs_smooth = smooth(elevs_interp, SMOOTH_WINDOW_M, SAMPLE_M)
    slopes = compute_slope(distances, elevs_smooth, SLOPE_WINDOW_M)

    # find_notable_climbs renvoie des cotes (start_m, end_m, length_m, gain_m, avg_slope_pct)
    raw_climbs = find_notable_climbs(
        distances, elevs_smooth, slopes,
        min_gain=params["min_gain"],
        min_avg_slope=params["min_avg_slope"],
    )

    # Pour chaque cote, geometry sub (lat/lon) + max_slope + midpoint
    climbs_out = []
    for c in raw_climbs:
        if c["length_m"] < params["min_length"]:
            continue
        # mapper start_m/end_m -> indices dans sampled (cum_raw)
        i_start = int(np.searchsorted(cum_raw, c["start_m"], side="left"))
        i_end = int(np.searchsorted(cum_raw, c["end_m"], side="right")) - 1
        i_start = max(0, min(i_start, len(sampled) - 1))
        i_end = max(i_start + 1, min(i_end, len(sampled) - 1))
        sub_lats = lats[i_start:i_end + 1].tolist()
        sub_lons = lons[i_start:i_end + 1].tolist()
        sub_elev = elev[i_start:i_end + 1].tolist()

        # max_slope: recompute sur le sous-segment lisse
        i_s_smooth = int(c["start_m"] / SAMPLE_M)
        i_e_smooth = int(c["end_m"] / SAMPLE_M)
        sub_slopes = slopes[i_s_smooth:i_e_smooth + 1]
        max_slope = float(np.max(sub_slopes)) if len(sub_slopes) else c["avg_slope_pct"]

        mid_idx = (i_start + i_end) // 2
        midpoint = (float(lats[mid_idx]), float(lons[mid_idx]))

        # FIETS index: D+^2 / dist + max_alt/1000
        fiets = (c["gain_m"] ** 2) / max(c["length_m"], 1) + max(sub_elev) / 1000

        climbs_out.append({
            "way_id": way["id"],
            "way_name": way["tags"].get("name") or way["tags"].get("ref") or "",
            "way_highway": way["tags"].get("highway", ""),
            "way_surface": way["tags"].get("surface", ""),
            "length_m": int(round(c["length_m"])),
            "gain_m": round(c["gain_m"], 1),
            "avg_slope_pct": round(c["avg_slope_pct"], 1),
            "max_slope_pct": round(max_slope, 1),
            "fiets_index": round(fiets, 2),
            "score_lxs2": round(c["length_m"] * (c["avg_slope_pct"] ** 2) / 1000, 1),
            "midpoint_lat": round(midpoint[0], 6),
            "midpoint_lon": round(midpoint[1], 6),
            "start_lat": round(float(sub_lats[0]), 6),
            "start_lon": round(float(sub_lons[0]), 6),
            "end_lat": round(float(sub_lats[-1]), 6),
            "end_lon": round(float(sub_lons[-1]), 6),
            "elev_start_m": round(float(sub_elev[0]), 1),
            "elev_end_m": round(float(sub_elev[-1]), 1),
            "geometry": [[round(la, 6), round(lo, 6)]
                         for la, lo in zip(sub_lats, sub_lons)],
            "elevations": [round(e, 1) for e in sub_elev],
        })
    return climbs_out


# ============================================================================
# Dedup spatial
# ============================================================================

def dedup_climbs(climbs: list[dict]) -> list[dict]:
    """Cluster par midpoint < DEDUP_MIDPOINT_M, garde celle avec plus de gain."""
    if not climbs:
        return []
    # Trie par gain DESC pour que le 1er rencontre soit l'ancre
    sorted_climbs = sorted(climbs, key=lambda c: -c["gain_m"])
    kept = []
    for c in sorted_climbs:
        is_dup = False
        for k in kept:
            d = haversine_m(c["midpoint_lat"], c["midpoint_lon"],
                            k["midpoint_lat"], k["midpoint_lon"])
            if d < DEDUP_MIDPOINT_M:
                # meme cote: skip si k a deja un gain >= au notre
                if k["gain_m"] >= c["gain_m"]:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(c)
    return kept


# ============================================================================
# Outputs
# ============================================================================

def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[-\s]+", "_", s)[:40] or "unnamed"


def write_outputs(climbs: list[dict]):
    """CSV catalog + GeoJSON + per-climb JSON."""
    # Tri final par fiets DESC pour assigner ID stable au top
    climbs = sorted(climbs, key=lambda c: -c["fiets_index"])
    for i, c in enumerate(climbs, 1):
        c["id"] = i

    # CSV
    cols = ["id", "length_m", "gain_m", "avg_slope_pct", "max_slope_pct",
            "fiets_index", "score_lxs2", "way_name", "way_highway", "way_surface",
            "midpoint_lat", "midpoint_lon", "start_lat", "start_lon",
            "end_lat", "end_lon", "elev_start_m", "elev_end_m", "way_id"]
    with open(CATALOG_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in climbs:
            w.writerow({k: c.get(k, "") for k in cols})

    # GeoJSON
    features = []
    for c in climbs:
        coords = [[lo, la] for la, lo in c["geometry"]]   # [lon, lat]
        props = {k: c.get(k) for k in cols}
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props,
        })
    with open(CATALOG_GEOJSON, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    # Per-climb JSON
    for c in climbs:
        slug = slugify(c["way_name"]) if c["way_name"] else f"way{c['way_id']}"
        path = DISCOVERED_DIR / f"{c['id']:03d}_{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)

    print(f"  [out] {CATALOG_CSV.name} ({len(climbs)} climbs)")
    print(f"  [out] {CATALOG_GEOJSON.name}")
    print(f"  [out] {DISCOVERED_DIR}/  ({len(climbs)} per-climb JSON)")


def write_gpx(climb: dict, out_path: Path):
    """Ecrit un GPX simple pour 1 cote."""
    name = f"climb_{climb['id']:03d}"
    if climb.get("way_name"):
        name += f"_{slugify(climb['way_name'])}"
    desc = (f"L={climb['length_m']}m gain={climb['gain_m']}m "
            f"avg={climb['avg_slope_pct']}% max={climb['max_slope_pct']}% "
            f"fiets={climb['fiets_index']} highway={climb['way_highway']}")
    pts = []
    for (la, lo), e in zip(climb["geometry"], climb["elevations"]):
        pts.append(f'<trkpt lat="{la}" lon="{lo}"><ele>{e}</ele></trkpt>')
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="discover_climbs.py" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>{name}</name>
    <desc>{desc}</desc>
    <trkseg>
      {chr(10).join('      ' + p for p in pts)}
    </trkseg>
  </trk>
</gpx>
"""
    out_path.write_text(body, encoding="utf-8")


def write_all_gpx(climbs: list[dict]):
    for c in climbs:
        slug = slugify(c["way_name"]) if c["way_name"] else f"way{c['way_id']}"
        path = GPX_DIR / f"{c['id']:03d}_{slug}.gpx"
        write_gpx(c, path)
    print(f"  [out] {GPX_DIR}/  ({len(climbs)} GPX)")


def write_map(climbs: list[dict], center: tuple[float, float]):
    """Carte Leaflet self-contained avec panneau de filtres live."""
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lo, la] for la, lo in c["geometry"]]},
                "properties": {
                    "id": c["id"],
                    "name": c.get("way_name") or f"way #{c['way_id']}",
                    "length_m": c["length_m"],
                    "gain_m": c["gain_m"],
                    "avg_slope": c["avg_slope_pct"],
                    "max_slope": c["max_slope_pct"],
                    "fiets": c["fiets_index"],
                    "score": c["score_lxs2"],
                    "highway": c["way_highway"],
                    "surface": c["way_surface"],
                },
            }
            for c in climbs
        ],
    }
    geojson_str = json.dumps(geojson)
    # Bornes pour les sliders (calculees pour ne pas exclure le top par defaut)
    if climbs:
        max_len = max(max(c["length_m"] for c in climbs), 2500)
        max_gain = max(c["gain_m"] for c in climbs)
        max_avg = max(c["avg_slope_pct"] for c in climbs)
        max_max = max(c["max_slope_pct"] for c in climbs)
        max_fiets = max(c["fiets_index"] for c in climbs)
    else:
        max_len = max_gain = max_avg = max_max = max_fiets = 1
    highways = sorted({c["way_highway"] for c in climbs if c["way_highway"]})

    hw_checkboxes = "".join(
        f'<label><input type="checkbox" class="hw" value="{h}" checked> {h}</label> '
        for h in highways
    )

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Discovered climbs</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
html,body{{height:100%;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
#map{{position:absolute;top:0;left:340px;right:0;bottom:0}}
#panel{{position:absolute;top:0;left:0;bottom:0;width:340px;background:#f8f9fa;border-right:1px solid #ddd;
       overflow-y:auto;padding:14px;font-size:13px;box-sizing:border-box}}
#panel h2{{margin:0 0 4px 0;font-size:15px;color:#222}}
#panel h3{{margin:14px 0 6px 0;font-size:12px;color:#555;text-transform:uppercase;letter-spacing:.05em}}
.row{{display:flex;align-items:center;gap:6px;margin:4px 0;font-size:12px}}
.row label{{flex:0 0 70px;color:#555}}
.row input[type=range]{{flex:1}}
.row .v{{flex:0 0 60px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600;color:#222}}
.hw-list{{display:flex;flex-wrap:wrap;gap:4px 8px}}
.hw-list label{{display:inline-flex;align-items:center;gap:3px;font-size:11px;color:#444;cursor:pointer;
              padding:2px 6px;background:white;border:1px solid #ddd;border-radius:3px}}
.hw-list label:has(input:checked){{background:#dbeafe;border-color:#60a5fa}}
.hw-list input{{margin:0}}
#counter{{font-weight:600;color:#0369a1;margin:8px 0}}
#sort{{width:100%;padding:4px;font-size:12px}}
button{{padding:4px 10px;font-size:12px;cursor:pointer;border:1px solid #ccc;background:white;border-radius:3px}}
button:hover{{background:#f0f0f0}}
.actions{{display:flex;gap:6px;margin-top:8px}}
#topn{{width:50px;padding:2px 4px;font-size:12px}}
.popup table{{border-collapse:collapse;font-size:12px}}
.popup td{{padding:2px 8px;border-bottom:1px solid #eee}}
.popup td:first-child{{font-weight:bold;color:#555}}
.legend{{background:white;padding:8px;line-height:1.4;font-size:11px;border-radius:4px;
         box-shadow:0 1px 4px rgba(0,0,0,0.3)}}
.legend i{{display:inline-block;width:16px;height:4px;margin-right:6px;vertical-align:middle}}
#topbox{{margin-top:10px;border-top:1px solid #ddd;padding-top:10px;font-size:11px}}
#topbox table{{border-collapse:collapse;width:100%;margin-top:4px}}
#topbox td{{padding:2px 4px;border-bottom:1px solid #eee;font-variant-numeric:tabular-nums}}
#topbox tr{{cursor:pointer}}
#topbox tr:hover{{background:#fef3c7}}
.muted{{color:#888;font-size:11px}}
</style></head><body>
<div id="panel">
  <h2>Cotes decouvertes</h2>
  <div class="muted" id="totalcount">{len(climbs)} cotes au catalogue</div>

  <h3>Longueur (m)</h3>
  <div class="row"><label>min</label><input type="range" id="lmin" min="0" max="{int(max_len)}" value="0" step="50"><span class="v" id="lmin_v">0</span></div>
  <div class="row"><label>max</label><input type="range" id="lmax" min="0" max="{int(max_len)}" value="{int(max_len)}" step="50"><span class="v" id="lmax_v">{int(max_len)}</span></div>

  <h3>D+ (m)</h3>
  <div class="row"><label>min</label><input type="range" id="gmin" min="0" max="{int(max_gain)}" value="0" step="5"><span class="v" id="gmin_v">0</span></div>

  <h3>Pente moy (%)</h3>
  <div class="row"><label>min</label><input type="range" id="smin" min="0" max="{int(max_avg)+1}" value="0" step="0.5"><span class="v" id="smin_v">0</span></div>
  <div class="row"><label>max</label><input type="range" id="smax" min="0" max="{int(max_avg)+1}" value="{int(max_avg)+1}" step="0.5"><span class="v" id="smax_v">{int(max_avg)+1}</span></div>

  <h3>Pente max (%)</h3>
  <div class="row"><label>min</label><input type="range" id="mmin" min="0" max="{int(max_max)+1}" value="0" step="0.5"><span class="v" id="mmin_v">0</span></div>

  <h3>FIETS index</h3>
  <div class="row"><label>min</label><input type="range" id="fmin" min="0" max="{max_fiets}" value="0" step="0.1"><span class="v" id="fmin_v">0</span></div>

  <h3>Type voirie</h3>
  <div class="hw-list">{hw_checkboxes}</div>

  <h3>Tri / Top N</h3>
  <select id="sort">
    <option value="fiets">FIETS index DESC</option>
    <option value="gain_m">D+ DESC</option>
    <option value="length_m">Longueur DESC</option>
    <option value="max_slope">Pente max DESC</option>
    <option value="avg_slope">Pente moy DESC</option>
  </select>
  <div class="row" style="margin-top:6px">
    <label>Top N</label>
    <input type="number" id="topn" value="0" min="0" max="{len(climbs)}">
    <span class="muted">(0 = tout)</span>
  </div>

  <div id="counter">- cotes affichees</div>
  <div class="actions">
    <button id="reset">Reset filtres</button>
    <button id="zoomfit">Recadrer</button>
  </div>

  <div id="topbox">
    <b>Top affiche</b>
    <table id="toptable"></table>
  </div>
</div>
<div id="map"></div>
<script>
var center=[{center[0]},{center[1]}];
var map=L.map("map").setView(center,12);
var carto=L.tileLayer("https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png",{{attribution:"&copy; OSM &copy; CartoDB",subdomains:"abcd",maxZoom:19}});
var topo=L.tileLayer("https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png",{{attribution:"&copy; OpenTopoMap (CC-BY-SA)",maxZoom:17,subdomains:"abc"}});
var sat=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",{{attribution:"&copy; Esri",maxZoom:19}});
carto.addTo(map);
L.control.layers({{"CartoDB Voyager":carto,"OpenTopoMap (relief)":topo,"Satellite (Esri)":sat}},null,{{collapsed:true}}).addTo(map);
L.marker(center).addTo(map).bindPopup("Search center");

function color(s){{if(s<3)return"#22c55e";if(s<5)return"#84cc16";if(s<7)return"#eab308";if(s<9)return"#f97316";if(s<12)return"#ef4444";return"#7f1d1d";}}
function popup(p){{return "<div class=popup><b>#"+p.id+" "+p.name+"</b><table>"+
  "<tr><td>Longueur</td><td>"+p.length_m+" m</td></tr>"+
  "<tr><td>D+</td><td>"+p.gain_m+" m</td></tr>"+
  "<tr><td>Pente moy</td><td>"+p.avg_slope+" %</td></tr>"+
  "<tr><td>Pente max</td><td>"+p.max_slope+" %</td></tr>"+
  "<tr><td>FIETS</td><td>"+p.fiets+"</td></tr>"+
  "<tr><td>Score LxS&sup2;</td><td>"+p.score+"</td></tr>"+
  "<tr><td>Highway</td><td>"+(p.highway||"")+"</td></tr>"+
  "<tr><td>Surface</td><td>"+(p.surface||"?")+"</td></tr>"+
  "</table></div>";}}
var data={geojson_str};
var allLayers=[];
data.features.forEach(function(f){{
  var coords=f.geometry.coordinates.map(function(c){{return [c[1],c[0]];}});
  var l=L.polyline(coords,{{color:color(f.properties.avg_slope),weight:5,opacity:0.85}});
  l.bindPopup(popup(f.properties));
  l.bindTooltip("#"+f.properties.id+" "+f.properties.length_m+"m "+f.properties.avg_slope+"%");
  l.feature=f;
  allLayers.push(l);
}});
var layerGroup=L.layerGroup().addTo(map);

function applyFilters(){{
  var lmin=+document.getElementById("lmin").value;
  var lmax=+document.getElementById("lmax").value;
  var gmin=+document.getElementById("gmin").value;
  var smin=+document.getElementById("smin").value;
  var smax=+document.getElementById("smax").value;
  var mmin=+document.getElementById("mmin").value;
  var fmin=+document.getElementById("fmin").value;
  var hwOk={{}};
  document.querySelectorAll(".hw").forEach(function(c){{if(c.checked)hwOk[c.value]=true;}});
  var sortKey=document.getElementById("sort").value;
  var topN=+document.getElementById("topn").value||0;

  document.getElementById("lmin_v").textContent=lmin;
  document.getElementById("lmax_v").textContent=lmax;
  document.getElementById("gmin_v").textContent=gmin;
  document.getElementById("smin_v").textContent=smin;
  document.getElementById("smax_v").textContent=smax;
  document.getElementById("mmin_v").textContent=mmin;
  document.getElementById("fmin_v").textContent=fmin;

  var pass=allLayers.filter(function(l){{
    var p=l.feature.properties;
    if(p.length_m<lmin||p.length_m>lmax)return false;
    if(p.gain_m<gmin)return false;
    if(p.avg_slope<smin||p.avg_slope>smax)return false;
    if(p.max_slope<mmin)return false;
    if(p.fiets<fmin)return false;
    if(!hwOk[p.highway||""]&&!(p.highway==""&&Object.keys(hwOk).length===0))return false;
    return true;
  }});
  pass.sort(function(a,b){{return b.feature.properties[sortKey]-a.feature.properties[sortKey];}});
  if(topN>0)pass=pass.slice(0,topN);

  layerGroup.clearLayers();
  pass.forEach(function(l){{layerGroup.addLayer(l);}});

  document.getElementById("counter").textContent=pass.length+" cotes affichees";
  var tbody=document.getElementById("toptable");
  tbody.innerHTML="";
  pass.slice(0,15).forEach(function(l){{
    var p=l.feature.properties;
    var tr=document.createElement("tr");
    tr.innerHTML="<td>#"+p.id+"</td><td>"+p.length_m+"m</td><td>"+p.gain_m+"m</td><td>"+p.avg_slope+"%</td><td>"+p.max_slope+"%</td>";
    tr.onclick=function(){{map.fitBounds(l.getBounds(),{{maxZoom:16}});l.openPopup();}};
    tbody.appendChild(tr);
  }});
}}

document.querySelectorAll("#panel input,#panel select").forEach(function(e){{
  e.addEventListener("input",applyFilters);
  e.addEventListener("change",applyFilters);
}});
document.getElementById("reset").onclick=function(){{
  document.getElementById("lmin").value=0;
  document.getElementById("lmax").value={int(max_len)};
  document.getElementById("gmin").value=0;
  document.getElementById("smin").value=0;
  document.getElementById("smax").value={int(max_avg)+1};
  document.getElementById("mmin").value=0;
  document.getElementById("fmin").value=0;
  document.getElementById("topn").value=0;
  document.getElementById("sort").value="fiets";
  document.querySelectorAll(".hw").forEach(function(c){{c.checked=true;}});
  applyFilters();
}};
document.getElementById("zoomfit").onclick=function(){{
  var bounds=L.latLngBounds([]);
  layerGroup.eachLayer(function(l){{bounds.extend(l.getBounds());}});
  if(bounds.isValid())map.fitBounds(bounds,{{padding:[20,20]}});
}};

var legend=L.control({{position:"bottomright"}});
legend.onAdd=function(){{var d=L.DomUtil.create("div","legend");d.innerHTML="<b>Pente moy</b><br>"+
  "<i style=background:#22c55e></i>&lt;3%<br>"+
  "<i style=background:#84cc16></i>3-5%<br>"+
  "<i style=background:#eab308></i>5-7%<br>"+
  "<i style=background:#f97316></i>7-9%<br>"+
  "<i style=background:#ef4444></i>9-12%<br>"+
  "<i style=background:#7f1d1d></i>&gt;12%";return d;}};
legend.addTo(map);

applyFilters();
</script></body></html>"""
    MAP_HTML.write_text(html, encoding="utf-8")
    print(f"  [out] {MAP_HTML}  ({len(climbs)} climbs)")


# ============================================================================
# Validation contre cotes connues
# ============================================================================

KNOWN_CLIMBS = [
    # name, midpoint_lat, midpoint_lon, exp_length_m, exp_gain_m, exp_slope_pct
    ("cote_courte_pentu", 48.39790, 0.64074, 413, 36.5, 8.8),
    ("cote_de_corubert",  48.39771, 0.64587, 1207, 59.1, 5.0),
    ("cote_douce",        None, None, 1250, 52.0, 4.2),   # midpoint inconnu
]


def validate(climbs: list[dict]):
    print("\n=== Validation contre cotes connues ===")
    for name, mlat, mlon, e_len, e_gain, e_slope in KNOWN_CLIMBS:
        if mlat is None:
            print(f"  {name:25s} (skip, midpoint inconnu)")
            continue
        # Cherche le climb decouvert le plus proche
        best = min(climbs, key=lambda c: haversine_m(
            c["midpoint_lat"], c["midpoint_lon"], mlat, mlon))
        d = haversine_m(best["midpoint_lat"], best["midpoint_lon"], mlat, mlon)
        len_err = (best["length_m"] - e_len) / e_len * 100
        gain_err = (best["gain_m"] - e_gain) / e_gain * 100
        slope_err = (best["avg_slope_pct"] - e_slope) / e_slope * 100
        match = "OK" if d < 200 else "FAR"
        print(f"  {name:25s} closest #{best['id']} d={d:.0f}m  "
              f"L={best['length_m']}m ({len_err:+.0f}%)  "
              f"D+={best['gain_m']}m ({gain_err:+.0f}%)  "
              f"avg={best['avg_slope_pct']}% ({slope_err:+.0f}%)  [{match}]")


# ============================================================================
# Subcommands
# ============================================================================

def cmd_detect(args):
    center = tuple(float(x) for x in args.center.split(","))
    print(f"\n=== DETECT ({args.radius}km autour de {center}) ===\n")

    # 1. Overpass
    print("[1/4] Fetch ways OSM")
    ways = fetch_ways(center, args.radius, force=args.force_overpass)

    # 2. Resample geometries + collecte points uniques
    print(f"[2/4] Resample geometries (step={args.sample_step}m)")
    sampled_per_way = []
    all_points = []
    for w in ways:
        sw = resample_way(w["geometry"], step_m=args.sample_step)
        sampled_per_way.append(sw)
        all_points.extend(sw)
    print(f"  {len(all_points)} points sampled across {len(ways)} ways")

    # 3. Elevation
    print("[3/4] Fetch elevations (EU-DEM 25m + cache)")
    elevs_dict = fetch_elevations(all_points)

    # 4. Detect climbs
    print("[4/4] Detect climbs per way + dedup")
    params = {
        "min_length": args.min_length,
        "min_gain": args.min_gain,
        "min_avg_slope": args.min_slope,
    }
    raw = []
    for w, sw in zip(ways, sampled_per_way):
        raw.extend(detect_climbs_in_way(w, sw, elevs_dict, params))
    print(f"  raw climbs: {len(raw)}")
    deduped = dedup_climbs(raw)
    print(f"  after dedup: {len(deduped)}")

    # Outputs
    print("\n[outputs]")
    write_outputs(deduped)
    write_all_gpx(deduped)
    write_map(deduped, center)

    # Validation
    if deduped:
        validate(deduped)

    # Top 10 par fiets
    print("\n=== TOP 10 par FIETS index ===")
    print(f"{'#':>3s}  {'L(m)':>5s}  {'D+(m)':>5s}  {'avg%':>5s}  {'max%':>5s}  "
          f"{'fiets':>6s}  {'highway':>15s}  name")
    for c in deduped[:10]:
        print(f"  {c['id']:>3d}  {c['length_m']:>5d}  {c['gain_m']:>5.1f}  "
              f"{c['avg_slope_pct']:>5.1f}  {c['max_slope_pct']:>5.1f}  "
              f"{c['fiets_index']:>6.2f}  {c['way_highway']:>15s}  {c['way_name']}")


def cmd_filter(args):
    if not CATALOG_CSV.exists():
        print(f"No catalog yet. Run `detect` first.")
        sys.exit(1)
    rows = list(csv.DictReader(open(CATALOG_CSV, encoding="utf-8")))
    out = []
    for r in rows:
        L = int(r["length_m"]); g = float(r["gain_m"])
        s_avg = float(r["avg_slope_pct"]); s_max = float(r["max_slope_pct"])
        if args.min_length and L < args.min_length: continue
        if args.max_length and L > args.max_length: continue
        if args.min_gain and g < args.min_gain: continue
        if args.slope_min and s_avg < args.slope_min: continue
        if args.slope_max and s_avg > args.slope_max: continue
        if args.max_slope_min and s_max < args.max_slope_min: continue
        if args.highway and r["way_highway"] not in args.highway.split(","): continue
        out.append(r)
    print(f"{len(out)} cotes match (sur {len(rows)})\n")
    print(f"{'#':>3s}  {'L(m)':>5s}  {'D+(m)':>5s}  {'avg%':>5s}  {'max%':>5s}  "
          f"{'fiets':>6s}  {'highway':>14s}  name")
    for r in out:
        print(f"  {int(r['id']):>3d}  {int(r['length_m']):>5d}  {float(r['gain_m']):>5.1f}  "
              f"{float(r['avg_slope_pct']):>5.1f}  {float(r['max_slope_pct']):>5.1f}  "
              f"{float(r['fiets_index']):>6.2f}  {r['way_highway']:>14s}  {r['way_name']}")


def cmd_export_gpx(args):
    files = sorted(DISCOVERED_DIR.glob("*.json"))
    target = None
    for f in files:
        c = json.load(open(f, encoding="utf-8"))
        if c["id"] == args.id:
            target = c; break
    if not target:
        print(f"id {args.id} not found"); sys.exit(1)
    slug = slugify(target["way_name"]) if target["way_name"] else f"way{target['way_id']}"
    out = GPX_DIR / f"{target['id']:03d}_{slug}.gpx"
    write_gpx(target, out)
    print(f"GPX: {out}")


def cmd_map(args):
    if not CATALOG_GEOJSON.exists():
        print("No catalog. Run `detect` first."); sys.exit(1)
    gj = json.load(open(CATALOG_GEOJSON, encoding="utf-8"))
    climbs = []
    for f in gj["features"]:
        p = f["properties"]
        coords = f["geometry"]["coordinates"]
        climbs.append({
            "id": p["id"], "way_id": p["way_id"], "way_name": p["way_name"],
            "way_highway": p["way_highway"], "way_surface": p["way_surface"],
            "length_m": p["length_m"], "gain_m": p["gain_m"],
            "avg_slope_pct": p["avg_slope_pct"], "max_slope_pct": p["max_slope_pct"],
            "fiets_index": p["fiets_index"], "score_lxs2": p["score_lxs2"],
            "geometry": [[la, lo] for lo, la in coords],
        })
    center = tuple(float(x) for x in (args.center or f"{DEFAULT_CENTER[0]},{DEFAULT_CENTER[1]}").split(","))
    write_map(climbs, center)


def cmd_validate(args):
    if not CATALOG_GEOJSON.exists():
        print("No catalog. Run `detect` first."); sys.exit(1)
    gj = json.load(open(CATALOG_GEOJSON, encoding="utf-8"))
    climbs = [{**f["properties"],
               "midpoint_lat": f["properties"]["midpoint_lat"],
               "midpoint_lon": f["properties"]["midpoint_lon"]}
              for f in gj["features"]]
    validate(climbs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("detect", help="Decouvre les cotes via Overpass + DEM")
    pd.add_argument("--center", default=f"{DEFAULT_CENTER[0]},{DEFAULT_CENTER[1]}")
    pd.add_argument("--radius", type=float, default=DEFAULT_RADIUS_KM, help="km")
    pd.add_argument("--sample-step", type=float, default=DEFAULT_SAMPLE_M, help="m")
    pd.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH)
    pd.add_argument("--min-gain", type=int, default=DEFAULT_MIN_GAIN)
    pd.add_argument("--min-slope", type=float, default=DEFAULT_MIN_AVG_SLOPE)
    pd.add_argument("--force-overpass", action="store_true",
                    help="Re-fetch Overpass meme si cache existant")
    pd.set_defaults(func=cmd_detect)

    pf = sub.add_parser("filter", help="Filtre catalog.csv")
    pf.add_argument("--min-length", type=int)
    pf.add_argument("--max-length", type=int)
    pf.add_argument("--min-gain", type=float)
    pf.add_argument("--slope-min", type=float)
    pf.add_argument("--slope-max", type=float)
    pf.add_argument("--max-slope-min", type=float, help="Filtre sur max_slope >= X")
    pf.add_argument("--highway", help="csv: path,track,unclassified,...")
    pf.set_defaults(func=cmd_filter)

    pe = sub.add_parser("export-gpx", help="Genere un GPX pour une cote (par id)")
    pe.add_argument("--id", type=int, required=True)
    pe.set_defaults(func=cmd_export_gpx)

    pm = sub.add_parser("map", help="Regenere la carte HTML")
    pm.add_argument("--center")
    pm.set_defaults(func=cmd_map)

    pv = sub.add_parser("validate", help="Compare contre cotes connues")
    pv.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
