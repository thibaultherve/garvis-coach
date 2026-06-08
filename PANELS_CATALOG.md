# Panels catalog — Garvis Coach dashboards

> **3 dashboards** (reorg 2026-06-07). Auto-généré depuis les JSON canoniques de `dashboards/`. Chaque entrée = titre du panel + description + 1ʳᵉ(s) requête(s) source. Avant toute analyse/bilan, lire la section du dashboard concerné.
> Les lignes **▸ …** sont des séparateurs de section (panneaux `row`), pas des données.

---

## Training Load & Terrain (`garvis-b-load`)

*Pilotage de la charge d'entrainement (ACWR, polarisation, CTL/ATL/TSB, monotonie/strain, volume, training status, HRV, acclimatation chaleur) + charge verticale & terrain (ACWR vertical D+, budget D+ vs plafond ~830 m, D+/km, VAM, cout terrain, cumul denivele). Prevention de la surcharge globale ET verticale. Inclut l'ex-« Hill & Trail ».*

`02-training-load-acwr.json` — 26 panneaux + 4 sections (rows)

### Training Status Timeline — 180d
Garmin training status bands (Productive / Peaking / Maintaining / Recovery / Strained / Unproductive / Detraining / Overreaching). Garmin enum suffix _N indicates duration in state — grouped by main category here.
_Source:_ `SELECT "trainingStatusFeedbackPhrase" AS Status FROM "TrainingStatus" WHERE $timeFilter`

### Load Focus History — 180d
Garmin trainingBalanceFeedbackPhrase: BALANCED (ideal) / AEROBIC_LOW_FOCUS (base focus = OK for Seiler polarized plan) / AEROBIC_LOW/HIGH_SHORTAGE / ANAEROBIC_SHORTAGE/FOCUS. Garmin _N suffixes stripped via regex.
_Source:_ `SELECT "trainingBalanceFeedbackPhrase" AS "Load Focus" FROM "TrainingStatus" WHERE $timeFilter`

### Training Status
Raw Garmin phrase (e.g. PRODUCTIVE_1, MAINTAINING_2, RECOVERY_2). Numeric trainingStatus code not used (mapping uncertain across firmware).

### Load Focus
Official Garmin source (trainingBalanceFeedbackPhrase). Requires extended fetcher patch.
_Source:_ `SELECT last("trainingBalanceFeedbackPhrase") AS "shortage" FROM "TrainingStatus" WHERE $timeFilter`

### Acute Training Load (ACWR)

### Acute vs Chronic Load + Garmin Targets

### Load Focus 28d — vs Optimal Range
Bands: blue = shortage (below target_min), green = optimal range, red = overload (above target_max). Thresholds calibrated on current Garmin target_min/max (recalibrate if Garmin adjusts).
_Source:_ `SELECT last("monthlyLoadAnaerobic") AS "Anaerobic", last("monthlyLoadAerobicHigh") AS "High Aerobic", last("monthlyLoadAerobicLow") AS "Low ...`

### Polarization 80/10/10 — Weekly (12 wk)
Weekly % time in HR zones (Mon-Sun, Europe/Paris TZ). Garmin colors: Z1+Z2 blue (target >= 80%), Z3 green (target 10%), Z4+Z5 red (target <= 10%). Rolling 12 weeks including current week.
_Source:_ `SELECT sum("hrTimeInZone_1") + sum("hrTimeInZone_2") AS "Z1+Z2 (cible 80%)", sum("hrTimeInZone_3") AS "Z3 (cible 10%)", sum("hrTimeInZone_4"...`

### Training Intensity (Aerobic + Anaerobic + Load + Endurance)
Daily summary: aerobic/anaerobic TE + acute/chronic load + endurance score.

### Weekly Volume (Mon-Sun)
_Source:_ `SELECT sum("distance") FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySelector" =~ /running/ GROUP BY time(7d, 4d) fill(0); SELECT sum("elapsedDuration") FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySelector" =~ /running/ GROUP BY time(7d, 4d) fill(0)`

### Foster Monotony & Strain (7d Rolling)
Foster Monotony & Strain (Foster et al., J Strength Cond Res 2001).

Monotony = mean(daily_load_7d) / stddev(daily_load_7d). High monotony (>2.0) = increased illness/staleness risk. Strain = weekly_load × Monotony.

Source: activityTrainingLoad summed daily, running only, rest days = 0. Variance via identity Var(X) = E[X²] - E[X]². Strain = (mean_7d × 7) × Monotony.

