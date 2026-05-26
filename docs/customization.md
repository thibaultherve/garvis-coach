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

Dashboard 03 (Activity Drill-Down) and 07 (Validators) use HR/Power zone
thresholds from InfluxDB. These auto-populate from the `HRZones` and
`PowerZones` measurements once the fetcher has run.

The visual zone bands (colored backgrounds) in the per-second charts use
fallback defaults. To update them to your zones, run:

```bash
python scripts/generate_dashboard_drilldown.py
```

This reads your current zones from Garmin Connect and regenerates dashboard 03.

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
