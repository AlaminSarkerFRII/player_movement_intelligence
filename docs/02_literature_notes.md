# Literature Notes

> **Superseded (Phase 4) by [`06_literature_review.md`](06_literature_review.md).**
> This file is kept as the original Phase 1 reading log.

Status key:
- **Verified (metadata):** title, authors, venue and year confirmed from an
  online record. Full text not yet read.
- **Read:** full text read and summarized by me (the project author).
- **MUST READ:** directly affects whether our research question is novel.

No claim in the proposal may depend on a paper that is only "verified (metadata)".

## A. Core references for team spatial organization

| # | Reference | Status | Why it matters |
|---|---|---|---|
| 1 | Frencken, W., Lemmink, K., Delleman, N., & Visscher, C. (2011). Oscillations of centroid position and surface area of soccer teams in small-sided games. *European Journal of Sport Science*, 11(4), 215–223. doi:10.1080/17461391.2010.499967 | Verified (metadata) | Defines centroid and surface area as collective variables (4-vs-4 small-sided games) |
| 2 | Memmert, D., Lemmink, K. A. P. M., & Sampaio, J. (2017). Current approaches to tactical performance analyses in soccer using position data. *Sports Medicine*, 47(1), 1–10. doi:10.1007/s40279-016-0562-5 | Verified (metadata) | Overview of position-data methods, including compactness measures |
| 3 | Low, B., Coutinho, D., Gonçalves, B., Rein, R., Memmert, D., & Sampaio, J. (2020). A systematic review of collective tactical behaviours in football using positional data. *Sports Medicine*, 50(2), 343–385. | Verified (metadata) | Systematic review; tells us which metrics and contexts were already studied |
| 4 | Welch, M., Schaerf, T. M., & Murphy, A. (2021). Collective states and their transitions in football. *PLOS ONE*. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0251970 | Partly read (summary) | 2 matches, 1 team, 20 Hz. Defending phases were more compact and ordered. Grouped by phase, **not aligned to the moment of possession change** |
| 5 | Zhang, G., Kempe, M., McRobert, A., Folgado, H., & Olthof, S. B. H. (2025). Navigating team tactical analysis in football: An analytical pipeline leveraging player tracking technology. *Proc. IMechE Part P (SAGE)*. doi:10.1177/17543371251392456 | **Read (Phase 4)** | 1 match, phase averages incl. two transition phases; suggests a delayed reaction after regaining the ball. See 06 §2 |
| 6 | Serra, E., et al. (2026). "Team Synergies in Professional Football: A Goal-Referenced Performance Indicator for Rapid Ball Recovery in Negative Transitions." *Sports* (MDPI), 14(9), 374. https://www.mdpi.com/2075-4663/14/9/374 | **Read (Phase 4)** | Goal-referenced movement coherence (rβ) vs recovery speed; no shape time course. See 06 §3 |

## B. Tracking-data methods (data science side)

| # | Reference | Status | Why it matters |
|---|---|---|---|
| 7 | Bialkowski, A., Lucey, P., Carr, P., Yue, Y., Sridharan, S., & Matthews, I. (2014). Large-scale analysis of soccer matches using spatiotemporal tracking data. *IEEE ICDM*, 725–730. doi:10.1109/ICDM.2014.133 | Verified (metadata) | Role-based representation; formation discovery from tracking data |
| 8 | Shaw, L., & Glickman, M. (2019). Dynamic analysis of team strategy in professional football. *Barça Sports Analytics Summit*. [PDF](https://www.sportperformanceanalysis.com/s/Dynamic-analysis-of-team-strategy-in-professional-football-By-Laurie-Shaw-And-Mark-Glickman.pdf) | Verified (metadata) | Separate in-possession and out-of-possession formations |
| 9 | Bassek, M., Rein, R., Weber, H., & Memmert, D. (2025). An integrated dataset of spatiotemporal and event data in elite soccer. *Scientific Data*. doi:10.1038/s41597-025-04505-y | Verified (metadata) | Our replication dataset (CC-BY 4.0) |

## C. To add later (pose-estimation extension)

- SkillCorner Open Data documentation (3D body pose, 29 joints): https://github.com/SkillCorner/opendata
- Body-orientation / pose-in-soccer papers: search during the extension phase.

## Current assessment of novelty (honest)

- Static differences in team shape between attacking and defending are
  **well documented** (refs 1–4). Our H1 is a replication.
- Analysis **aligned to the exact moment of turnover** (the time course over
  the seconds afterwards) was **not found** in refs 1–4. It **may** exist in
  refs 5–6, which we have not read yet.
- **We claim no research gap until refs 5 and 6 are read.** If they already
  answer H2, our contribution becomes (a) independent replication on two open
  datasets and (b) a fully reproducible pipeline. That is still a legitimate
  portfolio contribution.
