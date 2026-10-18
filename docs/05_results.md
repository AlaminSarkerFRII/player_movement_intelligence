# Results

Every number on this page is produced by `make pipeline` from the raw data and
is saved in `reports/tables/`. A full rebuild from raw data (about 1 minute)
reproduces the tables exactly.

## H1: Team shape in vs out of possession (Phase 3.4)

**Hypothesis (from the proposal):** during open play, teams have larger area,
width, length and stretch index when in possession than when out of
possession. This replicates findings already reported in the literature (see
`02_literature_notes.md`). It is a sanity check of the pipeline, **not a novel
finding**.

### Data analysed

- 3 matches, 6 team-matches (Metrica Games 1–3).
- Unit: **one possession spell seen from one team**, using the team's mean shape
  over the spell. 1,576 spell-team rows.
- Frames used: ball in play, passed QC, 10 outfield players (always true here),
  inside a spell of at least 2 s of usable frames.
- Ball zone of each row, from the team's own perspective: middle 864,
  defensive 356, attacking 356.

### Model

`metric ~ state + ball_zone + (1 | team_match)`. This is a linear mixed model
(statsmodels `MixedLM`, REML) with a random intercept for each of the 6
team-matches. p-values are Holm-corrected across the 4 metrics.

### Results (primary model)

| Metric | Estimate: in − out | 95 % CI | Team-matches with in > out | Median Cohen's d |
|---|---|---|---|---|
| Length (m) | +2.7 | [2.0, 3.3] | 6/6 | 0.39 |
| Width (m) | +7.6 | [6.8, 8.3] | 6/6 | 0.91 |
| Convex-hull area (m²) | +240 | [213, 268] | 6/6 | 0.88 |
| Stretch index (m) | +2.0 | [1.8, 2.3] | 6/6 | 0.75 |

Raw spell means (all team-matches pooled), in vs out of possession: length
34.5 vs 32.2 m, width 44.6 vs 37.4 m, area 1,043 vs 815 m², stretch 16.7 vs
14.8 m.

Figure: `reports/figures/h1_shape_by_state.png`. Visual check of the metric
code on one frame: `reports/figures/shape_example_frame.png`.

### Sensitivity analyses

| Variant | Why | Result |
|---|---|---|
| No ball-zone adjustment | Is the effect just "attacking teams are higher up the pitch"? | Same direction; estimates 5–14 % smaller |
| Home-team rows only | Each spell then appears once (the two rows of a spell share the ball position) | Same direction; all CIs exclude 0 |
| Away-team rows only | Same reason | Same direction; all CIs exclude 0 |

All 16 models converged without warnings.

### Interpretation

- **H1 is supported in these three matches.** Teams were larger in possession
  on every metric, in every team-match, under every model variant.
- **Teams mainly spread across the pitch, not along it.** The width effect
  (d ≈ 0.9) is more than twice the length effect (d ≈ 0.4). In possession, a
  team became on average 7.6 m wider but only 2.7 m longer.
- The direction agrees with earlier position-data studies, which suggests
  the pipeline (loading → preprocessing → possession → metrics) produces
  sensible values.

### Limitations of this result

- **Small, non-random sample:** 3 matches and 6 team-matches from anonymized
  teams. The results describe these matches only.
- **The p-values overstate certainty.** They are extremely small (all
  < 1e-5), but consecutive spells within a match are not independent, so the
  effective sample is smaller than 1,576 rows. The conclusion rests on effect
  sizes, CIs and the 6/6 consistency, not on p-values.
- **Few groups:** a random-effect variance estimated from 6 team-matches is
  imprecise.
- Spell means weight a 2 s spell the same as a 40 s spell. A duration-weighted
  analysis is a possible extra sensitivity check.
- Possession labels come from event data and may be a few frames off.
- **No causal claim.** This shows how shape differs with possession state, not
  why.

## H2 and H3: Time course after a turnover (Phase 3.5)

