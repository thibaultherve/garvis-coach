# Architecture

## Data flow

```
Garmin watch
    | (auto-sync to Garmin Connect cloud)
    v
+---------------------+
| garmin-fetch-data   |  Polls Garmin Connect API every 15 min.
| (Docker container)  |  Writes daily stats, sleep, stress, body battery,
|                     |  HRV, activities, GPS tracks, zones, scores.
|                     |
|                     |  For each GPS activity, enrich_activity_surface()
|                     |  parses the FIT, POSTs the dense trace to Valhalla
|                     |  (/trace_attributes) for OSM map-matching, and
|                     |  appends terrain enrichment to the same write batch.
|                     |  Gated by ENRICH_SURFACE_VALHALLA, non-fatal.
+---------------------+
    |                         ^
    |                         | (map-matching, recorded activities)
    |                  +---------------------+
    |                  | valhalla            |  OSM map-matching engine.
    |                  | (Docker container)  |  France OSM tiles, port 8002.
    |                  | gis-ops/docker-     |  /trace_attributes: costing
    |                  | valhalla            |  pedestrian, shape_match map_snap.
    |                  +---------------------+  One-off ~3h tile build, then
    |                                           per-activity matching is instant.
    v
+---------------------+
| InfluxDB 1.x        |  Time-series DB. Database: GarminStats.
| (Docker container)  |  ~30 measurements (see CLAUDE.md for catalog).
|                     |  Terrain enrichment adds ActivitySurface,
|                     |  ActivityGrade, ActivityTrack.
+---------------------+
    |
    +---> Grafana (9 dashboards, auto-provisioned)
    |        |
    |        v
    |    grafana-mcp (official, port 8768)
    |        |  Tools: search_dashboards, get_dashboard_summary,
    |        |  query_influxdb, get_dashboard_panel_queries
    |        v
    +---> garmin-coach-mcp (port 8765)
    |        |  33 tools: raw InfluxDB read access
    |        |  Activities, sleep, stress, zones, fitness trends,
    |        |  Hill/Endurance Score, HRV status, heat acclimation,
    |        |  terrain: get_activity_surface_tool,
    |        |  get_activity_grade_summary_tool,
    |        |  get_activity_splits_tool, get_activity_workout_steps_tool
    |        v
    +---> garmin-toolbox (port 8770)
             |  13 tools in 5 modules:
             |  - pace: conversions (pace <-> km/h, distance, predict)
             |  - metrics: TRIMP, ACWR, CTL/ATL/TSB, polarization,
             |             decoupling, HR drift
             |  - dump: full activity JSON (laps, GPS, weather)
             |  - workouts_plan: list/get workouts from workouts_data.py
             |  - garmin_write: upload/delete/schedule on Garmin Connect
             v
         Claude / LLM (via MCP protocol)
```

## Docker services

| Service | Image | Port | Role |
|---|---|---|---|
| influxdb | influxdb:1.11 | 8087 (host) -> 8086 | Time-series storage |
| garmin-fetch-data | thisisarpanghosh/garmin-fetch-data | -- | Data fetcher (cron) + Valhalla surface enrichment |
| valhalla | ghcr.io/gis-ops/docker-valhalla | 8002 | OSM map-matching engine (France tiles) |
| grafana | grafana/grafana:latest | 3000 | Dashboard UI |
| garmin-coach-mcp | built from submodule | 8765 | MCP: raw InfluxDB read |
| garmin-toolbox | built from submodule | 8770 | MCP: metrics + workouts + Garmin API |
| grafana-mcp | mcp/grafana:latest | 8768 | MCP: Grafana proxy |

## Terrain enrichment (Valhalla)

Recorded GPS activities are map-matched against OpenStreetMap to recover
surface, way type and grade — data Garmin does not provide.

**Engine.** `valhalla` (ghcr.io/gis-ops/docker-valhalla, port 8002) is built
once from France OSM extracts (tile build takes ~3h on the DS920+); after that,
per-activity matching is instant.

**Flow.** The fetcher (`enrich_activity_surface()` in `garmin_fetch.py`) parses
each GPS activity's FIT, POSTs the dense trace to Valhalla `/trace_attributes`
(costing `pedestrian`, `shape_match: map_snap`), and appends the resulting
enrichment points to the *same* InfluxDB write batch as the normal ActivityGPS
write. Gated by env `ENRICH_SURFACE_VALHALLA`. Non-fatal: a Valhalla failure
never blocks the ActivityGPS write.

**Measurements added** (all tagged `ActivityID` + `ActivitySelector`):

| Measurement | Granularity | Tags | Fields |
|---|---|---|---|
| `ActivitySurface` | one row per merged OSM edge run | surface, waytype | start_m, end_m, length_m, road_class |
| `ActivityGrade` | one row per 100 m bin | steepness_class | distance_m, elev_m, avg_slope_pct |
| `ActivityTrack` | downsampled GPS points (surface-colored map) | -- | Latitude, Longitude, Surface, Waytype, surf_id, distance_m |

**Consumers.** Grafana dashboard 03 (ECharts panels) and 4 new garmin-coach
MCP tools: `get_activity_surface_tool`, `get_activity_grade_summary_tool`,
`get_activity_splits_tool`, `get_activity_workout_steps_tool`.

> Note: the older ORS route enrichment (`scripts/analyze_routes.py`) stays in
> place for **planned** routes. Valhalla handles **recorded** activities
> (map-matching against the actual GPS trace, not routing).

## Submodules

The monorepo uses 3 git submodules pinned to specific branches:

| Path | Repo | Branch | Purpose |
|---|---|---|---|
| `services/garmin-grafana` | thibaultherve/garmin-grafana | `extended-fetch-fields` | Patched fetcher (6 patches) |
| `services/garmin-coach-mcp` | thibaultherve/garmin-grafana-mcp-server | `extended-coaching-tools` | Extended MCP (33 tools) |
| `services/garmin-toolbox` | thibaultherve/garmin-toolbox | `main` | Metrics + workouts MCP |

## Dashboard provisioning

Dashboards in `dashboards/*.json` are auto-provisioned via `provisioning/dashboards.yml`.
Grafana watches the folder and reloads changes within ~10 seconds.

The datasource (InfluxDB) is provisioned via `provisioning/datasources.yml`
with UID `garmin_influxdb` (referenced by all dashboards).
