# Garvis Coach — CLAUDE.md

> Context file for Claude Code sessions in this repo. Covers the stack
> (services, dashboards, MCP tools, data access) and coaching methodology.
>
> **The athlete's training plan is in `./services/garmin-toolbox/workouts_data.py`** —
> that file is the **single source of truth** for workouts. Header comments document
> objectives, athlete profile, zones, constraints, cycles, and decisions.

**Vocabulary**:
- **garvis-coach** = this monorepo: docker-compose, Grafana dashboards, scripts, docs.
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
   - **For any running activity analysis**: always query the **03 Activity Drill-Down** dashboard (`garvis-j-activity`) panels via MCP Grafana for each activity being analyzed. The per-second curves (HR, pace, power, cadence, GCT, vertical oscillation, stride length, vertical ratio) + GPS map + zone distributions reveal drift, decoupling, and form degradation far better than numbers alone.
   - **For weekly reviews / bilans**: always query the **02 Training Load & ACWR** dashboard (`garvis-b-load`) panels via MCP Grafana. ACWR, acute vs chronic load, polarization, weekly volume, PMC (CTL/ATL/TSB), and training status timeline provide the full picture needed to assess the week and plan the next one.
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
garvis-coach/                          <- this monorepo
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
|-- dashboards/
|   |-- README.md                      <- canonical-JSON conventions + dashboard-03 build invariants
|   |-- 01-daily-readiness-recovery.json
|   |-- 02-training-load-acwr.json
|   |-- 03-activity-drill-down.json
|   |-- ...
|   +-- 10-calendar-volume.json
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

9 thematic dashboards numbered by workflow (morning readiness -> planning -> post-run -> quality -> terrain -> recovery -> validators -> long-term -> calendar). Auto-provisioned via `provisioning/dashboards.yml` — JSON in `dashboards/` is auto-loaded by Grafana on change (~10s).

### Overview

| File | UID | Title | Use case |
|---|---|---|---|
| `01-daily-readiness-recovery.json` | `garvis-a-daily` | 01 Daily Readiness & Recovery | Morning routine: can I train today? |
| `02-training-load-acwr.json` | `garvis-b-load` | 02 Training Load & ACWR | Weekly load management, overtraining prevention |
| `03-activity-drill-down.json` | `garvis-j-activity` | 03 Activity Drill-Down | Per-run drill-down (hand-maintained canonical JSON — see `dashboards/README.md`). ECharts panels: surface map, 2 elevation profiles, splits, workout analysis, surface/waytype donuts, zone bars. |
| `04-running-form-efficiency.json` | `garvis-d-runq` | 04 Running Form & Efficiency | Running form (cadence, GCT, vertical ratio, stride) |
| `05-hill-trail-performance.json` | `garvis-e-hill` | 05 Hill & Trail Performance | Hill Score, D+, climb rate |
| `06-recovery-diagnostics.json` | `garvis-f-sleep` | 06 Recovery Diagnostics | Sleep, stress, body battery diagnostics |
| `07-sport-science-validators.json` | `garvis-k-validators` | 07 Sport-Science Validators | Validate that the plan produces measurable adaptations |
| `08-long-term-trends.json` | `garvis-c-fitness` | 08 Long-Term Trends | Monthly / end-of-cycle review (VO2max, scores, zones, race predictions) |
| `10-calendar-volume.json` | `garvis-n-calendar` | 10 Calendar - Training Load | Calendar heatmap of runs colored by training load (1 year) |

### Panels by dashboard

> Owner: `PANELS_CATALOG.md` (same dir) — every panel across the 9 dashboards with
> title, description, and source query. Read it before any analysis/bilan.
> Panel counts: 01 (16), 02 (21), 03 (27), 04 (7), 05 (12), 06 (29), 07 (22), 08 (37), 10 (1).

### Structural notes

- **Datasource**: UID `garmin_influxdb`, schema v39, filter `"ActivitySelector" =~ /running/` on all activity panels.
- **ECharts plugin**: `volkovlabs-echarts-panel` is installed via `GF_PLUGINS_PREINSTALL`. Used by the new dashboard-03 surface/elevation/splits/workout panels.
- **Editing**: modify JSON in `dashboards/`, Grafana auto-reloads in ~10s. For rapid iteration, use `PUT /api/dashboards/db` (may be overwritten on next file reload).
- Panel IDs are stable (not renumbered after refactors — gaps are normal, preserving deeplink `?viewPanel=N`).

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

Official `grafana/mcp-grafana`. Key tools: `search_dashboards`, `get_dashboard_summary`, `get_dashboard_panel_queries`, `get_dashboard_property`. ⚠️ Avoid `query_influxdb` for reads (anonymises columns + broken time window — see Common pitfalls); use curl direct or `garmin-coach.get_activity_profile_tool`. No PNG/panel render tool exists (so "visual" dashboard analysis isn't available to the LLM today).

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

**Before any training analysis or bilan**, read `PANELS_CATALOG.md` (same directory) — it lists every panel across all 9 dashboards with title, description, and source query. Use it to know which metrics are available and what they measure.