Monotony thresholds: <1.5 green (varied), 1.5-2.0 yellow (caution), >2.0 red (risk). Strain: no absolute threshold — watch for >50% spikes above 4-week baseline.
_Source:_ `SELECT moving_average(daily_tl, 7) / sqrt(moving_average(daily_tl_sq, 7) - moving_average(daily_tl, 7) * moving_average(daily_tl, 7)) AS "Mo...; SELECT (moving_average(daily_tl, 7) * 7) * (moving_average(daily_tl, 7) / sqrt(moving_average(daily_tl_sq, 7) - moving_average(daily_tl, 7) ...`

### PMC — Fitness (CTL 42d) / Fatigue (ATL 7d) / Form (TSB)
Rolling mean approximation of TrainingPeaks EWMA. CTL = 6-week aerobic fitness. ATL = 7-day fatigue. TSB = CTL - ATL: negative = overload, positive = peak form. Competition sweet spot: TSB +5 to +15.
_Source:_ `SELECT moving_average(daily_tl, 42) AS "CTL (fitness 42j)", moving_average(daily_tl, 7) AS "ATL (fatigue 7j)" FROM (SELECT sum("activityTrai...; SELECT moving_average(daily_tl, 42) - moving_average(daily_tl, 7) AS "TSB (form)" FROM (SELECT sum("activityTrainingLoad") AS daily_tl FROM ...`

### HRV Status (7-day avg + baseline)
Replicates Garmin Connect HRV Status graph. Grey band = personal baseline. Colored markers by status: green = Balanced, orange = Unbalanced, red = Low.
_Source:_ `SELECT mean("weeklyAvg") AS "Balanced" FROM "HRVStatus" WHERE "status" = 'BALANCED' AND $timeFilter GROUP BY time(1d) fill(null); SELECT mean("weeklyAvg") AS "Unbalanced" FROM "HRVStatus" WHERE "status" = 'UNBALANCED' AND $timeFilter GROUP BY time(1d) fill(null)` (+1 more)

### Heat Trend
Current heat acclimation trend from Garmin.

### Heat Acclimation (historique)
Garmin heat acclimation %. Increases with training in hot conditions. >75% = well acclimated. Seasonal pattern expected.

### Heat Acclimation
Garmin heat acclimation %. >75 = well adapted.

**▸ Dénivelé, charge verticale & terrain**

**▸ ① Garde-fou charge verticale — prévention surcharge**

### ACWR vertical — D+ aigu:chronique (le garde-fou surcharge)
Ratio de charge verticale : moyenne glissante 7j du D+ quotidien / moyenne glissante 28j (fenêtres ACWR de Gabbett, appliquées au D+ — le facteur de charge verticale documenté, pas à la charge globale de ce dashboard).
Zone douce 0,80–1,30 (vert) · 1,30–1,50 prudence (ambre) · >1,50 surcharge verticale (rouge).
Aujourd'hui ~0,93. La semaine de surcharge (17/05) a culminé à 1,50. fill(0) = les jours de repos comptent 0 D+.
_Source:_ `SELECT moving_average(d,7)/moving_average(d,28) AS "ACWR D+" FROM (SELECT sum("elevationGain") AS d FROM "ActivitySummary" WHERE "activityTy...`

### ACWR vertical — maintenant
Valeur actuelle de l'ACWR vertical (mêmes bandes Gabbett que la courbe). Vert = montée en charge maîtrisée.
_Source:_ `SELECT moving_average(d,7)/moving_average(d,28) AS acwr FROM (SELECT sum("elevationGain") AS d FROM "ActivitySummary" WHERE "activityType"='...`

### D+ / D- hebdomadaire + charge chronique — vs plafond perso
D+ (barres, colorées par seuil) et D- (ligne bleue, miroir excentrique) par semaine. Rouge uniquement >800 m (ton plafond observé ~830). Ligne grise pointillée = D+ chronique (moyenne 4 semaines). Les semaines de surcharge (700 / 766 m) ressortent en ambre.
_Source:_ `SELECT sum("elevationGain") AS "D+", sum("elevationLoss") AS "D-" FROM "ActivitySummary" WHERE "activityType"='running' AND "distance">1000 ...; SELECT moving_average(w,4) AS "D+ chronique (4 sem)" FROM (SELECT sum("elevationGain") AS w FROM "ActivitySummary" WHERE "activityType"='run...`

### Budget vertical 4 sem. vs plafond
Moyenne glissante 4 semaines du D+ hebdo vs ton plafond observé (~830 m). Traduit l'ACWR abstrait en 'où j'en suis vs ma ligne rouge perso'. Actuellement ~481 m (58%).
_Source:_ `SELECT moving_average(wk,4) AS "Budget 4 sem" FROM (SELECT sum("elevationGain") AS wk FROM "ActivitySummary" WHERE "activityType"='running' ...`

**▸ ② Caractère du terrain — par sortie dans le temps**

