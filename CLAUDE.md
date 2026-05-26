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
- **garmin-coach-mcp** = MCP server (submodule in `./services/garmin-coach-mcp/`): raw read access to all Garmin data in InfluxDB (22 tools).

---

## TL;DR for a new Claude session

0. **Read `COACHING_PROTOCOL.md` first** (8 sections). It defines behavioral rules: anti-sycophancy, verify-before-claim, Chain-of-Verification, Program-of-Thought, calibration, fallback flowchart, Reflexion log. **If it conflicts with any other file, the protocol wins.**
1. **Read `./services/garmin-toolbox/workouts_data.py`** — the header covers the full plan (objectives, profile, zones, constraints, cycles, decisions). The `WORKOUTS` list below shows where we are. You can also list workouts via MCP: `garmin-toolbox.list_workouts(start_date, end_date)`.
2. **Read this CLAUDE.md** for infra (dashboards, MCP, InfluxDB).
3. **Before any analysis**: query fresh data via MCP `garmin-coach` (read InfluxDB raw) or MCP `grafana` / dashboards `garvis-*`. For derived metrics (TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, HR drift), use MCP `garmin-toolbox.compute_*`. Never do mental math.
4. **To modify a workout**: edit `workouts_data.py` then call `garmin-toolbox.garmin_upload_workout(code=..., replace=True)`.
5. **NEVER** modify workouts directly in Garmin Connect (source of truth is workouts_data.py).

---

## Tone & behavior

> Full details: `COACHING_PROTOCOL.md`. Summary here.

