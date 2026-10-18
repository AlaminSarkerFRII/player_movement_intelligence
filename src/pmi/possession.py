"""Possession spells and open-play turnovers, derived from event data.

Definitions (see docs/03_research_proposal.md, section 6):

- **Control event:** an event showing which team has the ball at that moment
  (``possession.control_event_types`` in the config). ``CARRY`` is excluded
  because only Metrica Game 3 has it.
- **Possession spell:** consecutive control events by one team with the ball
  in play throughout. A spell starts at its first control event and ends just
  before the next spell starts or when play stops, whichever is first.
- **Open-play turnover:** a spell that directly follows a spell of the other
  team with no stoppage in between. ``t0`` is the winning team's first control
  event, usually a ``RECOVERY``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pmi.config import Config


def _next_true(mask: np.ndarray) -> np.ndarray:
    """For each index, the index of the next True at or after it (len(mask) if none)."""
    n = len(mask)
    idx = np.where(mask, np.arange(n), n)
    return np.minimum.accumulate(idx[::-1])[::-1]


def attacking_x(x: pd.Series | np.ndarray, team: pd.Series | np.ndarray) -> np.ndarray:
    """x from a team's own perspective (+x = towards the opponent's goal).

    Assumes direction is normalized so the home team attacks towards +x.
    """
    return np.where(np.asarray(team) == "home", 1.0, -1.0) * np.asarray(x, dtype=float)


def pitch_third(x_att: np.ndarray, length_m: float) -> np.ndarray:
    """'defensive' / 'middle' / 'attacking' third from a team's own perspective."""
    edge = length_m / 6  # thirds split at ±17.5 m on a 105 m pitch
    return np.select([x_att < -edge, x_att > edge], ["defensive", "attacking"], "middle")


def possession_spells(
    events: pd.DataFrame, frames: pd.DataFrame, control_types: list[str], fps: int
) -> pd.DataFrame:
    """Build possession spells for one match.

    ``frames`` must contain every frame (consecutive numbers) with ``period``
    and ``in_play``.
    """
    frames = frames.sort_values("frame", ignore_index=True)
    f0 = int(frames["frame"].iloc[0])
    if not frames["frame"].diff().dropna().eq(1).all():
        raise ValueError("frames must be consecutive")
    in_play = frames["in_play"].to_numpy()
    n = len(frames)
    dead_cum = np.cumsum(~in_play)
    next_dead = _next_true(~in_play)
    next_play = _next_true(in_play)
    period_end = frames.groupby("period")["frame"].max().to_dict()

    ctrl = (
        events[events["type"].isin(control_types)]
        .sort_values("frame", kind="stable")
        .reset_index(drop=True)
    )
    i = ctrl["frame"].to_numpy() - f0
    prev_i = np.r_[i[0], i[:-1]]
    dead_between = (dead_cum[i] - dead_cum[prev_i]) > 0
    team_change = ctrl["team"].ne(ctrl["team"].shift()).to_numpy()
    period_change = ctrl["period"].ne(ctrl["period"].shift()).to_numpy()
    new_spell = team_change | period_change | dead_between
    new_spell[0] = True
    ctrl["spell_id"] = np.cumsum(new_spell) - 1
    ctrl["open_play_change"] = team_change & ~period_change & ~dead_between

    spells = ctrl.groupby("spell_id").agg(
        match_id=("match_id", "first"),
        period=("period", "first"),
        team=("team", "first"),
        start_frame=("frame", "first"),
        start_type=("type", "first"),
        start_subtype=("subtype", "first"),
        start_player=("player_id", "first"),
        n_events=("type", "size"),
        open_play_change=("open_play_change", "first"),
    ).reset_index()
    spells.loc[0, "open_play_change"] = False

    next_start = spells["start_frame"].shift(-1)
    same_period = spells["period"].shift(-1).eq(spells["period"])
    limit = np.where(same_period, next_start, spells["period"].map(period_end) + 1).astype(int)
    start_i = spells["start_frame"].to_numpy() - f0
    first_play = next_play[np.minimum(start_i, n - 1)]
    play_stops = np.where(first_play < n, next_dead[np.minimum(first_play, n - 1)], n)
    stop = np.minimum(limit - f0, play_stops)
    end_i = np.maximum(stop - 1, start_i)  # spell always contains its start frame
    spells["end_frame"] = (end_i + f0).astype(int)
    spells["in_play_s"] = [
        in_play[s:e + 1].sum() / fps for s, e in zip(start_i, end_i, strict=True)
    ]
    ends_by_turnover = spells["open_play_change"].shift(-1, fill_value=False)
    spells["end_reason"] = np.where(ends_by_turnover, "turnover", "stoppage")
    return spells


