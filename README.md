# Garvis Coach -- AI-powered running coach with Garmin data

> Garmin watch -> InfluxDB -> Grafana dashboards + MCP servers -> Claude
> becomes a real running coach with access to all my training data.

## What is this?

This is my personal coaching stack. I built it to turn my Garmin watch data
into something an AI can actually reason about -- not just display numbers,
but cross-reference sleep, stress, training load, weather, and physiology
to give real coaching advice backed by real data.

It's not a product. It's not meant to work out of the box for everyone. It's
an opinionated, customizable example of what you can build when you give an
LLM direct access to structured athletic data. Fork it, tear it apart, make
it yours.

Garmin Connect shows you what happened. This stack helps you understand why,
and what to do next.

---

## What the AI coach unlocks

The core idea: Claude gets direct read/write access to all my Garmin data
through 3 MCP servers. It can query, cross-reference, compute, and push
workouts to my watch -- all from a conversation.

- Ask **"why did today's run feel so hard?"** -- it checks last night's sleep,
  stress, cumulative load, temperature, and heart rate drift in one answer
- Ask **"am I ready for intervals tomorrow?"** -- it pulls body battery, HRV
  trend, recovery time, and recent session intensity
- Ask **"compare my last two long runs"** -- it accounts for elevation, heat,
  pacing, and fatigue instead of just comparing pace
- Ask **"is my base building working?"** -- it shows whether easy pace is
  improving at the same heart rate, whether decoupling is trending down,
  whether VO2max is moving
- Describe a workout in plain language and it **writes the structured session,
  uploads it to Garmin Connect, and schedules it** on my watch
- Every number is traceable to a real query -- no guessing, no approximation

---

## Everything this stack can do

### Daily readiness & recovery

- **Body Battery**: current level, 24h curve, drain during the day vs recharge overnight
- **Sleep**: score, total hours, deep/light/REM/awake breakdown, 14-day stage history
- **Sleep physiology**: intraday HRV and breathing rate at 5-minute resolution during sleep, SpO2, stress during sleep -- *Garmin shows a score, this shows what happened inside*
- **Sleep regularity**: bedtime consistency heatmap -- *not available in Garmin*
- **HRV status**: last night vs 7-day average vs personal baseline band (Balanced / Unbalanced / Low)
- **Resting heart rate**: 30-day trend -- rising RHR often signals accumulated fatigue before you feel it
- **Training Readiness**: 0-100 score with component breakdown (sleep, HRV, recovery time, stress, activity history)
- **Stress**: daily breakdown (high/medium/low/rest minutes), 30-day heatmap to spot weekly patterns -- *Garmin shows today, this shows the pattern*
- **Stress vs sleep scatter plot**: which bad nights actually hurt recovery and which didn't -- *not in Garmin*
- **Stress vs training load scatter plot**: separate life stress from training stress -- *not in Garmin*
- **Heat acclimation**: percentage and trend, useful before racing in warm conditions
- **Daily energy balance**: sedentary vs active vs highly active hours, BMR and active calories, steps, floors

### Activity analysis

- **Full summary**: distance, duration, avg/max HR, pace, calories, elevation gain/loss, aerobic + anaerobic training effect (0-5)
- **Per-second telemetry on a single timeline**: heart rate with zone shading, pace, power, cadence, stride length, ground contact time, vertical oscillation, vertical ratio -- *Garmin shows one metric at a time, this overlays all of them*
- **GPS track on map**: color-coded by speed or by heart rate
- **Lap-by-lap splits**: distance, time, HR, pace, cadence, power for each lap
- **HR zone and power zone distribution**: time in each zone as percentages (5 HR zones, 7 Coggan power zones)
- **Planned workout vs actual execution** side by side: prescribed steps and targets next to what you actually ran -- *not available in Garmin post-activity*
- **Peak power curve**: best average watts over 1s, 5s, 10s, 30s, 1min, 5min, 20min
- **Aerobic decoupling**: how much efficiency drops between first and second half of a steady run (<5% = solid base, >7% = needs work) -- *not computed by Garmin*
- **Cardiac drift**: heart rate creep on steady-paced efforts, detects fatigue or dehydration -- *not computed by Garmin*
- **Weather overlay**: temperature, humidity, wind, rain automatically fetched for any activity from GPS coordinates -- *Garmin doesn't cross-reference weather with performance*
- **Running form over 60 days**: cadence, ground contact time, vertical ratio, stride length trends with cardiac drift per activity
- **Hill Score**: overall, strength (short steep climbs) vs endurance (long sustained climbs) with balance indicator -- *Garmin shows overall only, not the breakdown*
- **D+ per kilometer**: normalized climbing intensity to compare routes fairly -- *not in Garmin*
- **Vertical climb rate**: meters per minute at steady effort, tracked over time

