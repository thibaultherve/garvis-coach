# Coaching Rules — Comportement + Litterature Sport-Science

> **Source de verite unique** pour le comportement Claude ET les decisions coaching.
> Fusionne l'ancien COACHING_PROTOCOL.md (comportement) et les regles sport-science.
> Claude DOIT consulter ce fichier avant toute analyse ou prescription.
> **Si conflit avec un autre fichier, ce fichier gagne.**
> Derniere mise a jour : 2026-05-27.

---

## 0. Comportement Claude — regles anti-bullshit

### Anti-sycophancy (Sharma et al. ICLR 2024)
- **Data contredit l'athlete → le dire en premiere phrase.** Pas de sugar-coating.
- **Contre-pression sans donnee = restaurer la position initiale.** Ne pas plier.
- **Verdicts tranches.** "Drift 7.2%, c'est trop haut." Pas de hedging.
- **Phrases bannies** : "great question", "you're right to", "indeed", "interesting observation".

### Anti-hallucination : verify-before-claim
- **Chaque chiffre cite = source tracable dans le meme turn** (MCP, query, script).
- **Donnee absente = "je n'ai pas, je dois requeter X".** Jamais de "probablement autour de".
- **Conflit entre 2 sources** : flagger explicitement. Priorite : InfluxDB raw > MCP aggrege > screenshot Garmin.

