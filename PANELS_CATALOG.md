## 01 Daily Readiness & Recovery (garvis-a-daily)

### Body Battery (now)

### Sleep Score (last night)

### HRV last night vs 7d avg

### RHR last night

### Training Readiness

### Recovery Time (h)
Garmin native recoveryTime (minutes) divided by 60.
Source: SELECT last("recoveryTime") / 60 AS "h" FROM "TrainingReadiness" WHERE $timeFilt...

### Body Battery 24h

### Stress 24h

### RHR & HRV 30d

### Training Readiness composantes (30d)

### Month at a Glance — Daily Average (30j)
Calendar multi-metric view: RHR, Stress, Active, BB, Steps, SpO2, Sleep score, Sleep, HRV.

### HR Distribution (histogram intraday)
HR distribution over selected range with sleep/active/peak thresholds.
Source: select mean_value from (SELECT mean("HeartRate") as mean_value FROM "HeartRateIn...; select mean_value from (SELECT mean("HeartRate") as mean_value FROM "HeartRateIn...

### HR Range daily (Max-Min)
Daily HR spread (max-min). Low spread = stressed autonomic system.

### Selected time range at a Glance
Summary table for the selected time range.
Source: SELECT max("totalDistanceMeters") FROM "DailyStats" WHERE $timeFilter GROUP BY t...; SELECT max("totalSteps") FROM "DailyStats" WHERE $timeFilter GROUP BY time(1d) f...

## 02 Training Load & ACWR (garvis-b-load)

### Training Status Timeline — 180d
Garmin training status bands (Productive / Peaking / Maintaining / Recovery / Strained / Unproductive / Detraining / Overreaching). Garmin enum suffix _N indicates duration in state — grouped by main category here.
Source: SELECT "trainingStatusFeedbackPhrase" AS Status FROM "TrainingStatus" WHERE $tim...

### Load Focus History — 180d
Garmin trainingBalanceFeedbackPhrase: BALANCED (ideal) / AEROBIC_LOW_FOCUS (base focus = OK for Seiler polarized plan) / AEROBIC_LOW/HIGH_SHORTAGE / ANAEROBIC_SHORTAGE/FOCUS. Garmin _N suffixes stripped via regex.
Source: SELECT "trainingBalanceFeedbackPhrase" AS "Load Focus" FROM "TrainingStatus" WHE...

### Training Status
Raw Garmin phrase (e.g. PRODUCTIVE_1, MAINTAINING_2, RECOVERY_2). Numeric trainingStatus code not used (mapping uncertain across firmware).

### Load Focus
Official Garmin source (trainingBalanceFeedbackPhrase). Requires extended fetcher patch.
Source: SELECT last("trainingBalanceFeedbackPhrase") AS "shortage" FROM "TrainingStatus"...

### Acute Training Load (ACWR)

### Acute vs Chronic Load + Garmin Targets

### Load Focus 28d — vs Optimal Range
Bands: blue = shortage (below target_min), green = optimal range, red = overload (above target_max). Thresholds calibrated on current Garmin target_min/max (recalibrate if Garmin adjusts).
Source: SELECT last("monthlyLoadAnaerobic") AS "Anaerobic", last("monthlyLoadAerobicHigh...

### Polarization 80/10/10 — Weekly (12 wk)
Weekly % time in HR zones (Mon-Sun, Europe/Paris TZ). Garmin colors: Z1+Z2 blue (target >= 80%), Z3 green (target 10%), Z4+Z5 red (target <= 10%). Rolling 12 weeks including current week.
Source: SELECT sum("hrTimeInZone_1") + sum("hrTimeInZone_2") AS "Z1+Z2 (cible 80%)", sum...

### Training Intensity (Aerobic + Anaerobic + Load + Endurance)
Daily summary: aerobic/anaerobic TE + acute/chronic load + endurance score.

### Weekly Volume — 6 Months (Mon-Sun)
Source: SELECT sum("distance") FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySel...; SELECT sum("elapsedDuration") FROM "ActivitySummary" WHERE $timeFilter AND "Acti...

### Foster Monotony & Strain (7d Rolling)
Foster Monotony & Strain (Foster et al., J Strength Cond Res 2001).

Monotony = mean(daily_load_7d) / stddev(daily_load_7d). High monotony (>2.0) = increased illness/staleness risk. Strain = weekly_load × Monotony.
Source: SELECT moving_average(daily_tl, 7) / sqrt(moving_average(daily_tl_sq, 7) - movin...; SELECT (moving_average(daily_tl, 7) * 7) * (moving_average(daily_tl, 7) / sqrt(m...

### PMC — Fitness (CTL 42d) / Fatigue (ATL 7d) / Form (TSB)
Rolling mean approximation of TrainingPeaks EWMA. CTL = 6-week aerobic fitness. ATL = 7-day fatigue. TSB = CTL - ATL: negative = overload, positive = peak form. Competition sweet spot: TSB +5 to +15.
Source: SELECT moving_average(daily_tl, 42) AS "CTL (fitness 42j)", moving_average(daily...; SELECT moving_average(daily_tl, 42) - moving_average(daily_tl, 7) AS "TSB (form)...

### HRV Status (7-day avg + baseline)
Replicates Garmin Connect HRV Status graph. Grey band = personal baseline. Colored markers by status: green = Balanced, orange = Unbalanced, red = Low.
Source: SELECT mean("weeklyAvg") AS "Balanced" FROM "HRVStatus" WHERE "status" = 'BALANC...; SELECT mean("weeklyAvg") AS "Unbalanced" FROM "HRVStatus" WHERE "status" = 'UNBA...

### Heat Trend
Current heat acclimation trend from Garmin.

### Heat Acclimation (historique)
Garmin heat acclimation %. Increases with training in hot conditions. >75% = well acclimated. Seasonal pattern expected.

### Heat Acclimation
Garmin heat acclimation %. >75 = well adapted.

## 03 Activity Drill-Down (garvis-j-activity)

### Distance
Source: SELECT last("distance")/1000 FROM "ActivitySummary" WHERE "ActivitySelector" = '...

### Duration
Source: SELECT last("elapsedDuration") FROM "ActivitySummary" WHERE "ActivitySelector" =...

### Avg HR
Source: SELECT last("averageHR") FROM "ActivitySummary" WHERE "ActivitySelector" = '$act...

### Max HR
Source: SELECT last("maxHR") FROM "ActivitySummary" WHERE "ActivitySelector" = '$activit...

### Avg Pace (per km)
Source: SELECT 1000.0/last("averageSpeed") FROM "ActivitySummary" WHERE "ActivitySelecto...

### Calories
Source: SELECT last("calories") FROM "ActivitySummary" WHERE "ActivitySelector" = '$acti...

### Elev gain (D+)
Source: SELECT last("elevationGain") FROM "ActivitySummary" WHERE "ActivitySelector" = '...

### Elev loss (D-)
Source: SELECT last("elevationLoss") FROM "ActivitySummary" WHERE "ActivitySelector" = '...

### Aerobic TE
Source: SELECT last("aerobicTrainingEffect") FROM "ActivitySummary" WHERE "ActivitySelec...

### Anaerobic TE
Source: SELECT last("anaerobicTrainingEffect") FROM "ActivitySummary" WHERE "ActivitySel...

### Exercise Load
Source: SELECT last("activityTrainingLoad") FROM "ActivitySummary" WHERE "ActivitySelect...

### VO2max (post-run)
Source: SELECT last("vO2MaxValue") FROM "ActivitySummary" WHERE "ActivitySelector" = '$a...

### GPS Track by Velocity
Track colored by speed (km/h). Green = slow, red = fast.
Source: SELECT "Latitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'; SELECT "Longitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'

### GPS Track by Heart Rate
Track colored by HR (bpm). Green = low, red = high.
Source: SELECT "Latitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'; SELECT "Longitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'

### Time in HR Zones (%) - reference plan
% time per HR zone (Garmin zones at time of recording). Target for Z2-strict easy runs: >75% Z2.
Source: SELECT 100.0 * last("hrTimeInZone_1") / (last("hrTimeInZone_1")+last("hrTimeInZo...; SELECT 100.0 * last("hrTimeInZone_2") / (last("hrTimeInZone_1")+last("hrTimeInZo...

### Time in Power Zones (%) - computed from per-second
% time per power zone computed on-the-fly from per-second ActivityGPS data. Garmin auto-FTP zones.
Source: SELECT 100.0 * count("Power") / $activity_end FROM "ActivityGPS" WHERE "Activity...; SELECT 100.0 * count("Power") / $activity_end FROM "ActivityGPS" WHERE "Activity...

### Heart Rate (bpm) with HR zone bands + prescribed target overlay
Z1-Z5 bands (auto-populated from InfluxDB HRZones). Purple band = prescribed HR target. Dashed orange staircase = avg HR per step. Y-axis auto-fits HR + target union.
Source: SELECT "HeartRate" AS "HR" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activ...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Workout steps — prescribed vs executed
One row per prescription step. TargetType=open means no HR target (e.g. tests, sprints). DurationS = prescribed duration (s). ActualDurationS = actual executed duration.
Source: SELECT "StepIndex", "IntensityType", "TargetType", "TargetLowBPM", "TargetHighBP...

### Pace (min/km) — lower = faster + avg per step
Per-second pace (mm:ss/km). Lower on Y-axis = faster. Orange staircase = avg pace per step (1000/StepAvgSpeed, fetcher filters Speed>0.5 m/s to exclude pauses).
Source: SELECT 1000.0/"Speed" AS "Pace" FROM "ActivityGPS" WHERE "ActivitySelector" = '$...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Power (W) with power zone bands + prescribed target overlay
Z1-Z5 bands (auto-populated from InfluxDB PowerZones). Purple band = prescribed power target (empty if session targets HR only). Orange staircase = avg power per step.
Source: SELECT "Power" AS "Power" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activi...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Cadence (spm) with prescribed target overlay
Healthy cadence depends on pace (170 spm at 7:00/km is OK). Purple band = target cadence (if prescribed). Orange staircase = avg cadence per step.
Source: SELECT "Cadence" * 2 AS "Cadence" FROM "ActivityGPS" WHERE "ActivitySelector" = ...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Stride Length (m) + avg per step
Per-second stride length (meters). Orange staircase = avg stride per step (StepAvgStride/1000).
Source: SELECT "Step_Length"/1000 AS "Stride" FROM "ActivityGPS" WHERE "ActivitySelector...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Vertical Ratio (%) — target <7% + avg per step
Vertical Ratio (vertical oscillation / stride length, %). <7% = good efficiency. Orange staircase = avg VR per step.
Source: SELECT "Vertical_Ratio" AS "VR" FROM "ActivityGPS" WHERE "ActivitySelector" = '$...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Vertical Oscillation (cm)
Source: SELECT "Vertical_Oscillation"/10 AS "VO" FROM "ActivityGPS" WHERE "ActivitySelec...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Ground Contact Time (ms) — target <250
Source: SELECT "Stance_Time" AS "GCT" FROM "ActivityGPS" WHERE "ActivitySelector" = '$ac...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Avg HR per lap (drift = aerobic decoupling) + altitude
Avg + max HR per lap (1 km). Altitude in light background to distinguish cardiac drift from topographic effort. X-axis = elapsed time.
Source: SELECT "Avg_HR" AS "Avg HR", "Max_HR" AS "Max HR" FROM "ActivityLap" WHERE "Acti...; SELECT "DurationSeconds" AS "Duration" FROM "ActivityGPS" WHERE "ActivitySelecto...

### Splits per lap (km)
Garmin auto-laps per km. First column 'Index' = order. Pace in mm:ss/km, Power in W, HR in bpm.
Source: SELECT "Index", "Distance" AS "Distance (m)", "Elapsed_Time" AS "Time", 1000.0/(...

## 04 Running Form & Efficiency (garvis-d-runq)

### Avg Cadence per run (target 175-185 spm)
Garmin cadence ×2 (native ActivityGPS value is half-cadence).
Source: SELECT mean("Cadence") * 2 AS "Cadence (spm)" FROM "ActivityGPS" WHERE $timeFilt...

### Vertical Ratio (form — target <7%)
Vertical oscillation / step length. Lower = less vertical bounce = better running economy.

### Ground Contact Time (ms) — target <250

### Step Length (m)
Longer stride at equivalent speed = improving. Target: 1.20-1.50 m at easy pace.
Source: SELECT mean("Step_Length") AS "Step length (m)" FROM "ActivityGPS" WHERE $timeFi...

### Avg Speed per run (m/s)
Correlate with EF: speed rising while EF stable = fitness improvement.
Source: SELECT mean("Speed") AS "Speed (m/s)" FROM "ActivityGPS" WHERE $timeFilter AND "...

### Recent Runs (last 15)
Source: SELECT "activityName", "distance", "elapsedDuration", "averageHR", "maxHR", "ele...

### HR difference per activity (Max - Avg)
Per-session HR spread. Shrinking spread may indicate reduced capacity to push (fatigue).

## 05 Hill & Trail Performance (garvis-e-hill)

### Hill Score Overall

### Strength

### Endurance

### Balance Gap (str - end)
Positive = strength dominant (hilly long runs need work). Target: balance within ±5.
Source: SELECT last("strengthScore") - last("enduranceScore") AS "gap" FROM "HillScore" ...

### D+ 30j (m)

### D+ 7j (m)

### Hill Score : Overall / Strength / Endurance

### Weekly D+ — last 12 weeks (m)
Source: SELECT sum("elevationGain") FROM "ActivitySummary" WHERE $timeFilter AND "Activi...

### D+/km per run (hill intensity)
Higher = hillier course. >50 m/km = sustained trail intensity.
Source: SELECT ("elevationGain" / ("distance" / 1000)) AS "m_per_km" FROM "ActivitySumma...

### Altitude profile — runs (7d)
Per-second altitude for all activities in the last 7 days. Each run appears as a distinct series.
Source: SELECT mean("Altitude") AS "Altitude" FROM "ActivityGPS" WHERE $timeFilter AND "...

### D+ 365j glissants (m)

### D+ YTD 2026 (m)
Source: SELECT sum("elevationGain") FROM "ActivitySummary" WHERE time >= '2026-01-01' AN...

## 06 Recovery Diagnostics (garvis-f-sleep)

### Sleep Score (last)

### Sleep duration (last)

### Overnight HRV (last)

### Avg Breathing Rate

### Awakenings

### Overnight SpO2 min

### Sleep Score 30d

### Sleep Stages (h) per night — 14d
Target: >1h30 deep + >1h30 REM. Low awake time.

### Overnight HRV + Breathing Rate (30d)

### Avg Sleep Stress (30d)
Average stress during sleep. Target: low (<25). High = poor parasympathetic recovery.

### Avg Stress Today

### High stress duration today

### Body Battery (now)

### BB drained today

### BB charged today

### Stress %

### Body Battery 14d

### Stress heatmap (hour x day)

### Stress vs Sleep Score — correlation
Rising stress + falling sleep score over several days = pre-overreaching or anxiety signal.

### Stress vs Training Load — overreaching detector
Daily stress vs training load. Both rising together + declining performance = signal to reduce load.

### Sleep Regularity (heatmap hour × day)
Bed/wake regularity over selected range. Clear horizontal bands = stable rhythm.
Source: SELECT median("level") FROM "Sleep Levels" WHERE $timeFilter GROUP BY time(1h)

### Month at a Glance — Intraday (30d)
Band wearing (watch observance) + HR zones + BB + Stress + Steps per hour.

### HR Histogram Heatmap
HR distribution over time. Light night bands (low HR) / active daytime.

### Body Battery Level Change (low/high per day)
Daily low/high BB trajectory — different from day-only stat.

### Sleep Intraday — HR + SpO2 + Overnight HRV
Overlaid nightly metrics to correlate poor sleep with desaturation or elevated HR.

### Last Sleep (piechart, last night)
Last night snapshot — complements the 14-day barchart.
Source: SELECT distinct("minutes_deep") FROM "sleep" WHERE is_main_sleep = true AND $tim...; SELECT distinct("minutes_deep") FROM "sleep" WHERE is_main_sleep = true AND $tim...

### Stress Overview stacked (30d)
Breakdown by level (low/rest/medium/uncategorized/high) over selected range.

## 07 Sport-Science Validators (garvis-k-validators)

### Z2 Pace median 30d
Median pace when HR is in Z2 (auto from InfluxDB HRZones). Faster at constant HR = improving endurance. Speed filter: 1.5-6 m/s.
Source: SELECT 1000.0 / mean("Speed") AS "pace" FROM "ActivityGPS" WHERE $timeFilter AND...

### HRV CV (14j)
HRV coefficient of variation. Stable (<10%) = good. High (>15%) = nervous system stress.
Source: SELECT 100 * stddev("avgOvernightHrv") / mean("avgOvernightHrv") AS "CV %" FROM ...

### Avg HR at High Altitude
Average HR when altitude > 200m (high portions of local hills).
Source: SELECT mean("HeartRate") AS "HR" FROM "ActivityGPS" WHERE $timeFilter AND "Activ...

### Avg Climb Rate 30d
Average vertical speed per run (m/h). Higher = more vertical work.
Source: SELECT ("elevationGain" / "elapsedDuration") * 3600 AS "m/h" FROM "ActivitySumma...

### Avg Decoupling %
EF drift: (1st half - 2nd half) / 1st half × 100. <5% = solid base, >8% = started too fast.
Source: SELECT median("RunningEfficiency") AS "ef_first" FROM "ActivityGPS" WHERE $timeF...; SELECT median("RunningEfficiency") AS "ef_after" FROM "ActivityGPS" WHERE $timeF...

### Aerobic Decoupling — EF 1st vs 2nd half per run
Median EF over the first 30 min vs 30-90 min. If 2nd half drops = endurance not yet solid. Target: gap < 5%.
Source: SELECT median("RunningEfficiency") AS "EF 1st half (0-30min)" FROM "ActivityGPS"...; SELECT median("RunningEfficiency") AS "EF 2nd half (30-90min)" FROM "ActivityGPS...

### Pace Z2 + Volume Z2 — weekly Mon→Sun (side-by-side bars)
Weekly bucket Mon-Sun (Europe/Paris TZ, current week included). Purple bar = mean Z2 pace weighted per-second (left axis, lower = faster). Grey bar = Z2 volume in minutes (right axis, pace reliability). Speed filter 1.5-6 m/s excludes walking/GPS spikes. Volume benchmarks: <30 min/wk = noisy (ignore pace), 30-60 = decent, >60 = robust.
Source: SELECT 1000.0 / mean("Speed") AS "Z2 Pace weekly (weighted)" FROM "ActivityGPS" ...; SELECT count("HeartRate") / 60.0 AS "Z2 Volume (min)" FROM "ActivityGPS" WHERE $...

### Pace Z4+Z5 + Volume Z4+Z5 — weekly Mon→Sun (side-by-side bars)
Weekly bucket Mon-Sun (Europe/Paris TZ, current week included). Red bar = mean Z4+Z5 pace (HR >= 166) weighted per-second (left axis, lower = faster). Grey bar = Z4+Z5 volume in minutes (right axis, pace reliability). Speed filter 1.5-7 m/s. Tracks VO2max/threshold progression.
Source: SELECT 1000.0 / mean("Speed") AS "Z4+Z5 Pace weekly (weighted)" FROM "ActivityGP...; SELECT count("HeartRate") / 60.0 AS "Z4+Z5 Volume (min)" FROM "ActivityGPS" WHER...

### Overnight HRV (ms) + CV% (stability)
Raw overnight HRV in blue (left). CV% in red (right) = stddev/mean. Low CV = stable nervous system.
Source: SELECT 100 * stddev("avgOvernightHrv") / mean("avgOvernightHrv") AS "HRV CV %" F...

### Climb Rate per run (m/h)
elevationGain / duration × 3600. Average vertical intensity per run.
Source: SELECT ("elevationGain" / "elapsedDuration") * 3600 AS "Climb rate (m/h)" FROM "...

### HR vs Pace aggregate (Z2, window)
Z2 points only (HR 130-150 bpm). Speed (km/h) left axis, HR right axis. Speed rising at constant HR = improving aerobic base.
Source: SELECT mean("Speed")*3.6 AS "Speed Z2 (km/h)" FROM "ActivityGPS" WHERE "Activity...; SELECT mean("HeartRate") AS "HR Z2 (bpm)" FROM "ActivityGPS" WHERE "ActivitySele...

### Running Power Curve — best mean power by duration (90d)
Best sustained mean power per duration over the last 90 days. Shape reflects energy system balance. 20-60 min plateau = Critical Power.
Source: SELECT max("Power") FROM "ActivityGPS" WHERE time > now() - 90d AND "ActivitySel...; SELECT max(mp) FROM (SELECT moving_average("Power", 5)    AS mp FROM "ActivityGP...

### Critical Pace Curve — best mean speed by duration (90d)
Best sustained mean speed per duration. 20-60 min plateau = Critical Pace (FTPace).
Source: SELECT max("Speed") * 3.6 FROM "ActivityGPS" WHERE time > now() - 90d AND "Activ...; SELECT max(ms) * 3.6 FROM (SELECT moving_average("Speed", 5)    AS ms FROM "Acti...

### Pace @ fixed HR — 7 bins (120→180 ±5 bpm) — flat runs (D+/km < 25)
Cardiac efficiency progression — pace at fixed HR.

Each run binned by avg HR into 7 bands (120-180 ±5 bpm), plotting avg pace per bin. Descending trend = faster at same cardiac effort = aerobic adaptation.
Source: SELECT 1000 / "averageSpeed" AS "FC 120" FROM "ActivitySummary" WHERE $timeFilte...; SELECT 1000 / "averageSpeed" AS "FC 130" FROM "ActivitySummary" WHERE $timeFilte...

## 08 Long-Term Trends (garvis-c-fitness)

### VO2max Running

### Endurance Score

### Hill Score (overall)
Numeric rating of your ability to run uphill, based on VO2 Max and training history.

Tiers: Recreational (1-24) | Challenger (25-49) | Trained (50-69) | Skilled (70-84) | Expert (85-94) | Elite (95-100).

### Fitness Age

### Current Weight
Source: SELECT last("weight") / 1000 AS "kg" FROM "BodyComposition" WHERE $timeFilter

### HRmax (Running)
Max HR used by Garmin for running zone calculation. Recalibrated after max HR test.
Source: SELECT last("maxHeartRate") FROM "HRZones" WHERE "sport"='RUNNING' AND $timeFilt...

### LTHR (Running)
Lactate Threshold HR used by Garmin. Recalibrated after 30-min threshold test or auto-detection during efforts.
Source: SELECT last("lactateThresholdHeartRate") FROM "HRZones" WHERE "sport"='RUNNING' ...

### Resting HR
Resting HR used to compute HRR (Heart Rate Reserve). Auto-updated by Garmin (sleep average).
Source: SELECT last("restingHeartRate") FROM "HRZones" WHERE "sport"='RUNNING' AND $time...

### FTP Power (Running)
Functional Threshold Power (running). Auto-FTP computed by the watch from efforts.
Source: SELECT last("functionalThresholdPower") FROM "PowerZones" WHERE "sport"='RUNNING...

### Delta vs 30d
Change from ~30 days ago.
Source: SELECT (last("weight") - first("weight")) / 1000 AS "delta" FROM "BodyCompositio...

### VO2max
VO2max running, ranked by percentile tiers:
Iron <28 (bottom 3%) | Bronze 28-37 (3-20%) | Silver 37-42 (20-42%) | Gold 42-47 (42-67%) | Platinum 47-53 (67-85%) | Emerald 53-60 (85-95%) | Diamond 60-68 (95-99.2%) | Master 68-75 (99.2-99.9%) | Grandmaster 75-80 (99.9-99.98%) | Challenger >=80 (top 0.02%).

### Endurance Score (Weekly)

### Hill Score — Overall
Numeric rating of your ability to run uphill, based on VO2 Max and training history.

Tiers: Recreational (1-24) | Challenger (25-49) | Trained (50-69) | Skilled (70-84) | Expert (85-94) | Elite (95-100).

### Hill Score — Strength
Hill Strength measures your ability to maintain running power on hills. Based on higher-intensity hill efforts.

### Hill Score — Endurance
Hill Endurance measures how well you can sustain pace and performance when running uphill. Based on elevation gain and time spent on hills with low intensity.

### Race Prediction — 5K
Garmin Race Prediction 5K. Tiers based on Daniels VDOT table.
Source: SELECT mean("time5K") / 5 AS "Pace /km" FROM "RacePredictions" WHERE $timeFilter...

### Race Prediction — 10K
Garmin Race Prediction 10K. Tiers based on Daniels VDOT table.
Source: SELECT mean("time10K") / 10 AS "Pace /km" FROM "RacePredictions" WHERE $timeFilt...

### Race Prediction — Half Marathon
Garmin Race Prediction Half Marathon. Tiers based on Daniels VDOT table.
Source: SELECT mean("timeHalfMarathon") / 21.0975 AS "Pace /km" FROM "RacePredictions" W...

### Race Prediction — Full Marathon
Garmin Race Prediction Marathon. Tiers based on Daniels VDOT table.
Source: SELECT mean("timeMarathon") / 42.195 AS "Pace /km" FROM "RacePredictions" WHERE ...

### HR Zone Boundaries — Trajectory
Z1-Z5 floor + LTHR + HRmax evolution over time. Zone recalibrations by Garmin appear as steps.
Source: SELECT last("zone1Floor") AS "Z1", last("zone2Floor") AS "Z2", last("zone3Floor"...

### Power Zone Boundaries — Trajectory
Z1-Z5 floor + FTP evolution. Garmin auto-FTP drives zone scale. Good plan progression = FTP rising over time.
Source: SELECT last("zone1Floor") AS "Z1", last("zone2Floor") AS "Z2", last("zone3Floor"...

### LTHR as % of HRmax
LTHR as % of HRmax over time. Key marker of lactate threshold fitness.

DASHED LINES (population benchmarks)
Source: SELECT mean("pct_fcmax") AS "% HRmax" FROM "ThresholdComputed" WHERE $timeFilter...; SELECT mean("lthr_bpm") AS "LTHR (bpm)" FROM "ThresholdComputed" WHERE $timeFilt...

### Weight 3m
Source: SELECT mean("weight") / 1000 AS "kg" FROM "BodyComposition" WHERE $timeFilter GR...

### Cardiac Efficiency (Power/HR) — 14d avg
Ratio mean(Power) / mean(HR) per day (running, Power>100W and HR>130bpm to exclude warmup/cooldown). Rising ratio = more watts per bpm. Ascending trend over 90d = successful aerobic adaptation.
Source: SELECT mean("Power") / mean("HeartRate") AS "W/bpm" FROM "ActivityGPS" WHERE $ti...

### Eddington — Running (Lifetime)
Eddington number: how many runs of >= N km for each N.

Blue bars = count of runs >= N km. Grey dashed line = y=x threshold. The Eddington E = last bar exceeding the diagonal. At N=E+1, the gap between diagonal and bar = runs needed to level up.
Source: SELECT "distance" FROM "ActivitySummary" WHERE "ActivitySelector" =~ /running/ A...

### Heat Acclimation
Heat acclimation percentage from Garmin. >75% = well acclimated. Seasonal pattern expected.

### Altitude Acclimation
Altitude acclimation from Garmin. Shows the altitude (in meters) you are fully adapted to. Tracking activates above 800m. Range: 800-4000m.

### Efficiency Factor (GAP/HR) — 7d avg
TrainingPeaks canonical Efficiency Factor: mean(GradeAdjustedSpeed) / mean(HR) x 100.

METHOD
Source: SELECT mean("GradeAdjustedSpeed") * 100.0 / mean("HeartRate") AS "EF" FROM "Acti...; SELECT moving_average("EF", 7) AS "EF_ma7" FROM (SELECT mean("GradeAdjustedSpeed...

## 10 Calendar - Training Load 1 Year (garvis-n-calendar)

### Training Load Calendar — last 12 months (running)
Color = daily activityTrainingLoad (green <60, yellow 60-120, orange 120-200, red >200).
Source: SELECT sum("activityTrainingLoad") AS tl, sum("distance")/1000 AS km FROM "Activ...
