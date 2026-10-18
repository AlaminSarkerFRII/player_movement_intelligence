"""H1: compare team shape in vs out of possession (spell level, mixed models).

Writes:
    reports/tables/h1_spell_table.csv       one row per (spell, team): the analysed data
    reports/tables/h1_team_match_summary.csv
    reports/tables/h1_models.csv            estimates, CIs, p-values for every variant
    reports/figures/h1_shape_by_state.png

Usage:
    uv run python scripts/run_h1.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pmi import viz
from pmi.analysis.static import run_h1, spell_shape_table, team_match_summary
from pmi.config import load_config

LABELS = {
    "length": "Length (m)",
    "width": "Width (m)",
    "area": "Convex-hull area (m²)",
    "stretch": "Stretch index (m)",
}


def plot_dumbbells(summary: pd.DataFrame, models: pd.DataFrame, cfg) -> None:
    """Per team-match mean in vs out of possession, one panel per metric."""
    primary = models[models["variant"] == "primary"].set_index("metric")
    order = summary.sort_values("team_match", ascending=False)
    y = np.arange(len(order))
    in_color, out_color = viz.SERIES[0], viz.SERIES[1]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.8), sharey=True)
    for ax, metric in zip(axes, LABELS, strict=True):
        a, b = order[f"{metric}_in"].to_numpy(), order[f"{metric}_out"].to_numpy()
        ax.hlines(y, b, a, color=viz.GRID, lw=2, zorder=1)
        ax.scatter(b, y, s=50, color=out_color, edgecolor=viz.SURFACE, lw=1.5, zorder=2,
                   label="out of possession")
        ax.scatter(a, y, s=50, color=in_color, edgecolor=viz.SURFACE, lw=1.5, zorder=3,
                   label="in possession")
        r = primary.loc[metric]
        ax.set_title(LABELS[metric], fontsize=10)
        ax.set_xlabel(f"Δ {r['estimate_in_minus_out']:.1f} "
                      f"[{r['ci_low']:.1f}, {r['ci_high']:.1f}]", fontsize=9)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, order["team_match"])
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2)
    fig.suptitle("Teams are larger in possession in every team-match "
                 "(spell means; Δ = mixed-model estimate, 95% CI)",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    viz.save(fig, "h1_shape_by_state", cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    proc, tables = cfg.path("processed"), cfg.path("tables")
    tables.mkdir(parents=True, exist_ok=True)

    parts = []
    for mid in cfg.match_ids:
        parts.append(spell_shape_table(
            pd.read_parquet(proc / f"{mid}_shape.parquet"),
            pd.read_parquet(proc / f"{mid}_possession.parquet"),
            pd.read_parquet(proc / f"{mid}_frames.parquet"),
            fps=cfg["tracking"]["fps"],
            min_spell_s=cfg["possession"]["min_possession_length_s"],
            required_players=cfg["metrics"]["required_players"],
            length_m=cfg["pitch"]["length_m"],
        ))
    table = pd.concat(parts, ignore_index=True)
    summary = team_match_summary(table)
    models = run_h1(table)

    table.to_csv(tables / "h1_spell_table.csv", index=False)
    summary.round(3).to_csv(tables / "h1_team_match_summary.csv", index=False)
    models.to_csv(tables / "h1_models.csv", index=False)

    viz.apply_style()
    plot_dumbbells(summary, models, cfg)

    print(f"{len(table)} spell-team rows, {table['team_match'].nunique()} team-matches")
    show = models[["variant", "metric", "estimate_in_minus_out", "ci_low", "ci_high",
                   "p_holm", "team_matches_in_gt_out", "median_cohens_d", "converged"]]
    with pd.option_context("display.width", 200, "display.float_format", "{:.3g}".format):
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
