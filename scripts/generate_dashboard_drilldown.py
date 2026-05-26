"""
Genere le dashboard Grafana 'Activity Drill-Down' (drill-down par run)
depuis workouts_data.py + un template JSON.

Usage : python generate_dashboard_drilldown.py
Sortie : ecrit dans DASHBOARD_OUTPUT_PATH (defaut: ./dashboards/03-activity-drill-down.json)

Env vars :
  DASHBOARD_OUTPUT_PATH  - chemin du JSON de sortie (defaut: ./dashboards/03-activity-drill-down.json)
  GRAFANA_URL            - URL Grafana pour le lien final (defaut: http://localhost:3000)

Zones HR/Power : lues depuis l'API Garmin si garminconnect est installe,
sinon fallback generiques. Les zones sont aussi exposees en variables
dashboard qui lisent HRZones/PowerZones depuis InfluxDB.

Si workouts_data.py change (nouveaux cycles) -> re-run pour rafraichir le panel
'Workout prescribed reference'.
"""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# --- InfluxDB helper (lit .env pour les creds) ---
def load_env():
    env = {}
    envp = Path(__file__).parent / ".env"
    if envp.exists():
        for line in envp.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def fetch_recent_activities(limit=30):
    """Query InfluxDB pour les N dernieres activites running avec leurs bounds.
    Retourne liste de dicts {selector, name, distance_km, duration_s, avg_hr, start_iso, end_iso}.
    """
    env = load_env()
    if "INFLUX_URL" not in env:
        print("WARN: .env not found or INFLUX_URL missing - skipping activity list")
        return []
    q = (
        'SELECT "ActivitySelector","activityName","distance","elapsedDuration","averageHR" '
        'FROM "ActivitySummary" '
        'WHERE "ActivitySelector" =~ /running/ AND "activityName" != \'END\' '
        f'ORDER BY time DESC LIMIT {limit}'
    )
    url = f'{env["INFLUX_URL"]}/query?db={env["INFLUX_DB"]}&q=' + urllib.parse.quote(q)
    req = urllib.request.Request(url)
    import base64
    auth = base64.b64encode(f'{env["INFLUX_USER"]}:{env["INFLUX_PASS"]}'.encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    series = data.get("results", [{}])[0].get("series", [])
    if not series:
        return []
    cols = series[0]["columns"]
    rows = series[0]["values"]
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        if not d.get("elapsedDuration"):
            continue
        start = datetime.fromisoformat(d["time"].replace("Z", "+00:00"))
        end = start + timedelta(seconds=float(d["elapsedDuration"]))
        out.append({
            "selector": d["ActivitySelector"],
            "name": d["activityName"] or "(no name)",
            "distance_km": (d.get("distance") or 0) / 1000,
            "duration_s": float(d["elapsedDuration"]),
            "avg_hr": d.get("averageHR") or 0,
            "start_iso": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_iso": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_local": start.strftime("%Y-%m-%d %H:%M"),
        })
    return out


DEST = Path(os.environ.get("DASHBOARD_OUTPUT_PATH", "./dashboards/03-activity-drill-down.json"))

# Fallback (utilises seulement si l'API Garmin est inaccessible)
_FALLBACK_HR_Z = [(120, 140), (140, 155), (155, 170), (170, 185), (185, 220)]
_FALLBACK_PWR_Z = [(200, 260), (260, 310), (310, 350), (350, 400), (400, 9999)]

# Zones recuperees au runtime depuis l'API Garmin (overridees dans main())
HR_Z = list(_FALLBACK_HR_Z)
PWR_Z = list(_FALLBACK_PWR_Z)

DS = {"type": "influxdb", "uid": "garmin_influxdb"}


def fetch_zones_from_garmin():
    """Query Garmin API pour les zones HR + Power running actuelles.
    Retourne (hr_z, pwr_z) ou les fallbacks en cas d'erreur."""
    try:
        from garminconnect import Garmin
        api = Garmin()
        api.login()
        # HR zones (sport=RUNNING)
        hr_data = api.connectapi("/biometric-service/heartRateZones")
        hr_z = list(_FALLBACK_HR_Z)
        for entry in hr_data or []:
            if entry.get("sport") == "RUNNING":
                floors = [int(entry[f"zone{i}Floor"]) for i in range(1, 6)]
                top = int(entry["maxHeartRateUsed"])
                hr_z = [(floors[i], floors[i + 1] if i < 4 else top) for i in range(5)]
                break
        # Power zones (sport=RUNNING)
        pwr_z = list(_FALLBACK_PWR_Z)
        try:
            pwr_data = api.connectapi("/biometric-service/powerZones/sport/RUNNING")
            if pwr_data:
                floors = [int(pwr_data[f"zone{i}Floor"]) for i in range(1, 6)]
                # Z5 = floor jusqu'a +inf, on met une borne haute fictive pour la query InfluxDB
                pwr_z = [(floors[i], floors[i + 1] if i < 4 else 9999) for i in range(5)]
        except Exception as e:
            print(f"  WARN power zones API: {e}")
        return hr_z, pwr_z
    except Exception as e:
        print(f"  WARN garmin login/zones API failed: {e} - using fallback values")
        return list(_FALLBACK_HR_Z), list(_FALLBACK_PWR_Z)


def stat_panel(panel_id, title, x, y, w_, h, query, unit="none", decimals=0, thresholds=None, description=""):
    fc = {"defaults": {"unit": unit, "decimals": decimals, "color": {"mode": "thresholds"}}}
    if thresholds:
        fc["defaults"]["thresholds"] = {"mode": "absolute", "steps": thresholds}
    return {
        "type": "stat", "id": panel_id, "title": title, "description": description,
        "gridPos": {"h": h, "w": w_, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": fc,
        "options": {
            "graphMode": "none", "colorMode": "value", "textMode": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "auto", "justifyMode": "center"
        },
        "targets": [{"refId": "A", "rawQuery": True, "query": query, "resultFormat": "time_series", "groupBy": [], "tags": []}],
    }


def ts_panel(panel_id, title, x, y, w_, h, query, unit="none", decimals=2, thresholds=None, description="", min_=None, max_=None):
    """Time series classique (X = Time absolu). Pour les panels qui n'ont pas DurationSeconds (lap-based)."""
    fc = {"defaults": {"unit": unit, "decimals": decimals,
                       "custom": {"lineWidth": 2, "fillOpacity": 10, "spanNulls": True, "drawStyle": "line", "showPoints": "never"}}}
    if thresholds:
        fc["defaults"]["thresholds"] = {"mode": "absolute", "steps": thresholds}
        fc["defaults"]["custom"]["thresholdsStyle"] = {"mode": "area"}
    if min_ is not None:
        fc["defaults"]["min"] = min_
    if max_ is not None:
        fc["defaults"]["max"] = max_
    return {
        "type": "timeseries", "id": panel_id, "title": title, "description": description,
        "gridPos": {"h": h, "w": w_, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": fc,
        "options": {"legend": {"showLegend": True, "calcs": ["mean", "max"], "displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "single"}},
        "targets": [{"refId": "A", "rawQuery": True, "query": query, "resultFormat": "time_series", "groupBy": [], "tags": []}],
    }


# Mapping overlay_target -> WorkoutTarget field names. 2 modes :
#   has_band=True  : overlay complet HR/Power/Cadence avec bande prescription purple
#                    (Target Low/High/middle) + staircase orange (Avg per step).
#                    Sentinel -1 (steps OPEN) filtre la bande, mais l'avg reste visible.
#   has_band=False : overlay "avg-only" Stride/VR/Altitude/Pace -> juste la staircase
#                    orange (Avg per step). Pas de prescription possible pour ces
#                    metriques (pas de Target* dans WorkoutTarget).
# expr   : template SQL pour le field (placeholder {f} = nom du field), permet de
#          gerer multiplications (cadence x2 spm) ou inversions (pace = 1000/speed).
# Cadence Garmin stocke "rpm per foot" : x2 cote query pour aligner avec spm panel.
# Stride stocke en mm : /1000 pour metres. Speed en m/s : 1000/x pour pace s/km.
_OVERLAY_CFG = {
    "hr":       {"avg": "StepAvgHR",        "low": "TargetLowBPM", "high": "TargetHighBPM", "expr": '"{f}"',          "filter_sentinel": False, "has_band": True},
    "power":    {"avg": "StepAvgPower",     "low": "TargetLowW",   "high": "TargetHighW",   "expr": '"{f}"',          "filter_sentinel": True,  "has_band": True},
    "cadence":  {"avg": "StepAvgCadence",   "low": "TargetLowRPM", "high": "TargetHighRPM", "expr": '"{f}" * 2',      "filter_sentinel": True,  "has_band": True},
    "stride":   {"avg": "StepAvgStride",                                                    "expr": '"{f}" / 1000',   "filter_sentinel": False, "has_band": False},
    "vr":       {"avg": "StepAvgVR",                                                        "expr": '"{f}"',          "filter_sentinel": False, "has_band": False},
    "altitude": {"avg": "StepAvgAltitude",                                                  "expr": '"{f}"',          "filter_sentinel": False, "has_band": False},
    "pace":     {"avg": "StepAvgSpeed",                                                     "expr": '1000.0 / "{f}"', "filter_sentinel": False, "has_band": False},
}

# Couleurs pour les "fake floor lines" Z1..Z5 (lineWidth=0, juste pour la legende/tooltip).
# Les bandes de fond colorees sont rendues separement via thresholdsStyle "area".
_ZONE_FLOOR_COLORS = [
    "rgba(120, 120, 120, 0.9)",   # Z1 gris
    "rgba(59, 130, 246, 0.9)",    # Z2 bleu
    "rgba(101, 188, 39, 0.9)",    # Z3 vert
    "rgba(249, 115, 22, 0.9)",    # Z4 orange
    "rgba(220, 38, 38, 0.9)",     # Z5 rouge
]


def ts_dur_panel(panel_id, title, x, y, w_, h, metric_select, metric_alias, where_clause,
                 unit="none", decimals=2, thresholds=None, description="", min_=None, max_=None,
                 smooth=True, extra_filter=None, overlay_target=None, zone_floor_lines=None):
    """Time series avec X = DurationSeconds (duree relative depuis debut activite).

    metric_select : expression SQL (ex: '"HeartRate"', '"Cadence"*2', '1000.0/"Speed"')
    metric_alias  : nom de la colonne (utilise pour overrides + smoothing field)
    where_clause  : sans le mot-cle WHERE (ex: '"ActivitySelector" = \'$activity\'')
    extra_filter  : filtre supplementaire post-WHERE (ex: 'AND "Cadence" > 30')
    smooth        : si True, ajoute calculateField windowFunctions pour lisser
    overlay_target : "hr" | "power" | "cadence" | None. Si set, ajoute 4 series depuis
                     WorkoutTarget : Target Low/High (bande purple semi-transparente),
                     Target middle (staircase pointillee purple), Avg per step
                     (staircase pointillee orange = realisation moyenne par step).
                     Sentinel -1 (steps OPEN) filtre cote SQL pour power/cadence
                     pour que l'axe Y ne soit pas tire vers 0.
    zone_floor_lines : list[(label, value)] = ajoute des lignes invisibles aux floors
                       de zones pour que la legende/tooltip affiche les bornes.
                       (Les bandes colorees de fond sont separees via thresholds.)

    Returns un panel "trend" Grafana avec joinByField + transformations + xField=Duration.
    Style aligne sur le pattern Pyrenees-J de Laurent (pour coherence visuelle).
    """
    # Filtre $activity_end : clip l'axe X pile a la duree de l'activite (sinon
    # Grafana ajoute un padding et l'axe va au-dela des donnees).
    extra = f" {extra_filter}" if extra_filter else ""
    duration_clip = ' AND "DurationSeconds" <= $activity_end'
    metric_query = f'SELECT {metric_select} AS "{metric_alias}" FROM "ActivityGPS" WHERE {where_clause}{extra}{duration_clip}'
    # CRITICAL 1 : la duration_query NE DOIT PAS partager le filter du metric.
    # Sinon les rangees ou metric=0 (ex: Cadence=0 au demarrage) ont Duration NULL
    # apres outer-join avec WorkoutTarget E (qui couvre Duration=0 -> fin sans
    # filter), et trend panel + xField=Duration s'effondre en un seul point.
    # cf. memory feedback_grafana_trend_xfield_duration.md
    # CRITICAL 2 : la duration_query NE DOIT PAS non plus partager $activity_end.
    # La variable est refresh:2 (on time range change) et peut resoudre a null
    # / "" / cache stale selon le timing (initial load avec time range qui ne
    # couvre pas la row ActivitySummary, switch de dropdown sans re-trigger,
    # END marker row a NULL elapsedDuration). Dans ces cas le clip
    # "DurationSeconds <= ''" exclut TOUTES les lignes -> duration_query renvoie
    # 0 rows -> trend panel s'effondre a un seul tick. Le metric_query conserve
    # le clip (cosmetique: pas de fantome apres fin d'activite) mais Duration
    # doit etre robuste sans dependre de la variable.
    duration_query = f'SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE {where_clause}'

    transformations = [
        {"id": "joinByField", "options": {"byField": "Time", "mode": "outer"}},
        # Grafana 13+ rename les value fields apres join en "<measurement>.<alias>"
        # (ex: "ActivityGPS.Duration", "WorkoutTarget.Avg per step") via displayName.
        # Le panel "trend" + xField="Duration" + windowFunctions(field=...) ne
        # matchent pas ces noms prefixes -> "Unable to find field" + chart vide.
        # Strip le prefixe pour normaliser sur les alias bruts. WorkoutTarget.* perd
        # aussi son prefixe -> updater keep_fields plus bas en consequence.
        {"id": "renameByRegex", "options": {"regex": r"^.*\.(.+)$", "renamePattern": "$1"}},
    ]

    display_name = metric_alias
    if smooth:
        smoothed = f"Smoothed {metric_alias}"
        transformations.append({
            "id": "calculateField",
            "options": {
                "alias": smoothed,
                "mode": "windowFunctions",
                "reduce": {"reducer": "sum"},
                "window": {
                    "field": metric_alias, "reducer": "mean",
                    "windowAlignment": "centered",
                    "windowSize": 0.01, "windowSizeMode": "percentage"
                }
            }
        })
        display_name = smoothed

    # Build the fake "Z1..Z5" constant lines via Duration*0+floor (Laurent pattern).
    # Permet aux floors de zones d'apparaitre dans la legende avec leur valeur,
    # sans tirer une ligne visible (lineWidth=0 dans les overrides).
    floor_field_names = []
    if zone_floor_lines:
        for i, (label, val) in enumerate(zone_floor_lines, start=1):
            transformations.append({
                "id": "calculateField",
                "options": {
                    "mode": "binary",
                    "binary": {"left": "Duration", "operator": "*", "right": "0"},
                    "alias": f"__zero_z{i}",
                    "replaceFields": False,
                }
            })
            transformations.append({
                "id": "calculateField",
                "options": {
                    "mode": "binary",
                    "binary": {"left": f"__zero_z{i}", "operator": "+", "right": str(val)},
                    "alias": label,
                    "replaceFields": False,
                }
            })
            floor_field_names.append(label)

    # Apres renameByRegex, les fields perdent leur prefixe "<measurement>." donc
    # on garde just les alias bruts ("Avg per step", "Target Low/High/middle").
    keep_fields = ["Time", "Duration", display_name]
    if overlay_target:
        keep_fields.append("Avg per step")
        if _OVERLAY_CFG[overlay_target].get("has_band", True):
            keep_fields += [
                "Target Low",
                "Target High",
                "Target middle",
            ]
    keep_fields += floor_field_names

    transformations.append({
        "id": "filterFieldsByName",
        "options": {"include": {"names": keep_fields}}
    })

    fc = {
        "defaults": {
            "unit": unit, "decimals": decimals,
            "custom": {
                "lineWidth": 2, "fillOpacity": 10, "spanNulls": True,
                "drawStyle": "line", "showPoints": "never",
                "lineInterpolation": "smooth"
            }
        },
        "overrides": [
            # Duration en seconds -> formatte en HH:MM:SS sur l'axe X via override
            {"matcher": {"id": "byName", "options": "Duration"},
             "properties": [
                 {"id": "unit", "value": "dthms"},
                 {"id": "custom.hideFrom", "value": {"legend": True, "viz": False, "tooltip": False}},
                 {"id": "fieldMinMax", "value": True},
             ]},
        ]
    }
    if thresholds:
        fc["defaults"]["thresholds"] = {"mode": "absolute", "steps": thresholds}
        fc["defaults"]["custom"]["thresholdsStyle"] = {"mode": "area"}
    # min/max ne vont pas dans defaults : clipperait aussi Duration (axe X).
    # On les applique via override sur le field metric/Smoothed metric.
    # En mode overlay : on ignore min_/max_ (Grafana auto-fit sur l'union des series).
    # Sinon Grafana cree 2 axes Y separes (un pour Smoothed metric avec min, un pour
    # les floor lines + target lines sans min) -> doublons d'axes sur le panel.
    metric_override_props = []
    if min_ is not None and not overlay_target:
        metric_override_props.append({"id": "min", "value": min_})
    if max_ is not None and not overlay_target:
        metric_override_props.append({"id": "max", "value": max_})
    if overlay_target:
        metric_override_props.append({"id": "custom.axisPlacement", "value": "left"})
        metric_override_props.append({"id": "fieldMinMax", "value": True})
    if metric_override_props:
        fc["overrides"].append({
            "matcher": {"id": "byName", "options": display_name},
            "properties": metric_override_props,
        })

    targets = [
        {"refId": "A", "rawQuery": True, "query": metric_query,
         "resultFormat": "time_series", "alias": metric_alias, "groupBy": [], "tags": []},
        {"refId": "B", "rawQuery": True, "query": duration_query,
         "resultFormat": "time_series", "alias": "Duration", "groupBy": [], "tags": []},
    ]

    if overlay_target:
        cfg = _OVERLAY_CFG[overlay_target]
        has_band = cfg.get("has_band", True)
        avg_expr = cfg["expr"].format(f=cfg["avg"])
        # Decimals des stats moy/step : 2 si pace/stride/vr (decimaux significatifs),
        # 0 sinon (HR/Power/Cadence/Altitude entiers).
        avg_decimals = 2 if overlay_target in ("stride", "vr") else 0

        # Avg per step : pas de sentinel filter. Pour HR/Power/Cadence ca preserve
        # la mean reelle meme sur steps OPEN (le user veut voir power=280W meme si
        # step ciblait que la FC). Pour Stride/VR/Altitude/Pace y a juste pas de
        # sentinel a appliquer (no Target* a filtrer).
        # RowMarker comme 2e field (defensif) pour disambiguer les rows lors du joinByField.
        targets.append({"refId": "E", "rawQuery": True,
            "query": f'SELECT {avg_expr} AS "Avg per step", "RowMarker" AS "_rm_avg" FROM "WorkoutTarget" WHERE {where_clause} ORDER BY time ASC',
            "resultFormat": "time_series", "groupBy": [], "tags": []})

        if has_band:
            # Filtre sentinel -1 (steps OPEN sans target prescrite) sur Target
            # Low/High/middle pour Power/Cadence (HR target toujours present).
            sentinel_band_clause = f' AND "{cfg["low"]}" >= 0' if cfg["filter_sentinel"] else ""
            wt_where_band = f'{where_clause}{sentinel_band_clause}'
            low_expr = cfg["expr"].format(f=cfg["low"])
            high_expr = cfg["expr"].format(f=cfg["high"])
            mid_expr = f'({low_expr} + {high_expr}) / 2'
            targets.append({"refId": "C", "rawQuery": True,
                "query": f'SELECT {low_expr} AS "Target Low", "RowMarker" AS "_rm_low" FROM "WorkoutTarget" WHERE {wt_where_band} ORDER BY time ASC',
                "resultFormat": "time_series", "groupBy": [], "tags": []})
            targets.append({"refId": "D", "rawQuery": True,
                "query": f'SELECT {high_expr} AS "Target High", "RowMarker" AS "_rm_high" FROM "WorkoutTarget" WHERE {wt_where_band} ORDER BY time ASC',
                "resultFormat": "time_series", "groupBy": [], "tags": []})
            targets.append({"refId": "F", "rawQuery": True,
                "query": f'SELECT {mid_expr} AS "Target middle", "RowMarker" AS "_rm_mid" FROM "WorkoutTarget" WHERE {wt_where_band} ORDER BY time ASC',
                "resultFormat": "time_series", "groupBy": [], "tags": []})

            # Style Laurent : Target Low = bars invisibles (anchor pour fillBelowTo),
            # Target High = bars purple semi-transparent qui remplissent jusqu'a Target Low
            # -> rendu d'une bande de prescription sous forme de quadrilateres verticaux.
            fc["overrides"].append({
                "matcher": {"id": "byRegexp", "options": ".*Target Low$"},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(168, 85, 247, 0.2)"}},
                    {"id": "custom.drawStyle", "value": "bars"},
                    {"id": "custom.barAlignment", "value": 0},
                    {"id": "custom.spanNulls", "value": False},
                    {"id": "custom.fillOpacity", "value": 0},
                    {"id": "custom.lineWidth", "value": 0},
                    {"id": "displayName", "value": "Target min (prescrit)"},
                    {"id": "unit", "value": unit},
                    {"id": "custom.axisPlacement", "value": "left"},
                ]
            })
            fc["overrides"].append({
                "matcher": {"id": "byRegexp", "options": ".*Target High$"},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(168, 85, 247, 0.2)"}},
                    {"id": "custom.drawStyle", "value": "bars"},
                    {"id": "custom.barAlignment", "value": 0},
                    {"id": "custom.spanNulls", "value": False},
                    {"id": "custom.fillBelowTo", "value": "Target min (prescrit)"},
                    {"id": "custom.fillOpacity", "value": 10},
                    {"id": "displayName", "value": "Target max (prescrit)"},
                    {"id": "unit", "value": unit},
                    {"id": "custom.axisPlacement", "value": "left"},
                ]
            })
            # Target middle : staircase pointillee purple solide ((low+high)/2 par step).
            fc["overrides"].append({
                "matcher": {"id": "byRegexp", "options": ".*Target middle$"},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(168, 85, 247, 1.0)"}},
                    {"id": "custom.lineWidth", "value": 2},
                    {"id": "custom.lineInterpolation", "value": "stepAfter"},
                    {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [6, 4]}},
                    {"id": "custom.spanNulls", "value": False},
                    {"id": "custom.fillOpacity", "value": 0},
                    {"id": "displayName", "value": "Target middle (prescrit)"},
                    {"id": "unit", "value": unit},
                    {"id": "decimals", "value": 0},
                    {"id": "custom.axisPlacement", "value": "left"},
                ]
            })

        # Avg per step : staircase pointillee orange (realisation moyenne par step,
        # calculee par le sidecar fetcher quand il ecrit WorkoutTarget). Toujours
        # rendue, en mode "has_band" comme en mode "avg-only".
        fc["overrides"].append({
            "matcher": {"id": "byRegexp", "options": ".*Avg per step$"},
            "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(255, 140, 60, 0.95)"}},
                {"id": "custom.lineWidth", "value": 2},
                {"id": "custom.lineInterpolation", "value": "stepAfter"},
                {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 6]}},
                {"id": "custom.spanNulls", "value": False},
                {"id": "custom.fillOpacity", "value": 0},
                {"id": "displayName", "value": "Moy / step"},
                {"id": "unit", "value": unit},
                {"id": "decimals", "value": avg_decimals},
                {"id": "custom.axisPlacement", "value": "left"},
            ]
        })
        # Smoothed metric :
        #   - has_band (HR/Power/Cad)  : orange smooth + fillOpacity=0. Cote staircase
        #     orange + bande purple, on garde un visuel coherent (orange = realisation,
        #     purple = prescription). FillOpacity=0 evite que l'aire teinte marron les
        #     bandes Z thresholds derriere.
        #   - !has_band (Stride/VR/Alt/Pace) : on laisse la couleur Grafana par defaut
        #     (vert) pour distinguer visuellement smoothed (vert continu) et staircase
        #     (orange dashed). Pas d'override de couleur => un override des proprietes
        #     internes est inutile, on skip.
        if has_band:
            fc["overrides"].append({
                "matcher": {"id": "byName", "options": display_name},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(255, 140, 60, 0.95)"}},
                    {"id": "custom.fillOpacity", "value": 0},
                ]
            })

    # Floor lines invisibles — n'apparaissent que dans la legende avec leur valeur.
    # hideFrom.viz=True : pas dessine sur le chart ET exclu du calcul d'axe Y
    # (sinon Z5=180 tirerait l'axe vers le haut meme si HR=130-150).
    if zone_floor_lines:
        for i, (label, _) in enumerate(zone_floor_lines):
            fc["overrides"].append({
                "matcher": {"id": "byName", "options": label},
                "properties": [
                    {"id": "color", "value": {"mode": "fixed", "fixedColor": _ZONE_FLOOR_COLORS[i % 5]}},
                    {"id": "custom.hideFrom", "value": {"legend": False, "viz": True, "tooltip": False}},
                    {"id": "unit", "value": unit},
                    {"id": "decimals", "value": 0},
                ]
            })

    return {
        "type": "trend", "id": panel_id, "title": title, "description": description,
        "gridPos": {"h": h, "w": w_, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": fc,
        "options": {
            "legend": {"showLegend": True, "calcs": ["mean", "max", "min"], "displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "none"},
            "xField": "Duration",
        },
        "targets": targets,
        "transformations": transformations,
    }


def gps_track_panel(panel_id, title, x, y, w_, h, where_clause, color_field, color_mode,
                    basemap_server, layer_name, decimals=1, description=""):
    """Geomap avec tracé GPS coloré par un field metric (HR, speed, etc.).

    color_field   : "HR" ou "speed (Km/h)" (matche l'alias des sub-queries)
    color_mode    : "continuous-RdYlGr" (vert→jaune→rouge), "continuous-GrYlRd" (inverse), etc.
    basemap_server: "streets" (carte routes) ou "world-imagery" (satellite)
    layer_name    : nom de la layer affiché dans la légende (ex: "Speed (Km/h)" / "Heart Rate")

    Architecture : 4 sub-queries (lat/lon/HR/speed) joinByField sur Time, layer markers
    avec color = field. Reproduit le pattern garmin-stats-custom-reference.json.
    """
    return {
        "type": "geomap", "id": panel_id, "title": title, "description": description,
        "gridPos": {"h": h, "w": w_, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "decimals": decimals,
                "thresholds": {"mode": "absolute", "steps": [{"value": 0, "color": "green"}]},
                "color": {"mode": color_mode, "fixedColor": "yellow"},
                "custom": {"hideFrom": {"legend": False, "tooltip": False, "viz": False}},
                "fieldMinMax": False,
            },
            "overrides": [],
        },
        "options": {
            "basemap": {"config": {"server": basemap_server, "showLabels": True, "theme": "auto"},
                        "name": "Layer 0", "opacity": 1, "tooltip": True, "type": "esri-xyz"},
            "controls": {"mouseWheelZoom": False, "showAttribution": False, "showDebug": False,
                         "showMeasure": False, "showScale": True, "showZoom": True},
            "layers": [{
                "config": {
                    "showLegend": True,
                    "style": {
                        "color": {"field": color_field, "fixed": "dark-green"},
                        "opacity": 0.4,
                        "rotation": {"fixed": 0, "max": 360, "min": -360, "mode": "mod"},
                        "size": {"fixed": 3, "max": 15, "min": 2},
                        "symbol": {"fixed": "img/icons/marker/circle.svg", "mode": "fixed"},
                        "symbolAlign": {"horizontal": "center", "vertical": "center"},
                        "textConfig": {"fontSize": 12, "offsetX": 0, "offsetY": 0,
                                       "textAlign": "center", "textBaseline": "middle"},
                    },
                },
                "filterData": {"id": "byRefId", "options": "joinByField-I-J-A-B"},
                "location": {"mode": "auto"},
                "name": layer_name,
                "opacity": 0.8,
                "tooltip": False,
                "type": "markers",
            }],
            "tooltip": {"mode": "details"},
            "view": {"allLayers": True, "id": "fit", "lastOnly": False,
                     "lat": 48.4, "lon": 0.7, "padding": 3, "shared": True, "zoom": 13},
        },
        "targets": [
            {"refId": "I", "rawQuery": True, "alias": "lat",
             "query": f'SELECT "Latitude" FROM "ActivityGPS" WHERE {where_clause}',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
            {"refId": "J", "rawQuery": True, "alias": "lon",
             "query": f'SELECT "Longitude" FROM "ActivityGPS" WHERE {where_clause}',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
            {"refId": "A", "rawQuery": True, "alias": "HR",
             "query": f'SELECT "HeartRate" FROM "ActivityGPS" WHERE {where_clause}',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
            {"refId": "B", "rawQuery": True, "alias": "speed (Km/h)",
             "query": f'SELECT "Speed" * 3.6 FROM "ActivityGPS" WHERE {where_clause}',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
        ],
        "transformations": [
            {"id": "joinByField", "options": {"byField": "Time", "mode": "outer"}},
        ],
    }


def bargauge_zones(panel_id, title, x, y, w_, h, queries, unit="s", description="", max_val=None):
    """queries = [(ref, alias, raw_query, color)]"""
    targets = []
    overrides = []
    for ref, alias, q, color in queries:
        targets.append({"refId": ref, "rawQuery": True, "query": q, "resultFormat": "time_series", "groupBy": [], "tags": []})
        overrides.append({
            "matcher": {"id": "byFrameRefID", "options": ref},
            "properties": [{"id": "displayName", "value": alias}, {"id": "color", "value": {"fixedColor": color, "mode": "fixed"}}]
        })
    defaults = {"unit": unit, "color": {"mode": "fixed"}, "min": 0}
    if max_val is not None:
        defaults["max"] = max_val
    return {
        "type": "bargauge", "id": panel_id, "title": title, "description": description,
        "gridPos": {"h": h, "w": w_, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": {"defaults": defaults, "overrides": overrides},
        "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True, "valueMode": "color",
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        "targets": targets,
    }


def build_panels(activities):
    panels = []
    pid = [0]
    def nid():
        pid[0] += 1
        return pid[0]

    A = "$activity"  # variable
    where = f"\"ActivitySelector\" = '{A}'"

    # Row 0 : 6 stats (h=4, y=0)
    y = 0
    panels.append(stat_panel(nid(), "Distance", 0, y, 4, 4,
        f"SELECT last(\"distance\")/1000 FROM \"ActivitySummary\" WHERE {where}",
        unit="lengthkm", decimals=2))
    panels.append(stat_panel(nid(), "Duration", 4, y, 4, 4,
        f"SELECT last(\"elapsedDuration\") FROM \"ActivitySummary\" WHERE {where}",
        unit="dthms"))
    panels.append(stat_panel(nid(), "Avg HR", 8, y, 4, 4,
        f"SELECT last(\"averageHR\") FROM \"ActivitySummary\" WHERE {where}",
        unit="bpm", thresholds=[{"color": "blue"}, {"color": "green", "value": 130}, {"color": "yellow", "value": 160}, {"color": "red", "value": 175}]))
    panels.append(stat_panel(nid(), "Max HR", 12, y, 4, 4,
        f"SELECT last(\"maxHR\") FROM \"ActivitySummary\" WHERE {where}",
        unit="bpm", thresholds=[{"color": "green"}, {"color": "yellow", "value": 175}, {"color": "red", "value": 190}]))
    panels.append(stat_panel(nid(), "Avg Pace (per km)", 16, y, 4, 4,
        f"SELECT 1000.0/last(\"averageSpeed\") FROM \"ActivitySummary\" WHERE {where}",
        unit="dthms"))
    panels.append(stat_panel(nid(), "Calories", 20, y, 4, 4,
        f"SELECT last(\"calories\") FROM \"ActivitySummary\" WHERE {where}",
        unit="kcal"))

    # Row 1 : 6 stats (h=4, y=4)
    y = 4
    panels.append(stat_panel(nid(), "Elev gain (D+)", 0, y, 4, 4,
        f"SELECT last(\"elevationGain\") FROM \"ActivitySummary\" WHERE {where}",
        unit="lengthm"))
    panels.append(stat_panel(nid(), "Elev loss (D-)", 4, y, 4, 4,
        f"SELECT last(\"elevationLoss\") FROM \"ActivitySummary\" WHERE {where}",
        unit="lengthm"))
    panels.append(stat_panel(nid(), "Aerobic TE", 8, y, 4, 4,
        f"SELECT last(\"aerobicTrainingEffect\") FROM \"ActivitySummary\" WHERE {where}",
        decimals=1, thresholds=[{"color": "blue"}, {"color": "green", "value": 2}, {"color": "yellow", "value": 4}, {"color": "red", "value": 5}]))
    panels.append(stat_panel(nid(), "Anaerobic TE", 12, y, 4, 4,
        f"SELECT last(\"anaerobicTrainingEffect\") FROM \"ActivitySummary\" WHERE {where}",
        decimals=1, thresholds=[{"color": "blue"}, {"color": "green", "value": 1}, {"color": "yellow", "value": 3}, {"color": "red", "value": 4.5}]))
    panels.append(stat_panel(nid(), "Exercise Load", 16, y, 4, 4,
        f"SELECT last(\"activityTrainingLoad\") FROM \"ActivitySummary\" WHERE {where}",
        decimals=0))
    panels.append(stat_panel(nid(), "VO2max (post-run)", 20, y, 4, 4,
        f"SELECT last(\"vO2MaxValue\") FROM \"ActivitySummary\" WHERE {where}",
        decimals=1))

    # Row 2 : 2 GPS Track maps cote a cote (h=11, y=8) - reproduit garmin-stats-custom
    y = 8
    panels.append(gps_track_panel(nid(), "GPS Track by Velocity", 0, y, 12, 11, where,
        color_field="speed (Km/h)", color_mode="continuous-RdYlGr",
        basemap_server="streets", layer_name="Speed (Km/h)",
        description="Trace colore par vitesse (km/h). Vert lent -> rouge rapide. Basemap routes."))
    panels.append(gps_track_panel(nid(), "GPS Track by Heart Rate", 12, y, 12, 11, where,
        color_field="HR", color_mode="continuous-GrYlRd",
        basemap_server="world-imagery", layer_name="Heart Rate",
        description="Trace colore par FC (bpm). Vert bas -> rouge haut. Basemap satellite."))
    # Row 2.5 : HR + Power bargauges (% time-in-zone) au-dessus du tableau steps
    # (h=8, y=19, w=12 chacun cote a cote).
    hr_total_dur_inline = "(last(\"hrTimeInZone_1\")+last(\"hrTimeInZone_2\")+last(\"hrTimeInZone_3\")+last(\"hrTimeInZone_4\")+last(\"hrTimeInZone_5\"))"
    hr_queries_top = [
        (chr(ord("A") + i), f"Z{i+1} ({HR_Z[i][0]}-{HR_Z[i][1]} bpm)",
         f"SELECT 100.0 * last(\"hrTimeInZone_{i+1}\") / {hr_total_dur_inline} FROM \"ActivitySummary\" WHERE {where}",
         color)
        for i, color in enumerate(["#3274d9", "#56a64b", "#f2cc0c", "#ff7833", "#e02f44"])
    ]
    panels.append(bargauge_zones(nid(), "Time in HR Zones (%) - reference plan", 0, 19, 12, 8, hr_queries_top, unit="percent", max_val=100,
        description="% du temps en activite par zone FC (Garmin avec zones du moment de l'enregistrement). Cible Z2-strict footings : >75% Z2."))
    pwr_queries_top = [
        (chr(ord("A") + i), f"Z{i+1} ({PWR_Z[i][0]}-{PWR_Z[i][1] if i<4 else '∞'} W)",
         f"SELECT 100.0 * count(\"Power\") / $activity_end FROM \"ActivityGPS\" WHERE {where} AND \"Power\" >= {PWR_Z[i][0]}" + (f" AND \"Power\" < {PWR_Z[i][1]+1}" if i<4 else ""),
         color)
        for i, color in enumerate(["#cccccc", "#3274d9", "#56a64b", "#ff7833", "#e02f44"])
    ]
    panels.append(bargauge_zones(nid(), "Time in Power Zones (%) - calcule from per-second", 12, 19, 12, 8, pwr_queries_top, unit="percent", max_val=100,
        description="% du temps par zone power calcule on-the-fly depuis ActivityGPS (1 sample = 1s). Zones Garmin auto-FTP au 01/05/2026."))

    # Row 3 : HR over time with zone bands (h=10, y=41 — apres bargauges + table)
    # Style aligne sur le pattern Pyrenees-J de Laurent : bandes Z basse opacite
    # (0.09-0.15) + floor lines invisibles pour la legende + bande purple prescrite.
    y = 41
    panels.append(ts_dur_panel(nid(), "Heart Rate (bpm) avec bandes zones FC + overlay target prescrit", 0, y, 24, 10,
        '"HeartRate"', "HR", where,
        unit="bpm", decimals=0,
        extra_filter='AND "HeartRate" > 60',
        thresholds=[
            {"color": "rgba(0,0,0,0)"},                                    # below Z1 = vraie transparence
            {"color": "rgba(225, 225, 225, 0.09)", "value": HR_Z[0][0]},   # Z1 blanc/gris clair
            {"color": "rgba(59, 130, 246, 0.11)", "value": HR_Z[1][0]},    # Z2 bleu
            {"color": "rgba(101, 188, 39, 0.11)", "value": HR_Z[2][0]},    # Z3 vert
            {"color": "rgba(249, 115, 22, 0.12)", "value": HR_Z[3][0]},    # Z4 orange
            {"color": "rgba(220, 38, 38, 0.15)", "value": HR_Z[4][0]},     # Z5 rouge
        ],
        description=f"Bandes Z1-Z5 ({HR_Z[0][0]}/{HR_Z[1][0]}/{HR_Z[2][0]}/{HR_Z[3][0]}/{HR_Z[4][0]} bpm). Bande purple = target HR prescrit. Staircase pointillee orange = HR moy / step. Axe Y auto-fit sur l'union HR + Target.",
        overlay_target="hr",
        zone_floor_lines=[
            (f"Z1 ({HR_Z[0][0]}-{HR_Z[1][0]})", HR_Z[0][0]),
            (f"Z2 ({HR_Z[1][0]}-{HR_Z[2][0]})", HR_Z[1][0]),
            (f"Z3 ({HR_Z[2][0]}-{HR_Z[3][0]})", HR_Z[2][0]),
            (f"Z4 ({HR_Z[3][0]}-{HR_Z[4][0]})", HR_Z[3][0]),
            (f"Z5 ({HR_Z[4][0]}+)", HR_Z[4][0]),
        ]))

    # Steps prescription table sous les bargauges (y=27, w=24, h=14 pour fit
    # tous les steps sans scroll).
    panels.append({
        "type": "table", "id": nid(), "title": "Workout steps prescrits + executes",
        "description": "Une row par step de la prescription. TargetType=open = aucune cible HR (ex: tests, sprints). DurationS = duree prescrite en s. ActualDurationS = duree reellement executee.",
        "gridPos": {"h": 14, "w": 24, "x": 0, "y": 27},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {"custom": {"align": "auto"}},
            "overrides": [
                {"matcher": {"id": "byName", "options": "TargetType"},
                 "properties": [{"id": "mappings", "value": [
                     {"type": "value", "options": {"open": {"text": "OPEN", "color": "text", "index": 0}, "heart_rate": {"text": "HR zone", "color": "blue", "index": 1}}},
                 ]}]},
                {"matcher": {"id": "byName", "options": "TargetLowBPM"}, "properties": [{"id": "unit", "value": "bpm"}]},
                {"matcher": {"id": "byName", "options": "TargetHighBPM"}, "properties": [{"id": "unit", "value": "bpm"}]},
                {"matcher": {"id": "byName", "options": "DurationValueS"}, "properties": [{"id": "unit", "value": "dthms"}, {"id": "displayName", "value": "Duree prescrite"}]},
                {"matcher": {"id": "byName", "options": "StepActualDurationS"}, "properties": [{"id": "unit", "value": "dthms"}, {"id": "displayName", "value": "Duree reelle"}]},
                {"matcher": {"id": "byName", "options": "StepStartOffsetS"}, "properties": [{"id": "unit", "value": "dthms"}, {"id": "displayName", "value": "Debut step"}]},
                {"matcher": {"id": "byName", "options": "Notes"}, "properties": [{"id": "custom.width", "value": 600}]},
                {"matcher": {"id": "byName", "options": "StepIndex"}, "properties": [{"id": "displayName", "value": "#"}, {"id": "custom.width", "value": 40}]},
                {"matcher": {"id": "byName", "options": "IntensityType"}, "properties": [{"id": "displayName", "value": "Intensity"}, {"id": "custom.width", "value": 90}]},
                {"matcher": {"id": "byName", "options": "TargetType"}, "properties": [{"id": "displayName", "value": "Target"}, {"id": "custom.width", "value": 80}]},
                {"matcher": {"id": "byName", "options": "TargetLowBPM"}, "properties": [{"id": "displayName", "value": "Min"}, {"id": "custom.width", "value": 70}]},
                {"matcher": {"id": "byName", "options": "TargetHighBPM"}, "properties": [{"id": "displayName", "value": "Max"}, {"id": "custom.width", "value": 70}]},
            ]
        },
        "options": {"showHeader": True, "footer": {"show": False}, "cellHeight": "sm"},
        "targets": [{"refId": "A", "rawQuery": True,
            "query": f"""SELECT "StepIndex", "IntensityType", "TargetType", "TargetLowBPM", "TargetHighBPM", "StepStartOffsetS", "DurationValueS", "StepActualDurationS", "Notes" FROM "WorkoutStep" WHERE {where} ORDER BY time ASC""",
            "resultFormat": "table", "groupBy": [], "tags": []}],
    })

    # Rows 4+ : evolution panels empiles full-width (w=24, h=8).
    # Demande utilisateur : un graphe par ligne pour faciliter la lecture, repere
    # temporel partage par graphTooltip:1 (crosshair entre tous les panels).
    y = 51
    panels.append(ts_dur_panel(nid(), "Pace (min/km) - bas = rapide + moy / step", 0, y, 24, 8,
        '1000.0/"Speed"', "Pace", where,
        unit="dthms", decimals=0,
        extra_filter='AND "Speed" > 0.5',
        description="Pace per-second (mm:ss/km). Convention Garmin : plus bas sur l'axe = plus rapide. Staircase orange = pace moy / step (1000/StepAvgSpeed, fetcher filtre Speed>0.5 m/s pour exclure pauses).",
        overlay_target="pace"))
    y += 8
    # Power : meme pattern que HR (bandes zones + bande prescrite + floor lines).
    # Le sentinel -1 (steps OPEN sans target power) filtre uniquement la bande
    # purple ; le mean per step orange reste visible sur tous les steps pour qu'on
    # voie la realisation power meme quand seule la FC etait prescrite.
    panels.append(ts_dur_panel(nid(), "Power (W) avec bandes zones power + overlay target prescrit", 0, y, 24, 8,
        '"Power"', "Power", where,
        unit="watt", decimals=0,
        extra_filter='AND "Power" > 0',
        thresholds=[
            {"color": "rgba(0,0,0,0)"},
            {"color": "rgba(120, 120, 120, 0.07)", "value": PWR_Z[0][0]},  # Z1 gris (recovery)
            {"color": "rgba(59, 130, 246, 0.09)", "value": PWR_Z[1][0]},   # Z2 bleu (endurance)
            {"color": "rgba(101, 188, 39, 0.10)", "value": PWR_Z[2][0]},   # Z3 vert (tempo)
            {"color": "rgba(249, 115, 22, 0.11)", "value": PWR_Z[3][0]},   # Z4 orange (threshold)
            {"color": "rgba(220, 38, 38, 0.15)", "value": PWR_Z[4][0]},    # Z5 rouge (VO2max+)
        ],
        description=f"Bandes Z1-Z5 ({PWR_Z[0][0]}/{PWR_Z[1][0]}/{PWR_Z[2][0]}/{PWR_Z[3][0]}/{PWR_Z[4][0]} W). Bande purple = target power prescrit (vide si la seance ne cible que la FC). Staircase orange = power moy / step. Auto-FTP Garmin.",
        overlay_target="power",
        zone_floor_lines=[
            (f"Z1 ({PWR_Z[0][0]}-{PWR_Z[1][0]})", PWR_Z[0][0]),
            (f"Z2 ({PWR_Z[1][0]}-{PWR_Z[2][0]})", PWR_Z[1][0]),
            (f"Z3 ({PWR_Z[2][0]}-{PWR_Z[3][0]})", PWR_Z[2][0]),
            (f"Z4 ({PWR_Z[3][0]}-{PWR_Z[4][0]})", PWR_Z[3][0]),
            (f"Z5 ({PWR_Z[4][0]}+)", PWR_Z[4][0]),
        ]))

    y += 8
    # Cadence : multiplie x2 (Garmin stocke per-foot, on veut spm). Overlay cadence
    # applique x2 aussi cote WorkoutTarget. La plupart des plans ne prescrivent pas la cadence
    # -> bande purple souvent vide, mais staircase orange (mean per step) toujours
    # visible (cf. fix sentinel split).
    panels.append(ts_dur_panel(nid(), "Cadence (spm) avec overlay target prescrit (si present)", 0, y, 24, 8,
        '"Cadence" * 2', "Cadence", where,
        unit="rpm", decimals=0,
        extra_filter='AND "Cadence" > 30',
        thresholds=[{"color": "yellow"}, {"color": "green", "value": 170}, {"color": "yellow", "value": 190}],
        description="Cadence saine depend de l'allure (170 spm a 7:00/km c'est OK). Bande purple = target cadence (si prescrit). Staircase orange = cadence moy / step (toujours visible).",
        overlay_target="cadence"))
    y += 8
    panels.append(ts_dur_panel(nid(), "Stride length (m) + moy / step", 0, y, 24, 8,
        '"Step_Length"/1000', "Stride", where,
        unit="lengthm", decimals=2,
        extra_filter='AND "Step_Length" > 0',
        description="Longueur foulee par seconde (en metres). Staircase orange = stride moy / step (StepAvgStride/1000).",
        overlay_target="stride"))
    y += 8
    panels.append(ts_dur_panel(nid(), "Vertical Ratio (%) - cible <7% + moy / step", 0, y, 24, 8,
        '"Vertical_Ratio"', "VR", where,
        unit="percent", decimals=1,
        extra_filter='AND "Vertical_Ratio" > 0',
        thresholds=[{"color": "green"}, {"color": "yellow", "value": 7}, {"color": "red", "value": 9}],
        description="Vertical Ratio (oscillation verticale / stride length, en %). <7% = bonne efficacite. Staircase orange = VR moy / step.",
        overlay_target="vr"))
    y += 8
    panels.append(ts_dur_panel(nid(), "Vertical Oscillation (cm)", 0, y, 24, 8,
        '"Vertical_Oscillation"/10', "VO", where,
        unit="lengthcm", decimals=1,
        extra_filter='AND "Vertical_Oscillation" > 0'))
    y += 8
    panels.append(ts_dur_panel(nid(), "Ground Contact Time (ms) - cible <250", 0, y, 24, 8,
        '"Stance_Time"', "GCT", where,
        unit="ms", decimals=0,
        extra_filter='AND "Stance_Time" > 0',
        thresholds=[{"color": "green"}, {"color": "yellow", "value": 260}, {"color": "red", "value": 290}]))
    y += 8
    # HR drift par lap (decouplage aerobie) - panel "trend" + xField=Duration.
    # Avg/Max HR par lap (ActivityLap, 1 lap = 1 km par defaut). Overlay Altitude
    # per-second en fond leger pour reperer si le drift correspond a un relief.
    # Duration query SANS filter (cf. memory feedback_grafana_trend_xfield_duration).
    panels.append({
        "type": "trend", "id": nid(), "title": "Avg HR par lap (drift = decouplage aerobie) + altitude",
        "description": "FC moyenne + max par lap (1 km). Altitude en fond leger pour distinguer drift cardiaque vs effort topographique. Axe X = duree de course.",
        "gridPos": {"h": 8, "w": 24, "x": 0, "y": y},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {"unit": "bpm", "decimals": 0,
                         "custom": {"lineWidth": 2, "spanNulls": True, "drawStyle": "line",
                                    "showPoints": "always", "pointSize": 8, "fillOpacity": 10,
                                    "lineInterpolation": "linear"}},
            "overrides": [
                {"matcher": {"id": "byName", "options": "Duration"},
                 "properties": [
                     {"id": "unit", "value": "dthms"},
                     {"id": "custom.hideFrom", "value": {"legend": True, "viz": True, "tooltip": False}},
                     {"id": "fieldMinMax", "value": True},
                 ]},
                {"matcher": {"id": "byName", "options": "Avg HR"},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(101, 188, 39, 0.95)"}},
                     {"id": "custom.axisPlacement", "value": "left"},
                     {"id": "custom.lineInterpolation", "value": "stepAfter"},
                     {"id": "custom.spanNulls", "value": True},
                     {"id": "fieldMinMax", "value": True},
                 ]},
                {"matcher": {"id": "byName", "options": "Max HR"},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(249, 200, 50, 0.95)"}},
                     {"id": "custom.axisPlacement", "value": "left"},
                     {"id": "custom.lineInterpolation", "value": "stepAfter"},
                     {"id": "custom.spanNulls", "value": True},
                     {"id": "fieldMinMax", "value": True},
                 ]},
                {"matcher": {"id": "byName", "options": "Altitude"},
                 "properties": [
                     {"id": "color", "value": {"mode": "fixed", "fixedColor": "rgba(160, 160, 160, 0.35)"}},
                     {"id": "custom.lineWidth", "value": 0},
                     {"id": "custom.fillOpacity", "value": 25},
                     {"id": "custom.showPoints", "value": "never"},
                     {"id": "custom.lineInterpolation", "value": "smooth"},
                     {"id": "custom.axisPlacement", "value": "right"},
                     {"id": "unit", "value": "lengthm"},
                     {"id": "fieldMinMax", "value": True},
                 ]},
            ],
        },
        "options": {
            "legend": {"showLegend": True, "calcs": ["mean", "max", "min"], "displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "none"},
            "xField": "Duration",
        },
        "targets": [
            {"refId": "A", "rawQuery": True,
             "query": f'SELECT "Avg_HR" AS "Avg HR", "Max_HR" AS "Max HR" FROM "ActivityLap" WHERE {where} ORDER BY time ASC',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
            {"refId": "B", "rawQuery": True,
             "query": f'SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE {where}',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
            {"refId": "C", "rawQuery": True,
             "query": f'SELECT "Altitude" AS "Altitude" FROM "ActivityGPS" WHERE {where} AND "Altitude" > 0 AND "DurationSeconds" <= $activity_end',
             "resultFormat": "time_series", "groupBy": [], "tags": []},
        ],
        "transformations": [
            {"id": "joinByField", "options": {"byField": "Time", "mode": "outer"}},
            {"id": "renameByRegex", "options": {"regex": r"^.*\.(.+)$", "renamePattern": "$1"}},
            {"id": "filterFieldsByName", "options": {"include": {"names": ["Time", "Duration", "Avg HR", "Max HR", "Altitude"]}}},
        ],
    })
    y += 8

    # Per-lap table (h=10)
    panels.append({
        "type": "table", "id": nid(), "title": "Splits par lap (km)",
        "description": "Garmin auto-laps par km. La 1ere col 'Index' donne l'ordre. Pace = mm:ss/km, Power en W, HR en bpm.",
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": y},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {"custom": {"align": "auto"}},
            "overrides": [
                {"matcher": {"id": "byName", "options": "Pace"}, "properties": [{"id": "unit", "value": "dthms"}]},
                {"matcher": {"id": "byName", "options": "Avg HR"}, "properties": [{"id": "unit", "value": "bpm"}, {"id": "color", "value": {"mode": "thresholds"}}, {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "blue"}, {"color": "green", "value": 130}, {"color": "yellow", "value": 160}, {"color": "red", "value": 175}]}}, {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}}]},
                {"matcher": {"id": "byName", "options": "Max HR"}, "properties": [{"id": "unit", "value": "bpm"}]},
                {"matcher": {"id": "byName", "options": "Avg Power"}, "properties": [{"id": "unit", "value": "watt"}]},
                {"matcher": {"id": "byName", "options": "Distance (m)"}, "properties": [{"id": "unit", "value": "lengthm"}]},
                {"matcher": {"id": "byName", "options": "Time"}, "properties": [{"id": "unit", "value": "dthms"}]},
                {"matcher": {"id": "byName", "options": "D+ (m)"}, "properties": [{"id": "unit", "value": "lengthm"}]},
                {"matcher": {"id": "byName", "options": "D- (m)"}, "properties": [{"id": "unit", "value": "lengthm"}]},
                {"matcher": {"id": "byName", "options": "Cadence"}, "properties": [{"id": "unit", "value": "rpm"}]},
            ]
        },
        "options": {"showHeader": True, "footer": {"show": False}, "cellHeight": "sm"},
        "targets": [{"refId": "A", "rawQuery": True,
            "query": f"""SELECT "Index", "Distance" AS "Distance (m)", "Elapsed_Time" AS "Time", 1000.0/("Distance"/"Elapsed_Time") AS "Pace", "Avg_HR" AS "Avg HR", "Max_HR" AS "Max HR", "Avg_Power" AS "Avg Power", "Avg_Cadence"*2 AS "Cadence", "Ascent" AS "D+ (m)", "Descent" AS "D- (m)" FROM "ActivityLap" WHERE {where} ORDER BY time ASC""",
            "resultFormat": "table", "groupBy": [], "tags": []}],
    })

    return panels