- **No over-cautious health warnings.** When the athlete reports pain or fatigue, it's context for adapting training, not a signal to produce "red flag" checklists or repeated "see a doctor" disclaimers. Adapt pragmatically.
- **No sycophancy.** If data contradicts the athlete, say so in the first sentence. No "great question" / "you're right to" / "indeed". Firm verdicts, no hedging. (cf. PROTOCOL section 1)
- **Verify-before-claim.** No number without a traceable source in the same turn (MCP / InfluxQL / Python script). Missing data = "I don't have this, I need to query X" — never a plausible estimate. (cf. PROTOCOL section 2)
- **ZERO mental arithmetic, even trivial.** Pace conversions, distance from pace x time, weighted means, percentages, deltas, projections, UTC to local time — **everything** goes through: (a) MCP `garmin-toolbox.compute_pace` for sport conversions, (b) a throwaway `python -c "..."`, or (c) MCP/dashboard if the number already exists. Advanced metrics (TRIMP, CTL/ATL/TSB, ACWR, decoupling, polarization, HR drift) via MCP `garmin-toolbox.compute_*`. Prose = number quoted verbatim from JSON. (cf. PROTOCOL sections 4 and 4bis)
- **Explicit calibration**: tags `[conf X, n=Y, sigma=Z]` on key numeric claims. No confidence without `n=`. (cf. PROTOCOL section 5)

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
|-- COACHING_PROTOCOL.md               <- behavioral rules (anti-sycophancy, PoT, etc.)
|-- README.md
|-- CREDITS.md
|
|-- services/
|   |-- garmin-grafana/                <- [submodule] extended fetcher
|   |-- garmin-coach-mcp/              <- [submodule] MCP InfluxDB reader (22 tools)
|   +-- garmin-toolbox/                <- [submodule] MCP compute + workouts + Garmin write
|       |-- workouts_helpers.py        <- DSL (committed)
|       |-- workouts_data.example.py   <- template (committed)
|       +-- workouts_data.py           <- GITIGNORED (your training plan)
|
|-- dashboards/
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
|   |-- generate_dashboard_drilldown.py
|   |-- analyze_routes.py
|   |-- routes_db.py, dedup_routes.py
|   |-- geocode_routes.py
|   +-- discover_climbs.py
|
|-- data/                              <- GITIGNORED (tokens, dumps, gpx, routes, history)
+-- docs/
```

---

## Dashboards

9 thematic dashboards numbered by workflow (morning readiness -> planning -> post-run -> quality -> terrain -> recovery -> validators -> long-term -> calendar). Auto-provisioned via `provisioning/dashboards.yml` — JSON in `dashboards/` is auto-loaded by Grafana on change (~10s).

### Overview

| File | UID | Title | Use case |
|---|---|---|---|
| `01-daily-readiness-recovery.json` | `garvis-a-daily` | 01 Daily Readiness & Recovery | Morning routine: can I train today? |
| `02-training-load-acwr.json` | `garvis-b-load` | 02 Training Load & ACWR | Weekly load management, overtraining prevention |
| `03-activity-drill-down.json` | `garvis-j-activity` | 03 Activity Drill-Down | Per-run drill-down (generated by `generate_dashboard_drilldown.py`) |
| `04-running-form-efficiency.json` | `garvis-d-runq` | 04 Running Form & Efficiency | Running form (cadence, GCT, vertical ratio, stride) |
| `05-hill-trail-performance.json` | `garvis-e-hill` | 05 Hill & Trail Performance | Hill Score, D+, climb rate |
| `06-recovery-diagnostics.json` | `garvis-f-sleep` | 06 Recovery Diagnostics | Sleep, stress, body battery diagnostics |
| `07-sport-science-validators.json` | `garvis-k-validators` | 07 Sport-Science Validators | Validate that the plan produces measurable adaptations |
| `08-long-term-trends.json` | `garvis-c-fitness` | 08 Long-Term Trends | Monthly / end-of-cycle review (VO2max, scores, zones, race predictions) |
| `10-calendar-volume.json` | `garvis-n-calendar` | 10 Calendar - Training Load | Calendar heatmap of runs colored by training load (1 year) |

### Panels by dashboard

**01 Daily Readiness & Recovery** (16 panels, 30d window, refresh 5min):
Top stats: Body Battery, Sleep Score, HRV vs 7d, RHR, Training Readiness, Recovery Time. Heat acclimation: Heat %, Heat Trend. Time series: Body Battery 24h, Stress 24h, RHR & HRV 30d, Training Readiness components. Calendar/distribution: Month at a Glance, HR Distribution, HR Range, Selected time range table.

**02 Training Load & ACWR** (21 panels, 90d window, refresh 10min):
Top stats: ACWR, Acute 7d, Chronic 28d, Weekly load, Training Status. Time series: ACWR + sweet spot, Acute vs Chronic, TE cumul 30d, Polarisation 80/10/10 weekly (12w), Load Focus shortage, Load Focus vs optimal. Volume: Weekly volume 6m, Training Intensity, Activities calendar, Daily Intensity Minutes. PMC row: CTL/ATL/TSB, Training Status timeline, Load Focus history. HRV Status row: 7-day avg + baseline band.

**03 Activity Drill-Down** (27 panels, per-activity vars):
Header stats (12): Distance, Duration, Avg/Max HR, Avg Pace, Calories, D+/D-, Aerobic/Anaerobic TE, Exercise Load, VO2max. Geo: GPS Track by Velocity, GPS Track by HR. Zones: HR Zones %, Power Zones %. Per-second trends with overlay: HR + Z1-Z5 bands, Pace, Power, Cadence, Stride length, Vertical Ratio, Vertical Oscillation, GCT, Avg HR per lap + altitude. Tables: Workout steps prescribed/executed, Splits per lap. Zone thresholds are auto-populated from InfluxDB `HRZones`/`PowerZones` via dashboard variables.

**04 Running Form & Efficiency** (7 panels, 60d window, refresh 1h):
Cadence, Vertical Ratio, GCT, Step Length, Speed, Recent runs table, HR difference per activity.

**05 Hill & Trail Performance** (12 panels, 90d window):
Hill Score Overall/Strength/Endurance, Balance Gap, D+ (7d/30d/365d/YTD), Hill Score trend, D+ per week, D+/km per run, Altitude profiles.

**06 Recovery Diagnostics** (29 panels, 30d window, refresh 30min):
Sleep row: Score, Duration, HRV, Breathing rate, Awakenings, SpO2, Sleep Score 30d, Sleep stages 14d, HRV + Breathing, Avg sleep stress. Stress row: Stress avg, High stress duration, Body Battery, BB drained/charged, Stress %, Body Battery 14d, Stress heatmap, Stress vs Sleep, Stress vs Training Load. Sleep complement: Regularity heatmap, Intraday HR/SpO2/HRV, Sleep piechart, Stress overview.

**07 Sport-Science Validators** (22 panels, 90d window, refresh 1h):
Top stats: EF 30d, Pace Z2 median, HRV CV, HR in altitude, Climb rate, Decoupling %. Sections: Aerobic Decoupling, Pace progression weekly (Z2 + Z4/Z5), HRV stability, Vertical climb rate, HR vs Pace scatter, Power Curve 90d, Critical Pace Curve 90d, EF trend. Z2 queries auto-adapt to athlete zones via InfluxDB `HRZones` variables.

**08 Long-Term Trends** (37 panels, 6 month window, refresh 1h):
Cardio: VO2max, Endurance Score, Hill Score, Fitness Age, LTHR, RHR, trends. Zones recalibration: HRmax, LTHR, HRrest, FTP, HR/Power zone boundary trends. Body: Weight. Race Predictions (LoL-style VDOT tiers): 5K, 10K, Half, Marathon. Power-HR ratio. Eddington number + distribution. Heat & Altitude Acclimation.

**10 Calendar** (1 panel, 365d window):
Training load calendar heatmap (green <60, yellow 60-120, orange 120-200, red >200).

### Structural notes

- **Datasource**: UID `garmin_influxdb`, schema v39, filter `"ActivitySelector" =~ /running/` on all activity panels.
- **Editing**: modify JSON in `dashboards/`, Grafana auto-reloads in ~10s. For rapid iteration, use `PUT /api/dashboards/db` (may be overwritten on next file reload).
- Panel IDs are stable (not renumbered after refactors — gaps are normal, preserving deeplink `?viewPanel=N`).

---

## Data access

### 1. MCP `garmin-coach` (preferred)

22 tools covering: schema exploration, training zones (HR + Power), recent activities, activity details (per-second), weekly load summary, training status, fitness trends (VO2max, race predictions, weight), fitness age, Hill/Endurance Score history, daily recovery (sleep, HRV, RHR, body battery, training readiness), sleep physiology, stress/body battery intraday, personal records, peak power, power history, activity load history, energy balance, HRV status, heat acclimation.

**Notes**:
- Activities expose `training_effect_label`: `AEROBIC_BASE` / `TEMPO` / `LACTATE_THRESHOLD` / `VO2MAX` / `ANAEROBIC_CAPACITY` / `SPRINT`.
- Do NOT use `garmin_coaching_advice` — FIT SDK enum mapping is incorrect on some codes. Read `trainingBalanceFeedbackPhrase` directly via `get_training_status_tool`.
- `recovery_time_h` is in **minutes** (naming bug) — divide by 60.
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

Official `grafana/mcp-grafana`. Key tools: `search_dashboards`, `get_dashboard_summary`, `get_dashboard_panel_queries`, `get_dashboard_property`, `query_influxdb`.

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

---

## Common pitfalls

- **If Garmin API bugs** -> `pip install -U garminconnect` first (unofficial lib, frequent releases).
- **Grafana unit `m` = minutes** (not meters). For D+: use `lengthm`. For pace: `dthms`.
- **Garmin `trainingStatus` numeric mapping unreliable** -> use `trainingStatusFeedbackPhrase` string.
- **Per-ActivityID groupBy saturates the legend** -> prefer `GROUP BY time(1d)`. If truly per-activity, use `resultFormat: "table"` + transformations.
- **InfluxQL sub-queries with `TOP()` invalid** -> rethink as `GROUP BY ActivityID, time(30s)` + dashboard variable.
- **New source to InfluxDB** -> check field types before first write (silent type conflict possible).
- **Dashboard 03 xField=Duration**: query B (DurationSeconds) must ignore the metric filter (e.g. Cadence>0), otherwise NULL Duration at start breaks the trend.

---

## Panel catalog

**Before any training analysis or bilan**, read `PANELS_CATALOG.md` (same directory) — it lists every panel across all 9 dashboards with title, description, and source query. Use it to know which metrics are available and what they measure.
