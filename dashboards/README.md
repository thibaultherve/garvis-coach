# Grafana dashboards — canonical JSON

The JSON files in this folder **are** the dashboards. They are auto-provisioned
(`provisioning/dashboards.yml`) and Grafana reloads them ~10s after a file
change. Edit the JSON directly — there is no build step.

Panel IDs are stable (gaps after refactors are intentional — they preserve
`?viewPanel=N` deeplinks).

---

## 03 Activity Drill-Down (`garvis-j-activity`) — hand-maintained, do NOT regenerate

This dashboard used to be emitted by `scripts/generate_dashboard_drilldown.py`.
**That generator was retired and deleted on 2026-05-29.** The JSON here is the
single source of truth: it was hand-edited beyond what the generator produced
(most importantly the live zone variables). Re-running any old copy of the
generator over this file would regress those edits. To change the dashboard,
edit the JSON.

The training plan is **not** involved in rendering this dashboard. The plan lives
in `services/garmin-toolbox/workouts_data.py` (its own source of truth) and is
**never** read by the dashboard. The prescribed-vs-executed overlay is 100% live
InfluxQL against `WorkoutStep` / `WorkoutTarget`, which the fetcher reconstructs
from each *executed* activity's FIT file (keyed by `ActivitySelector`) — not from
the forward plan. (The old docstring claiming "generated from workouts_data.py"
was always false.)

### Zone bands — how zones reach the dashboard

- **Time-in-zone queries** (e.g. the Power-zone bargauge) interpolate the live
  Grafana variables `z1_hr`…`z5_hr` / `z1_pwr`…`z5_pwr`, each defined as
  `SELECT last("zoneNFloor") FROM "HRZones"|"PowerZones" WHERE "sport" =~ /(?i)running/`.
  Raw InfluxQL is where `$var` interpolation works, so these auto-adapt to the
  athlete's current Garmin zones with no edit.
- **Colored background bands** on the per-second charts use Grafana `thresholds`
  steps. Grafana does **not** interpolate `$variables` in threshold values, so
  those boundaries are static numbers baked in the JSON (e.g. the HR bands at
  120/140/155/170/185 bpm). Edit them by hand if the athlete's zones shift.

### ECharts panels (surface / grade / splits / workout analysis)

Several panels use the **volkovlabs-echarts-panel** plugin (installed via
`GF_PLUGINS_PREINSTALL` in the compose env). Building their `getOption` JS has a
few non-obvious gotchas:

- **Data access**: read the panel's series from `context.panel.data.series`
  (NOT a global `data` object — that doesn't exist in this build).
- **visualMap can't color a line/area by an arbitrary non-geometric dimension**
  in this plugin build. To color the elevation profile by grade or by surface,
  either emit **multiple line series** (one per band, `null` everywhere except
  that band, and the bands **share the transition point** so the line stays
  continuous), or fall back to **pure `graphic` custom rendering**.
- **Per-bar color**: set `itemStyle` **inside each individual data item**
  (e.g. pace-band color on Splits bars, grade color on Elev, HR-zone color on the
  HR number) — not via a single series-level color.
- **Strava-style column layouts** (Splits id 101, Workout Analysis id 102) are
  drawn with **pure `graphic`** elements, sized off
  `context.panel.chart.getWidth()` / `context.panel.chart.getHeight()`.

These panels consume **3 new enriched measurements**: `ActivitySurface`,
`ActivityGrade`, `ActivityTrack` (alongside the existing `ActivityGPS` /
`ActivityLap`).

### CRITICAL build invariants (preserved from the retired generator)

Every per-second "trend" panel (`xField=Duration`) carries two InfluxDB targets:
refId **A** = the metric (HR / Pace / Power / Cadence / …), refId **B** =
`Duration`. The split is load-bearing:

1. **The Duration query (refId B) must NOT share the metric's filter.**
   It must be exactly
   `SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'`
   — nothing else. If it inherited the metric filter (e.g. `Cadence > 30`,
   `HeartRate > 60`), the rows where the metric is 0/absent (Cadence=0 at the
   start) get `Duration = NULL` after the outer-join with `WorkoutTarget`
   (refId E, which spans Duration=0 → end). The `trend` panel + `xField=Duration`
   then collapses to a single point.

2. **The Duration query (refId B) must NOT share `$activity_end` either.**
   `$activity_end` is `refresh:2` (on time-range change) and can resolve to
   `null` / `""` / a stale cache depending on timing (initial load with a time
   range that doesn't cover the `ActivitySummary` row; dropdown switch without
   re-trigger; the END-marker row with NULL `elapsedDuration`). In those cases a
   clip `DurationSeconds <= ''` excludes **every** row → the Duration query
   returns 0 rows → the trend collapses to one tick. The *metric* query (refId A)
   keeps the `AND "DurationSeconds" <= $activity_end` clip (cosmetic: no ghost
   tail after the activity ends), but Duration must stay robust without the
   variable.

### `$activity` selector variable

```
query: SHOW TAG VALUES FROM "ActivitySummary" WITH KEY = "ActivitySelector" WHERE "ActivitySelector" =~ /running/
regex: /^(?<value>(?<text>\d{8}T\d{4})\d{2}UTC-running)$/
sort:  2   (alphabetical DESC → chrono DESC, most recent first)
```

The raw selector (e.g. `20260513T092228UTC-running`) starts with
`YYYYMMDDTHHMMSS`, so alphabetical-DESC sort == chronological-DESC. The regex
named group `text` extracts `20260513T0922` for a compact label (date + time,
without the `UTC-running` suffix) while the named group `value` keeps the
**entire** selector as the variable value — every panel filters via
`"ActivitySelector" = '$activity'`, so the value must stay intact. (Trade-off vs
the old Python pre-bake: the rich label with km/duration/name is lost, because
InfluxQL can't compose strings and the Grafana regex can only extract, not
reformat.)