def build_dashboard(activities):
    panels = build_panels(activities)
    # Default time = bounds de la latest activite (premier element de la liste, sortee desc)
    if activities:
        default_from = activities[0]["start_iso"]
        default_to = activities[0]["end_iso"]
        default_selector = activities[0]["selector"]
    else:
        default_from = "now-1h"
        default_to = "now"
        default_selector = ""

    # Variable "activity" = query InfluxDB a chaque chargement du dashboard
    # (plus de pre-bake Python). Le selector brut "20260501T092010UTC-running"
    # commence par YYYYMMDDTHHMMSS donc sort=5 (alpha DESC) = chrono DESC
    # (recent first). Le regex extrait "20260501T0920" pour l'affichage (date +
    # heure compactes, sans le suffixe UTC-running), tout en gardant le selector
    # entier comme valeur — les panels filtrent toujours via
    # "ActivitySelector" = '$activity' donc la valeur doit rester intacte.
    # Trade-off vs l'ancien mode "custom" : on perd le label riche
    # (km/duree/activityName) car InfluxQL ne sait pas composer de strings et
    # le regex Grafana ne fait qu'extraire (pas de reformat possible).
    var_activity = {
        "name": "activity",
        "label": "Course a analyser",
        "type": "query",
        "datasource": DS,
        "query": "SHOW TAG VALUES FROM \"ActivitySummary\" WITH KEY = \"ActivitySelector\" WHERE \"ActivitySelector\" =~ /running/",
        "regex": "/^(?<value>(?<text>\\d{8}T\\d{4})\\d{2}UTC-running)$/",
        "sort": 2,  # 2 = alphabetical DESC -> chrono DESC (recent first)
        "refresh": 1,  # on dashboard load
        "current": {"selected": False, "text": default_selector, "value": default_selector},
        "multi": False,
        "includeAll": False,
    }

    # Variable cachee : duree elapsed de l'activite selectionnee. Sert a clip
    # l'axe X des panels ts_dur_panel pile a la fin de l'activite (evite le rabbe
    # auto-padding Grafana). Refresh sur change time range. Default 999999 = no-op
    # le temps que la query resolve.
    var_activity_end = {
        "name": "activity_end",
        "label": "Activity end (s)",
        "type": "query",
        "datasource": DS,
        "query": "SELECT last(\"elapsedDuration\") FROM \"ActivitySummary\" WHERE \"ActivitySelector\" = '$activity'",
        "hide": 2,  # hidden from UI
        "refresh": 2,  # refresh on time range change
        "current": {"selected": True, "text": "999999", "value": "999999"},
        "multi": False,
        "includeAll": False,
    }

    return {
        "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]},
        "description": "Drill-down par activite course a pied. Cliquer un lien dans le tableau du haut pour zoomer sur une activite (set time range + variable). Le panel markdown en bas liste les prescriptions de toutes les seances.",
        "editable": True,
        "graphTooltip": 1,  # shared crosshair entre panels
        "id": None,
        "links": [],
        "panels": panels,
        "refresh": "",  # pas de refresh auto, c'est un drill-down
        "schemaVersion": 39,
        "tags": ["activity-detail", "hr", "pace", "power", "cadence", "splits", "gps", "laps", "workout-steps"],
        "templating": {"list": [var_activity, var_activity_end]},
        "time": {"from": default_from, "to": default_to},
        "timezone": "browser",
        "title": "03 Activity Drill-Down",
        "uid": "garvis-j-activity",
        "version": 1,
        "weekStart": "",
    }


def main():
    global HR_Z, PWR_Z
    print("Fetching current zones from Garmin API...")
    HR_Z[:], PWR_Z[:] = fetch_zones_from_garmin()
    print(f"  HR running zones: {HR_Z}")
    print(f"  Power running zones: {PWR_Z}")
    print()
    print("Fetching recent activities from InfluxDB...")
    activities = fetch_recent_activities(limit=30)
    print(f"  Found {len(activities)} activities")
    if activities:
        print(f"  Latest: {activities[0]['start_local']} - {activities[0]['name']}")
    dash = build_dashboard(activities)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with open(DEST, "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    print(f"Wrote {DEST}")
    print(f"Panels: {len(dash['panels'])}")
    print(f"Default time range: {dash['time']['from']} to {dash['time']['to']}")
    grafana_url = os.environ.get("GRAFANA_URL", "http://localhost:3000")
    print(f"Auto-load Grafana ~10s. URL: {grafana_url}/d/garvis-j-activity")


if __name__ == "__main__":
    main()
