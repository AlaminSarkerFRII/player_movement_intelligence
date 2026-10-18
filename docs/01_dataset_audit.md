# Dataset Audit: Metrica Sports Sample Data

Audit date: 2026-10-18
Source: https://github.com/metrica-sports/sample-data (commit `e706dd5`, "Added Sample Game 3")
Local path: `data/raw/metrica/` (not committed to git; 234 MB)

All numbers below were produced by inspecting the raw files with shell tools
(`head`, `wc`, `awk`). Items marked **TO VERIFY** are hypotheses that Phase 3
code must confirm.

## 1. License and terms

The repository has **no formal license file**. The README's "Legal stuff"
section says only:

- "Please be responsible with the use of this data."
- "If you use it for anything public, please aknowledge the source."

**Consequence:** We do not redistribute the raw data. The repo contains a
download instruction and acknowledges Metrica Sports in the README.

## 2. Files

| Game | Format | Files |
|---|---|---|
| 1 | CSV | `RawTrackingData_Home_Team.csv`, `RawTrackingData_Away_Team.csv`, `RawEventsData.csv` |
| 2 | CSV | same as Game 1 |
| 3 | FIFA EPTS | `metadata.xml`, `tracking.txt`, `events.json` |

Event type/subtype definitions: `documentation/events-definitions.pdf`.

## 3. Tracking data (Games 1–2, CSV)

**Header layout:** three header rows.
1. Team label (`Home` / `Away`)
2. Jersey number
3. Column names: `Period, Frame, Time [s], PlayerN, <unnamed>, ..., Ball, <unnamed>`

Each player and the ball use **two columns (x, y)**. The y column has no name,
so the loader must build names such as `Home_11_x`, `Home_11_y`.

**Coordinates:** normalized to [0, 1]. (0, 0) is top-left and (0.5, 0.5) is the
kick-off spot. The README states the pitch is 105 × 68 m.

| Property | Game 1 | Game 2 |
|---|---|---|
| Frames | 145,006 | 141,156 |
| Period 1 / Period 2 frames | 71,268 / 73,738 | 67,941 / 73,215 |
| Duration (frames × 0.04 s) | 96.7 min | 94.1 min |
| Time step between frames | always 0.04 s, so **25 Hz confirmed** | always 0.04 s, so **25 Hz confirmed** |
| Missing frame numbers | 0 | 0 |
| Ball position missing (NaN) | **39.1 %** of frames | **41.0 %** of frames |

**Players:** Substitutes are `NaN` while they are not on the pitch. In Game 2
the away team has 12 player columns, and one is named `Player 26` (with a
space) while the others have no space. This is a cleaning issue to handle.

## 4. Event data (Games 1–2, CSV)

Columns: `Team, Type, Subtype, Period, Start Frame, Start Time [s], End Frame,
End Time [s], From, To, Start X, Start Y, End X, End Y`

Event frames use the same frame index as tracking, so the two can be joined
directly.

| Type | Game 1 | Game 2 |
|---|---|---|
| PASS | 799 | 964 |
| RECOVERY | 278 | 248 |
| BALL LOST | 257 | 233 |
| CHALLENGE | 233 | 311 |
| SET PIECE | 77 | 80 |
| BALL OUT | 51 | 49 |
| SHOT | 24 | 24 |
| FAULT RECEIVED | 22 | 20 |
| CARD | 4 | 6 |
| **Total** | **1,745** | **1,935** |

`RECOVERY` and `BALL LOST` events give us candidate possession-change
moments, which the research question needs.

## 5. Game 3 (FIFA EPTS format)

- `metadata.xml`: `<FrameRate>25</FrameRate>`, `TrackingType: Optical`. Period
  boundaries: first half frames 1–69,661, second half 69,662–143,761.
- `tracking.txt`: 143,761 lines. Format: `frame:x,y;x,y;...(players):ball_x,ball_y`
- `events.json`: teams labelled "Team A" and "Team B", with player IDs.
- We will parse this with the `kloppy` library rather than writing a custom parser.

## 6. Open questions (TO VERIFY in Phase 3)

1. ~~**Why is the ball missing in about 40 % of frames?**~~ **Partly confirmed
   (Phase 3.2).** Missing ball frames agree with event-derived stoppages in
   86–95 % of frames, but not fully. See section 8.
2. ~~**Direction of play**~~ **Resolved (Phase 3.2).** Goalkeepers switch ends
   at half-time in all games. Periods are rotated 180° so the home team always
   attacks towards +x.
3. ~~**Goalkeeper identification**~~ **Resolved (Phase 3.1).** A heuristic
   (the player furthest from the centre line on average) finds Player11 and
   Player25 in Games 1–2, the first column of each file, and P3578 and P3595
   in Game 3, exactly the goalkeepers labelled in the Game 3 metadata.
4. ~~**Tracking quality**~~ **Checked (Phase 3.2).** See section 8.

## 7. Findings from loading the data (Phase 3.1)

Produced by `make interim` (summary table) and `make test-data`.

| Property | Game 1 | Game 2 | Game 3 |
|---|---|---|---|
| Frames / minutes | 145,006 / 96.7 | 141,156 / 94.1 | 143,761 / 95.8 |
| Players used (home / away) | 14 / 14 | 14 / 12 | 17 / 18 |
| Events | 1,745 | 1,935 | 3,620 |
| Ball position missing | 39.1 % | 41.0 % | 32.2 % |

- **Time column:** in the CSV, `Time [s]` runs continuously across both halves
  (period 2 starts at 2,850.76 s in Game 1). The common format recomputes
  `time_s` as seconds since period start, matching kloppy's Game 3 timestamps.