def frame_possession(spells: pd.DataFrame, frames: pd.DataFrame) -> pd.DataFrame:
    """Per-frame table: ``spell_id`` and ``possession`` team (None when out of play)."""
    out = frames[["match_id", "period", "frame", "in_play"]].copy()
    f0 = int(out["frame"].iloc[0])
    sid = np.full(len(out), None, dtype=object)
    team = np.full(len(out), None, dtype=object)
    for s in spells.itertuples():
        sl = slice(s.start_frame - f0, s.end_frame - f0 + 1)
        sid[sl] = s.spell_id
        team[sl] = s.team
    out["spell_id"] = pd.array(sid, dtype="Int64")
    out["possession"] = team
    out.loc[~out["in_play"], ["spell_id", "possession"]] = [pd.NA, None]
    return out.drop(columns="in_play")


def find_turnovers(
    spells: pd.DataFrame, frames: pd.DataFrame, events: pd.DataFrame, cfg: Config
) -> pd.DataFrame:
    """One row per open-play turnover, with the inclusion filters as columns.

    Filters are recorded rather than applied, so the analysis can report how many
    turnovers each rule removes. ``included`` combines all of them.
    """
    pos_cfg = cfg["possession"]
    fps = cfg["tracking"]["fps"]
    prev = spells.shift(1)
    to = spells[spells["open_play_change"]].copy()
    p = prev.loc[to.index]

    to = to.assign(
        t0_frame=to["start_frame"],
        won_team=to["team"],
        lost_team=p["team"],
        prev_spell_s=p["in_play_s"].astype(float),
        next_spell_s=to["in_play_s"],
        trigger=to["start_type"],
        trigger_subtype=to["start_subtype"],
        trigger_player_id=to["start_player"],
    )
    # Seconds since the previous open-play turnover in the same period.
    gap = to.groupby("period")["t0_frame"].diff() / fps
    to["gap_prev_s"] = gap

    ball = frames.set_index("frame")[["ball_x", "ball_y"]]
    to["ball_x"] = ball["ball_x"].reindex(to["t0_frame"]).to_numpy()
    to["ball_y"] = ball["ball_y"].reindex(to["t0_frame"]).to_numpy()
    to["x_att_won"] = attacking_x(to["ball_x"], to["won_team"])
    to["zone_won"] = pitch_third(to["x_att_won"], cfg["pitch"]["length_m"])
    to.loc[to["ball_x"].isna(), "zone_won"] = None

    min_len = pos_cfg["min_possession_length_s"]
    to["ok_prev_spell"] = to["prev_spell_s"] >= min_len
    to["ok_next_spell"] = to["next_spell_s"] >= min_len
    min_gap = pos_cfg["min_gap_between_turnovers_s"]
    to["ok_gap"] = to["gap_prev_s"].isna() | (to["gap_prev_s"] >= min_gap)
    to["ok_ball"] = to["ball_x"].notna()
    to["included"] = to[["ok_prev_spell", "ok_next_spell", "ok_gap", "ok_ball"]].all(axis=1)

    cols = [
        "match_id", "period", "t0_frame", "won_team", "lost_team", "trigger", "trigger_subtype",
        "trigger_player_id",
        "prev_spell_s", "next_spell_s", "gap_prev_s", "ball_x", "ball_y", "x_att_won",
        "zone_won", "ok_prev_spell", "ok_next_spell", "ok_gap", "ok_ball", "included",
    ]
    return to[cols].reset_index(drop=True)


def turnover_funnel(turnovers: pd.DataFrame) -> pd.DataFrame:
    """How many turnovers survive each inclusion rule, applied in order."""
    steps = [
        ("open-play turnovers", None),
        ("losing team had the ball >= min length", "ok_prev_spell"),
        ("winning team kept the ball >= min length", "ok_next_spell"),
        (">= min gap since previous turnover", "ok_gap"),
        ("ball position known at t0", "ok_ball"),
    ]
    keep = pd.Series(True, index=turnovers.index)
    rows = []
    for label, col in steps:
        if col:
            keep &= turnovers[col]
        rows.append({"step": label, "n": int(keep.sum())})
    return pd.DataFrame(rows)