### Training load & balance

- **ACWR** (Acute:Chronic Workload Ratio) with sweet-spot band (0.8-1.3): below = undertraining, above = injury risk. Two variants: rolling average and exponentially-weighted -- *Garmin has a simpler version without the visual band or EWMA*
- **Performance Manager Chart (CTL/ATL/TSB)**: fitness built over 42 days, fatigue over 7 days, and the balance between them. Warnings when overreaching (<-30) or detraining (>+25) -- *this is the TrainingPeaks model, not available in Garmin*
- **Training Status timeline**: Productive, Maintaining, Overreaching, Detraining, Peaking, Recovery -- tracked over time, not just current
- **Polarization analysis**: time in easy (Z1+Z2), moderate (Z3), hard (Z4+Z5) with elite targets (80/5/15). Flags the "moderate intensity trap" -- *Garmin shows zone time per activity but doesn't analyze the overall training balance*
- **12-week polarization trend**: see whether your training discipline is improving week by week -- *not in Garmin*
- **Weekly volume**: distance and duration by sport over 6 months
- **Training intensity minutes**: daily breakdown
- **TRIMP**: training impulse per session (combines duration and intensity into one stress number)
- **Year-at-a-glance calendar heatmap**: every training day color-coded by load -- *not in Garmin*

### Long-term fitness & race predictions

- **VO2max**: running and cycling separately, trended over 6 months
- **Race predictions**: estimated 5K, 10K, half-marathon, marathon times trending over months
- **Endurance Score**: weekly, with classification (Novice to Expert) and breakdown by sport contribution -- *Garmin shows the score but not the sport breakdown trend*
- **Fitness Age vs real age**: tracked over time, watch the gap grow
- **Zone recalibration history**: when did max HR, lactate threshold, resting HR, FTP, and zone boundaries shift? -- *Garmin updates these silently, this shows every change*
- **Power-to-heart-rate ratio** over months: more watts per beat = better efficiency -- *not in Garmin*
- **HR vs pace scatter across all runs**: should spread horizontally as fitness builds -- *not in Garmin*
- **Peak power curve**: improvements at different durations (1s through 20min)
- **Critical pace estimates** for standard race distances
- **Weight** weekly average
- **Heat and altitude acclimation** tracked over time
- **Decoupling trend over 90 days**: should decrease during base building -- *not in Garmin*
- **Z2 pace progression**: is easy pace getting faster at the same HR? -- *not in Garmin*
- **HRV stability** (coefficient of variation): should decrease during a good training block -- *not in Garmin*

### Workout planning & Garmin Connect management

- **Write workouts in Python**: warm-up, intervals, repeats, cool-down with HR zone or power targets and coaching notes
- **Preview** any workout's full step structure before uploading
- **Upload** to Garmin Connect: shows up on the watch with step-by-step guidance
- **Replace**: delete old version and upload updated one in one command
- **Bulk update**: refresh an entire training block (date range) at once
- **Delete** workouts by name or ID
- **List** all uploaded workouts with search by name pattern
- **Pace calculator**: convert pace/speed, calculate distance from pace+time, predict total session from multi-segment workouts

### Multi-athlete support

- Separate MCP instances per athlete, each with isolated data
- Each athlete gets activity analysis, load tracking, recovery, fitness trends, sleep, power, personal records, training zones

---

## Dashboards

| # | Name | What it answers |
|---|---|---|
| 01 | Daily Readiness & Recovery | Can I train today? |
| 02 | Training Load & ACWR | Am I overtraining? |
| 03 | Activity Drill-Down | How was this run? |
| 04 | Running Form & Efficiency | Is my technique improving? |
| 05 | Hill & Trail Performance | How strong am I on climbs? |
| 06 | Recovery Diagnostics | Why am I tired? |
| 07 | Sport-Science Validators | Is my plan actually working? |
| 08 | Long-Term Trends | Big picture over months |
| 10 | Calendar | Year-at-a-glance load heatmap |

---

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
    |---> Grafana (9 dashboards, auto-provisioned)
    |        |
    |        v
    |    grafana MCP -----> Claude / LLM
    |                           ^
    |---> garmin-coach MCP -----+
    |     (per-athlete instances)
    |                           ^
    +---> garmin-toolbox MCP ---+
          (computations + Garmin Connect API)
```

- **garmin-fetch-data** pulls data from Garmin Connect every 15 minutes into InfluxDB
- **garmin-coach MCP** gives the AI read access to all Garmin data (activities, recovery, sleep, trends, zones, records)
- **garmin-toolbox MCP** gives the AI computation tools (TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, drift) and Garmin Connect write access (upload, schedule, delete workouts)
- **grafana MCP** lets the AI query InfluxDB directly and inspect/modify dashboards

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
