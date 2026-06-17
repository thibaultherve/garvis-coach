# Garvis Coach — CLAUDE.md

> Context file for Claude Code sessions in this repo. Covers the stack
> (services, dashboards, MCP tools, data access) and coaching methodology.
>
> **The athlete's training plan is in `./services/garmin-toolbox/workouts_data.py`** —
> that file is the **single source of truth** for workouts. Header comments document
> objectives, athlete profile, zones, constraints, cycles, and decisions.

**Vocabulary**:
- **garvis-running-coach** = this monorepo: docker-compose, Grafana dashboards, scripts, docs.
- **garmin-toolbox** = MCP server (submodule in `./services/garmin-toolbox/`): pace conversions, training metrics, activity dumps, workout plan read/write, Garmin Connect operations.
- **garmin-coach-mcp** = MCP server (submodule in `./services/garmin-coach-mcp/`): raw read access to all Garmin data in InfluxDB (33 tools).

---

## Source of truth (who owns what)

Each topic has **one** owning file; the others summarize + point to it.
Fix a rule/pitfall → edit the owner, never the copies (prevents drift across files).

| Topic | Owner | Others |
|---|---|---|
| Claude behavior + sport-science | `COACHING_RULES.md` §0-13 | summary + pointer only |
| Training plan (workouts) | `workouts_data.py` | read via MCP `garmin-toolbox` |
| Stack / infra (dashboards, MCP, InfluxDB) + infra/build pitfalls | `CLAUDE.md` (this file) | — |
| Data-read pitfalls (reading MCP/Influx values) | `CLAUDE.md` (this file + the PC entry file) | always-loaded quick-list |

---

## TL;DR for a new Claude session

0. **Read `COACHING_RULES.md` first** — regles comportement Claude (anti-sycophancy, verify-before-claim, zero mental math, calibration) + regles sport-science sourcees (Daniels, Seiler, Gabbett, Bakken, meta-analyses 2022-2025). Checklist pre-cycle incluse. **Si conflit avec un autre fichier, COACHING_RULES.md gagne.**
2. **Read `./services/garmin-toolbox/workouts_data.py`** — the header covers the full plan (objectives, profile, zones, constraints, cycles, decisions). The `WORKOUTS` list below shows where we are. You can also list workouts via MCP: `garmin-toolbox.list_workouts(start_date, end_date)`.
3. **Read this CLAUDE.md** for infra (dashboards, MCP, InfluxDB).
4. **Before any analysis**: query fresh data via MCP `garmin-coach` (read InfluxDB raw) or MCP `grafana` / dashboards `garvis-*`. For derived metrics (TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, HR drift), use MCP `garmin-toolbox.compute_*`. Never do mental math.
   - **For any running activity analysis**: always query the **Activity Drill-Down** dashboard (`garvis-j-activity`) panels via MCP Grafana for each activity being analyzed. The per-second curves (HR, pace, power, cadence, GCT, vertical oscillation, stride length, vertical ratio) + GPS map + zone distributions reveal drift, decoupling, and form degradation far better than numbers alone.
   - **For weekly reviews / bilans**: always query the **Training Load & Terrain** dashboard (`garvis-b-load`) panels via MCP Grafana. ACWR, acute vs chronic load, polarization, weekly volume, PMC (CTL/ATL/TSB), training status timeline, **and the vertical-load section (ACWR vertical D+, weekly D+/D-, D+/km, VAM, terrain cost)** provide the full picture needed to assess the week and plan the next one.
5. **To modify a workout**: edit `workouts_data.py` then call `garmin-toolbox.garmin_upload_workout(code=..., replace=True)`.
6. **NEVER** modify workouts directly in Garmin Connect (source of truth is workouts_data.py).

---

## Tone & behavior

> Owner: `COACHING_RULES.md` §0 (read first every session — anti-sycophancy, no
> over-cautious health warnings, calibration). The two rules that actually prevent
> errors are restated here:
> - **Verify-before-claim**: no number without a traceable source in the same turn (MCP / InfluxQL / script). Missing data = "I need to query X", never an estimate.
> - **ZERO mental arithmetic**: pace, %, deltas, UTC→local → `garmin-toolbox.compute_*` or `python -c`. Quote numbers verbatim from JSON.

---

## Operational workflows

### Modify a workout

