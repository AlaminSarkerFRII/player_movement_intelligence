# Research Proposal (draft v0.1)

**Title:** How Soccer Teams Reorganize Their Shape After a Change of
Possession: A Reproducible Analysis of Open Positional Tracking Data

**Status:** Proposal only. No experiments have been run. Everything under
"Expected outcomes" is a hypothesis, not a result.

## 1. Background

Positional (tracking) data records the x, y location of every player and the
ball many times per second. Researchers summarize a team's collective
organization with metrics such as centroid, surface area and stretch index
(Frencken et al., 2011; Memmert et al., 2017; Low et al., 2020). Earlier work
reports that teams are more compact when defending (e.g., Welch et al., 2021).
Less is known, as far as we have checked, about **how quickly and how
consistently** a team changes shape in the seconds after it wins or loses the
ball. Two recent papers (Zhang et al., 2025; MDPI *Sports* 14(9):374) must be
read before we claim this is a gap (see `02_literature_notes.md`).

## 2. Research question

**Primary RQ:** How do team shape metrics change in the seconds after a team
wins or loses possession, and how consistent is that pattern across teams and
matches?

**Secondary RQ (reliability, optional):** How accurately can a team's
possession state be predicted from its shape alone, when evaluated on unseen
matches?

## 3. Hypotheses

- **H1 (replication):** During open play, teams have larger surface area,
  width, length and stretch index when in possession than when out of
  possession.
- **H2 (time course):** After losing possession, a team's surface area falls
  from its in-possession level towards its out-of-possession level. The change
  can be described by a measurable time course: the time to complete 50 % of
  the change.
- **H3 (consistency):** The size and timing of this change vary between teams
  and matches. We estimate how much variation there is; we predict no direction.

## 4. Data

| Role | Dataset | Unit |
|---|---|---|
| Primary | Metrica Sports sample data, Games 1–3 (25 Hz tracking + events) | 3 matches, 6 team-matches |
| Replication | Bassek et al. (2025), 7 Bundesliga / 2. Bundesliga matches (CC-BY 4.0) | 7 matches, 14 team-matches |

## 5. Variables

**Independent / context variables**
- Possession state: in / out (derived from events)
- Time relative to turnover: −5 s to +10 s
- Turnover type: ball lost / ball won
- Ball zone at turnover: defensive / middle / attacking third
- Team, match, half (grouping factors)

**Outcome variables** (computed per frame on the 10 outfield players; goalkeeper excluded)
- Team length: range of player x positions along the pitch (m)
- Team width: range of player y positions across the pitch (m)
- Surface area: area of the convex hull of player positions (m²)
- Stretch index: mean distance of players from the team centroid (m)
- Centroid x: how far up the pitch the team is (m)

## 6. Key definitions (operational)

- **Ball in play:** frames where the ball position is tracked and that do not
  fall between a `BALL OUT` event and the next `SET PIECE` event (to be
  validated, see dataset audit).
- **Possession:** the team of the most recent on-ball event.
- **Open-play turnover:** a possession change marked by a `BALL LOST` or
  `RECOVERY` event, not a set-piece restart. Turnovers within 3 s of a
  previous turnover are excluded so that post-turnover windows do not overlap
  (the threshold will be sensitivity-tested).

## 7. Methods

1. **Preprocessing:** convert coordinates to meters (105 × 68 m); flip
   coordinates so each team attacks the same direction in both halves; light
   smoothing; validate player speeds.
2. **H1, static comparison:** aggregate each metric to one value per
   **possession sequence**, not per frame. Consecutive 25 Hz frames are almost
   identical, so frame-level tests would produce falsely tiny p-values. Fit a
   linear mixed-effects model:
   `metric ~ possession_state + ball_zone + (1 | match/team)`.
   Report effect sizes with 95 % confidence intervals.
3. **H2, event-aligned time course:** for each turnover, extract the metric from
   −5 s to +10 s, expressed as the change from the pre-turnover average.
   Average across turnovers and compute confidence bands with a bootstrap that
   resamples turnovers within each match.
4. **Baseline / control:** repeat step 3 at randomly chosen open-play moments
   **without** a turnover, matched on ball zone. If shape changes after a
   turnover just as much as at random moments, H2 is not supported.
5. **H3, consistency:** estimate between-team and between-match variance from
   the mixed model; plot per-team curves.
6. **Secondary RQ (optional):** classify possession state from 1-second shape
   windows using logistic regression, then a tree model. Evaluate with
   **leave-one-match-out** cross-validation, so no match appears in both
   training and testing. Compare against a majority-class baseline and a
   single-feature (area only) baseline, using balanced accuracy and ROC AUC.
   Report results with the error analysis.
7. **Replication:** run the identical pipeline (same code and settings) on the
   IDSSE dataset.
8. **Sensitivity analyses:** goalkeeper included vs excluded; minimum
   possession length; smoothing window; turnover exclusion threshold.

All random procedures use a fixed seed recorded in a config file.

## 8. Expected outcomes (hypotheses, not results)

- Larger shape metrics in possession (H1). This direction is expected from
  prior literature.
- A visible contraction after losing the ball (H2), with a size and timing
  that we will estimate.
- Unknown amount of between-team variation (H3).

## 9. Limitations (known in advance)

- **Small sample:** 3 + 7 matches. Results describe these matches and cannot
  be generalized to "all football".
- Metrica teams are anonymized, so we cannot add context such as league,
  team quality or formation.
- Possession labels come from event data and may be off by a few frames.
- Shape metrics describe *what* happens, not *why*. **No causal claims.**
- The two datasets come from different providers and leagues, so differences
  may reflect the data source rather than football.

## 10. Planned extension: pose estimation

SkillCorner Open Data provides broadcast tracking plus 3D body pose (29
joints) for 2 A-League matches. Follow-up question: during the reorganization
window found in H2, does defenders' body orientation (from pose) differ from
other moments? This links team-level tracking analysis to individual pose data.
It is exploratory, because only 2 matches have pose data and its accuracy has
not been independently checked.
