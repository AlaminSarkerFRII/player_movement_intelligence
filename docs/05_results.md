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

## H2: Time course after a turnover

*Not yet run (Phase 3.5).*
