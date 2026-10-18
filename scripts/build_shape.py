"""Compute per-frame team shape metrics and draw one example frame for visual checking.

Writes data/processed/{match}_shape.parquet and reports/figures/shape_example_frame.png.

Usage:
    uv run python scripts/build_shape.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import pandas as pd
from scipy.spatial import ConvexHull

from pmi import viz
from pmi.config import load_config
from pmi.metrics import team_shape


def plot_example_frame(tracking: pd.DataFrame, frames: pd.DataFrame, shape: pd.DataFrame,
                       possession: pd.DataFrame, cfg) -> None:
    """Players, convex hulls and centroids for one in-play frame: a visual metric check."""
    live = frames.merge(possession[["frame", "possession"]], on="frame")
    live = live[live["in_play"] & live["qc_ok"] & live["possession"].notna()]
    frame = int(live["frame"].iloc[len(live) // 3])  # deterministic pick
    poss = live.loc[live["frame"] == frame, "possession"].iloc[0]
    t = tracking[tracking["frame"] == frame]
    s = shape[shape["frame"] == frame].set_index("team")
    ball = frames.loc[frames["frame"] == frame, ["ball_x", "ball_y"]].iloc[0]

    fig, ax = plt.subplots(figsize=(8, 5.6))
    viz.draw_pitch(ax, cfg["pitch"]["length_m"], cfg["pitch"]["width_m"])
    for team, color in (("home", viz.SERIES[0]), ("away", viz.SERIES[1])):
        p = t[t["team"] == team]
        out = p[~p["is_goalkeeper"]]
        hull = ConvexHull(out[["x", "y"]].to_numpy())
        ax.fill(out["x"].to_numpy()[hull.vertices], out["y"].to_numpy()[hull.vertices],
                color=color, alpha=0.12, zorder=1)
        ax.scatter(out["x"], out["y"], s=60, color=color, edgecolor=viz.SURFACE, lw=1.5,
                   zorder=3)
        gk = p[p["is_goalkeeper"]]
        ax.scatter(gk["x"], gk["y"], s=60, facecolor=viz.SURFACE, edgecolor=color, lw=2,
                   zorder=3)
        r = s.loc[team]
        ax.scatter(r["centroid_x"], r["centroid_y"], marker="X", s=90, color=color,
                   edgecolor=viz.SURFACE, lw=1, zorder=4)
        state = "in possession" if team == poss else "out of possession"
        ax.plot([], [], "o", color=color, label=(
            f"{team} ({state}): length {r['length']:.0f} m, width {r['width']:.0f} m, "
            f"area {r['area']:.0f} m², stretch {r['stretch']:.1f} m"))
    ax.scatter(ball["ball_x"], ball["ball_y"], s=30, color=viz.TEXT, zorder=5)
    ax.set_title(f"Team shape in one frame (metrica_1, frame {frame}); home attacks →", pad=8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=1, fontsize=9)
    ax.text(0.99, 0.01, "filled = outfield (hull), hollow = goalkeeper (excluded), X = centroid",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
            color=viz.TEXT_SECONDARY)
    viz.save(fig, "shape_example_frame", cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    proc = cfg.path("processed")

    for game in cfg["datasets"]["metrica"]["games"]:
        match_id = f"metrica_{game}"
        print(f"Shape metrics for {match_id} ...", flush=True)
        tracking = pd.read_parquet(proc / f"{match_id}_tracking.parquet")
        shape = team_shape(tracking, cfg["metrics"]["exclude_goalkeeper"])
        shape.to_parquet(proc / f"{match_id}_shape.parquet", index=False)
        if game == cfg["datasets"]["metrica"]["games"][0]:
            viz.apply_style()
            plot_example_frame(
                tracking, pd.read_parquet(proc / f"{match_id}_frames.parquet"), shape,
                pd.read_parquet(proc / f"{match_id}_possession.parquet"), cfg,
            )


if __name__ == "__main__":
    main()