**H2 (proposal):** after losing possession, a team's area falls towards its
out-of-possession level, and the time course can be measured (time to 50 % of
the change, T50). **H3:** the size and timing vary between teams and matches
(no direction predicted).

### Design

- **Events:** 354 included turnovers (see `01_dataset_audit.md` section 9),
  plus **1,770 matched controls**: 5 per turnover, drawn from the same match.
  Controls follow the same rules except that possession does not change: the
  team has had the ball for ≥ 2 s and keeps it ≥ 2 s, no turnover is within
  3 s, and the ball is in the same pitch third from that team's perspective.
  Control sampling uses the fixed seed in the config.
- **Window:** −5 s to +10 s around t0 (the winning team's first control
  event). Each event's curve is the change from its **own baseline, −5 s to
  −2 s**. The baseline ends at −2 s because `BALL LOST` typically comes about
  1.6 s before t0 (audit section 9).
- **Usable events:** 334 turnovers and 1,690 controls had at least 50 %
  usable baseline frames. 307 turnovers and 1,486 controls also had usable
  frames in the late window (+5 to +10 s).
- **Perspectives:** the team that **lost** the ball and the team that **won** it.
- **Turnover effect** = turnover curve − control curve. 95 % bands come from a
  bootstrap (2,000 resamples of events within each match). Both perspectives
  of a metric use the same resamples (paired bootstrap).
- **Late change:** each event's mean change at +5 to +10 s. Mixed model
  `late ~ condition + (1 | team_match)`, Holm-corrected across 4 metrics per
  perspective. Cross-check: OLS with team-match fixed effects.

### Results: size of the change (late window, turnover − control)

| Metric | Lost the ball | Won the ball | Share of H1 static difference (lost / won) |
|---|---|---|---|
| Area (m²) | **−191** [−231, −152] | **+226** [193, 259] | 80 % / 94 % |
| Width (m) | −6.4 [−7.8, −5.0] | +6.4 [5.4, 7.4] | 84 % / 84 % |
| Stretch index (m) | −1.7 [−2.0, −1.3] | +1.8 [1.5, 2.1] | 82 % / 87 % |
| Length (m) | −1.5 [−2.4, −0.6] | +1.5 [0.4, 2.5] | 57 % / 55 % |

All Holm-corrected p ≤ 0.006. The fixed-effects cross-check gives the same
estimates to within 0.01. One model (length, team that won the ball) did not
converge cleanly; its fixed-effects estimate is identical (+1.48).

**H2 is supported:** after losing the ball, a team's area contracts
substantially more than in comparable open play without a turnover. Within
5–10 s it covers about 80 % of the full in-vs-out-of-possession difference
estimated in H1.

### Results: timing (T50, seconds after t0)

| Metric | Lost the ball | Won the ball | Difference (won − lost), paired 95 % CI |
|---|---|---|---|
| Area | **1.2** [0.7, 1.6] | **3.4** [3.0, 4.0] | **+2.3 s** [1.6, 3.1] |
| Width | 0.4 [−0.2, 1.0] | 4.0 [3.6, 4.4] | +3.6 s [2.8, 4.4] |
| Stretch index | 0.8 [0.3, 1.3] | 4.2 [3.7, 4.8] | +3.4 s [2.6, 4.2] |
| Length | 2.5 [1.7, 4.0] | −0.8 [−2.0, 3.3] | not estimable (effect too small) |

T50 uses the late-window change as "100 %". **With the peak change as 100 %
instead (robust to the partial rebound after ~5 s), the conclusions are the
same:** area 1.4 s vs 3.8 s, a difference of +2.4 s [1.6, 3.2].

**Main new observation (descriptive, these 3 matches): the reorganization is
asymmetric.** The team that lost the ball contracted fast (half the change
about 1 s after t0), while the team that won it expanded more slowly (half the
change about 3.5–4 s after t0). The winning team's curve is still rising at
+10 s, so its true T50 may be later still, which would make the asymmetry
larger. Whether this asymmetry has been reported before is **not yet known**:
the two "must read" papers in `02_literature_notes.md` have not been read.