1. Edit `./services/garmin-toolbox/workouts_data.py` — modify the `WORKOUTS` list.
2. Push to Garmin via MCP: `garmin-toolbox.garmin_upload_workout(code="C1-S3-Fri-Trail-LR-85min", replace=True)`.
3. If the code changes (rename): delete the old one via `garmin-toolbox.garmin_delete_workout(workout_name="OLD-CODE")`, then upload the new one.
4. To replay a whole block: `garmin-toolbox.garmin_bulk_replace(start_date, end_date, code_pattern?)`.

### Add a new workout / cycle

Edit `workouts_data.py` directly:

```python
WORKOUTS.append({
    "date": "2026-MM-DD",
    "code": "Cx-Sy-Day-ShortName",
    "description": "...",
    "steps": [
        s("Warmup", 15, type="warmup", target=hrZ(2)),
        s("Effort", 30, type="active", target=hrZ(2), notes="Z2 strict"),
        ...
    ]
})
```

Helpers: `s(name, duration_min, type=, target=, notes=)`, `rep(iters, *steps)`, `hrZ(n)`, `hrR(low, high)`, `pwr(low, high)`, `OPEN()`, `NONE()`.

Then upload via `garmin-toolbox.garmin_upload_workout(code=...)`. The MCP reloads `workouts_data.py` on every call (importlib.reload).

### List / inspect workouts

```
garmin-toolbox.list_workouts(start_date="2026-05-18", end_date="2026-05-24")
garmin-toolbox.get_workout(code="C1-S3-Fri-Trail-LR-85min")
garmin-toolbox.garmin_list_uploaded(name_pattern="C1-S3")
```

---

## File architecture

```
garvis-running-coach/                          <- this monorepo
|-- docker-compose.yml
|-- .env.example
|-- CLAUDE.md                          <- this file (generic)
|-- CLAUDE.local.md                    <- GITIGNORED (your personal config)
|-- COACHING_RULES.md                  <- SoT: behavior rules + sport-science (anti-sycophancy, PoT, Daniels/Seiler/Gabbett)
|-- README.md
|-- CREDITS.md
|
|-- services/
|   |-- garmin-grafana/                <- [submodule] extended fetcher (+ Valhalla surface enrichment)
|   |-- garmin-coach-mcp/              <- [submodule] MCP InfluxDB reader (33 tools)
|   +-- garmin-toolbox/                <- [submodule] MCP compute + workouts + Garmin write
|       |-- workouts_helpers.py        <- DSL (committed)
|       |-- workouts_data.example.py   <- template (committed)
|       +-- workouts_data.py           <- GITIGNORED (your training plan)
|
|-- dashboards/                        <- 3 dashboards (reorg 2026-06-07)
|   |-- README.md                      <- canonical-JSON conventions + Activity-Drill-Down build invariants
|   |-- 02-training-load-acwr.json     <- "Training Load & Terrain" (garvis-b-load) — inclut l'ex-05 Hill/Trail
|   |-- 03-activity-drill-down.json    <- "Activity Drill-Down" (garvis-j-activity)
|   +-- 08-long-term-trends.json       <- "Fitness Trends & Validation" (garvis-c-fitness) — inclut l'ex-07 Validators
|
|-- provisioning/
|   |-- dashboards.yml
|   +-- datasources.yml
|
|-- scripts/
|   |-- analyze_routes.py
|   |-- routes_db.py, dedup_routes.py
|   |-- geocode_routes.py
|   +-- discover_climbs.py
|
|-- data/                              <- GITIGNORED (tokens, dumps, gpx, routes, history)
+-- docs/
```

### Services (docker-compose)

