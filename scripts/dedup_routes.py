"""
Deduplique la bibliotheque de parcours analyses.

Critere "meme parcours physique" (multi-criteres) :
  - is_loop identique
  - depart proche (haversine < START_TOL_M) ET arrivee proche, OU
    depart match arrivee de l'autre + arrivee match depart (parcours inverse)
  - distance differe de < DIST_TOL_PCT %
  - D+ differe de < ELEV_TOL_PCT % (mais avec un floor absolu ELEV_TOL_M)

Survivant choisi par cluster :
  - Route nommee (ex. cote_courte_pentu, mariette_classique) > activity_*
  - Sinon : activity_<id> avec id le plus eleve (= recording le plus recent)

Pour les doublons :
  - JSON supprime de data/routes/
  - GPX deplace dans data/gpx/_duplicates/ (archive recuperable)

Usage :
  python dedup_routes.py            # dry-run par defaut
  python dedup_routes.py --apply    # execute la suppression
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
ROUTES_DIR = ROOT / "data" / "routes"
GPX_DIR = ROOT / "data" / "gpx"
DUPS_DIR = GPX_DIR / "_duplicates"

# Tolerances (serrees : pour les loops partant du meme point, dist+D+ sont
# les seuls vrais discriminants)
START_TOL_M = 150.0
DIST_TOL_PCT = 0.05
ELEV_TOL_PCT = 0.12
ELEV_TOL_M = 10.0


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))


def load_all():
    routes = []
    for p in sorted(ROUTES_DIR.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            routes.append(json.load(f))
    return routes


def is_named(name: str) -> bool:
    return not name.startswith("activity_")


def activity_id(name: str) -> int:
    return int(name.replace("activity_", "")) if name.startswith("activity_") else 0


def similar(a: dict, b: dict) -> bool:
    if a["is_loop"] != b["is_loop"]:
        return False

    a_s, a_e = a["start_coords"], a["end_coords"]
    b_s, b_e = b["start_coords"], b["end_coords"]
    d_ss = haversine_m(*a_s, *b_s)
    d_ee = haversine_m(*a_e, *b_e)
    d_se = haversine_m(*a_s, *b_e)   # a-start vs b-end (sens inverse)
    d_es = haversine_m(*a_e, *b_s)

    fwd = d_ss < START_TOL_M and d_ee < START_TOL_M
    rev = d_se < START_TOL_M and d_es < START_TOL_M
    # Pour les boucles, depart=arrivee donc seul d_ss compte
    if a["is_loop"] and b["is_loop"]:
        same_area = d_ss < START_TOL_M
    else:
        same_area = fwd or rev
    if not same_area:
        return False

    # Distance
    da, db = a["distance_m"], b["distance_m"]
    if max(da, db) > 0 and abs(da - db) / max(da, db) > DIST_TOL_PCT:
        return False

    # D+
    ea, eb = a["elev_gain_m"], b["elev_gain_m"]
    elev_diff = abs(ea - eb)
    elev_max = max(ea, eb)
    if elev_diff > max(ELEV_TOL_M, ELEV_TOL_PCT * elev_max):
        return False

    return True


def cluster(routes: list[dict]) -> list[list[dict]]:
    """Clustering strict : un point est ajoute a un cluster ssi il est similaire
    a TOUS les membres deja presents (clique). Ca casse l'effet de chaine du
    union-find quand bcp de loops partent du meme point.

    Routes nommees traitees en priorite (deviennent les "ancres" des clusters).
    """
    ordered = sorted(
        routes,
        key=lambda r: (0 if is_named(r["name"]) else 1, -r["distance_m"]),
    )
    clusters: list[list[dict]] = []
    for r in ordered:
        placed = False
        for c in clusters:
            if all(similar(r, m) for m in c):
                c.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])
    return clusters


def pick_survivor(group: list[dict]) -> dict:
    named = [r for r in group if is_named(r["name"])]
    if named:
        # priorite la plus enrichie (le plus de segments)
        return max(named, key=lambda r: len(r.get("segments", [])))
    # Sinon : activity_<id> max (le + recent)
    return max(group, key=lambda r: activity_id(r["name"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="execute la suppression (sinon dry-run)")
    args = ap.parse_args()

    routes = load_all()
    print(f"Loaded {len(routes)} routes\n")

    clusters = cluster(routes)
    dupe_clusters = [g for g in clusters if len(g) > 1]
    singletons = [g[0] for g in clusters if len(g) == 1]

    print(f"=== {len(dupe_clusters)} clusters de doublons (cumul {sum(len(g) for g in dupe_clusters)} routes) ===\n")
    to_delete = []
    for g in sorted(dupe_clusters, key=lambda x: -len(x)):
        survivor = pick_survivor(g)
        print(f"Cluster ({len(g)} routes) - SURVIVOR: {survivor['name']}")
        print(f"   ({survivor['distance_m']}m, D+{int(survivor['elev_gain_m'])}m, "
              f"loop={survivor['is_loop']}, segs={len(survivor.get('segments', []))})")
        for r in g:
            mark = " [KEEP]" if r["name"] == survivor["name"] else " [DEL ]"
            print(f"  {mark} {r['name']:35s} {r['distance_m']:>6}m  "
                  f"D+{int(r['elev_gain_m']):>4}m  segs={len(r.get('segments', [])):>3}")
            if r["name"] != survivor["name"]:
                to_delete.append(r["name"])
        print()

    print(f"=== {len(singletons)} routes uniques (conservees) ===")
    for r in sorted(singletons, key=lambda x: x["name"]):
        print(f"  {r['name']:35s} {r['distance_m']:>6}m  D+{int(r['elev_gain_m']):>4}m  "
              f"loop={'Y' if r['is_loop'] else 'N'}")

    print(f"\n=== Resultat ===")
    print(f"  routes initiales : {len(routes)}")
    print(f"  a supprimer      : {len(to_delete)}")
    print(f"  routes finales   : {len(routes) - len(to_delete)}")

    if not args.apply:
        print("\n(dry-run, rien n'est supprime. Relance avec --apply.)")
        return

    DUPS_DIR.mkdir(parents=True, exist_ok=True)
    n_json = n_gpx = 0
    for name in to_delete:
        json_p = ROUTES_DIR / f"{name}.json"
        gpx_p = GPX_DIR / f"{name}.gpx"
        if json_p.exists():
            json_p.unlink()
            n_json += 1
        if gpx_p.exists():
            target = DUPS_DIR / gpx_p.name
            shutil.move(str(gpx_p), str(target))
            n_gpx += 1
    print(f"\nApplied: {n_json} JSON supprimes, {n_gpx} GPX deplaces vers {DUPS_DIR}")


if __name__ == "__main__":
    main()
