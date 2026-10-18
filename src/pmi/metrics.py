"""Team shape metrics per frame.

For each team in each frame, computed from outfield players only (goalkeeper
excluded when ``metrics.exclude_goalkeeper`` is true):

- ``length``: extent along the pitch, max(x) - min(x) (m)
- ``width``: extent across the pitch, max(y) - min(y) (m)
- ``area``: area of the convex hull of player positions (m²)
- ``stretch``: stretch index, the mean distance of players from the team centroid (m)
- ``centroid_x``, ``centroid_y``: mean position (m, home attacks towards +x)
- ``centroid_x_att``: centroid x from the team's own perspective (+ = towards
  the opponent's goal)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError

from pmi.possession import attacking_x

SHAPE_METRICS = ["length", "width", "area", "stretch"]


def hull_area(points: np.ndarray) -> float:
    """Convex hull area of 2-D points; 0 for collinear points, NaN for fewer than 3."""
    if len(points) < 3:
        return np.nan
    try:
        return float(ConvexHull(points).volume)  # in 2-D, "volume" is the area
    except QhullError:
        return 0.0  # all points on one line


def team_shape(tracking: pd.DataFrame, exclude_goalkeeper: bool = True) -> pd.DataFrame:
    """One row per (frame, team) with the shape metrics listed in the module docstring."""
    t = tracking[~tracking["is_goalkeeper"]] if exclude_goalkeeper else tracking
    t = t.sort_values(["frame", "team"], kind="stable", ignore_index=True)

    keys = ["match_id", "period", "frame", "team"]
    g = t.groupby(keys, observed=True, sort=False)
    out = g.agg(
        n_players=("x", "size"),
        x_min=("x", "min"), x_max=("x", "max"),
        y_min=("y", "min"), y_max=("y", "max"),
        centroid_x=("x", "mean"), centroid_y=("y", "mean"),
    ).reset_index()
    out["length"] = out["x_max"] - out["x_min"]
    out["width"] = out["y_max"] - out["y_min"]

    # Stretch index: distance of each player to their team's centroid, averaged.
    cx = g["x"].transform("mean").to_numpy()
    cy = g["y"].transform("mean").to_numpy()
    dist = np.hypot(t["x"].to_numpy() - cx, t["y"].to_numpy() - cy)
    out["stretch"] = pd.Series(dist).groupby(g.ngroup().to_numpy()).mean().to_numpy()

    # Convex hull per group (groups are contiguous because rows are sorted).
    xy = t[["x", "y"]].to_numpy()
    bounds = np.r_[0, np.cumsum(out["n_players"].to_numpy())]
    out["area"] = [hull_area(xy[a:b]) for a, b in zip(bounds[:-1], bounds[1:], strict=True)]

    out["centroid_x_att"] = attacking_x(out["centroid_x"], out["team"])
    cols = keys + ["n_players", *SHAPE_METRICS, "centroid_x", "centroid_y", "centroid_x_att"]
    return out[cols]