- **garmin-grafana** — extended fetcher. Now also runs `enrich_activity_surface()` (`garmin_fetch.py`) at fetch time for each GPS activity: map-matches the trace against OSM via Valhalla and writes 3 measurements (see catalog). Gated by env `ENRICH_SURFACE_VALHALLA=True` (set in `.env`); **non-fatal** (failures log + skip, never block the fetch).
- **valhalla** — `ghcr.io/gis-ops/docker-valhalla`, France OSM tiles, port **8002**. Routing/map-matching engine used for OSM surface + waytype enrichment. ⚠️ One-off France tile build is long (~3 h on the DS920+); once built the tiles persist (don't rebuild casually).

---

## Dashboards

3 thematic dashboards (post-run drill-down · load & terrain planning · long-term & validation). Auto-provisioned via `provisioning/dashboards.yml` — JSON in `dashboards/` is auto-loaded by Grafana on change (~10s).

> **Reorg 2026-06-07** : passé de 9 à 3 dashboards. Supprimés : 01 Readiness, 04 Running Form, 06 Recovery Diagnostics (peu utilisés ; la donnée sous-jacente reste lisible via MCP `garmin-coach`). Fusionnés : 05 Hill & Trail → `garvis-b-load`, 07 Sport-Science Validators → `garvis-c-fitness`. Numérotation des titres retirée. Pas de dashboard calendrier (le fichier `10-calendar-volume.json` n'existe pas / n'est pas provisionné).

### Overview

| File | UID | Title | Use case |
|---|---|---|---|
| `02-training-load-acwr.json` | `garvis-b-load` | Training Load & Terrain | Pilotage charge (ACWR, polarisation, CTL/ATL/TSB, monotonie/strain, volume, training status, HRV, chaleur) **+ charge verticale & terrain** (ACWR vertical D+, budget D+ vs plafond ~830 m, D+/km, VAM, coût terrain, cumul D+). Inclut l'ex-05 Hill & Trail. |
| `03-activity-drill-down.json` | `garvis-j-activity` | Activity Drill-Down | Per-run drill-down (hand-maintained canonical JSON — see `dashboards/README.md`). ECharts panels: surface map, 2 elevation profiles, splits, workout analysis, surface/waytype donuts, zone bars. |
| `08-long-term-trends.json` | `garvis-c-fitness` | Fitness Trends & Validation | Review mensuel / fin de cycle : trajectoires long-terme (VO2max, race predictions, Hill/Endurance Score, zones FCmax/LTHR/FTP, poids, Eddington, EF GAP/HR, acclimatation) **+ validateurs sport-science** (aerobic decoupling, allure/volume Z2 & Z4-Z5, power/pace curves, allure à FC fixée, impact chaleur EF/WBGT). Inclut l'ex-07 Validators. |

### Panels by dashboard

> Owner: `PANELS_CATALOG.md` (same dir) — every panel across the 3 dashboards with
> title, description, and source query. Read it before any analysis/bilan.
> Content-panel counts (2026-06-08): `garvis-b-load` 27 (+4 rows), `garvis-j-activity` 20, `garvis-c-fitness` 29 (+1 row).

### Structural notes

- **Datasource**: UID `garmin_influxdb`, schema v39, filter `"ActivitySelector" =~ /running/` on all activity panels.
- **ECharts plugin**: `volkovlabs-echarts-panel` is installed via `GF_PLUGINS_PREINSTALL`. Used by the Activity-Drill-Down surface/elevation/splits/workout panels and several `garvis-c-fitness` ECharts panels.
- **Live HR-zone variables**: `garvis-j-activity` and `garvis-c-fitness` (validators section) carry hidden query variables `z1_hr`…`z5_hr` + `fcmax` (live from `HRZones`), so the Z2 / Z4-Z5 panels auto-adapt to the athlete's current Garmin zones.
- **Editing**: modify JSON in `dashboards/`, Grafana auto-reloads in ~10s. For rapid iteration, use `PUT /api/dashboards/db` (may be overwritten on next file reload).
- Panel IDs are stable (not renumbered after refactors — gaps are normal, preserving deeplink `?viewPanel=N`). On the 2026-06-07 merge only colliding source IDs were renumbered: into `garvis-b-load`, ex-05 content ids 5/6/7/8/10 + row 101 → 152-157, and the pre-existing duplicate id 12 (Weekly Volume) → 151; into `garvis-c-fitness`, ex-07 ids 8/13 → 501/502 — so existing `#120`/`#300` cross-references stay valid.

---

## Data access

### 1. MCP `garmin-coach` (preferred)

33 tools covering: schema exploration, training zones (HR + Power), recent activities, activity details (per-second), weekly load summary, training status, fitness trends (VO2max, race predictions, weight), fitness age, Hill/Endurance Score history, daily recovery (sleep, HRV, RHR, body battery, training readiness), sleep physiology, stress/body battery intraday, personal records, peak power, power history, activity load history, energy balance, HRV status, heat acclimation, plus terrain enrichment (surface/waytype breakdown, grade summary, per-km splits, per-step workout analysis).

Surface/grade/splits tools (all accept an `ActivitySelector`, fall back to the last activity):
- `get_activity_surface_tool` — merged OSM surface/waytype runs (from `ActivitySurface`).
- `get_activity_grade_summary_tool` — per-bin steepness distribution (from `ActivityGrade`).
- `get_activity_splits_tool` — per-km / per-lap splits.
- `get_activity_workout_steps_tool` — structured workout steps + targets for the activity.

**Notes**:
- Activities expose `training_effect_label`: `AEROBIC_BASE` / `TEMPO` / `LACTATE_THRESHOLD` / `VO2MAX` / `ANAEROBIC_CAPACITY` / `SPRINT`.
- Do NOT use `garmin_coaching_advice` — FIT SDK enum mapping is incorrect on some codes. Read `trainingBalanceFeedbackPhrase` directly via `get_training_status_tool`.
- `get_training_status_tool` returns `recovery_time_min` (minutes) and `recovery_time_h` (hours, already converted) — use directly, don't divide. `training_readiness.factors` (hrv/sleep_score/recovery_time/acwr/stress_history %) is populated.
- All Garmin timestamps are **UTC** — always convert to athlete's local timezone.

### 2. MCP `garmin-toolbox` (derived metrics + dump + workout ops)

13 tools in 5 modules:

| Module | Tool | Usage |
|---|---|---|
| pace | `compute_pace(op, ...)` | sport conversions (op = kmh/pace/dist/pace_from/predict) |
| metrics | `compute_trimp` | TRIMP Banister 1991 |
| metrics | `compute_acwr` | ACWR rolling + EWMA (Hulin/Gabbett 2016, Williams 2017) |
| metrics | `compute_ctl_atl_tsb` | Performance Manager (TrainingPeaks) |
| metrics | `compute_polarization` | LIT/MIT/HIT Seiler 2010 |
| metrics | `compute_decoupling` | Aerobic decoupling Pa:HR (Friel) |
| metrics | `compute_hr_drift` | HR drift (Maffetone/Friel) |
| dump | `dump_activity` | Full activity dump (summary + laps + workout steps + targets + GPS per-second + weather) |
| workouts_plan | `list_workouts` / `get_workout` | Read training plan |
| garmin_write | `garmin_upload_workout` / `garmin_delete_workout` / `garmin_bulk_replace` / `garmin_list_uploaded` | Garmin Connect operations |

### 3. MCP `grafana` (dashboards + InfluxQL proxy)

Official `grafana/mcp-grafana`. Key tools: `search_dashboards`, `get_dashboard_summary`, `get_dashboard_panel_queries`, `get_dashboard_property`. ⚠️ Avoid `query_influxdb` for reads (anonymises columns + broken time window — see Common pitfalls); use curl direct or `garmin-coach.get_activity_profile_tool`.

**Visual screenshots (PNG) — `get_panel_image`** *(activé 2026-06-07, nécessite le Grafana Image Renderer désormais installé)* : rend un panel **ou un dashboard entier** en PNG et **retourne l'image en base64** → le LLM la VOIT (analyse visuelle des courbes, debug d'un panel, ou simplement donner l'image à l'utilisateur). C'est LE tool pour "screenshot un dashboard / un graph". Params :
- `dashboardUid` **(requis)** — ex. `garvis-b-load`, `garvis-j-activity`, `garvis-c-fitness`. ⚠️ le nom du param est `dashboardUid`, **pas** `uid` (sinon Grafana rend une page "Page not found" en PNG, sans erreur).
- `panelId` *(optionnel)* — un panel précis ; **omis = dashboard entier**. (Récupérer les IDs via `get_dashboard_summary`.)
- `timeRange` `{from,to}` (ex. `{"from":"now-90d","to":"now"}`), `width` (déf. 1000), `height` (déf. 500), `scale` 1-3, `theme` light/dark, `variables`, `timeout` (déf. 60s).
- Pile technique : `get_panel_image` → endpoint `/render` de Grafana → conteneur sidecar `grafana-image-renderer` (Chromium headless). Le `--enabled-tools` du service `grafana-mcp` doit inclure `rendering`. Un full-dashboard met ~10 s.
- ⚠️ Après (ré)activation côté serveur, **une session Claude Code déjà ouverte ne voit pas le nouveau tool** tant que la connexion MCP grafana n'a pas été relancée (`/mcp` reconnect, ou redémarrer la session).