Figures: `h2_timecourse_area.png`, `h2_effect_all_metrics.png`.

### H3: Between-team variation (area, team that lost the ball)

| Team-match | Turnovers | Mean late change (m²) | T50 (s) [95 % CI] |
|---|---|---|---|
| metrica_1:away | 57 | −97 | 0.5 [−2.0, 6.9] |
| metrica_1:home | 57 | −117 | 2.2 [0.9, 3.6] |
| metrica_2:away | 46 | −173 | 0.8 [−1.6, 2.2] |
| metrica_2:home | 47 | −100 | 1.1 [−2.0, 5.7] |
| metrica_3:away | 62 | −228 | 0.6 [−0.2, 1.3] |
| metrica_3:home | 65 | −298 | 1.2 [0.6, 1.9] |

- Only **3.6 %** of the variance in late change lies between team-matches
  (ICC = 0.036). Most of the variation is between individual turnovers.
- Contraction was larger in Game 3 for **both** teams (−228 and −298 m²), so
  it may be a match-level difference (style, tempo, or data source) rather
  than a team trait. With 3 matches we cannot separate these.
- Per-team-match T50 intervals are wide (some span −2 to +7 s). With about 50
  turnovers per team-match, **this data cannot reliably distinguish teams'
  reorganization speed**. H3 is therefore inconclusive, apart from showing
  that the direction of the effect is the same for every team-match.

Figure: `h3_team_match_area.png`.

### Sensitivity (area, team that lost the ball)

| Variant | n | Late effect (m²) [95 % CI] | T50 (s) |
|---|---|---|---|
| Primary | 307 | −191 [−231, −152] | 1.2 [0.7, 1.6] |
| Exclude 29 turnovers won by a goalkeeper | 282 | −198 [−239, −157] | 1.1 [0.6, 1.5] |
| Baseline −5 to −3 s | 297 | −195 [−236, −154] | 1.1 [0.6, 1.6] |
| Ball lost in own defensive third | 24 | −135 [−327, 57] | inconclusive |
| Ball lost in own middle third | 119 | −269 [−331, −206]* | 0.6 [0.0, 1.2] |
| Ball lost in own attacking third | 164 | −129 [−178, −79] | 1.9 [1.2, 2.4] |
| Game 1 only | 106 | −99 [−165, −33] | 1.6 [−0.3, 2.8] |
| Game 2 only | 82 | −137 [−209, −64] | 1.1 [−0.3, 2.0] |
| Game 3 only | 119 | −310 [−376, −245] | 1.0 [0.4, 1.4] |

\* The mixed model did not converge cleanly; treat this row with caution.
Single-game rows use team-match fixed effects because 2 groups are too few
for a random effect.

- Goalkeeper catches and the baseline choice do not change the result.
- **Where the ball is lost matters:** losing it in midfield gave the largest
  and fastest contraction. Losing it high up the pitch (own attacking third)
  gave a smaller, slower one. This is exploratory: it was not a pre-specified
  hypothesis.

### Limitations of H2/H3

- 3 anonymized matches; results describe these matches only.
- **t0 comes from event data,** whose timestamps may be off by several frames.
  This blurs absolute timings, but affects both perspectives equally, so it
  does not create the asymmetry.
- The 10 s window may end before the winning team finishes expanding.
- Controls match on match, pitch third and spell rules, but not on everything
  (for example, game state or score, which are unavailable).
- Some contraction begins before t0 (visible from about −1 s), consistent
  with the ball being lost before the recovery event. T50 is measured
  relative to the recovery, not to the moment the ball was lost.
- Exploratory subgroup results (pitch third, single games) are not
  multiplicity-corrected.
- **No causal claim** beyond the turnover-versus-matched-control comparison.
