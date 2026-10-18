"""Preprocessing: direction of play, velocities with quality control, ball in play.

Input is a :class:`~pmi.io.common.MatchData` in the common format. Output is a
:class:`ProcessedMatch` with:

- ``tracking``: positions with the home team always attacking towards +x,
  plus ``vx``, ``vy``, ``speed`` (m/s) and a per-row ``qc_ok`` flag
- ``frames``: one row per frame with the ball position, ``ball_tracked``,
  ``event_live``, ``in_play`` and a frame-level ``qc_ok`` flag
- ``events``: events in the same (flipped) coordinates
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from pmi.config import Config
from pmi.io.common import MatchData

# ---------------------------------------------------------------- direction


def home_attack_sign(tracking: pd.DataFrame) -> dict[int, int]:
    """+1 if the home team attacks towards +x in a period, else -1.

    Uses the home goalkeeper's mean x: a goalkeeper defending the goal at -x
    means the team attacks towards +x.
    """
    gk = tracking[tracking["is_goalkeeper"] & (tracking["team"] == "home")]
    mean_x = gk.groupby("period")["x"].mean()
    return {int(p): (1 if x < 0 else -1) for p, x in mean_x.items()}


def _rotate(df: pd.DataFrame, rows: pd.Series, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    df = df.copy()
    for cx, cy in pairs:
        df.loc[rows, cx] = -df.loc[rows, cx]
        df.loc[rows, cy] = -df.loc[rows, cy]
    return df


def normalize_direction(match: MatchData) -> MatchData:
    """Rotate periods by 180° so the home team always attacks towards +x.

    A 180° rotation (x -> -x, y -> -y) keeps the pitch's left/right sides
    consistent from each team's point of view, unlike a mirror on x only.
    """
    signs = home_attack_sign(match.tracking)
    flipped = [p for p, s in signs.items() if s < 0]
    xy = [("x", "y")]
    tracking = _rotate(match.tracking, match.tracking["period"].isin(flipped), xy)
    ball = _rotate(match.ball, match.ball["period"].isin(flipped), xy)
    events = _rotate(
        match.events, match.events["period"].isin(flipped), [("x", "y"), ("end_x", "end_y")]
    )
    return replace(
        match, tracking=tracking, ball=ball, events=events,
        meta={**match.meta, "flipped_periods": flipped},
    )


# ---------------------------------------------------------------- velocity


def add_velocity(
    tracking: pd.DataFrame, fps: int, window_s: float, polyorder: int, max_speed: float
) -> pd.DataFrame:
    """Add smoothed ``vx``, ``vy``, ``speed`` and a ``qc_ok`` flag per row.

    Velocities are the first derivative of a Savitzky-Golay filter fitted to
    each player's contiguous position segment. A row fails QC when the raw
    frame-to-frame speed exceeds ``max_speed``; velocities within half a
    window of a failed row are set to NaN because the filter would spread the
    error. Positions are kept unchanged.
    """
    window = int(round(window_s * fps)) | 1  # odd number of frames
    half = window // 2
    t = tracking.sort_values(["player_id", "frame"], ignore_index=True)

    new_seg = (
        t["player_id"].ne(t["player_id"].shift())
        | t["period"].ne(t["period"].shift())
        | t["frame"].diff().ne(1)
    )
    seg = new_seg.cumsum().to_numpy()
    x, y = t["x"].to_numpy(), t["y"].to_numpy()

    raw_speed = np.hypot(np.diff(x, prepend=np.nan), np.diff(y, prepend=np.nan)) * fps
    raw_speed[new_seg.to_numpy()] = np.nan
    bad = raw_speed > max_speed

    vx = np.full(len(t), np.nan)
    vy = np.full(len(t), np.nan)
    blocked = np.zeros(len(t), dtype=bool)
    bounds = np.flatnonzero(np.r_[True, seg[1:] != seg[:-1], True])
    for start, stop in zip(bounds[:-1], bounds[1:], strict=True):
        if stop - start < window:
            continue  # too short to fit the filter
        sl = slice(start, stop)
        vx[sl] = savgol_filter(x[sl], window, polyorder, deriv=1, delta=1 / fps)
        vy[sl] = savgol_filter(y[sl], window, polyorder, deriv=1, delta=1 / fps)
        for i in np.flatnonzero(bad[sl]) + start:
            blocked[max(start, i - half): min(stop, i + half + 1)] = True

    vx[blocked] = np.nan
    vy[blocked] = np.nan
    t["vx"], t["vy"] = vx, vy
    t["speed"] = np.hypot(vx, vy)
    t["qc_ok"] = ~bad
    return t.sort_values(["frame", "team", "player_id"], ignore_index=True)


# ---------------------------------------------------------------- ball in play


def _run_lengths(mask: np.ndarray) -> np.ndarray:
    """Length of the True-run each element belongs to (0 for False elements)."""
    edges = np.diff(np.r_[0, mask.astype(np.int8), 0])
    starts, stops = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    out = np.zeros(len(mask), dtype=int)
    for s, e in zip(starts, stops, strict=True):
        out[s:e] = e - s
    return out


def fill_short_ball_gaps(ball: pd.DataFrame, max_gap_frames: int) -> pd.DataFrame:
    """Linearly interpolate ball gaps of at most ``max_gap_frames`` inside a period.

    Longer gaps stay NaN. Adds ``ball_tracked`` (True where the ball has a position
    after filling).
    """
    out = []
    for _, b in ball.groupby("period", sort=True):
        b = b.sort_values("frame").copy()
        missing = b["x"].isna().to_numpy()
        short = missing & (_run_lengths(missing) <= max_gap_frames)
        for c in ("x", "y"):
            filled = b[c].interpolate(limit_area="inside")
            b[c] = b[c].where(~short, filled)
        out.append(b)
    ball = pd.concat(out, ignore_index=True)
    ball["ball_tracked"] = ball["x"].notna()
    return ball


def event_live_mask(frames: pd.DataFrame, events: pd.DataFrame, cfg_bip: dict) -> np.ndarray:
    """True where the event data implies the ball is in play.

    Play is dead from each stoppage event (ball out, foul, shot out/goal, offside) until the
    next restart event (set piece or goal kick), before the first restart of a
    period, and after the last event of a period.
    """
    sub = events["subtype"].fillna("")
    stop = (
        events["type"].isin(cfg_bip["stop_types"])
        | (events["type"].eq("SHOT") & sub.str.contains("|".join(cfg_bip["stop_shot_subtypes"])))
        | sub.str.contains("|".join(cfg_bip["stop_subtypes"]))
    )
    restart = events["type"].isin(cfg_bip["restart_types"]) | sub.str.contains(
        "|".join(cfg_bip["restart_subtypes"])
    )
    live = np.ones(len(frames), dtype=bool)
    f = frames["frame"].to_numpy()
    p = frames["period"].to_numpy()

    for period, ev in events.groupby("period"):
        in_period = p == period
        restarts = np.sort(ev.loc[restart.loc[ev.index], "frame"].to_numpy())
        if len(restarts) == 0:
            live[in_period] = False
            continue
        live[in_period & (f < restarts[0])] = False
        live[in_period & (f > ev["frame"].max())] = False
        for stop_frame in ev.loc[stop.loc[ev.index], "frame"]:
            nxt = restarts[restarts >= stop_frame]
            end = nxt[0] if len(nxt) else f[in_period].max() + 1
            live[in_period & (f >= stop_frame) & (f < end)] = False
    return live


# ---------------------------------------------------------------- pipeline


@dataclass
class ProcessedMatch:
    match_id: str
    fps: int
    tracking: pd.DataFrame
    frames: pd.DataFrame
    events: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)


def preprocess_match(match: MatchData, cfg: Config) -> ProcessedMatch:
    """Run all preprocessing steps on one match."""
    trk_cfg, bip_cfg = cfg["tracking"], cfg["ball_in_play"]
    fps = match.fps
    match = normalize_direction(match)

    tracking = add_velocity(
        match.tracking, fps, trk_cfg["smoothing_window_s"],
        trk_cfg["smoothing_polyorder"], trk_cfg["max_speed_ms"],
    )

    max_gap = int(round(bip_cfg["max_ball_gap_s"] * fps))
    frames = fill_short_ball_gaps(match.ball, max_gap).rename(
        columns={"x": "ball_x", "y": "ball_y"}
    )
    frames["event_live"] = event_live_mask(frames, match.events, bip_cfg)
    frames["in_play"] = frames["event_live"] & frames["ball_tracked"]
    frame_ok = tracking.groupby("frame")["qc_ok"].all()
    frames["qc_ok"] = frames["frame"].map(frame_ok).fillna(True).astype(bool)

    return ProcessedMatch(
        match_id=match.match_id, fps=fps, tracking=tracking, frames=frames,
        events=match.events, meta=match.meta,
    )


def qc_summary(pm: ProcessedMatch) -> dict[str, Any]:
    """One row of quality-control numbers for the preprocessing report."""
    f, t = pm.frames, pm.tracking
    raw_missing = ~f["ball_tracked"]
    return {
        "match_id": pm.match_id,
        "flipped_periods": ",".join(map(str, pm.meta.get("flipped_periods", []))) or "-",
        "player_rows_failed_qc_pct": round(100 * (~t["qc_ok"]).mean(), 3),
        "frames_failed_qc_pct": round(100 * (~f["qc_ok"]).mean(), 2),
        "ball_missing_after_fill_pct": round(100 * raw_missing.mean(), 1),
        "event_dead_pct": round(100 * (~f["event_live"]).mean(), 1),
        "agreement_ball_vs_events_pct": round(
            100 * (f["ball_tracked"] == f["event_live"]).mean(), 1
        ),
        "in_play_minutes": round(f["in_play"].sum() / pm.fps / 60, 1),
        "in_play_pct": round(100 * f["in_play"].mean(), 1),
        "median_speed_in_play_ms": round(
            t.loc[t["frame"].isin(f.loc[f["in_play"], "frame"]), "speed"].median(), 2
        ),
    }


def write_processed(pm: ProcessedMatch, cfg: Config) -> None:
    out = cfg.path("processed")
    out.mkdir(parents=True, exist_ok=True)
    for table in ("tracking", "frames", "events"):
        getattr(pm, table).to_parquet(out / f"{pm.match_id}_{table}.parquet", index=False)


def read_processed(match_id: str, cfg: Config) -> ProcessedMatch:
    src = cfg.path("processed")
    tables = {
        t: pd.read_parquet(src / f"{match_id}_{t}.parquet")
        for t in ("tracking", "frames", "events")
    }
    return ProcessedMatch(match_id=match_id, fps=cfg["tracking"]["fps"], **tables)
