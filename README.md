# Garvis Coach -- AI-powered running coach with Garmin data

> Your Garmin watch data -> InfluxDB -> Grafana dashboards + MCP servers
> -> Claude (or any LLM) becomes your personal running coach with access
> to real training data.

## What is this?

Garvis Coach is a self-hosted stack that turns your Garmin watch data into an
AI-accessible coaching platform. It connects your Garmin Connect account to a
local time-series database, visualizes everything in 9 thematic dashboards,
and exposes 3 MCP (Model Context Protocol) servers so any LLM can read your
training data and act as your coach.

### Features

- **9 Grafana dashboards**: daily readiness, training load & ACWR, per-activity
  drill-down, running form, hill/trail performance, recovery diagnostics,
  sport-science validators, long-term trends, calendar heatmap
- **garmin-toolbox MCP**: pace conversions, training metrics (TRIMP, ACWR,
  CTL/ATL/TSB, polarization, decoupling, HR drift), activity dumps with weather,
  workout management, Garmin Connect API operations
- **garmin-coach MCP**: raw access to all Garmin data in InfluxDB (activities,
  sleep, stress, HRV, body battery, zones, fitness trends)
- **Workout DSL**: encode training plans in Python, compile to .fit files,
  auto-schedule in Garmin Connect

### What this is NOT

- Not a turn-key app. You'll read code, edit config files, and run Docker.
- Not a training plan. You write your own workouts (or ask your AI coach to).
- Not limited to running -- the data layer covers all Garmin activities, though
  the dashboards are optimized for running/trail.

## Architecture

```
Garmin watch
    | (Garmin Connect cloud sync)
    v
garmin-fetch-data (every 15 min)
    |
    v
InfluxDB 1.x
    |
    |---> Grafana (9 dashboards)
    |        |
    |        v
    |    grafana MCP -----> Claude / LLM
    |                           ^
    |---> garmin-coach MCP -----+
    |                           ^
    +---> garmin-toolbox MCP ---+
```

## Quick start

### Prerequisites

- Docker & Docker Compose
- A Garmin Connect account with a compatible watch
- (Optional) Claude Code or another MCP-compatible LLM client

### Setup

1. Clone with submodules:
   ```bash
   git clone --recurse-submodules https://github.com/thibaultherve/garvis-coach.git
   cd garvis-coach
   ```

2. Configure:
   ```bash
   cp .env.example .env
   # Edit .env: set your Garmin credentials, athlete HR zones, passwords
   ```

3. (Optional) Create your training plan:
   ```bash
   cp services/garmin-toolbox/workouts_data.example.py \
      services/garmin-toolbox/workouts_data.py
   # Edit with your own workouts
   ```

4. Start:
   ```bash
   docker compose up -d
   ```

5. Wait ~15 minutes for the fetcher to populate InfluxDB, then open
   Grafana at http://localhost:3000 (default: admin/admin).

6. (Optional) Connect your LLM to the MCP servers -- see
   [docs/claude-workflow.md](docs/claude-workflow.md).

## Dashboards

| # | Name | What it answers |
|---|---|---|
| 01 | Daily Readiness & Recovery | Can I train today? (sleep, HRV, body battery, stress) |
| 02 | Training Load & ACWR | Am I overtraining? (load, ACWR, polarization, PMC) |
| 03 | Activity Drill-Down | How was this run? (HR/pace/power per-second overlay) |
| 04 | Running Form & Efficiency | Is my form improving? (cadence, GCT, vertical ratio) |
| 05 | Hill & Trail Performance | How strong am I on hills? (Hill Score, D+, climb rate) |
| 06 | Recovery Diagnostics | Why am I tired? (sleep stages, stress heatmap, BB drain) |
| 07 | Sport-Science Validators | Is the plan working? (decoupling, pace progression, HRV) |
| 08 | Long-Term Trends | Big picture (VO2max, race predictions, zones, weight) |
| 10 | Calendar | Year-at-a-glance training load heatmap |

## Components

| Component | Repo | License |
|---|---|---|
| Garvis Coach (this repo) | [garvis-coach](https://github.com/thibaultherve/garvis-coach) | MIT |
| garmin-toolbox (MCP) | [garmin-toolbox](https://github.com/thibaultherve/garmin-toolbox) | MIT |
| garmin-grafana (fetcher) | [garmin-grafana](https://github.com/thibaultherve/garmin-grafana) fork, branch `extended-fetch-fields` | Upstream |
| garmin-grafana-mcp-server | [garmin-grafana-mcp-server](https://github.com/thibaultherve/garmin-grafana-mcp-server) fork, branch `extended-coaching-tools` | MIT |
| grafana/mcp-grafana | [Official](https://github.com/grafana/mcp-grafana) | Apache 2.0 |

## Documentation

- [Architecture](docs/architecture.md) -- how the pieces fit together
- [Customization](docs/customization.md) -- adapt for your own training
- [Claude workflow](docs/claude-workflow.md) -- using MCP servers with an LLM
- [Upstream tracking](docs/upstream-tracking.md) -- keeping forks in sync

## Credits

Built on top of:
- [arpanghosh8453/garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana) -- Garmin data fetcher + Grafana setup
- [ghighi3f/garmin-grafana-mcp-server](https://github.com/ghighi3f/garmin-grafana-mcp-server) -- MCP server for Garmin/InfluxDB data
- [grafana/mcp-grafana](https://github.com/grafana/mcp-grafana) -- official Grafana MCP server

## License

MIT for original code in this repo and garmin-toolbox.
Forks inherit their upstream license (see each fork's LICENSE file).
