"""Common data format shared by all dataset loaders.

Every loader converts its provider format into three long-format tables:

- ``tracking``: one row per player per frame (only frames where the player is on the pitch)
- ``ball``: one row per frame (NaN position where the ball is not tracked)
- ``events``: one row per event

Coordinate convention (all tables): meters, origin at the centre spot, ``x``
along the pitch (goal to goal), ``y`` across the pitch, positive ``y`` towards
the top of the provider's image. Directions of play are *not* normalized here;
that is a preprocessing step.

``time_s`` is seconds since the start of the period, computed from frame numbers
so it is identical in definition across providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pmi.config import Config

TRACKING_COLUMNS = [
    "match_id", "period", "frame", "time_s", "team", "player_id", "is_goalkeeper", "x", "y",
]
BALL_COLUMNS = ["match_id", "period", "frame", "time_s", "x", "y"]
EVENT_COLUMNS = [
    "match_id", "period", "frame", "time_s", "end_frame", "end_time_s", "team",
    "type", "subtype", "player_id", "to_player_id", "x", "y", "end_x", "end_y",
]
TEAMS = ("home", "away")
TABLES = ("tracking", "ball", "events")


@dataclass
class MatchData:
    """One match in the common format."""

    match_id: str
    fps: int
    tracking: pd.DataFrame
    ball: pd.DataFrame
    events: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        validate_match(self)


def normalized_to_meters(
    x: np.ndarray, y: np.ndarray, length_m: float, width_m: float
) -> tuple[np.ndarray, np.ndarray]:
    """Convert [0, 1] coordinates (origin top-left, y pointing down) to centred meters (y up)."""
    return (np.asarray(x) - 0.5) * length_m, (0.5 - np.asarray(y)) * width_m


def period_start_frames(frames: pd.Series, periods: pd.Series) -> dict[int, int]:
    """First tracking frame of each period."""
    return frames.groupby(periods).min().to_dict()


def frames_to_period_time(
    frames: pd.Series, periods: pd.Series, starts: dict[int, int], fps: int
) -> pd.Series:
    """Seconds since period start for each frame."""
    return (frames - periods.map(starts)) / fps


def wide_to_long(
    wide: pd.DataFrame, players: dict[str, str], match_id: str, fps: int
) -> pd.DataFrame:
    """Reshape a one-row-per-frame table into one row per player per frame.

    ``wide`` needs ``period``, ``frame`` and ``{player_id}_x`` / ``{player_id}_y``
    columns; ``players`` maps player_id to team. Frames where a player has no
    position (not on the pitch) are dropped.
    """
    starts = period_start_frames(wide["frame"], wide["period"])
    frames = wide["frame"].to_numpy()
    periods = wide["period"].to_numpy()
    times = frames_to_period_time(wide["frame"], wide["period"], starts, fps).to_numpy()

    parts = []
    for pid, team in players.items():
        x = wide[f"{pid}_x"].to_numpy(dtype=float)
        y = wide[f"{pid}_y"].to_numpy(dtype=float)
        on = ~(np.isnan(x) | np.isnan(y))
        parts.append(pd.DataFrame({
            "period": periods[on], "frame": frames[on], "time_s": times[on],
            "team": team, "player_id": pid, "x": x[on], "y": y[on],
        }))
    long = pd.concat(parts, ignore_index=True)
    long.insert(0, "match_id", match_id)
    long["is_goalkeeper"] = False
    long = long.sort_values(["frame", "team", "player_id"], ignore_index=True)
    return long[TRACKING_COLUMNS]


def assign_goalkeepers(tracking: pd.DataFrame, min_share: float = 0.5) -> pd.DataFrame:
    """Mark one goalkeeper per team and period.

    Heuristic: among players on the pitch for at least ``min_share`` of the
    period, the goalkeeper is the one whose mean x is furthest from the centre
    line (goalkeepers stay near their own goal). A goalkeeper substituted
    mid-period is not detected. The heuristic is checked against provider labels
    in the tests.
    """
    stats = (
        tracking.groupby(["period", "team", "player_id"], observed=True)["x"]
        .agg(["mean", "size"])
        .reset_index()
    )
    period_frames = tracking.groupby("period")["frame"].nunique()
    stats = stats[stats["size"] >= min_share * stats["period"].map(period_frames)]
    stats["abs_mean"] = stats["mean"].abs()
    gks = stats.loc[stats.groupby(["period", "team"], observed=True)["abs_mean"].idxmax()]

    is_gk = np.zeros(len(tracking), dtype=bool)
    for row in gks.itertuples():
        is_gk |= (
            (tracking["period"] == row.period)
            & (tracking["team"] == row.team)
            & (tracking["player_id"] == row.player_id)
        ).to_numpy()
    tracking = tracking.copy()
    tracking["is_goalkeeper"] = is_gk
    return tracking


def build_match(
    match_id: str,
    wide: pd.DataFrame,
    players: dict[str, str],
    events: pd.DataFrame,
    meta: dict[str, Any],
    cfg: Config,
    ball_extra: dict[str, pd.Series] | None = None,
) -> MatchData:
    """Turn a loader's provider-neutral pieces into a :class:`MatchData`.

    ``wide`` has ``period``, ``frame`` (consecutive within the match) and
    ``{key}_x/_y`` columns in [0, 1] coordinates (origin top-left, y down) for
    the ball and every player; ``events`` uses the same coordinates.
    ``ball_extra`` adds per-frame columns to the ball table (e.g. provider ball status).
    """
    fps = cfg["tracking"]["fps"]
    length, width = cfg["pitch"]["length_m"], cfg["pitch"]["width_m"]
    wide = wide.copy()
    for key in ["ball", *players]:
        wide[f"{key}_x"], wide[f"{key}_y"] = normalized_to_meters(
            wide[f"{key}_x"], wide[f"{key}_y"], length, width
        )
    starts = period_start_frames(wide["frame"], wide["period"])

    tracking = assign_goalkeepers(wide_to_long(wide, players, match_id, fps))

    ball = pd.DataFrame({
        "match_id": match_id,
        "period": wide["period"].to_numpy(),
        "frame": wide["frame"].to_numpy(),
        "time_s": frames_to_period_time(wide["frame"], wide["period"], starts, fps).to_numpy(),
        "x": wide["ball_x"].to_numpy(),
        "y": wide["ball_y"].to_numpy(),
    })
    for name, values in (ball_extra or {}).items():
        ball[name] = np.asarray(values)

    events = events.copy()
    events.insert(0, "match_id", match_id)
    events["time_s"] = frames_to_period_time(events["frame"], events["period"], starts, fps)
    events["end_time_s"] = frames_to_period_time(
        events["end_frame"].astype(float), events["period"], starts, fps
    )
    events["x"], events["y"] = normalized_to_meters(events["x"], events["y"], length, width)
    events["end_x"], events["end_y"] = normalized_to_meters(
        events["end_x"], events["end_y"], length, width
    )

    return MatchData(
        match_id=match_id, fps=fps, tracking=tracking, ball=ball,
        events=events[EVENT_COLUMNS], meta={"period_start_frames": starts, **meta},
    )


def _require_columns(df: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def validate_match(m: MatchData) -> None:
    """Raise ``ValueError`` if a match violates the common format."""
    _require_columns(m.tracking, TRACKING_COLUMNS, "tracking")
    _require_columns(m.ball, BALL_COLUMNS, "ball")
    _require_columns(m.events, EVENT_COLUMNS, "events")

    teams = set(m.tracking["team"].unique()) | set(m.events["team"].dropna().unique())
    if not teams <= set(TEAMS):
        raise ValueError(f"unexpected team labels: {teams - set(TEAMS)}")
    if m.tracking.duplicated(["frame", "player_id"]).any():
        raise ValueError("tracking: duplicate (frame, player_id) rows")
    if m.ball["frame"].duplicated().any():
        raise ValueError("ball: duplicate frames")

    gk_counts = (
        m.tracking[m.tracking["is_goalkeeper"]]
        .groupby(["period", "team"], observed=True)["player_id"].nunique()
    )
    if len(gk_counts) != 2 * m.tracking["period"].nunique() or (gk_counts != 1).any():
        raise ValueError(f"expected exactly one goalkeeper per team and period, got\n{gk_counts}")

    lo, hi = m.ball["frame"].min(), m.ball["frame"].max()
    if not m.events["frame"].between(lo, hi).all():
        raise ValueError("events: frames outside the tracking frame range")


def summarize_match(m: MatchData) -> dict[str, Any]:
    """One-row summary used to check loaded data against the dataset audit."""
    gks = (
        m.tracking[m.tracking["is_goalkeeper"]]
        .groupby(["team", "period"], observed=True)["player_id"].first()
    )
    return {
        "match_id": m.match_id,
        "frames": m.ball["frame"].nunique(),
        "minutes": round(m.ball["frame"].nunique() / m.fps / 60, 1),
        "players_home": m.tracking.loc[m.tracking["team"] == "home", "player_id"].nunique(),
        "players_away": m.tracking.loc[m.tracking["team"] == "away", "player_id"].nunique(),
        "gk_home": "/".join(gks.get("home", pd.Series(dtype=str)).astype(str).unique()),
        "gk_away": "/".join(gks.get("away", pd.Series(dtype=str)).astype(str).unique()),
        "events": len(m.events),
        "ball_missing_pct": round(100 * m.ball["x"].isna().mean(), 1),
        "x_range_m": (round(m.tracking["x"].min(), 1), round(m.tracking["x"].max(), 1)),
        "y_range_m": (round(m.tracking["y"].min(), 1), round(m.tracking["y"].max(), 1)),
    }


def write_interim(m: MatchData, cfg: Config) -> list[Path]:
    """Write the three tables to ``data/interim/{match_id}_{table}.parquet``."""
    out = cfg.path("interim")
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for table in TABLES:
        path = out / f"{m.match_id}_{table}.parquet"
        getattr(m, table).to_parquet(path, index=False)
        paths.append(path)
    return paths


def read_interim(match_id: str, cfg: Config) -> MatchData:
    """Read a match previously written by :func:`write_interim`."""
    src = cfg.path("interim")
    tables = {t: pd.read_parquet(src / f"{match_id}_{t}.parquet") for t in TABLES}
    return MatchData(match_id=match_id, fps=cfg["tracking"]["fps"], **tables)
