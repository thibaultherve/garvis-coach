# Customization

How to adapt Garvis Coach for your own training.

## 1. Environment variables (.env)

Copy `.env.example` to `.env` and fill in:

```env
# Garmin Connect credentials
GARMIN_EMAIL=your.email@example.com
GARMIN_PASSWORD=your_password

# InfluxDB (change the password)
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=your_secure_password

# Athlete physiological parameters (used by garmin-toolbox)
ATHLETE_HR_MAX=190        # Your max HR (Garmin Connect > Settings > HR Zones)
ATHLETE_HR_REST=50        # Your resting HR
# ATHLETE_LTHR=170        # Optional: lactate threshold HR
# ATHLETE_FTP=250         # Optional: functional threshold power
```

## 2. Training plan (workouts_data.py)

```bash
cp services/garmin-toolbox/workouts_data.example.py \
   services/garmin-toolbox/workouts_data.py
```

Edit with your own workouts using the DSL helpers:

```python
from workouts_helpers import *

WORKOUTS = [
    {
        "date": "2026-06-01",
        "code": "W1-Mon-EZ-40min",
        "description": "Easy Z2 run",
        "steps": [
            s("Warmup", 10, type="warmup", target=hrZ(2)),
            s("Main", 25, type="active", target=hrZ(2)),
            s("Cooldown", 5, type="cooldown", target=hrZ(1)),
        ]
    },
]
```

Available helpers: `s()`, `rep()`, `hrZ()`, `hrR()`, `pwr()`, `OPEN()`, `NONE()`.
See `workouts_data.example.py` for detailed examples.

## 3. Dashboard zone thresholds

Activity Drill-Down (`garvis-j-activity`) and the validators section of Fitness Trends &
Validation (`garvis-c-fitness`) read your HR/Power zones
from InfluxDB. The `HRZones` / `PowerZones` measurements (populated once the
fetcher has run) feed Grafana dashboard variables (`z1_hr`…`z5_hr`,
`z1_pwr`…`z5_pwr`) that the time-in-zone InfluxQL queries interpolate
automatically — no regeneration needed.

The only static piece is the **colored band background** on the per-second
charts: Grafana threshold steps can't interpolate variables, so those boundary
values are hard-coded in the JSON. If your zones differ from the defaults and you
want the colored bands to match, edit the `thresholds.steps[].value` numbers
directly in `dashboards/03-activity-drill-down.json` (the HR / Power band panels).

> Dashboard 03 is a hand-maintained canonical JSON — there is no generator
> script. Read `dashboards/README.md` for the build invariants before editing it.

## 4. GPX routes and climbs (optional)

If you want route analysis and climb discovery:

1. Place your GPX files in `data/gpx/`
2. Run `python scripts/analyze_routes.py` to generate route profiles
3. Run `python scripts/discover_climbs.py --center LAT,LON --radius 15` to
   find all climbs near your training area

## 5. Claude Code MCP configuration

Add to your `.claude.json` or Claude Code settings:

```json
{
  "mcpServers": {
    "garmin-coach": {
      "url": "http://YOUR_IP:8765/mcp"
    },
    "garmin-toolbox": {
      "url": "http://YOUR_IP:8770/mcp"
    },
    "grafana": {
      "url": "http://YOUR_IP:8768/mcp"
    }
  }
}
```

## 6. Local Claude configuration

Copy `CLAUDE.local.example.md` to `CLAUDE.local.md` and fill in your:
- Server IP and paths
- Athlete profile (HR zones, FTP, weight, age)
- Training plan context
- Any health notes relevant to training decisions

This file is gitignored and stays private.

## 7. Weather in activity dumps (optional)

Activity dumps (`garmin-toolbox.dump_activity`) automatically include weather
data from Open-Meteo using the GPS coordinates from the activity. No
configuration needed -- it uses the first GPS point of each activity.
