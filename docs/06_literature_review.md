# Literature Review (Phase 4)

Date: 2026-10-18. This review supersedes the reading log in
`02_literature_notes.md`.

## How this review was done (and its limits)

This is a **targeted** review, not a systematic one. Sources were found by:

- starting from known reviews (Memmert et al., 2017; Low et al., 2020);
- web searches on team shape, transitions and possession changes;
- following the reference lists of the two most relevant papers (Zhang et
  al., 2025; Serra et al., 2026).

Each reference is tagged with how deeply it was read:

- **[Full text]** read completely by the project author;
- **[Abstract]** only the abstract and bibliographic record were read;
- **[Cited]** known only through another paper's reference list.

Claims in the write-up must not go beyond the reading level of their source.
A systematic search (PRISMA-style, several databases) was **not** done. A
relevant study may therefore have been missed.

## 1. Team shape metrics and possession

Collective tactical behaviour is commonly described with **centroid, length,
width, surface area (convex hull) and stretch index** computed from player
positions [Frencken et al., 2011 — Abstract; Memmert et al., 2017 — Abstract;
Low et al., 2020 — Abstract]. Frencken et al. (2011) introduced centroid and
surface area as collective variables in 4-vs-4 small-sided games. Low et al.
(2020) review collective tactical behaviour in football from positional data.

**Teams are larger with the ball than without it.** This is well documented.
Clemente et al. (2013) [Abstract] found differences in centroid, stretch index
and surface area with and without possession in one match. Praça et al.
(2022) [Abstract] report "a more spread tactical positioning" in the offensive
phase across 18 U-20 matches tracked by GPS, with game phase having the
largest influence on positioning. Welch et al. (2021) [Abstract] found defending phases more compact and more ordered than
attacking phases (2 matches, 1 team).

> **Implication for this project:** H1 (larger in possession) is a
> replication, as planned. Our width-over-length pattern is also consistent
> with Zhang et al. (2025), who report the in-possession difference to be
> "bigger … in width than length" (section 2).

## 2. Shape during transition phases (closest prior work)

**Zhang, Kempe, McRobert, Folgado & Olthof (2025)** [Full text], *Proc. IMechE
Part P*:

- **Study 1** is a processing pipeline for GNSS positional data.
- **Study 2** analyses **one** English Championship match of **one** team (GNSS,
  10 Hz). A professional analyst labelled four phases: in possession (IP), out
  of possession (OOP), attack-to-defence transition (ADT) and defence-to-attack
  transition (DAT). Shape metrics were **averaged within each phase** and
  compared with ANOVA.
- Mean surface area: IP 1,418 m², ADT 1,081 m², DAT 1,011 m², OOP 911 m². The
  team was larger in IP than in every other phase, and larger in ADT than in
  OOP. **DAT did not differ significantly from OOP.**
- Their interpretation: the more spread shape in ADT than OOP suggests "a
  quick adaptation from offensive to defensive modes", whereas a shape in DAT
  similar to OOP "**may imply a delayed team reaction to offensive behaviour**
  or suggest a short period required to switch from defensive to offensive
  mode."
- They also found a systematic offset between positional and event data and
  corrected it **per half**. They recommend that synchronization be reported.

> **Implication for this project:** the asymmetry we measured (the losing team
> contracts faster than the winning team expands) is **consistent with, and
> was tentatively suggested by,** Zhang et al. (2025). Our analysis therefore
> does **not** discover the asymmetry; it **quantifies** it. Differences in
> design:
>
> | | Zhang et al. (2025), Study 2 | This project |
> |---|---|---|
> | Data | 1 match, 1 team, GNSS 10 Hz, private | 10 matches (3 Metrica + 7 IDSSE), 2 providers, optical 25 Hz, open |
> | Time resolution | Mean per phase | Frame-level time course, −5 s to +10 s around t0 |
> | Teams compared | The analysed team, across phases | Losing and winning team **at the same moment** (paired) |
> | Comparison | Between phases (ANOVA) | Against matched open-play controls without a turnover |
> | Timing estimate | Not estimated | Time to 50 % of change (T50), with bootstrap CI |
> | Replication | None | Second dataset, three t0 definitions |

## 3. Defensive transitions and ball recovery

- **Vogelbein, Nopp & Hökelmann (2014)** [Abstract], *J Sports Sci*: "defensive
  reaction time", the time to regain the ball after losing it, across all 306
  matches of the 2010/11 Bundesliga. Top teams regained the ball about 1 s
  faster, and all teams reacted faster when trailing.
- **Bauer & Anzer (2021)** [Abstract], *Data Min Knowl Disc*: supervised
  detection of **counterpressing** from synchronized DFL positional and event
  data. Over 20,000 labelled defensive transitions from 97 matches, 134 expert
  features, XGBoost AUC 0.874; applied to six Bundesliga seasons.
- **Forcher, Altmann, Forcher, Jekauc & Kempe (2022)** [Abstract], *Int J
  Sports Sci Coach*: scoping review of 23 tracking-data studies of defensive
  play. Defensive studies are fewer than offensive ones. Successful defending
  is associated with high pressure and with intra- and inter-team
  synchronization.
