"""Derive possession spells and open-play turnovers, and make the first EDA figures.

Writes, per match, to data/processed/:
    {match}_spells.parquet, {match}_possession.parquet, {match}_turnovers.parquet
and to reports/:
    tables/turnover_funnel.csv, tables/possession_summary.csv,
    figures/eda_spell_durations.png, figures/eda_turnover_locations.png

Usage:
    uv run python scripts/build_possession.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pmi import viz
from pmi.config import load_config
from pmi.possession import (
    find_turnovers,
    frame_possession,
    possession_spells,
    turnover_funnel,
)
from pmi.preprocessing import read_processed


def plot_spell_durations(spells: pd.DataFrame, cfg) -> None:
    """ECDF of in-play spell duration per match (log x)."""
    colors = viz.game_colors(spells["match_id"].unique().tolist())
    fig, ax = plt.subplots(figsize=(7, 4))
    for mid, s in spells[spells["in_play_s"] > 0].groupby("match_id"):
        d = np.sort(s["in_play_s"].to_numpy())
        y = np.arange(1, len(d) + 1) / len(d)
        ax.step(d, y, where="post", color=colors[mid],
                label=f"{mid}  (median {np.median(d):.1f} s, n={len(d)})")
    min_len = cfg["possession"]["min_possession_length_s"]
    ax.axvline(min_len, color=viz.TEXT_SECONDARY, lw=1, ls="--")
    ax.text(min_len * 1.08, 0.03, f"{min_len:g} s inclusion threshold", fontsize=8,
            color=viz.TEXT_SECONDARY, va="bottom")
    ax.set_xscale("log")
    ax.set_xlabel("Possession spell length, ball in play (s, log scale)")
    ax.set_ylabel("Share of spells ≤ length")
    ax.set_title("Most possession spells are short")
    ax.legend(loc="upper left", frameon=True, facecolor=viz.SURFACE, edgecolor="none",
              framealpha=1)
    viz.save(fig, "eda_spell_durations", cfg)


def plot_turnover_locations(turnovers: pd.DataFrame, cfg) -> None:
    """Where included turnovers happen, from the winning team's view (attacking right)."""
    inc = turnovers[turnovers["included"]]
    colors = viz.game_colors(turnovers["match_id"].unique().tolist())
    fig, ax = plt.subplots(figsize=(8, 5.6))
    viz.draw_pitch(ax, cfg["pitch"]["length_m"], cfg["pitch"]["width_m"])
    third = cfg["pitch"]["length_m"] / 6
    for x in (-third, third):
        ax.axvline(x, color=viz.PITCH_LINE, lw=1, ls=":", zorder=0)
    sign = np.where(inc["won_team"] == "home", 1.0, -1.0)
    for mid in sorted(inc["match_id"].unique()):
        m = (inc["match_id"] == mid).to_numpy()
        ax.scatter(inc.loc[m, "x_att_won"], sign[m] * inc.loc[m, "ball_y"], s=36,
                   color=colors[mid], edgecolor=viz.SURFACE, linewidth=1.5,
                   alpha=0.9, label=f"{mid} (n={m.sum()})", zorder=2)
    counts = inc["zone_won"].value_counts()
    for label, xc in (("defensive", -2 * third), ("middle", 0), ("attacking", 2 * third)):
        ax.text(xc, cfg["pitch"]["width_m"] / 2 + 1.2, f"{label} third: {counts.get(label, 0)}",
                ha="center", va="bottom", fontsize=9, color=viz.TEXT_SECONDARY)
    ax.annotate("", xy=(20, -38.5), xytext=(-20, -38.5),
                arrowprops={"arrowstyle": "->", "color": viz.TEXT_SECONDARY})
    ax.text(0, -40.5, "winning team attacks →", ha="center", va="top", fontsize=8,
            color=viz.TEXT_SECONDARY)
    ax.set_ylim(-44, 38)
    ax.set_title(f"Where the ball was won ({len(inc)} included open-play turnovers)", pad=22)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3)
    viz.save(fig, "eda_turnover_locations", cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    fps = cfg["tracking"]["fps"]
    out = cfg.path("processed")

    all_spells, all_turnovers, funnels, summary = [], [], [], []
    for game in cfg["datasets"]["metrica"]["games"]:
        match_id = f"metrica_{game}"
        pm = read_processed(match_id, cfg)
        spells = possession_spells(
            pm.events, pm.frames, cfg["possession"]["control_event_types"], fps
        )
        possession = frame_possession(spells, pm.frames)
        turnovers = find_turnovers(spells, pm.frames, pm.events, cfg)

        spells.to_parquet(out / f"{match_id}_spells.parquet", index=False)
        possession.to_parquet(out / f"{match_id}_possession.parquet", index=False)
        turnovers.to_parquet(out / f"{match_id}_turnovers.parquet", index=False)

        all_spells.append(spells)
        all_turnovers.append(turnovers)
        funnels.append(turnover_funnel(turnovers).set_index("step")["n"].rename(match_id))
        held = possession["possession"].value_counts(normalize=True)
        summary.append({
            "match_id": match_id,
            "spells": len(spells),
            "spells_with_ball_in_play": int((spells["in_play_s"] > 0).sum()),
            "median_spell_s": round(spells.loc[spells["in_play_s"] > 0, "in_play_s"].median(), 1),
            "home_possession_pct": round(100 * held.get("home", 0), 1),
            "open_play_turnovers": len(turnovers),
            "included_turnovers": int(turnovers["included"].sum()),
        })

    funnel = pd.concat(funnels, axis=1)
    funnel["total"] = funnel.sum(axis=1)
    tables = cfg.path("tables")
    tables.mkdir(parents=True, exist_ok=True)
    funnel.to_csv(tables / "turnover_funnel.csv")
    pd.DataFrame(summary).to_csv(tables / "possession_summary.csv", index=False)

    viz.apply_style()
    plot_spell_durations(pd.concat(all_spells, ignore_index=True), cfg)
    plot_turnover_locations(pd.concat(all_turnovers, ignore_index=True), cfg)

    print(pd.DataFrame(summary).T.to_string(header=False))
    print()
    print(funnel.to_string())


if __name__ == "__main__":
    main()
