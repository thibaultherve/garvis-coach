"""
Analyse des parcours GPX.

Pour chaque .gpx dans data/gpx/ :
  1. Parse + interpole le profil altitude tous les 10 m (gpxpy + numpy)
  2. Calcule D+/-, distribution pentes, ascensions/descentes notables, plus
     long segment plat
  3. Enrichit via OpenRouteService API : surface (asphalt/track/path/...),
     waytype (residential/track/path/...), steepness, green index
  4. Sauvegarde un JSON par parcours dans data/routes/

Usage :
  python analyze_routes.py            # analyse tous les .gpx
  python analyze_routes.py <name>     # analyse un seul (sans .gpx)
  python analyze_routes.py --no-ors   # skip enrichissement ORS (offline)
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import gpxpy
import numpy as np
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent
GPX_DIR = ROOT / "data" / "gpx"
OUT_DIR = ROOT / "data" / "routes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")
ORS_API_KEY = os.environ.get("ORS_API_KEY")
ORS_URL = "https://api.openrouteservice.org/v2/directions/foot-hiking/geojson"

# ----------------------------------------------------------------------------
# Constantes d'analyse
# ----------------------------------------------------------------------------

SAMPLE_M = 10                       # interpolation profil tous les 10 m
SMOOTH_WINDOW_M = 50                # smoothing altitude
SLOPE_WINDOW_M = 50                 # fenetre pour calcul de pente locale

SLOPE_BINS = [
    ("<-8%", -1e9, -8),
    ("-8_-5%", -8, -5),
    ("-5_-2%", -5, -2),
    ("-2_2%",  -2,  2),
    ("2_5%",    2,  5),
    ("5_8%",    5,  8),
    ("8_12%",   8, 12),
    (">12%",   12, 1e9),
]

NOTABLE_CLIMB_MIN_GAIN_M = 30.0
NOTABLE_CLIMB_MIN_AVG_SLOPE = 3.0
NOTABLE_DESCENT_MIN_LOSS_M = 30.0
NOTABLE_DESCENT_MAX_AVG_SLOPE = -5.0    # plus negatif que -5%
FLAT_MAX_ABS_SLOPE = 1.5
LOOP_THRESHOLD_M = 100.0
ORS_MAX_WAYPOINTS = 65              # downsample si plus (limit ORS = 70)

# Mappings ORS (cf. https://giscience.github.io/openrouteservice/api-reference/extra-info/)
SURFACE_MAP = {
    0: "unknown", 1: "paved", 2: "unpaved", 3: "asphalt", 4: "concrete",
    5: "cobblestone", 6: "metal", 7: "wood", 8: "compacted_gravel",
    9: "fine_gravel", 10: "gravel", 11: "dirt", 12: "ground",
    13: "ice", 14: "paving_stones", 15: "sand", 16: "woodchips",
    17: "grass", 18: "grass_paver",
}
WAYTYPE_MAP = {
    0: "unknown", 1: "state_road", 2: "road", 3: "street", 4: "path",
    5: "track", 6: "cycleway", 7: "footway", 8: "steps", 9: "ferry",
    10: "construction",
}
STEEPNESS_MAP = {
    -5: "<=-16%", -4: "-15_-12%", -3: "-11_-7%", -2: "-6_-4%", -1: "-3_-1%",
    0: "0%", 1: "1_3%", 2: "4_6%", 3: "7_11%", 4: "12_15%", 5: ">=16%",
}

# ----------------------------------------------------------------------------
# Geo helpers
# ----------------------------------------------------------------------------

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))

# ----------------------------------------------------------------------------
# GPX parsing + profil
# ----------------------------------------------------------------------------

def parse_gpx(path: Path):
    """Renvoie (lats, lons, elevs) en arrays numpy."""
    with open(path, encoding="utf-8") as f:
        g = gpxpy.parse(f)
    lat, lon, elev = [], [], []
    for trk in g.tracks:
        for seg in trk.segments:
            for p in seg.points:
                if p.elevation is None:
                    continue
                lat.append(p.latitude); lon.append(p.longitude); elev.append(p.elevation)
    if not lat:
        raise ValueError(f"GPX vide ou sans elevation : {path}")
    return np.array(lat), np.array(lon), np.array(elev)

def cumulative_distance(lat, lon):
    """Cumulative haversine distance (m)."""
    cum = np.zeros(len(lat))
    for i in range(1, len(lat)):
        cum[i] = cum[i-1] + haversine_m(lat[i-1], lon[i-1], lat[i], lon[i])
    return cum

def resample(cum, values, step_m=SAMPLE_M):
    """Interpole values aux distances [0, step_m, 2*step_m, ...]."""
    total = cum[-1]
    n = max(2, int(total / step_m) + 1)
    new_d = np.linspace(0, total, n)
    new_v = np.interp(new_d, cum, values)
    return new_d, new_v

def smooth(values, window_m, step_m):
    """Moving average sur fenetre de window_m (en metres)."""
    half = max(1, int((window_m / step_m) / 2))
    n = len(values)
    out = np.zeros(n)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = values[lo:hi].mean()
    return out

def compute_slope(distances, elevs, window_m=SLOPE_WINDOW_M):
    """Pente locale en % calculee sur fenetre +-window_m/2."""
    step_m = distances[1] - distances[0] if len(distances) > 1 else 1
    half = max(1, int((window_m / step_m) / 2))
    n = len(distances)
    slopes = np.zeros(n)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n - 1, i + half)
        d = distances[hi] - distances[lo]
        if d > 0:
            slopes[i] = (elevs[hi] - elevs[lo]) / d * 100.0
    return slopes

# ----------------------------------------------------------------------------
# Metriques
# ----------------------------------------------------------------------------

def slope_distribution(distances, slopes):
    step_m = distances[1] - distances[0] if len(distances) > 1 else 0
    out = {}
    for label, lo, hi in SLOPE_BINS:
        mask = (slopes >= lo) & (slopes < hi)
        out[label] = round(float(mask.sum() * step_m), 1)
    return out

def find_notable_climbs(distances, elevs, slopes,
                        min_gain=NOTABLE_CLIMB_MIN_GAIN_M,
                        min_avg_slope=NOTABLE_CLIMB_MIN_AVG_SLOPE):
    """Detection contiguous climbs avec hysteresis (entree slope>=1.5, sortie<0.5)."""
    climbs = []
    in_climb = False
    start_i = 0
    for i in range(len(slopes)):
        if not in_climb and slopes[i] >= 1.5:
            in_climb = True
            start_i = i
        elif in_climb and slopes[i] < 0.5:
            in_climb = False
            _emit_climb(climbs, distances, elevs, start_i, i, min_gain, min_avg_slope)
    if in_climb:
        _emit_climb(climbs, distances, elevs, start_i, len(slopes)-1, min_gain, min_avg_slope)
    return climbs

def _emit_climb(climbs, distances, elevs, i_start, i_end, min_gain, min_slope):
    gain = float(elevs[i_end] - elevs[i_start])
    length = float(distances[i_end] - distances[i_start])
    if length <= 0 or gain < min_gain:
        return
    avg = gain / length * 100.0
    if avg < min_slope:
        return
    climbs.append({
        "start_m": int(round(distances[i_start])),
        "end_m": int(round(distances[i_end])),
        "length_m": int(round(length)),
        "gain_m": round(gain, 1),
        "avg_slope_pct": round(avg, 1),
    })

def find_notable_descents(distances, elevs, slopes,
                          min_loss=NOTABLE_DESCENT_MIN_LOSS_M,
                          max_avg_slope=NOTABLE_DESCENT_MAX_AVG_SLOPE):
    descents = []
    in_desc = False
    start_i = 0
    for i in range(len(slopes)):
        if not in_desc and slopes[i] <= -1.5:
            in_desc = True
            start_i = i
        elif in_desc and slopes[i] > -0.5:
            in_desc = False
            _emit_descent(descents, distances, elevs, start_i, i, min_loss, max_avg_slope)
    if in_desc:
        _emit_descent(descents, distances, elevs, start_i, len(slopes)-1, min_loss, max_avg_slope)
    return descents

def _emit_descent(out, distances, elevs, i_start, i_end, min_loss, max_avg_slope):
    loss = float(elevs[i_start] - elevs[i_end])
    length = float(distances[i_end] - distances[i_start])
    if length <= 0 or loss < min_loss:
        return
    avg = -loss / length * 100.0
    if avg > max_avg_slope:    # avg plus haut que seuil = pas assez raide
        return
    out.append({
        "start_m": int(round(distances[i_start])),
        "end_m": int(round(distances[i_end])),
        "length_m": int(round(length)),
        "loss_m": round(loss, 1),
        "avg_slope_pct": round(avg, 1),
    })

def longest_flat_segment(distances, slopes, max_abs=FLAT_MAX_ABS_SLOPE):
    best = 0.0
    cur = None
    for i in range(len(slopes)):
        if abs(slopes[i]) < max_abs:
            if cur is None: cur = i
        else:
            if cur is not None:
                length = float(distances[i] - distances[cur])
                if length > best: best = length
                cur = None
    if cur is not None:
        length = float(distances[-1] - distances[cur])
        if length > best: best = length
    return int(round(best))

def total_dplus_dminus(elevs):
    """D+/D- robuste sur signal lisse."""
    diff = np.diff(elevs)
    dplus = float(diff[diff > 0].sum()) if (diff > 0).any() else 0.0
    dminus = float(-diff[diff < 0].sum()) if (diff < 0).any() else 0.0
    return round(dplus, 1), round(dminus, 1)

# ----------------------------------------------------------------------------
# OpenRouteService
# ----------------------------------------------------------------------------

def downsample_for_ors(lat, lon, max_pts=ORS_MAX_WAYPOINTS):
    """Garde max_pts points uniformement distribues (premier + dernier inclus)."""
    n = len(lat)
    if n <= max_pts:
        return lat, lon
    idx = np.linspace(0, n - 1, max_pts).round().astype(int)
    idx = sorted(set(idx.tolist()))
    return lat[idx], lon[idx]

def call_ors(lat, lon):
    coords = [[float(lon[i]), float(lat[i])] for i in range(len(lat))]
    body = {
        "coordinates": coords,
        "extra_info": ["surface", "waytype", "steepness", "green"],
        "elevation": True,
    }
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    r = requests.post(ORS_URL, json=body, headers=headers, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"ORS {r.status_code}: {r.text[:300]}")
    return r.json()

def parse_ors_response(resp):
    """Retourne (ors_cum_dist, ors_extras_dict, ors_dist_total).

    extras_dict[key] = list of (start_m, end_m, label)
    Le mapping ORS donne values=[start_idx, end_idx, val_id] ou les indices
    sont ceux de la geometry retournee. On convertit en cumulative distance.
    """
    feat = resp["features"][0]
    geom = feat["geometry"]["coordinates"]   # [[lon, lat, elev], ...]
    # cumulative distance le long de la geometry ORS
    pts = np.array(geom)
    cum = np.zeros(len(pts))
    for i in range(1, len(pts)):
        cum[i] = cum[i-1] + haversine_m(pts[i-1][1], pts[i-1][0], pts[i][1], pts[i][0])
    extras_raw = feat["properties"].get("extras", {})
    summaries = {}
    extras_segs = {}
    for key, val_map in [("surface", SURFACE_MAP), ("waytype", WAYTYPE_MAP),
                         ("steepness", STEEPNESS_MAP), ("green", None)]:
        if key not in extras_raw:
            extras_segs[key] = []
            summaries[key] = {}
            continue
        values = extras_raw[key].get("values", [])
        summary = extras_raw[key].get("summary", [])
        # Summary: distance + amount (%)
        sm = {}
        for s in summary:
            v = int(s["value"])
            label = val_map.get(v, str(v)) if val_map else float(v)
            sm[str(label)] = round(float(s["amount"]) / 100, 3)
        summaries[key] = sm
        segs = []
        for start_idx, end_idx, val in values:
            s_m = float(cum[int(start_idx)])
            e_m = float(cum[min(int(end_idx), len(cum)-1)])
            label = val_map.get(int(val), str(val)) if val_map else float(val)
            segs.append((s_m, e_m, label))
        extras_segs[key] = segs
    return cum, extras_segs, summaries

def lookup_at(d_m, segs, default=None):
    for s, e, lbl in segs:
        if s <= d_m <= e:
            return lbl
    return default

# ----------------------------------------------------------------------------
# Construction segments fusionnes
# ----------------------------------------------------------------------------

def build_merged_segments(my_dist, my_elev, ors_total, extras_segs):
    """Decoupe le parcours aux changements OSM (surface, waytype, steepness)
    en utilisant les distances ORS rescalees sur la distance reelle GPX.

    On suppose ors_total ~ my_dist[-1]. On rescale lineairement.
    """
    my_total = float(my_dist[-1])
    if ors_total <= 0:
        scale = 1.0
    else:
        scale = my_total / ors_total

    breaks = {0.0, my_total}
    for key in ("surface", "waytype", "steepness"):
        for s, e, _ in extras_segs.get(key, []):
            breaks.add(round(s * scale, 1))
            breaks.add(round(e * scale, 1))
    breaks = sorted(b for b in breaks if 0 <= b <= my_total)
    # Deduplique tres rapproches (<5 m)
    cleaned = [breaks[0]]
    for b in breaks[1:]:
        if b - cleaned[-1] >= 5:
            cleaned.append(b)
    if cleaned[-1] != my_total:
        cleaned.append(my_total)

    segments = []
    for i in range(len(cleaned) - 1):
        s_m, e_m = cleaned[i], cleaned[i+1]
        mid = (s_m + e_m) / 2
        elev_s = float(np.interp(s_m, my_dist, my_elev))
        elev_e = float(np.interp(e_m, my_dist, my_elev))
        length = e_m - s_m
        # extras a chercher en distance ORS (mid / scale)
        ors_mid = mid / scale if scale else mid
        surface = lookup_at(ors_mid, extras_segs.get("surface", []), default="unknown")
        waytype = lookup_at(ors_mid, extras_segs.get("waytype", []), default="unknown")
        steep_label = lookup_at(ors_mid, extras_segs.get("steepness", []), default="0%")
        # steepness_class : on remappe label -> int
        steep_class = next((k for k, v in STEEPNESS_MAP.items() if v == steep_label), 0)
        green = lookup_at(ors_mid, extras_segs.get("green", []), default=None)
        # pente locale : on relit my_dist/my_elev sur ce segment
        if length > 0:
            avg_slope = (elev_e - elev_s) / length * 100
        else:
            avg_slope = 0.0
        # max slope : on regarde le profil sur ce segment
        mask = (my_dist >= s_m) & (my_dist <= e_m)
        if mask.sum() >= 2:
            sub_d = my_dist[mask]; sub_e = my_elev[mask]
            local_slopes = np.diff(sub_e) / np.maximum(np.diff(sub_d), 1) * 100
            max_slope = float(local_slopes.max() if len(local_slopes) else avg_slope)
            min_slope = float(local_slopes.min() if len(local_slopes) else avg_slope)
        else:
            max_slope = avg_slope; min_slope = avg_slope
        segments.append({
            "start_m": int(round(s_m)),
            "end_m": int(round(e_m)),
            "length_m": int(round(length)),
            "elev_start_m": round(elev_s, 1),
            "elev_end_m": round(elev_e, 1),
            "elev_delta_m": round(elev_e - elev_s, 1),
            "avg_slope_pct": round(avg_slope, 1),
            "max_slope_pct": round(max_slope, 1),
            "min_slope_pct": round(min_slope, 1),
            "surface": surface,
            "waytype": waytype,
            "steepness_class": steep_class,
            "green_index": float(green) if green is not None else None,
        })
    # filtre micro-segments (<10m) sauf si le seul
    if len(segments) > 1:
        segments = [s for s in segments if s["length_m"] >= 10] or segments
    return segments

# ----------------------------------------------------------------------------
# Pipeline principal
# ----------------------------------------------------------------------------

def analyze_one(gpx_path: Path, use_ors: bool):
    name = gpx_path.stem
    print(f"\n=== {name} ===")
    lat, lon, elev = parse_gpx(gpx_path)
    cum_raw = cumulative_distance(lat, lon)
    print(f"  GPX brut: {len(lat)} pts, {cum_raw[-1]:.0f} m")

    # Profil interpole tous les SAMPLE_M, lisse
    distances, elevs_interp = resample(cum_raw, elev, step_m=SAMPLE_M)
    elevs_smooth = smooth(elevs_interp, SMOOTH_WINDOW_M, SAMPLE_M)
    slopes = compute_slope(distances, elevs_smooth, SLOPE_WINDOW_M)

    dplus, dminus = total_dplus_dminus(elevs_smooth)
    distance_m = float(distances[-1])
    is_loop = haversine_m(lat[0], lon[0], lat[-1], lon[-1]) <= LOOP_THRESHOLD_M

    climbs = find_notable_climbs(distances, elevs_smooth, slopes)
    descents = find_notable_descents(distances, elevs_smooth, slopes)
    flat = longest_flat_segment(distances, slopes)
    slopes_dist = slope_distribution(distances, slopes)

    print(f"  D+={dplus:.0f}m D-={dminus:.0f}m  loop={is_loop}  flat_max={flat}m")
    print(f"  climbs={len(climbs)} descents={len(descents)}")

    # ORS enrichissement
    surface_breakdown = {}
    waytype_breakdown = {}
    steepness_breakdown = {}
    segments = []
    ors_warning = None

    if use_ors and ORS_API_KEY:
        try:
            lat_ds, lon_ds = downsample_for_ors(lat, lon)
            print(f"  ORS query: {len(lat_ds)} waypoints...")
            resp = call_ors(lat_ds, lon_ds)
            ors_cum, extras_segs, summaries = parse_ors_response(resp)
            ors_total = float(ors_cum[-1])
            surface_breakdown = summaries.get("surface", {})
            waytype_breakdown = summaries.get("waytype", {})
            steepness_breakdown = summaries.get("steepness", {})
            segments = build_merged_segments(distances, elevs_smooth, ors_total, extras_segs)
            ratio = ors_total / max(distance_m, 1)
            print(f"    ORS ok: {ors_total:.0f}m (ratio={ratio:.2f}), {len(segments)} segments")
            if abs(ratio - 1) > 0.15:
                ors_warning = f"ORS distance differs by {(ratio-1)*100:.0f}% from GPX (routing may not match)"
                print(f"    WARN: {ors_warning}")
        except Exception as e:
            ors_warning = f"ORS failed: {e}"
            print(f"    ORS error: {e}")
    else:
        print("  ORS skipped")

    out = {
        "name": name,
        "is_loop": bool(is_loop),
        "start_coords": [float(round(lat[0], 6)), float(round(lon[0], 6))],
        "end_coords": [float(round(lat[-1], 6)), float(round(lon[-1], 6))],
        "distance_m": int(round(distance_m)),
        "elev_gain_m": dplus,
        "elev_loss_m": dminus,
        "dplus_per_km": round(dplus / max(distance_m / 1000, 0.001), 1),
        "longest_flat_segment_m": flat,
        "slope_distribution_m": slopes_dist,
        "surface_breakdown": surface_breakdown,
        "waytype_breakdown": waytype_breakdown,
        "steepness_breakdown": steepness_breakdown,
        "notable_climbs": climbs,
        "notable_descents": descents,
        "profile": [[int(round(d)), round(float(e), 1)] for d, e in zip(distances, elevs_smooth)],
        "segments": segments,
        "ors_warning": ors_warning,
    }
    return out

def write_route(name, data):
    p = OUT_DIR / f"{name}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  -> {p}")

# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    use_ors = True
    target = None
    for a in args:
        if a == "--no-ors":
            use_ors = False
        elif a.startswith("--"):
            print(f"unknown flag: {a}"); sys.exit(2)
        else:
            target = a

    if use_ors and not ORS_API_KEY:
        print("WARN: ORS_API_KEY not set in .env, falling back to --no-ors")
        use_ors = False

    if target:
        gpx = GPX_DIR / f"{target}.gpx"
        if not gpx.exists():
            print(f"not found: {gpx}"); sys.exit(1)
        files = [gpx]
    else:
        files = sorted(GPX_DIR.glob("*.gpx"))

    summary_rows = []
    for gpx in files:
        try:
            data = analyze_one(gpx, use_ors)
            write_route(gpx.stem, data)
            summary_rows.append((gpx.stem, data))
        except Exception as e:
            print(f"  FAIL: {e}")

    print("\n=== SUMMARY ===")
    print(f"{'name':40s} {'dist':>7s} {'D+':>5s} {'D+/km':>6s} {'loop':>5s} {'flat':>6s} {'segs':>5s}")
    for name, d in summary_rows:
        print(f"{name:40s} {d['distance_m']:>6d}m "
              f"{int(d['elev_gain_m']):>4d}m "
              f"{d['dplus_per_km']:>6.1f} "
              f"{'Y' if d['is_loop'] else 'N':>5s} "
              f"{d['longest_flat_segment_m']:>5d}m "
              f"{len(d['segments']):>5d}")

if __name__ == "__main__":
    main()