- **Forcher, Forcher, Altmann, Jekauc & Kempe (2024)** [Abstract], *Int J Sports
  Sci Coach*: 153 Bundesliga matches. **Whole-team compactness did not differ**
  between successful and unsuccessful defensive plays; the five defenders
  closest to the ball were more compact in successful plays.
- **Serra, Carrilho, Xiao, Savoia, Beato, Coppola, Vastola & Araújo (2026)**
  [Full text], *Sports* 14(9):374: 248 negative-transition episodes from 5
  matches of one Serie A team (GNSS, 10 Hz).
  - They propose **rβ**: how concentrated the outfield players' movement
    directions are relative to the direction of their own goal, summarised with
    Kuramoto's order parameter.
  - Higher rβ went with recovering the ball within 10 s (0.717 vs 0.600,
    d = 0.91), robust across thresholds, early fixed windows, zones and
    matches.
  - They argue that length, width, area and stretch index "mainly describe team
    shape" and do not capture the link between the team and its task.
  - Their design is close to ours in style: event-aligned windows, mixed models
    with match effects, landmark windows to avoid using information from after
    the outcome, and a match-by-match consistency check.

> **Implications for this project:**
> 1. Our study is **descriptive**: it measures how shape changes, not whether
>    that change helps defending. Forcher et al. (2024) is a caution: whole-team
>    area may not be linked to defensive success at all.
> 2. Serra et al.'s critique applies: area and width are not goal- or
>    ball-referenced. Using a task-referenced measure (such as rβ, or
>    compactness of players near the ball) is a natural extension.
> 3. Linking reorganization speed to outcomes (recovery time, as in Vogelbein et
>    al. 2014 and Serra et al. 2026; or shots conceded) is the obvious next
>    research question. It is not addressed here.

## 4. Data and methods

- **Open tracking data.** Bassek, Rein, Weber & Memmert (2025) [Abstract +
  dataset documentation via kloppy]: 7 Bundesliga / 2. Bundesliga matches with
  positional and event data, CC-BY 4.0. Used here as
  the replication dataset.
- **Synchronizing events and tracking.** Event and tracking clocks can be
  offset [Zhang et al., 2025 — Full text]. Bauer & Anzer (2021) and Anzer &
  Bauer (2021) [both Abstract] build models on synchronized DFL data.
  Sequence-alignment approaches exist (Kwiatkowski & Clark, sync.soccer
  [Cited, via Zhang et al.]). Our per-half constant shift is the simplest form
  of correction. We found the IDSSE lags to vary in size and sign between
  halves (−0.8 s to +1.8 s).
- **Formations and roles from tracking data** (context only): Bialkowski et
  al. (2014) [Abstract]; Shaw & Glickman (2019) [Abstract], who separate
  in- and out-of-possession formations.
- **Collective states:** Welch et al. (2021) analyse movement states by phase
  but do not align analysis to the moment of possession change.

## 5. Synthesis: what is known, what this project adds

**Known before this project:**

1. Teams are larger, especially wider, in possession (§1, §2).
2. Transition phases have intermediate shapes. In one match, the shape after
   regaining the ball resembled the defensive shape, suggesting a slow switch
   to attacking mode (Zhang et al., 2025).
3. Speed of ball recovery and counterpressing have been studied at scale
   (Vogelbein et al., 2014; Bauer & Anzer, 2021). Whole-team compactness may
   not predict defensive success (Forcher et al., 2024).

**Not found in this targeted search** (which is not proof that it does not
exist):

- a **frame-resolution time course** of team area and width aligned to the
  moment of possession change, for **both** teams at once;
- comparison against **matched no-turnover controls**;
- an **estimate of reorganization speed** (T50) with uncertainty;
- **replication across open datasets and providers**, including how the
  definition of the turnover moment changes the estimates.

**Defensible contribution statement (for the report and emails):**

> Using open tracking data from 10 professional matches (two providers), I
> quantified how team shape reorganizes in the seconds after a change of
> possession. The team that loses the ball contracts substantially faster than
> the team that wins it expands (T50 gap ≈ 2–5 s). This is consistent with a
> tentative suggestion from a single-match phase analysis (Zhang et al., 2025),
> and the effect replicated across datasets and turnover definitions.

**Not defensible:** "first to show", "novel discovery", or any claim that
faster contraction causes better defending.

## 6. Still to read before final claims

| Priority | Reference | Why |
|---|---|---|
| 1 | Bauer & Anzer (2021), full text | Its 134 features for counterpressing may include team-shape changes after ball loss, which is the closest large-scale overlap |
| 2 | Forcher et al. (2022) scoping review, full text | May list transition-specific shape studies |
| 3 | Praça et al. (2022), full text | Offensive vs defensive phase shapes; check whether transitions are treated separately |
| 4 | Vogelbein et al. (2014), full text | Defensive reaction time definitions |
| 5 | Frencken, van der Plaats, Visscher & Lemmink (2013) [Cited, via Zhang et al.] | Source of the 3-s "team response window" mentioned by Zhang et al. |

