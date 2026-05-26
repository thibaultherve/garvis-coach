# Credits

Garvis Coach is built on top of these open-source projects:

## Core data pipeline

**[arpanghosh8453/garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana)**
Garmin Connect data fetcher that populates InfluxDB with daily stats, sleep, stress, body battery, HRV, activities, GPS tracks, and more. We use a fork with extended fetch fields (training effect labels, monthly load, HRV status, heat acclimation, HR/Power zone snapshots).

## MCP servers

**[ghighi3f/garmin-grafana-mcp-server](https://github.com/ghighi3f/garmin-grafana-mcp-server)** (MIT)
MCP server providing raw read access to Garmin data in InfluxDB. We use a fork with extended coaching tools (22 tools covering zones, Hill/Endurance Score, activity extras, HRV status, heat acclimation).

**[grafana/mcp-grafana](https://github.com/grafana/mcp-grafana)** (Apache 2.0)
Official Grafana MCP server for dashboard search, panel query extraction, and InfluxDB proxy queries. Used unmodified.

## Infrastructure

**[InfluxDB 1.x](https://github.com/influxdata/influxdb)** (MIT)
Time-series database storing all Garmin data.

**[Grafana](https://github.com/grafana/grafana)** (AGPL-3.0)
Dashboard visualization platform hosting 9 thematic training dashboards.

## Sport science references

Training load calculations in garmin-toolbox are based on published methods:
- TRIMP: Banister 1991
- ACWR: Hulin/Gabbett 2016 (rolling), Williams 2017 (EWMA)
- CTL/ATL/TSB: TrainingPeaks Performance Manager
- Polarization: Seiler 2010 IJSPP
- Aerobic decoupling: Friel / TrainingPeaks
- HR drift: Maffetone / Friel
