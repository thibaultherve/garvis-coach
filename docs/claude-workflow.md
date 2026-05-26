# Claude workflow -- using MCP servers with an LLM

This guide explains how to use the 3 MCP servers with Claude Code (or any
MCP-compatible LLM) for AI-powered coaching.

## The 3 MCPs and when to use each

| MCP | Port | When to use |
|---|---|---|
| **garmin-coach** | 8765 | Default for reading data. Activities, sleep, stress, HRV, zones, fitness trends, Hill/Endurance Score. Fast, aggregated. |
| **garmin-toolbox** | 8770 | Derived metrics (TRIMP, ACWR, CTL/ATL/TSB, polarization, decoupling, HR drift). Activity dumps. Pace conversions. Workout read/write. Garmin Connect API. |
| **grafana** | 8768 | Dashboard inspection (what queries does panel X use?). Ad hoc InfluxQL via proxy. |

### Decision flowchart

```
Need a Garmin data point?
  |-> Try garmin-coach first (22 tools, fast)
  |     |-> null or need per-second data?
  |           |-> garmin-toolbox.dump_activity (full JSON)
  |
Need a derived metric (TRIMP, ACWR, CTL/ATL/TSB...)?
  |-> garmin-toolbox.compute_* (authoritative)
  |
Need to inspect a dashboard or run custom InfluxQL?
  |-> grafana MCP (query_influxdb, get_dashboard_panel_queries)
  |
Need to modify a workout?
  |-> garmin-toolbox (upload/delete/bulk_replace)
```

## Workflow: post-activity analysis

1. **Fetch the activity**: `garmin-coach.get_last_activity_tool()` or
   `get_activity_details_tool(activity_id)` for per-second data.

2. **Dump for deep analysis**: `garmin-toolbox.dump_activity(last=true)` writes
   a full JSON (summary + laps + workout steps + GPS per-second + weather) to
   `data/activities/`. Read the file for per-second analysis.

3. **Compare prescribed vs actual**: the dump includes `workout_target_collapsed`
   which groups steps by target ranges. Compare with actual HR/pace/power.

4. **Compute metrics**: `garmin-toolbox.compute_decoupling(selector=...)` for
   aerobic decoupling, `compute_hr_drift(selector=...)` for drift.

5. **Cross-reference dashboards**: check dashboard 03 (Activity Drill-Down) for
   visual confirmation, dashboard 02 for load impact.

## Workflow: weekly review

1. **Load summary**: `garmin-coach.get_weekly_load_summary_tool()` for km, time,
   ACWR, polarization, time-in-zones.

2. **Training status**: `garmin-coach.get_training_status_tool()` for Garmin's
   assessment + `trainingBalanceFeedbackPhrase`.

3. **PMC check**: `garmin-toolbox.compute_ctl_atl_tsb()` for CTL/ATL/TSB.

4. **Recovery check**: `garmin-coach.get_daily_recovery_tool()` for sleep, HRV,
   body battery, training readiness.

5. **Review dashboards**: dashboard 01 (readiness), 02 (load), 07 (validators).

## Workflow: modify a workout

1. **Read current plan**: `garmin-toolbox.list_workouts(start_date, end_date)`
   to see what's scheduled.

2. **Edit workouts_data.py**: modify the `WORKOUTS` list (via file edit or SMB).

3. **Upload**: `garmin-toolbox.garmin_upload_workout(code="...", replace=True)`.

4. **Verify**: `garmin-toolbox.garmin_list_uploaded(name_pattern="...")` to
   confirm it's on Garmin Connect.

## Workflow: monthly / end-of-cycle review

1. **Fitness trends**: `garmin-coach.get_fitness_trend_tool(days=90)` for VO2max,
   race predictions, weight.

2. **Hill/Endurance Score**: `garmin-coach.get_hill_score_history_tool(days=90)`,
   `get_endurance_score_history_tool(days=90)`.

3. **Long-term metrics**: dashboard 08 (Long-Term Trends) for visual review.

4. **Validator check**: dashboard 07 -- is pace improving at constant HR?
   Is decoupling trending down? Is HRV stable?

5. **PMC trajectory**: `garmin-toolbox.compute_ctl_atl_tsb(days=180)` for
   full fitness/fatigue history.

## Important rules

These are enforced by `COACHING_PROTOCOL.md`:

- **No mental math.** All numeric calculations through code or MCP tools.
- **Verify before claiming.** Every number needs a traceable source.
- **No sycophancy.** If data contradicts the athlete, say so first.
- **Calibration tags.** Key claims get `[conf X, n=Y]` tags.