## References

- Anzer, G., & Bauer, P. (2021). A goal scoring probability model for shots
  based on synchronized positional and event data in football (soccer).
  *Frontiers in Sports and Active Living*, 3, 624475.
  https://doi.org/10.3389/fspor.2021.624475 [Abstract]
- Bassek, M., Rein, R., Weber, H., & Memmert, D. (2025). An integrated dataset
  of spatiotemporal and event data in elite soccer. *Scientific Data*, 12, 195.
  https://doi.org/10.1038/s41597-025-04505-y [Abstract]
- Bauer, P., & Anzer, G. (2021). Data-driven detection of counterpressing in
  professional football. *Data Mining and Knowledge Discovery*, 35(5),
  2009–2049. https://doi.org/10.1007/s10618-021-00763-7 [Abstract]
- Bialkowski, A., Lucey, P., Carr, P., Yue, Y., Sridharan, S., & Matthews, I.
  (2014). Large-scale analysis of soccer matches using spatiotemporal tracking
  data. *IEEE ICDM*, 725–730. https://doi.org/10.1109/ICDM.2014.133 [Abstract]
- Clemente, F. M., Couceiro, M. S., Martins, F. M. L., Mendes, R., &
  Figueiredo, A. J. (2013). Measuring tactical behaviour using technological
  metrics: Case study of a football game. *International Journal of Sports
  Science & Coaching*, 8(4), 723–739. https://doi.org/10.1260/1747-9541.8.4.723
  [Abstract]
- Forcher, L., Altmann, S., Forcher, L., Jekauc, D., & Kempe, M. (2022). The
  use of player tracking data to analyze defensive play in professional
  soccer: A scoping review. *International Journal of Sports Science &
  Coaching*, 17, 1567–1592. https://doi.org/10.1177/17479541221075734
  [Abstract]
- Forcher, L., Forcher, L., Altmann, S., Jekauc, D., & Kempe, M. (2024). Is a
  compact organization important for defensive success in elite soccer? –
  Analysis based on player tracking data. *International Journal of Sports
  Science & Coaching*, 19(2), 757–768.
  https://doi.org/10.1177/17479541231172695 [Abstract]
- Frencken, W., Lemmink, K., Delleman, N., & Visscher, C. (2011). Oscillations
  of centroid position and surface area of soccer teams in small-sided games.
  *European Journal of Sport Science*, 11(4), 215–223.
  https://doi.org/10.1080/17461391.2010.499967 [Abstract]
- Low, B., Coutinho, D., Gonçalves, B., Rein, R., Memmert, D., & Sampaio, J.
  (2020). A systematic review of collective tactical behaviours in football
  using positional data. *Sports Medicine*, 50(2), 343–385. [Abstract]
- Memmert, D., Lemmink, K. A. P. M., & Sampaio, J. (2017). Current approaches
  to tactical performance analyses in soccer using position data. *Sports
  Medicine*, 47(1), 1–10. https://doi.org/10.1007/s40279-016-0562-5 [Abstract]
- Praça, G. M., et al. (2022, online first; issue 2025). Integrating notational
  and positional analysis to investigate tactical behavior in offensive and
  defensive phases of football matches. *Proceedings of the IMechE, Part P*,
  239(2). https://doi.org/10.1177/17543371221122044 [Abstract; full author list
  to be checked]
- Serra, E., Carrilho, D., Xiao, L., Savoia, C., Beato, M., Coppola, S.,
  Vastola, R., & Araújo, D. (2026). Team synergies in professional football: A
  goal-referenced performance indicator for rapid ball recovery in negative
  transitions. *Sports*, 14(9), 374. https://doi.org/10.3390/sports14090374
  [Full text]
- Shaw, L., & Glickman, M. (2019). Dynamic analysis of team strategy in
  professional football. *Barça Sports Analytics Summit*. [Abstract]
- Vogelbein, M., Nopp, S., & Hökelmann, A. (2014). Defensive transition in
  soccer – are prompt possession regains a measure of success? A quantitative
  analysis of German Fußball-Bundesliga 2010/2011. *Journal of Sports
  Sciences*, 32, 1076–1083. https://doi.org/10.1080/02640414.2013.879671
  [Abstract; issue number differs between indexes, to be checked]
- Welch, M., Schaerf, T. M., & Murphy, A. (2021). Collective states and their
  transitions in football. *PLOS ONE*, 16, e0251970.
  https://doi.org/10.1371/journal.pone.0251970 [Abstract; main findings
  checked from the article page, not read in full]
- Zhang, G., Kempe, M., McRobert, A., Folgado, H., & Olthof, S. B. H. (2025).
  Navigating team tactical analysis in football: An analytical pipeline
  leveraging player tracking technology. *Proceedings of the IMechE, Part P:
  Journal of Sports Engineering and Technology*.
  https://doi.org/10.1177/17543371251392456 [Full text, LJMU repository copy]
