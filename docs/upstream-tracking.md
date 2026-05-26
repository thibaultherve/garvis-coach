# Upstream tracking

This project uses 2 forks with custom patches. Here's how to keep them in sync.

## Fork: garmin-grafana

**Upstream**: [arpanghosh8453/garmin-grafana](https://github.com/arpanghosh8453/garmin-grafana)
**Our fork**: [thibaultherve/garmin-grafana](https://github.com/thibaultherve/garmin-grafana)
**Branch**: `extended-fetch-fields`

### Syncing with upstream

```bash
cd services/garmin-grafana
git remote add upstream https://github.com/arpanghosh8453/garmin-grafana.git  # once
git fetch upstream
git rebase upstream/main
# Resolve any conflicts with our patches
git push origin extended-fetch-fields --force-with-lease
```

### Our patches (6)

1. `trainingEffectLabel` exposed in ActivitySummary
2. `monthlyLoadLow` / `monthlyLoadMedium` / `monthlyLoadHigh` in TrainingStatus
3. `trainingBalanceFeedbackPhrase` in TrainingStatus
4. Daily `HRZones` / `PowerZones` snapshots
5. `HeatAltitudeAcclimation` measurement (heat/altitude acclimation %)
6. `HRVStatus` measurement (weekly avg, baseline band, status)

All patches are generic (not athlete-specific) and could be proposed as PRs upstream.

## Fork: garmin-grafana-mcp-server

**Upstream**: [ghighi3f/garmin-grafana-mcp-server](https://github.com/ghighi3f/garmin-grafana-mcp-server) (v1.7.0, MIT)
**Our fork**: [thibaultherve/garmin-grafana-mcp-server](https://github.com/thibaultherve/garmin-grafana-mcp-server)
**Branch**: `extended-coaching-tools`

### Syncing with upstream

```bash
cd services/garmin-coach-mcp
git remote add upstream https://github.com/ghighi3f/garmin-grafana-mcp-server.git  # once
git fetch upstream
git rebase upstream/main
git push origin extended-coaching-tools --force-with-lease
```

### Our extensions (22 tools total, ~10 added)

Added tools: `get_zones_snapshot_tool`, `get_hill_score_history_tool`,
`get_endurance_score_history_tool`, `get_activities_extras_tool`,
`get_hrv_status_tool`, `get_heat_acclimation_tool`, `get_power_zones_tool`,
`get_training_zones_tool`, plus enhanced existing tools.

## Submodule updates

After syncing a fork, update the submodule pointer in the monorepo:

```bash
cd /path/to/garvis-coach
git add services/garmin-grafana   # or services/garmin-coach-mcp
git commit -m "chore: update garmin-grafana submodule to latest"
```

## garmin-toolbox (not a fork)

`services/garmin-toolbox` tracks `main` on our own repo. No upstream to sync.
Just pull latest:

```bash
cd services/garmin-toolbox
git pull origin main
```

## Proposing patches upstream

Our fork patches are designed to be generic. To propose them upstream:

1. Create a branch from `upstream/main` with just one patch
2. Open a PR on the upstream repo
3. If accepted, remove the patch from our fork branch
4. Rebase our branch on the new upstream
