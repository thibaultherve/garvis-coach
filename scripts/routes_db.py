"""
Loader / requeteur pour la bibliotheque de parcours analyses.

Usage rapide :
    from routes_db import list_routes, load_route, summarize, segments_df

    list_routes()                          # ['cote_courte_pentu', ...]
    r = load_route('cote_de_corubert')     # dict complet
    summarize(r)                           # synthese 1 ligne
    df = segments_df()                     # DataFrame de TOUS les segments,
                                           # filtrable par attribut (surface,
                                           # waytype, slope, length)

Pour matcher un workout (ex. cotes 6x40s = ~150-200m / 6-8 % / surface souple) :

    df = segments_df()
    candidates = df.query(
        "150 <= length_m <= 250 and 6 <= avg_slope_pct <= 8 "
        "and surface in ['compacted', 'compacted_gravel', 'ground', 'dirt']"
    )
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).parent
ROUTES_DIR = ROOT / "data" / "routes"


def list_routes() -> list[str]:
    """Liste les noms de parcours disponibles."""
    if not ROUTES_DIR.exists():
        return []
    return sorted(p.stem for p in ROUTES_DIR.glob("*.json"))


def load_route(name: str) -> dict:
    """Charge un parcours par nom (sans .json)."""
    p = ROUTES_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"route not found: {name} (in {ROUTES_DIR})")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_all() -> list[dict]:
    return [load_route(n) for n in list_routes()]


def summarize(route: dict) -> str:
    """Resume une ligne d'un parcours (pour print)."""
    surf = ", ".join(f"{k}={v}" for k, v in (route.get("surface_breakdown") or {}).items()) or "n/a"
    return (f"{route['name']:35s}  {route['distance_m']/1000:5.2f}km "
            f"D+{int(route['elev_gain_m']):>4d}m ({route['dplus_per_km']:>5.1f}/km)  "
            f"loop={'Y' if route['is_loop'] else 'N'}  "
            f"flat={route['longest_flat_segment_m']:>5d}m  "
            f"climbs={len(route.get('notable_climbs', []))}  "
            f"surface=[{surf}]")


def routes_df() -> pd.DataFrame:
    """DataFrame top-level (1 ligne par route)."""
    rows = []
    for r in load_all():
        rows.append({
            "name": r["name"],
            "distance_m": r["distance_m"],
            "elev_gain_m": r["elev_gain_m"],
            "elev_loss_m": r["elev_loss_m"],
            "dplus_per_km": r["dplus_per_km"],
            "is_loop": r["is_loop"],
            "longest_flat_segment_m": r["longest_flat_segment_m"],
            "n_climbs": len(r.get("notable_climbs", [])),
            "n_descents": len(r.get("notable_descents", [])),
            "n_segments": len(r.get("segments", [])),
            "ors_warning": r.get("ors_warning"),
        })
    return pd.DataFrame(rows)


def segments_df(route_name: Optional[str] = None) -> pd.DataFrame:
    """DataFrame de TOUS les segments (avec colonne 'route'), filtrable.

    Si route_name fourni : segments de ce parcours uniquement.
    """
    rows = []
    routes = [load_route(route_name)] if route_name else load_all()
    for r in routes:
        for seg in r.get("segments", []):
            rows.append({"route": r["name"], **seg})
    return pd.DataFrame(rows)


def climbs_df(route_name: Optional[str] = None) -> pd.DataFrame:
    """DataFrame de toutes les ascensions notables (notable_climbs)."""
    rows = []
    routes = [load_route(route_name)] if route_name else load_all()
    for r in routes:
        for c in r.get("notable_climbs", []):
            rows.append({"route": r["name"], **c})
    return pd.DataFrame(rows)


def descents_df(route_name: Optional[str] = None) -> pd.DataFrame:
    rows = []
    routes = [load_route(route_name)] if route_name else load_all()
    for r in routes:
        for d in r.get("notable_descents", []):
            rows.append({"route": r["name"], **d})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Routes disponibles :\n")
    for n in list_routes():
        print(" ", summarize(load_route(n)))
