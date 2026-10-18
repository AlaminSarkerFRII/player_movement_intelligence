"""Loader for the IDSSE dataset (Bassek et al., 2025, Sci Data 12:195; CC-BY 4.0).

DFL position and event XML files are parsed with kloppy. Provider-specific
steps, documented in docs/01_dataset_audit.md (IDSSE section):

- **Frame numbers** restart each half in DFL data (10000..., 100000...); they
  are renumbered consecutively across the match.
- **Event vocabulary** is mapped to the control-event names used by the
  possession code (see ``map_event``).
- **Event timing:** raw DFL event timestamps lag the tracking data. A
  constant lag per half is estimated by matching pass/shot locations to the
  tracked ball position, then removed (``idsse.sync_events`` in the config).
- **Provider possession:** DFL tracking labels the team in possession on every
  frame. ``PROVIDER POSSESSION`` events are emitted where that label changes and
  where play restarts, so the same possession code can use it as an alternative
  (independent of event timing).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pmi.config import Config
from pmi.io.common import MatchData, build_match

SYNC_TYPES = ("PASS", "SET PIECE", "SHOT")  # events whose location is the ball's location


def _file(root: Path, prefix: str, code: str) -> Path:
    matches = sorted(root.glob(f"{prefix}_*_DFL-MAT-{code}.xml"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected one {prefix} file for {code} in {root} (run `make data`)"
        )
    return matches[0]


# ---------------------------------------------------------------- events


def map_event(name: str, event_name: str, raw: dict, team_id: str | None,
              set_piece: str | None) -> tuple[str, str | None, str | None]:
    """Map one kloppy/DFL event to (type, subtype, team id).

    =================  ==================================================
    our type           DFL source
    =================  ==================================================
    PASS               Play (pass or cross) in open play
    SET PIECE          Play with a set-piece qualifier (subtype = kind)
    SHOT               ShotAtGoal
    RECOVERY           BallClaiming
    DUEL WON           TacklingGame whose winner ends with ball control
    DUEL               other TacklingGame (not a control event)
    OTHER BALL ACTION  OtherBallAction (a touch by a player of that team)
    BALL OUT           kloppy's ball-out marker
    =================  ==================================================
    Anything else keeps its DFL name in capitals and is not a control event.
    """
    if name == "PASS":
        return ("SET PIECE", set_piece, team_id) if set_piece else ("PASS", None, team_id)
    if name in ("SHOT", "RECOVERY"):
        return name, None, team_id
    if name == "BALL_OUT":
        return "BALL OUT", None, team_id
    if event_name == "TacklingGame":
        winner = raw.get("WinnerTeam")
        if raw.get("WinnerRole") == "withBallControl" and winner:
            return "DUEL WON", raw.get("Type"), winner
        return "DUEL", raw.get("Type"), winner
    if event_name == "OtherBallAction":
        return "OTHER BALL ACTION", None, team_id
    return (event_name or name).upper(), None, team_id


def read_events(event_path: Path, meta_path: Path, grounds: dict[str, str],
                period_start: dict[int, int], fps: int) -> pd.DataFrame:
    """Read DFL events in [0, 1] coordinates with frames from their timestamps (unsynced)."""
    from kloppy import sportec

    dataset = sportec.load_event(event_data=event_path, meta_data=meta_path,
                                 coordinates="kloppy")
    rows = []
    for e in dataset.events:
        sp = next((q.value.name for q in (e.qualifiers or [])
                   if type(q).__name__ == "SetPieceQualifier"), None)
        raw = e.raw_event if isinstance(e.raw_event, dict) else {}
        etype, sub, team_id = map_event(e.event_type.name, getattr(e, "event_name", ""), raw,
                                        e.team.team_id if e.team else None, sp)
        player = raw.get("Winner") if etype.startswith("DUEL") else (
            e.player.player_id if e.player else None)
        end = getattr(e, "receiver_coordinates", None)
        rows.append({
            "period": e.period.id,
            "frame": period_start[e.period.id] + int(round(e.timestamp.total_seconds() * fps)),
            "team": grounds.get(team_id),
            "type": etype, "subtype": sub, "player_id": player,
            "to_player_id": getattr(getattr(e, "receiver_player", None), "player_id", None),
            "x": e.coordinates.x if e.coordinates else np.nan,
            "y": e.coordinates.y if e.coordinates else np.nan,
            "end_x": end.x if end else np.nan, "end_y": end.y if end else np.nan,
        })
    ev = pd.DataFrame(rows)
    ev["end_frame"] = pd.array([pd.NA] * len(ev), dtype="Int64")
    return ev


def estimate_lag(events: pd.DataFrame, ball: pd.DataFrame, max_lag: int,
                 length_m: float, width_m: float) -> dict[int, dict[str, float]]:
    """Per period, the frame shift that best aligns event locations with the ball.

    For each candidate shift, the median distance between pass/shot locations
    and the tracked ball at (event frame + shift) is computed; the shift with
    the smallest median wins. Both inputs use [0, 1] coordinates.
    """
    out = {}
    ev = events[events["type"].isin(SYNC_TYPES) & events["x"].notna()]
    for period, e in ev.groupby("period"):
        b = ball[ball["period"] == period]
        f0, n = int(b["frame"].min()), len(b)
        bx, by = b["x"].to_numpy() * length_m, b["y"].to_numpy() * width_m
        fi = e["frame"].to_numpy() - f0
        ex, ey = e["x"].to_numpy() * length_m, e["y"].to_numpy() * width_m
        lags = np.arange(-max_lag, max_lag + 1)
        med = np.array([
            np.nanmedian(np.hypot(bx[np.clip(fi + lag, 0, n - 1)] - ex,
                                  by[np.clip(fi + lag, 0, n - 1)] - ey))
            for lag in lags
        ])
        best = int(lags[np.argmin(med)])
        out[int(period)] = {"lag_frames": best, "median_dist_m": float(med.min()),
                            "median_dist_unsynced_m": float(med[lags == 0][0]),
                            "n_events": len(e)}
    return out


def provider_possession_events(period: np.ndarray, frame: np.ndarray, alive: np.ndarray,
                               owner: np.ndarray) -> pd.DataFrame:
    """``PROVIDER POSSESSION`` events where the provider's possession label changes
    during play, and where play (re)starts, with the team then in possession."""
    prev_owner = np.r_[None, owner[:-1]]
    prev_alive = np.r_[False, alive[:-1]]
    new_period = np.r_[True, period[1:] != period[:-1]]
    change = alive & pd.notna(owner) & (
        (owner != prev_owner) | ~prev_alive | new_period
    )
    idx = np.flatnonzero(change)
    return pd.DataFrame({
        "period": period[idx], "frame": frame[idx], "team": owner[idx],
        "type": "PROVIDER POSSESSION", "subtype": None, "player_id": None,
        "to_player_id": None, "x": np.nan, "y": np.nan, "end_x": np.nan, "end_y": np.nan,
        "end_frame": pd.array([pd.NA] * len(idx), dtype="Int64"),
    })


# ---------------------------------------------------------------- loader


def load_match(code: str, cfg: Config) -> MatchData:
    """Load one IDSSE match (DFL match id such as ``J03WMX``) into the common format."""
    from kloppy import sportec

    root = cfg.path("raw") / "idsse"
    meta_path = _file(root, "DFL_02_01_matchinformation", code)
    fps = cfg["tracking"]["fps"]

    dataset = sportec.load_tracking(
        raw_data=_file(root, "DFL_04_03_positions_raw_observed", code),
        meta_data=meta_path, coordinates="kloppy",
    )
    md = dataset.metadata
    if (md.pitch_dimensions.pitch_length, md.pitch_dimensions.pitch_width) != (
            cfg["pitch"]["length_m"], cfg["pitch"]["width_m"]):
        raise ValueError(f"{code}: pitch size differs from the config")
    grounds = {t.team_id: str(t.ground).lower() for t in md.teams}
    players = {p.player_id: grounds[t.team_id] for t in md.teams for p in t.players}
    provider_gks = sorted(
        p.player_id for t in md.teams for p in t.players
        if p.starting_position is not None and p.starting_position.name == "Goalkeeper"
    )
    df = dataset.to_df()
    del dataset

    df = df.sort_values(["period_id", "frame_id"], ignore_index=True)
    df["frame"] = np.arange(1, len(df) + 1)  # consecutive across halves
    players = {pid: team for pid, team in players.items() if f"{pid}_x" in df.columns}
    cols = ["ball_x", "ball_y"] + [f"{pid}_{a}" for pid in players for a in ("x", "y")]
    wide = df[["period_id", "frame", *cols]].rename(columns={"period_id": "period"})
    wide[cols] = wide[cols].astype(float)
    alive = (df["ball_state"].astype(str) == "alive").to_numpy()
    owner = df["ball_owning_team_id"].astype(object).map(grounds).to_numpy(dtype=object)
    starts = wide.groupby("period")["frame"].min().to_dict()

    events = read_events(_file(root, "DFL_03_02_events_raw", code), meta_path, grounds,
                         starts, fps)
    ball_norm = wide[["period", "frame"]].assign(x=wide["ball_x"], y=wide["ball_y"])
    lags = estimate_lag(events, ball_norm, int(cfg["idsse"]["max_sync_lag_s"] * fps),
                        cfg["pitch"]["length_m"], cfg["pitch"]["width_m"])
    if cfg["idsse"]["sync_events"]:
        shift = events["period"].map({p: v["lag_frames"] for p, v in lags.items()}).fillna(0)
        events["frame"] = events["frame"] + shift.astype(int)
    lo, hi = int(wide["frame"].min()), int(wide["frame"].max())
    n_outside = int((~events["frame"].between(lo, hi)).sum())
    events = events[events["frame"].between(lo, hi)]

    provider = provider_possession_events(wide["period"].to_numpy(), wide["frame"].to_numpy(),
                                          alive, owner)
    events = pd.concat([events, provider], ignore_index=True).sort_values(
        "frame", kind="stable", ignore_index=True)

    meta: dict[str, Any] = {
        "provider_goalkeepers": provider_gks, "sync_lags": lags,
        "events_outside_tracking": n_outside,
    }
    return build_match(f"idsse_{code}", wide, players, events, meta, cfg,
                       ball_extra={"alive": alive, "provider_possession": owner})