### Intensité de grimpe par sortie — D+/km (bandes locales)
Intensité de grimpe par sortie, calibrée terrain local : <8 plat / 8–15 vallonné (ton pain quotidien) / 15–22 costaud / >22 raide (rare, ~5 sorties/150j). Rouge réservé aux vraies sorties dures locales (fini le seuil alpin >50 absurde de l'ancien dashboard).
_Source:_ `SELECT ("elevationGain"/("distance"/1000)) AS "D+/km" FROM "ActivitySummary" WHERE "activityType"='running' AND "distance">1000 AND $timeFil...`

### Vitesse verticale (VAM, m/h) par sortie
Travail vertical : mètres grimpés par heure de course, par sortie. Tendance = est-ce que je grimpe plus vite. Orthogonal à l'Efficiency Factor GAP/FC (« Fitness Trends & Validation ») : ici aucune FC, juste du dénivelé/temps.
Honnête : VAM moyenne sur TOUTE la sortie (dilue plat/descente), pas la VAM en montée seule — ça viendra avec le sidecar ClimbMetrics.
_Source:_ `SELECT ("elevationGain"/("movingDuration"/3600)) AS "VAM" FROM "ActivitySummary" WHERE "activityType"='running' AND "distance">1000 AND $tim...`

### La montagne grimpée — D+ cumulé 2026
D+ course à pied cumulé depuis le 1er janvier (YTD = 9 833 m). Ancré au 1er janvier — ignore le sélecteur de temps, par définition. Ligne grise = total glissant 365j (12 659 m), l'horizon à atteindre. La pente de la courbe = ta charge verticale ; les plats = déloads.
_Source:_ `SELECT cumulative_sum(wk) AS "Cumul D+ 2026" FROM (SELECT sum("elevationGain") AS wk FROM "ActivitySummary" WHERE "activityType"='running' A...`

### Coût du terrain par sortie — GAP vs allure brute (%)
Combien le relief ralentit l'allure : (GAP − allure brute) / allure brute × 100, par sortie. Aucune FC — c'est une taxe topographique, ≠ l'Efficiency Factor GAP/FC de « Fitness Trends & Validation ».
Honnête : moyenne sur la sortie → mesure une dérive d'économie même-terrain, pas le coût pur de la montée (grade-split = sidecar).
_Source:_ `SELECT (mean("GradeAdjustedSpeed")-mean("Speed"))/mean("Speed")*100 AS "Coût terrain %" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySe...`

### Sorties récentes — détail terrain
Une ligne par sortie sur la fenêtre sélectionnée. D+/km coloré sur les mêmes bandes locales que le graphe. Triable.
_Source:_ `SELECT "activityName" AS "Sortie", ("distance"/1000) AS "km", "elevationGain" AS "D+", "elevationLoss" AS "D-", ("elevationGain"/("distance"...`

**▸ ③ Lecture & feuille de route**

### (panel id 157, text)
_(panneau texte / guide de lecture)_

---

## Activity Drill-Down (`garvis-j-activity`)

*Drill-down par activite course a pied. Cliquer un lien dans le tableau du haut pour zoomer sur une activite (set time range + variable). Le panel markdown en bas liste les prescriptions de toutes les seances.*

`03-activity-drill-down.json` — 20 panneaux

### Carte — type de surface
Trace GPS colorée par surface OSM (map-matching Valhalla). Bleu-gris=asphalte, tan=compacté, brun=terre, olive=sentier.
_Source:_ `SELECT "Latitude" FROM "ActivityTrack" WHERE "ActivitySelector" = '$activity'; SELECT "Longitude" FROM "ActivityTrack" WHERE "ActivitySelector" = '$activity'` (+2 more)

### Time in HR Zones (%) - reference plan
% time per HR zone (Garmin zones at time of recording). Target for Z2-strict easy runs: >75% Z2.
_Source:_ `SELECT 100.0 * last("hrTimeInZone_1") / (last("hrTimeInZone_1")+last("hrTimeInZone_2")+last("hrTimeInZone_3")+last("hrTimeInZone_4")+last("h...; SELECT 100.0 * last("hrTimeInZone_2") / (last("hrTimeInZone_1")+last("hrTimeInZone_2")+last("hrTimeInZone_3")+last("hrTimeInZone_4")+last("h...` (+3 more)

### Time in Power Zones (%) - computed from per-second
% time per power zone computed on-the-fly from per-second ActivityGPS data. Garmin auto-FTP zones.
_Source:_ `SELECT 100.0 * count("Power") / $activity_end FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Power" >= $z1_pwr AND "Power" <...; SELECT 100.0 * count("Power") / $activity_end FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Power" >= $z2_pwr AND "Power" <...` (+3 more)

### Heart Rate (bpm) — zones + cible prescrite
FC par seconde (lissée) vs durée. Bandes Z1-Z5. Bande violette = cible FC prescrite, pointillé violet = cible médiane, pointillé orange = moy/step.
_Source:_ `SELECT "HeartRate" AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "HeartRate" > 60 AND "DurationSeconds" <= $activity_...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+5 more)

### Structure de la séance — chaque rep + counts
Segmente la séance par step exécuté (changement de FC moyenne par seconde dans WorkoutTarget). Chaque segment = un rep/bloc, coloré par zone FC. Le titre résume la structure avec le nombre de répétitions détecté (ex. 10×(1:00/2:00)). NB : Garmin n'exporte pas le compteur de reps → il est déduit du motif des cibles.
_Source:_ `SELECT "DurationSeconds","StepAvgHR","TargetLowBPM","TargetHighBPM" FROM "WorkoutTarget" WHERE "ActivitySelector" = '$activity' ORDER BY tim...; SELECT "StepStartOffsetS","Notes","IntensityType" FROM "WorkoutStep" WHERE "ActivitySelector" = '$activity' ORDER BY time ASC` (+1 more)

### Pace (min/km) + moy/step
Allure par seconde (mm:ss/km). Plus bas = plus rapide. Pointillé orange = allure moy/step.
_Source:_ `SELECT 1000.0/"Speed" AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Speed" > 0.5 AND "DurationSeconds" <= $activity_...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+1 more)

### Power (W) — zones + cible prescrite
Puissance par seconde (lissée) vs durée. Bandes Z1-Z5 puissance. Bande violette = cible puissance prescrite, pointillé orange = moy/step.
_Source:_ `SELECT "Power" AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Power" > 0 AND "DurationSeconds" <= $activity_end; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+5 more)

### Cadence (spm) + cible prescrite
Cadence par seconde (×2) vs durée. Bande verte = cadence cible 170-190. Bande violette = cible prescrite, pointillé orange = moy/step.
_Source:_ `SELECT "Cadence" * 2 AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Cadence" > 30 AND "DurationSeconds" <= $activity_...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+4 more)

### Stride Length (m) + moy/step
Longueur de foulée par seconde (m). Pointillé orange = moy/step.
_Source:_ `SELECT "Step_Length"/1000 AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Step_Length" > 0 AND "DurationSeconds" <= $a...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+1 more)

### Vertical Ratio (%) — cible <7%
Vertical Ratio par seconde (%). Vert <7% = bonne efficacité. Pointillé orange = moy/step.
_Source:_ `SELECT "Vertical_Ratio" AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Vertical_Ratio" > 0 AND "DurationSeconds" <= $...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'` (+1 more)

### Vertical Oscillation (cm)
Oscillation verticale par seconde (cm).
_Source:_ `SELECT "Vertical_Oscillation"/10 AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Vertical_Oscillation" > 0 AND "Durati...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'`

### Ground Contact Time (ms) — cible <250
Temps de contact au sol par seconde (ms). Vert <260 = bon.
_Source:_ `SELECT "Stance_Time" AS "v" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Stance_Time" > 0 AND "DurationSeconds" <= $activi...; SELECT "DurationSeconds" AS "d" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity'`

### FC par lap — dérive (efficacité GAP/FC) + altitude
FC moyenne par lap, colorée par EFFICACITÉ (allure GAP / FC, vs la moyenne des premiers laps frais) : vert = efficace, rouge = dérive cardiaque réelle. La GAP neutralise la pente, donc une lap rouge = vraie dérive (fatigue/chaleur), PAS une côte. Altitude en fond. Découplage Pa:HR global (hors 10 min, 1re vs 2e moitié) chiffré en haut à droite — seuils Friel <5/5-7/>7 %.
_Source:_ `SELECT "Avg_HR" AS "lhr","Max_HR" AS "lmax","Ascent" AS "lasc","Descent" AS "ldesc","Distance" AS "ldist","Elapsed_Time" AS "lela" FROM "Act...; SELECT "DurationSeconds" AS "gdur","HeartRate" AS "ghr","GradeAdjustedSpeed" AS "ggap","Altitude" AS "galt" FROM "ActivityGPS" WHERE "Activi...` (+1 more)

### Splits par km
GROUNDED on ActivityGPS (selector 20260522T083908UTC verified): Distance=cumulative meters, DurationSeconds=1Hz seconds, Altitude>0 filter, HeartRate=bpm. Pace derived from time/distance (Report B), never from Speed. Per-km algorithm exactly matches Report B (d>=lo && d<hi contig
_Source:_ `SELECT "Distance" AS "d","DurationSeconds" AS "t","Altitude" AS "alt","HeartRate" AS "hr" FROM "ActivityGPS" WHERE "ActivitySelector"='$acti...`

### Conditions météo
Conditions météo de la sortie (Open-Meteo) : température, ressenti, WBGT, humidité, vent/rafales, nuages, pression.
_Source:_ `SELECT "temperature_c" AS "TempStart", "mid_temperature_c" AS "TempMid", "end_temperature_c" AS "TempEnd", "wbgt_estimated" AS "WBGT", "humi...`

### Profil d'élévation — coloré par pente
Altitude vs distance (ActivityGPS), ligne+aire colorées par la pente (bleu descente → vert plat → rouge montée). Tooltip Après/Élévation/Pente. Surface + Type de voie ajoutés via visualMap quand ActivitySurface (Valhalla) sera peuplé.
_Source:_ `SELECT "Distance" AS "distance", "Altitude" AS "altitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Altitude" > 0; SELECT "surface","waytype","start_m","end_m" FROM "ActivitySurface" WHERE "ActivitySelector" = '$activity' ORDER BY time`

### Workout Analysis
Workout Analysis par step : barres horizontales colorees par type (Echauffement/Rep/Recup/Repos/Retour calme), longueur proportionnelle a la vitesse, allure+FC par step.
_Source:_ `SELECT "Index" AS "lapidx","Intensity" AS "intensity","Distance" AS "dist","Elapsed_Time" AS "secs","Avg_HR" AS "hr","Ascent" AS "asc","Desc...`

### Répartition surfaces & types de chemin
Répartition par surface et par type de voie (ActivitySurface / Valhalla).
_Source:_ `SELECT "surface","waytype","length_m" FROM "ActivitySurface" WHERE "ActivitySelector" = '$activity'`

### Profil d'élévation — coloré par surface
Même profil, bandes colorées par surface OSM (Asphalte/Compacté/Terre/Sentier…). Tooltip surface + type de voie + pente.
_Source:_ `SELECT "Distance" AS "distance","Altitude" AS "altitude" FROM "ActivityGPS" WHERE "ActivitySelector" = '$activity' AND "Altitude" > 0; SELECT "surface","waytype","start_m","end_m" FROM "ActivitySurface" WHERE "ActivitySelector" = '$activity' ORDER BY time`

### Résumé de l'activité — KPI
KPI de l'activité sélectionnée (1 panel) : distance, durée, FC moy/max, allure, calories, D+/D−, TE aérobie/anaérobie, charge, VO2max. Cartes ECharts, couleur par seuil pour FC et TE.
_Source:_ `SELECT last("distance")/1000 AS "v" FROM "ActivitySummary" WHERE "ActivitySelector" = '$activity'; SELECT last("elapsedDuration") AS "v" FROM "ActivitySummary" WHERE "ActivitySelector" = '$activity'` (+10 more)

---

## Fitness Trends & Validation (`garvis-c-fitness`)

*Trajectoires long-terme (VO2max, race predictions, fitness age, Hill & Endurance Score, recalibration des zones FCmax/LTHR/FTP, poids, Eddington, EF GAP/HR, acclimatation chaleur/altitude) + validateurs sport-science (aerobic decoupling, allure & volume Z2 et Z4-Z5, power/pace curves, allure a FC fixee, impact chaleur EF/WBGT). Review mensuel / fin de cycle : le plan produit-il des adaptations mesurables. Inclut l'ex-« Sport-Science Validators ».*

`08-long-term-trends.json` — 29 panneaux + 1 sections (rows)

### VO2max
VO2max running, age-graded fitness categories (Cooper Institute norms, males 20-29):
Poor to Very Poor <41.7 | Fair 41.7-45.4 | Good 45.4-51.1 | Excellent 51.1-55.4 | Superior >=55.4 (ml/kg/min). Bandes de couleur = catégorie selon la valeur.
_Source:_ `SELECT last("VO2_max_value") AS "val" FROM "VO2_Max" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Endurance Score (Weekly)
Endurance Score (Garmin), tendance hebdomadaire. Paliers : Recreational <5100 | Intermediate 5100 | Trained 5800 | Well-trained 6600 | Expert 7300 | Superior 8100 | Elite 8800. Bandes de couleur = palier selon la valeur.
_Source:_ `SELECT last("EnduranceScore") AS "val" FROM "EnduranceScore" WHERE $timeFilter GROUP BY time(7d) fill(null)`

### Hill Score — Overall
Numeric rating of your ability to run uphill, based on VO2 Max and training history.

Tiers: Recreational (1-24) | Challenger (25-49) | Trained (50-69) | Skilled (70-84) | Expert (85-94) | Elite (95-100).

Factors: Hill Endurance (sustain pace uphill, elevation gain + time on hills at low intensity), Hill Strength (maintain running power on hills, higher-intensity efforts), VO2 Max (peak oxygen consumption, predictor of uphill ability).
_Source:_ `SELECT last("overallScore") AS "val" FROM "HillScore" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Hill Score — Strength
Hill Strength measures your ability to maintain running power on hills. Based on higher-intensity hill efforts.
_Source:_ `SELECT last("strengthScore") AS "val" FROM "HillScore" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Hill Score — Endurance
Hill Endurance measures how well you can sustain pace and performance when running uphill. Based on elevation gain and time spent on hills with low intensity.
_Source:_ `SELECT last("enduranceScore") AS "val" FROM "HillScore" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Race Prediction — 5K
Garmin Race Prediction 5K. Paliers VDOT (Daniels) en bandes de couleur — la couleur change selon le temps prévu.
_Source:_ `SELECT mean("time5K") AS "secs" FROM "RacePredictions" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Race Prediction — 10K
Garmin Race Prediction 10K. Paliers VDOT (Daniels) en bandes de couleur — la couleur change selon le temps prévu.
_Source:_ `SELECT mean("time10K") AS "secs" FROM "RacePredictions" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Race Prediction — Half Marathon
Garmin Race Prediction Half Marathon. Paliers VDOT (Daniels) en bandes de couleur — la couleur change selon le temps prévu.
_Source:_ `SELECT mean("timeHalfMarathon") AS "secs" FROM "RacePredictions" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Race Prediction — Full Marathon
Garmin Race Prediction Marathon. Paliers VDOT (Daniels) en bandes de couleur — la couleur change selon le temps prévu.
_Source:_ `SELECT mean("timeMarathon") AS "secs" FROM "RacePredictions" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### HR Zone Boundaries — Trajectory
Z1-Z5 HR floor evolution over time. Zone recalibrations by Garmin appear as steps. LTHR & FCmax ont leurs panneaux dedies (section Seuil).
_Source:_ `SELECT last("zone1Floor") AS "Z1", last("zone2Floor") AS "Z2", last("zone3Floor") AS "Z3", last("zone4Floor") AS "Z4", last("zone5Floor") AS...`

### Power Zone Boundaries — Trajectory
Z1-Z5 power floor evolution. Garmin auto-FTP drives zone scale; a hausse des floors = progression. (FTP retiree de l'overlay — visible via le stat FTP en haut.)
_Source:_ `SELECT last("zone1Floor") AS "Z1", last("zone2Floor") AS "Z2", last("zone3Floor") AS "Z3", last("zone4Floor") AS "Z4", last("zone5Floor") AS...`

### Seuil — FC (LTHR & FCmax)
Fréquences cardiaques liées au seuil lactique — source live HRZones (recalibrée chaque jour par Garmin).
• LTHR : FC au seuil (stable)
• FCmax : FC maximale (paliers dans le temps)
L'écart LTHR↔FCmax = réserve au-dessus du seuil.
_Source:_ `SELECT last("lactateThresholdHeartRate") AS "LTHR", last("maxHeartRate") AS "FCmax" FROM "HRZones" WHERE $timeFilter AND "sport" =~ /RUNNING...`

### Seuil — LTHR / FCmax (%)
LTHR exprimée en % de la FCmax — marqueur de forme au seuil (~88-92 % = bien entraîné ; ligne verte = repère 90 %).
⚠️ Une baisse du % peut venir d'une FCmax révisée à la hausse, pas d'une perte de forme.
_Source:_ `SELECT last("lactateThresholdHeartRate") / last("maxHeartRate") * 100 AS "% FCmax" FROM "HRZones" WHERE $timeFilter AND "sport" =~ /RUNNING/...`

### Seuil — Allure (min/km)
Allure au seuil lactique — source live LactateThreshold (détection Garmin, 100 / SpeedThreshold_RUNNING = sec/km).
Plus bas = plus rapide. Mise à jour quand Garmin détecte un nouveau seuil.
_Source:_ `SELECT 100 / last("SpeedThreshold_RUNNING") AS "Allure seuil" FROM "LactateThreshold" WHERE $timeFilter GROUP BY time(1d) fill(previous) tz(...`

### Weight 3m
_Source:_ `SELECT mean("weight") / 1000 AS "kg" FROM "BodyComposition" WHERE $timeFilter GROUP BY time(1d) fill(null)`

### Cardiac Efficiency (Power/HR) — 14d avg
Ratio mean(Power) / mean(HR) per day (running, Power>100W and HR>130bpm to exclude warmup/cooldown). Rising ratio = more watts per bpm. Ascending trend over 90d = successful aerobic adaptation.
_Source:_ `SELECT mean("Power") / mean("HeartRate") AS "val" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "Power" > 100...`

### Eddington — Running (Lifetime)
Nombre d'Eddington (course, lifetime) : pour chaque N, nombre de sorties >= N km. Barre verte = E (plus grand N tel que sorties>=N soit >= N), calcule dynamiquement. Diagonale pointillee = y=x ; E est le dernier N ou la barre depasse la diagonale. Source : ActivitySummary, toutes courses >= 1 km.
_Source:_ `SELECT "distance" FROM "ActivitySummary" WHERE "ActivitySelector" =~ /running/ AND "distance" > 1000 AND time > '2010-01-01T00:00:00Z' LIMIT...`

### Heat Acclimation
Heat acclimation percentage from Garmin. >75% = well acclimated. Seasonal pattern expected.

### Altitude Acclimation
Altitude acclimation from Garmin. Shows the altitude (in meters) you are fully adapted to. Tracking activates above 800m. Range: 800-4000m.

### Efficiency Factor (GAP/HR) — 7d avg
TrainingPeaks canonical Efficiency Factor: mean(GradeAdjustedSpeed) / mean(HR) x 100.

METHOD
• GradeAdjustedSpeed (Garmin GAP/NGP) normalizes for terrain grade
• mean(GAP) / mean(HR), not mean(GAP/HR) — per TrainingPeaks spec
• First 10 min excluded (HR stabilization per Friel)
• Speed > 0.5 m/s (exclude stops)
• No HR zone filter — full workout EF, compare similar session types

HOW TO READ
• Higher = faster at lower cardiac cost = better aerobic fitness
• Rising trend over 4-8 weeks = confirmed aerobic adaptation
• Orange line = 7-day moving average

Ref: TrainingPeaks EF, Joe Friel (2009), Coggan/Allen power-based training.
_Source:_ `SELECT mean("GradeAdjustedSpeed") * 100.0 / mean("HeartRate") AS "val" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /runni...`

### Profil athlète — KPI
Tableau de bord KPI (1 panel) : VO2max, Endurance, Hill, Fitness Age, poids, FCmax, LTHR, FC repos, FTP, delta poids 30j. Chaque carte : valeur + palier (quand applicable) + sparkline de tendance. Rendu custom ECharts (graphic).
_Source:_ `SELECT last("VO2_max_value") AS "v" FROM "VO2_Max" WHERE $timeFilter GROUP BY time(14d) fill(previous); SELECT last("EnduranceScore") AS "v" FROM "EnduranceScore" WHERE $timeFilter GROUP BY time(14d) fill(previous)` (+8 more)

**▸ Validateurs sport-science — adaptations du plan**

### Aerobic Decoupling — EF 1st vs 2nd half per run
Median EF over the first 30 min vs 30-90 min. If 2nd half drops = endurance not yet solid. Target: gap < 5%.
_Source:_ `SELECT median("RunningEfficiency") AS "EF 1st half (0-30min)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "...; SELECT median("RunningEfficiency") AS "EF 2nd half (30-90min)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND ...`

### Pace Z2 + Volume Z2 — weekly Mon→Sun (side-by-side bars)
Weekly bucket Mon-Sun (Europe/Paris TZ, current week included). Purple bar = mean Z2 pace weighted per-second (left axis, lower = faster). Grey bar = Z2 volume in minutes (right axis, pace reliability). Speed filter 1.5-6 m/s excludes walking/GPS spikes. Volume benchmarks: <30 min/wk = noisy (ignore pace), 30-60 = decent, >60 = robust.
_Source:_ `SELECT 1000.0 / mean("Speed") AS "Z2 Pace weekly (weighted)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "H...; SELECT count("HeartRate") / 60.0 AS "Z2 Volume (min)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "HeartRat...`

### Pace Z4+Z5 + Volume Z4+Z5 — weekly Mon→Sun (side-by-side bars)
Weekly bucket Mon-Sun (Europe/Paris TZ, current week included). Red bar = mean Z4+Z5 pace (HR >= 166) weighted per-second (left axis, lower = faster). Grey bar = Z4+Z5 volume in minutes (right axis, pace reliability). Speed filter 1.5-7 m/s. Tracks VO2max/threshold progression.
_Source:_ `SELECT 1000.0 / mean("Speed") AS "Z4+Z5 Pace weekly (weighted)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND...; SELECT count("HeartRate") / 60.0 AS "Z4+Z5 Volume (min)" FROM "ActivityGPS" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "Heart...`

### Running Power Curve — best mean power by duration (90d)
Best sustained mean power per duration over the last 90 days. Shape reflects energy system balance. 20-60 min plateau = Critical Power.
_Source:_ `SELECT max("Power") FROM "ActivityGPS" WHERE time > now() - 90d AND "ActivitySelector" =~ /running/; SELECT max(mp) FROM (SELECT moving_average("Power", 5) AS mp FROM "ActivityGPS" WHERE time > now() - 90d AND "ActivitySelector" =~ /running/...` (+5 more)

### Critical Pace Curve — best mean speed by duration (90d)
Best sustained mean speed per duration. 20-60 min plateau = Critical Pace (FTPace).
_Source:_ `SELECT max("Speed") * 3.6 FROM "ActivityGPS" WHERE time > now() - 90d AND "ActivitySelector" =~ /running/; SELECT max(ms) * 3.6 FROM (SELECT moving_average("Speed", 5) AS ms FROM "ActivityGPS" WHERE time > now() - 90d AND "ActivitySelector" =~ /ru...` (+5 more)

### Pace @ fixed HR - monthly trend, 3 bands (flat runs, D+/km < 25)
Progression de l'efficience cardiaque - allure a FC fixee, moyenne mensuelle (30j).

3 bandes de FC moyenne NON chevauchantes : ~140 (easy, 135-144 bpm) | ~150 (steady, 145-154) | ~160 (tempo, 155-164). Chaque point = 1000 / moyenne(vitesse) des runs plats dont la FC moy tombe dans la bande, agrege par 30 jours. Bandes <135 et >=165 retirees (2-5 runs, trop bruite).

Axe Y : allure mm:ss/km (plus bas = plus rapide). Filtre terrain : D+/km < 25. Distance > 1 km.

CORRECTION vs ancienne version : bins non chevauchants (plus de double-comptage aux bornes), seulement les 3 bandes qui portent des donnees, et lissage mensuel (fini la spaghetti de points bruts).

ATTENTION CONFONDANT METEO : sur une fenetre Dec->Mai l'allure a FC fixee MONTE (ralentit) surtout a cause de la chaleur croissante, PAS d'une perte de forme - a allure libre l'athlete ralentit quand il fait chaud (cf panel 'Heat impact' #120). Version corrigee chaleur : EF vs WBGT (#120) et EF GAP/HR (#300, ce dashboard). Lire la tendance en gardant la saison en tete.
_Source:_ `SELECT 1000 / MEAN("averageSpeed") AS "~140 (easy)" FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "distan...; SELECT 1000 / MEAN("averageSpeed") AS "~150 (steady)" FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "dist...` (+1 more)

### Pace vs avg HR - colored by recency (flat runs, D+/km < 25)
Nuage allure vs FC - chaque point = 1 run plat (D+/km < 25, 180j). X = FC moyenne (effort cardiaque), Y = allure mm:ss/km (plus bas = plus rapide). COULEUR = recence (degrade) : bleu = ancien (~6 mois) -> jaune -> rouge = recent.

LECTURE : a FC donnee, si les points rouges (recents) sont PLUS BAS (plus rapides) que les bleus (anciens) = gain d'efficience cardiaque. S'ils montent = cout. Ici le nuage recent monte surtout a cause de la chaleur croissante (Dec->Mai, cf #120) - ce n'est pas une regression de forme.

Avantage vs binning : pas de bornes arbitraires ni de double-comptage, chaque run apparait une fois et on voit la relation FC<->allure complete.
_Source:_ `SELECT "averageHR" AS "HR", 1000 / "averageSpeed" AS "Pace" FROM "ActivitySummary" WHERE $timeFilter AND time < now() - 540d AND "ActivitySe...; SELECT "averageHR" AS "HR", 1000 / "averageSpeed" AS "Pace" FROM "ActivitySummary" WHERE $timeFilter AND time >= now() - 540d AND time < now...` (+1 more)

### Heat impact — Efficiency Factor vs WBGT
Impact reel de la chaleur sur la physiologie. Chaque point = 1 run (365j). X = WBGT (indice de stress thermique : integre temperature + humidite + soleil + vent). Y = Efficiency Factor = vitesse/FC (m.min-1/bpm), plus haut = plus efficient.

Pourquoi EF et pas la FC : a allure libre l'athlete ralentit quand il fait chaud, donc la FC moyenne ne monte pas (effet ~ 0 bpm/degC a allure egale). Le cout de la chaleur se voit sur l'EFFICIENCE : EF baisse ~0.32%/degC (EF~WBGT p=0.004, n=92). Nuage qui descend vers la droite = impact chaleur.

Zones WBGT : <18 faible / 18-23 modere / 23-28 eleve / >28 extreme. Optimum perf ~8-15 degC.
Limites : peu de runs >25 degC ; surtout des runs easy/steady ; allure auto-selectionnee (le cout apparait aussi en pace perdue, pas que sur l'EF).
_Source:_ `SELECT ("averageSpeed" * 60 / "averageHR") AS "EF" FROM "ActivitySummary" WHERE $timeFilter AND "ActivitySelector" =~ /running/ AND "average...; SELECT "wbgt_estimated" AS "WBGT" FROM "ActivityWeather" WHERE $timeFilter`