### 4. InfluxDB direct (fallback)

```bash
curl -G http://$INFLUXDB_HOST:$INFLUXDB_PORT/query \
  --data-urlencode "db=GarminStats" \
  --data-urlencode "q=SELECT ..." \
  -u "$INFLUXDB_USERNAME:$INFLUXDB_PASSWORD"
```

---

## InfluxDB measurements catalog

- **Daily**: `DailyStats`, `BodyComposition` (weight only), `LifestyleJournal`
- **Intraday**: `HeartRateIntraday`, `StepsIntraday`, `StressIntraday`, `BodyBatteryIntraday`, `BreathingRateIntraday`, `HRV_Intraday`, `SleepIntraday`
- **Sleep**: `SleepSummary`
- **Performance**: `VO2_Max`, `RacePredictions`, `LactateThreshold`, `FitnessAge`, `EnduranceScore`, `HillScore`, `TrainingStatus`, `TrainingReadiness`, `HRZones`, `PowerZones`, `HeatAltitudeAcclimation`, `HRVStatus`
- **Activities**: `ActivitySummary` (per-run, with `trainingEffectLabel`), `ActivityGPS` (per-second), `ActivityLap`, `ActivitySession`, `ActivityLength`
- **Surface enrichment** (Valhalla map-matching, all tagged `ActivityID` + `ActivitySelector`):
  - `ActivitySurface` — one row per merged OSM edge run. Tags `surface`, `waytype`; fields `start_m`, `end_m`, `length_m`, `road_class`.
  - `ActivityGrade` — per 100 m bin. Tag `steepness_class`; fields `distance_m`, `elev_m`, `avg_slope_pct`.
  - `ActivityTrack` — downsampled points for the surface map. Fields `Latitude`, `Longitude`, `Surface`, `Waytype`, `surf_id`, `distance_m`.