### Zero arithmetique mentale (Chen et al. 2022 PoT)
- **TOUT via code** : pace, km/h, distance, %, deltas, UTC/local, sommes.
- Ordre de preference : `garmin-toolbox.compute_*` > `python -c` > MCP/dashboard.
- `5:48/km` != `5.48 min/km` (c'est `5.8`). Toujours convertir explicitement.

### Calibration (Kadavath 2022)
- Tags `[conf X, n=Y]` sur claims numeriques cles.
- Pas de confidence sans `n=` (vient d'une query, pas invente).
- Si analyse a au moins 1 incertitude reelle, forcer au moins un claim `<0.5`.

### Fallback data (ReAct, Yao 2022)
1. `garmin-coach.*` (rapide, agrege)
2. `garmin-toolbox.dump_activity` (JSON complet)
3. `garmin-toolbox.compute_*` (metriques derivees)
4. `grafana.query_influxdb` (InfluxQL brut)
5. Open-Meteo / scripts repo (hors Garmin)

### Pieges connus
> Les pieges data-read (recovery_time_h=minutes, timestamps UTC, Duration=secondes, etc.)
> et les pieges infra/build sont proprietaire de `CLAUDE.md` (working dir PC + repo NAS).
> Non duplicies ici pour eviter la derive — voir la table "Source de verite" de `CLAUDE.md`.

### Sources comportement
- Sharma et al. ICLR 2024 (sycophancy)
- Dhuliawala 2023 (Chain-of-Verification)
- Chen 2022 (Program-of-Thought)
- Kadavath 2022 (calibration)
- Yao 2022 (ReAct)

---

## 1. Hierarchie des priorites (Seiler)

Par ordre d'importance decroissant :

1. **Volume** — le levier #1, de loin
2. **Entrainement haute intensite** — bien dose (2x/sem)
3. **Distribution d'intensite** — pyramidal OK pour recreatif a 4-5h/sem
4. Periodisation, specificite, tapering — impact mineur

> "If you get your training volume and high intensity training right,
> you are 90% of the way there."
> — Seiler, scientifictriathlon.com/tts120/

---

## 2. Distribution d'intensite — pas de dogme

- Polarise (80/0-5/15-20) n'est PAS superieur au pyramidal pour les recreatifs
  (meta-analyse PMC 2024, pmc.ncbi.nlm.nih.gov/articles/PMC11329428/)
- Apres 12 semaines, AUCUN modele n'est superieur quel que soit le niveau
- Reponse individuelle : 32% polarise, 32% pyramidal, 18% les deux, 18% rien
  (Nature 2025, clustering marathoniens recreatifs)
- A 4-5h/sem (<350h/an), les athletes gravitent naturellement vers pyramidal/threshold
  (Frontiers Physiology 2025, fphys.2025.1657892)

**Regle : ne pas forcer un modele. Tracker ce qui marche pour Thibault.**

---

## 3. Frequence des seances qualite

- 1x/sem HIIT = quasi rien (+0.6 VO2max en 6 sem)
- **2x/sem = sweet spot** (+4.1 VO2max en 6 sem, effect size 0.48)
- 3x/sem = pas de benefice supplementaire vs 2x
- Protocole teste : 4x4 min, 3 min recup active, coureurs recreatifs

> Source : PMC 2025, pmc.ncbi.nlm.nih.gov/articles/PMC12451023/ (n=26, 6 sem)

**Regle : C2+ = 2 seances qualite/sem, pas plus.**

---

## 4. Format des intervalles

### VO2max (Seiler; PMC 2025)
- 4x4min a 4x8min, >15 min de travail total par seance
- Intervalles longs (3-5 min) > sprints courts pour temps a >90% VO2max
- Seance optimale Seiler : **4x8 min zone 4** (+8% VO2max vs +3-4% autres formats)

> Source : PMC 2025, pmc.ncbi.nlm.nih.gov/articles/PMC11743937/

### Seuil — methode norvegienne (Bakken)
- Pas d'all-out. Intensite **REPETABLE**. Lactate 2-3 mmol/L
- FC ~80-87% FCmax (~155-169 bpm pour Thibault si FCmax=195)
- Pour recreatif : 2 seances seuil/sem controlees (pas double session/jour)
- Au moins 1 jour facile entre deux seances seuil

> "You do not improve by training as hard as possible.
> You improve by training hard enough, often enough, for long enough."
> — Marius Bakken, mariusbakken.com/double-threshold-training.html

### Sprint/Repetition (Daniels R pace; Frontiers 2025)
- 10x30s sprints 2x/sem : -5 sec sur 3K en 6 sem (effect size 1.53)
- Nos cotes courtes (40-60s) remplissent ce role

> Source : Frontiers Physiology 2025, fphys.2025.1536287

---

## 5. Phases Daniels — mapping vers nos cycles

| Phase Daniels | Notre cycle | Contenu |
|---------------|-------------|---------|
| **Phase I (Foundation)** | C1 | E runs + **strides** + **montees legeres** (PAS d'intervalles structures) + Long Run progressif |
| **Phase II (Early Quality)** | C2 | R pace (repetitions) + introduction T pace (seuil) |
| **Phase III (Transition Quality)** | C3 | I pace (VO2max) + T pace maintenance |
| **Phase IV (Final Quality)** | C4 | Race-specific + taper |

### CORRECTION IMPORTANTE — Phase I Daniels vs nos cotes C1

Daniels Phase I prescrit du "light uphill running" = courir facilement en cote,
PAS des intervalles structures. Nos cotes (6x40s a 6x2min avec recup chronometree,
cible HR Z3-Z4) sont du travail de **Phase II** (R pace sur cote).

Notre C1 fait donc Phase I + Phase II simultanement. Ce n'est pas conforme a Daniels
strict mais reste defensible (Brad Hudson, Canova mettent des hill sprints en base).
A noter pour les prochains cycles : ne pas presenter les cotes comme "Phase I conforme
a Daniels".

> Source : Daniels Running Formula ch.11,
> run.wxm.be/books/jack-daniels-running-formula.html

---

## 6. Limites d'intensite par type (Daniels)

| Type | % max du volume hebdo |
|------|-----------------------|
| Tempo (T) | max 10% |
| Interval (I) | max 8% |
| Repetition (R) | max 5% |
| Single session a une intensite | max 20% |
| **Long Run** | **max 30%** (si <64 km/sem) |

Pour >64 km/sem : LR = min(25% du volume, 150 min).

> Source : Daniels Running Formula, resume fellrnr.com/wiki/Jack_Daniels

### Tension structurelle du plan actuel
Avec 4 sessions/sem, le LR represente 35-40% du volume (violation du 30%).
Pas corrigeable sans ajouter une 5e session ou reduire le LR.
Risque accepte — c'est courant chez les recreatifs a 4 sessions.

---

## 7. Progression volume (Daniels Equilibrium Method)

- Ajouter max **1.6 km par seance/semaine**
- **Rester au meme niveau 3-4 semaines** avant d'augmenter (ideal 4-6 sem)
- Ne jamais augmenter de plus de 16 km/sem au total

> Source : Daniels Running Formula

### Single run increase (BJSM 2023)
- Max **+10%** vs la plus longue sortie des 30 derniers jours
- Au-dessus de 10% : **+64% de risque de blessure de surcharge**
- Etude sur 5205 coureurs, 588k sessions Garmin

> Source : runnersconnect.net/injury-prevention/ (BJSM 2023)

### Decharge
- Pattern 3-up-1-down (3 sem charge, 1 sem decharge)
- Decharge = -20 a -40% du pic
- Individuel : certains repondent mieux a 4-up-1-down

---

## 8. Charge (Gabbett 2016)

- ACWR sweet spot : **0.8 - 1.3**
- Spike >1.5 = risque significatif de blessure
- Charge chronique haute = effet protecteur
- Ne PAS traiter les seuils comme des coupures dures (Impellizzeri 2020)

> Source : Gabbett 2016 BJSM; Impellizzeri 2020 critique

---

## 9. Renforcement musculaire (3 meta-analyses 2022-2024)

- Charges lourdes = **+2.9% economie de course** (Sports Medicine 2024)
- Resistance lourde > plyometrie pour RE et time trial (PMC 2022)
- Protocole : squats, fentes, mollets, **2x/sem, min 10 semaines**
- **OBLIGATOIRE** — aussi bien documente que le tempo pour le seuil

> Sources :
> - pmc.ncbi.nlm.nih.gov/articles/PMC11052887/ (Sports Medicine 2024)
> - pmc.ncbi.nlm.nih.gov/articles/PMC9653533/ (PMC 2022)
> - pmc.ncbi.nlm.nih.gov/articles/PMC11258194/ (Sports Medicine 2024)

---

## 10. Strides (Daniels Phase I; Frontiers 2025)

- 4-6x 20-30s en fin de footing, 2-3x/sem
- Cout fatigue quasi nul, benefice neuromusculaire significatif
- Standard en Phase I Daniels, absent de notre C1 actuel = **manque identifie**

---

## 11. Les 3 facteurs de performance

| Facteur | Contribution | Comment l'ameliorer |
|---------|-------------|---------------------|
| **VO2max** | Cylindree du moteur | Intervalles 3-5 min a allure 3K-5K, 2x/sem |
| **Seuil lactique** | Regime max soutenable | Tempo 20-30 min controlle, 1-2x/sem |
| **Economie de course** | Conso carburant/km | Volume accumule + renfo muscu lourd + cotes/strides |

Pour un recreatif visant le club :
- **70% du travail qualite sur le seuil, 30% sur VO2max** (Runners Connect)
- L'economie de course represente jusqu'a **65% de la variation de performance**
  entre coureurs de meme VO2max (Marathon Handbook)

---

## 12. Volume cible pour niveau club

- Seiler : volume = levier #1. Coureur de club typique = 60-80 km/sem
- Notre pic C1 = 47 km/sem. Marge de progression significative
- Plan actuel prevoit 40-55 km en C2-C4 — potentiellement insuffisant pour
  l'objectif "bon coureur de club"
- A reevaluer en fonction de l'absorption et du temps disponible

---

## 13. Zones FC — LTHR confirme

- LTHR Garmin auto-detecte : **177-178 bpm** (stable depuis mars 2026)
- FCmax : 194 (test 01/05/2026), Garmin utilise 195
- Ratio LTHR/FCmax : 90.8% (norme haute, bon signe aerobie)
- Pace seuil : 4:27-4:34/km (progression 5:30 → 4:27 en 7 mois, +24%)

### Zones Friel (a recalibrer apres test 27/06)

| Zone | % LTHR | FC (LTHR=177) |
|------|--------|---------------|
| Z1 Recup | <81% | <143 |
| Z2 Endurance | 81-89% | 143-158 |
| Z3 Tempo | 90-93% | 159-165 |
| Z4 Sous-seuil | 94-99% | 166-175 |
| Z5a Seuil | 100-102% | 177-181 |
| Z5b VO2max | 103-106% | 182-188 |
| Z5c Anaerobie | >106% | >188 |

---

## Checklist avant d'ecrire un nouveau cycle

- [ ] Relire ce fichier en entier
- [ ] Verifier les resultats du dernier test (seuil, 5K TT) pour recalibrer les zones
- [ ] Volume : quelle est la base actuelle ? Progression max +7%/sem
- [ ] Qualite : 2 seances/sem, pas plus (PMC 2025)
- [ ] LR : max 30% du volume hebdo (Daniels)
- [ ] Single run : max +10% vs record 30 jours (BJSM 2023)
- [ ] Decharge toutes les 3-4 semaines
- [ ] Renfo muscu prevu ? (obligatoire)
- [ ] Strides prevues ? (2-3x/sem en fin de footing)
- [ ] Daniels intensity caps respectes ? (10% T, 8% I, 5% R)
- [ ] ACWR projete dans le sweet spot 0.8-1.3 ?