- **Substitutions:** the CSV files show 12 players on one team for exactly one
  frame at each substitution (6 team-frames in Game 1, 4 in Game 2). Game 3
  used 6–7 substitutes per team, so it may not be a match under standard
  competition rules.
- **Event vocabulary differs:** Game 3 has 1,395 `CARRY` events, a type that
  does not exist in Games 1–2. Possession logic must not depend on `CARRY`, or
  Game 3 will not be comparable with Games 1–2.
- **Positions outside the pitch:** x reaches ±57.8 m (goal line at ±52.5 m)
  and y reaches 39.3 m (touchline at ±34 m). These are plausible (players
  behind the goal or beside the touchline), but are checked again in
  preprocessing.
- **Game 3 teams:** "Team A" (`FIFATMA`) is home and "Team B" (`FIFATMB`) is away.

## 8. Findings from preprocessing (Phase 3.2)

Produced by `make preprocess`; table saved in `reports/tables/preprocessing_qc.csv`.

| | Game 1 | Game 2 | Game 3 |
|---|---|---|---|
| Periods rotated 180° | 2 | 1 | 1 |
| Player rows failing speed QC (raw > 12 m/s) | 0.014 % | 0.035 % | 0.024 % |
| Frames with ≥ 1 player failing QC | 0.30 % | 0.74 % | 0.51 % |
| Ball missing (after filling gaps ≤ 1 s) | 38.9 % | 40.8 % | 32.1 % |
| Play dead according to events | 42.5 % | 36.3 % | 31.4 % |
| Agreement: ball tracked vs event-live | 85.6 % | 86.2 % | 94.7 % |
| **Ball in play (both signals agree)** | **50.3 min** | **51.3 min** | **62.8 min** |
| Median player speed in play | 1.96 m/s | 1.84 m/s | 1.98 m/s |

**Speed outliers.** Raw speeds above 12 m/s come in short bursts (median 6
frames) at a *constant* speed, sometimes above 100 m/s. That pattern suggests
the provider linearly interpolated across tracking gaps. Many bursts occur
just after a period starts, when play is dead anyway. These rows are flagged
(`qc_ok = False`), and velocities within ±3 frames are set to missing.
Positions are not changed.

**Remaining limitation.** After QC, the median per-player top speed in play
is 9.1, 9.7 and 11.1 m/s (Games 1–3). The Game 3 value is high for
footballers, so some interpolation artifacts probably remain just below the
12 m/s threshold. Speed is not a primary outcome of this project. Any
speed-based result must be checked for sensitivity to this threshold.

**Ball in play.** Neither signal is reliable on its own.
- About 92 % of the frames where the ball is missing while events say play is
  live fall in runs longer than 5 s (up to 130 s). These are probably stoppages
  the event data does not record, such as injuries or substitutions.
- Frames where the ball is tracked while events say play is dead come in short
  runs (median about 1 s), probably small timing offsets around restarts.

**Offside** (`BALL LOST | OFFSIDE`, 1–4 per game) is also treated as a
stoppage. It was added in Phase 3.3 after offside turnovers appeared among
the open-play turnovers.

**Decision:** `in_play = event_live AND ball_tracked`. This is conservative: it
excludes uncertain frames and so reduces sample size rather than adding noise.
The 1 s gap-filling threshold is part of the sensitivity analysis.

## 9. Possession and turnovers (Phase 3.3)

Produced by `make possession`. Tables are in `reports/tables/possession_summary.csv`
and `turnover_funnel.csv`; figures are `eda_spell_durations.png` and
`eda_turnover_locations.png`.

**Event sequence at a change of possession.** Usually `BALL LOST` (team A,
recorded when A plays the ball) is followed by `RECOVERY` (team B) about 1.5 s
later, often with `CHALLENGE` events in between. So `t0` is the winning
team's first control event: a `RECOVERY` in 82–89 % of open-play turnovers.

| | Game 1 | Game 2 | Game 3 |
|---|---|---|---|
| Possession spells (with ball in play) | 342 | 333 | 375 |
| Median spell length, ball in play | 4.9 s | 4.4 s | 5.0 s |
| Home possession share | 51.0 % | 52.0 % | 51.6 % |
| Open-play turnovers | 241 | 227 | 272 |
| **Included turnovers** | **121** | **96** | **137** |

**Inclusion funnel (all games, 740 → 354).** Each rule is applied in order:
losing team had the ball ≥ 2 s (552), winning team kept it ≥ 2 s (406), at
least 3 s since the previous turnover (354), ball position known (354).

**Where the ball is won** (included turnovers, from the winning team's view):
defensive third 187, middle third 142, attacking third 25. A visible cluster
inside the defending penalty area comes from goalkeepers collecting the ball
(`RECOVERY | SAVED` and similar). These should be analysed separately or
excluded in a sensitivity check, because a goalkeeper catch is a different
situation from an outfield interception.

**Notes**
- Spells with zero in-play time (46–89 per game) are control events recorded
  while play is stopped (for example, a `RECOVERY` just after the ball went
  out). They never count as turnovers.
- One in-play frame in Game 2 (0.001 %) has no possession label.
- One `RECOVERY | GOAL` event in Game 3 has unclear meaning. It is kept, and
  its effect is negligible (1 of 354).

## 10. Conclusion

The data contains **continuous 25 Hz positions for all players and the ball,
synchronized with event data**. It is suitable for the primary research
question. The main constraints are the small sample (3 matches, anonymized
teams) and the cleaning issues listed above.