---

## Common pitfalls

- **`grafana.query_influxdb` is broken for coaching reads** -> it renames every column to `Value` (ambiguous) and its `start/end` window does NOT translate to a reliable InfluxQL time filter (returns nulls or out-of-range rows). To read InfluxDB: use **curl direct** (`curl -G http://$INFLUXDB_HOST:$INFLUXDB_PORT/query ... -u user:pass`, keeps named columns) or `garmin-coach.get_activity_profile_tool` (pre-aggregated, named blocks). Reserve `query_influxdb` for trivial single-field cases only — never `SELECT *` or time series.
- **If Garmin API bugs** -> `pip install -U garminconnect` first (unofficial lib, frequent releases).
- **Grafana unit `m` = minutes** (not meters). For D+: use `lengthm`. For pace: `dthms`.
- **Garmin `trainingStatus` numeric mapping unreliable** -> use `trainingStatusFeedbackPhrase` string.
- **Per-ActivityID groupBy saturates the legend** -> prefer `GROUP BY time(1d)`. If truly per-activity, use `resultFormat: "table"` + transformations.
- **InfluxQL sub-queries with `TOP()` invalid** -> rethink as `GROUP BY ActivityID, time(30s)` + dashboard variable.
- **New source to InfluxDB** -> check field types before first write (silent type conflict possible).
- **Dashboard 03 xField=Duration**: the Duration query (refId B) must NOT share the metric filter (e.g. `Cadence>0`) **nor** `$activity_end` — either one makes the trend collapse to a single point. Full rationale + the `$activity` selector regex live in `dashboards/README.md`. (03 is a hand-maintained canonical JSON; the generator was retired 2026-05-29.)
- **ECharts (`volkovlabs-echarts-panel`) gotchas**:
  - In the `getOption` JS, read frames from `context.panel.data.series` — there is **no** global `data` object in this build.
  - `visualMap` **cannot** color a single line by an arbitrary dimension in this build → use multiple series (one per category) or a pure `graphic` render instead.
  - Per-bar color: set `itemStyle` on each individual data item (not via `visualMap`/series-level color).
- **Surface-enrichment backfill**: history was backfilled by a one-off script reading `ActivityGPS` from InfluxDB and feeding it to Valhalla (no Garmin re-fetch). Going forward, new activities are enriched at fetch by `enrich_activity_surface()`.

---

## Panel catalog

**Before any training analysis or bilan**, read `PANELS_CATALOG.md` (same directory) — it lists every panel across all 3 dashboards with title, description, and source query. Use it to know which metrics are available and what they measure.
