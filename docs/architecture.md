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
+---------------------+
    |
    v
+---------------------+
| InfluxDB 1.x        |  Time-series DB. Database: GarminStats.
| (Docker container)  |  ~30 measurements (see CLAUDE.md for catalog).
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
    |        |  22 tools: raw InfluxDB read access
    |        |  Activities, sleep, stress, zones, fitness trends,
    |        |  Hill/Endurance Score, HRV status, heat acclimation
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
| garmin-fetch-data | thisisarpanghosh/garmin-fetch-data | -- | Data fetcher (cron) |
| grafana | grafana/grafana:latest | 3000 | Dashboard UI |
| garmin-coach-mcp | built from submodule | 8765 | MCP: raw InfluxDB read |
| garmin-toolbox | built from submodule | 8770 | MCP: metrics + workouts + Garmin API |
| grafana-mcp | mcp/grafana:latest | 8768 | MCP: Grafana proxy |

## Submodules

The monorepo uses 3 git submodules pinned to specific branches:

| Path | Repo | Branch | Purpose |
|---|---|---|---|
| `services/garmin-grafana` | thibaultherve/garmin-grafana | `extended-fetch-fields` | Patched fetcher (6 patches) |
| `services/garmin-coach-mcp` | thibaultherve/garmin-grafana-mcp-server | `extended-coaching-tools` | Extended MCP (22 tools) |
| `services/garmin-toolbox` | thibaultherve/garmin-toolbox | `main` | Metrics + workouts MCP |

## Dashboard provisioning

Dashboards in `dashboards/*.json` are auto-provisioned via `provisioning/dashboards.yml`.
Grafana watches the folder and reloads changes within ~10 seconds.

The datasource (InfluxDB) is provisioned via `provisioning/datasources.yml`
with UID `garmin_influxdb` (referenced by all dashboards).
