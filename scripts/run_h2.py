"""H2/H3: team shape time course around turnovers, against matched controls.

Writes to reports/tables/:
    h2_events.csv            every turnover and control event used
    h2_curves.csv            mean change curves with 95 % bootstrap bands
    h2_late_change.csv       turnover vs control late-window change (mixed models)
    h2_half_change_time.csv  time to 50 % of the change, with 95 % CI
    h2_asymmetry.csv         paired difference in half-change time, won minus lost
    h3_team_match.csv        per team-match half-change time and late change (area)
    h3_icc.csv               between-team-match share of variance
    h2_sensitivity.csv       area / losing team under alternative choices
and figures h2_timecourse_area.png, h2_effect_all_metrics.png, h3_team_match_area.png.

Usage:
    uv run python scripts/run_h2.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pmi import viz
from pmi.analysis import timecourse as tc
from pmi.config import load_config, set_seed
from pmi.metrics import SHAPE_METRICS

PERSPECTIVES = {"lost": "team that lost the ball", "won": "team that won the ball"}
LABELS = {"length": "Length (m)", "width": "Width (m)", "area": "Area (m²)",
          "stretch": "Stretch index (m)"}


def build_events(cfg, rng) -> tuple[pd.DataFrame, dict]:
    """All turnover and control events, plus per-match data needed for windows."""
    proc = cfg.path("processed")
    fps = cfg["tracking"]["fps"]
    pos, length = cfg["possession"], cfg["pitch"]["length_m"]
    events, data = [], {}
    for mid in cfg.match_ids:
        load = {k: pd.read_parquet(proc / f"{mid}_{k}.parquet")
                for k in ("shape", "frames", "possession", "spells", "turnovers")}
        trk = pd.read_parquet(proc / f"{mid}_tracking.parquet",
                              columns=["player_id", "is_goalkeeper"])
        gk_ids = {(mid, p) for p in trk.loc[trk["is_goalkeeper"], "player_id"].unique()}
        events.append(tc.turnover_events(load["turnovers"], gk_ids, length))
        events.append(tc.control_events(
            load["turnovers"], load["spells"], load["frames"], load["possession"],
            cfg["timecourse"]["n_control_samples_per_turnover"],
            pos["min_possession_length_s"], pos["min_gap_between_turnovers_s"],
            fps, length, rng,
        ))
        data[mid] = load
    ev = pd.concat(events, ignore_index=True)
    ev.insert(0, "event_id", np.arange(len(ev)))
    return ev, data


def build_windows(ev, data, cfg, baseline_s=None):
    """{(metric, perspective): (baseline-corrected windows, usable-row mask)}."""
    tcfg = cfg["timecourse"]
    fps = cfg["tracking"]["fps"]
    offsets = np.arange(-int(tcfg["window_before_s"] * fps), int(tcfg["window_after_s"] * fps) + 1)
    offsets_s = offsets / fps
    baseline_s = baseline_s or tuple(tcfg["baseline_window_s"])
    out = {}
    for metric in SHAPE_METRICS:
        series = {mid: tc.metric_series(d["shape"], d["frames"], metric,
                                        cfg["metrics"]["required_players"])
                  for mid, d in data.items()}
        for persp in PERSPECTIVES:
            w = np.full((len(ev), len(offsets)), np.nan)
            for (mid, team), rows in ev.groupby(["match_id", f"{persp}_team"]).groups.items():
                f0, s = series[mid]
                w[rows] = tc.extract_windows(s[team], f0, ev.loc[rows, "t0_frame"].to_numpy(),
                                             offsets)
            out[(metric, persp)] = tc.baseline_correct(w, offsets_s, baseline_s,
                                                       tcfg["min_baseline_coverage"])
        # Keep only events where both teams are measurable, so the two perspectives
        # use the same events (paired comparison of half-change times).
        both = out[(metric, "lost")][1] & out[(metric, "won")][1]
        for persp in PERSPECTIVES:
            out[(metric, persp)] = (out[(metric, persp)][0], both)
    return out, offsets_s


def _metric_rng(cfg, metric):
    """Same random stream for both perspectives of a metric: a paired bootstrap."""
    return np.random.default_rng([cfg.seed, SHAPE_METRICS.index(metric)])


def analyse(ev, windows, offsets_s, cfg, mask=None):
    """Curves, half-change times and late-change models for every metric and perspective.

    Also returns the paired comparison of half-change times (won minus lost).
    """
    tcfg = cfg["timecourse"]
    late = tuple(tcfg["late_window_s"])
    mask = np.ones(len(ev), bool) if mask is None else mask
    curves, t50, models, reps, rows_used = [], [], [], {}, {}
    for (metric, persp), (w, ok) in windows.items():
        rng = _metric_rng(cfg, metric)
        keep = ok & mask
        rows_used[(metric, persp)] = keep
        is_t = keep & (ev["condition"] == "turnover").to_numpy()
        is_c = keep & (ev["condition"] == "control").to_numpy()
        c, s = tc.summarize_curves(w[is_t], w[is_c], ev["match_id"].to_numpy()[is_t],
                                   ev["match_id"].to_numpy()[is_c], offsets_s, tcfg, rng)
        curves.append(c.assign(metric=metric, perspective=persp))
        reps[(metric, persp)] = {k: s.pop(f"t50{k}_reps") for k in ("", "_peak")}
        t50.append({"metric": metric, "perspective": persp, **s})
        d = ev[keep].assign(late=tc.late_change(w[keep], offsets_s, late))
        d["team_match"] = d["match_id"] + ":" + d[f"{persp}_team"]
        models.append({"metric": metric, "perspective": persp,
                       **tc.late_change_model(d, "late"),
                       "turnover_mean_late": d.loc[d["condition"] == "turnover", "late"].mean(),
                       "control_mean_late": d.loc[d["condition"] == "control", "late"].mean()})
    models = pd.DataFrame(models)
    h1_path = cfg.path("tables") / "h1_models.csv"
    if h1_path.exists():  # how much of the static in-vs-out difference is reached
        h1 = pd.read_csv(h1_path)
        h1 = h1[h1["variant"] == "primary"].set_index("metric")["estimate_in_minus_out"]
        sign = np.where(models["perspective"] == "lost", -1.0, 1.0)
        models["share_of_h1_difference"] = sign * models["effect"] / models["metric"].map(h1)
    models["p_holm"] = np.nan
    for _, g in models.groupby("perspective"):
        models.loc[g.index, "p_holm"] = tc.holm(g["p_value"].tolist())

    t50 = pd.DataFrame(t50)
    asym = []
    for metric in sorted({m for m, _ in reps}):
        if (metric, "lost") not in reps or (metric, "won") not in reps:
            continue
        for k, ref in (("", "late"), ("_peak", "peak")):
            d = reps[(metric, "won")][k] - reps[(metric, "lost")][k]
            d = d[np.isfinite(d)]
            point = t50.set_index(["metric", "perspective"])[f"t50{k}_s"]
            asym.append({
                "metric": metric, "reference": ref,
                "t50_won_minus_lost_s": point[(metric, "won")] - point[(metric, "lost")],
                "ci_low": np.percentile(d, 2.5), "ci_high": np.percentile(d, 97.5),
                "paired": bool(np.array_equal(rows_used[(metric, "lost")],
                                              rows_used[(metric, "won")])),
            })
    asym = pd.DataFrame(asym)
    return pd.concat(curves, ignore_index=True), t50, models, asym


def team_match_analysis(ev, windows, offsets_s, cfg, metric="area", persp="lost"):
    """H3: half-change time and late change for each team-match (losing-team view)."""
    tcfg = cfg["timecourse"]
    rng = _metric_rng(cfg, metric)
    w, ok = windows[(metric, persp)]
    tm = (ev["match_id"] + ":" + ev[f"{persp}_team"]).to_numpy()
    rows, curves = [], []
    for name in sorted(np.unique(tm)):
        is_t = ok & (tm == name) & (ev["condition"] == "turnover").to_numpy()
        is_c = ok & (tm == name) & (ev["condition"] == "control").to_numpy()
        c, s = tc.summarize_curves(w[is_t], w[is_c], np.zeros(is_t.sum()),
                                   np.zeros(is_c.sum()), offsets_s, tcfg, rng)
        late = tc.late_change(w[is_t], offsets_s, tuple(tcfg["late_window_s"]))
        s.pop("t50_reps")
        s.pop("t50_peak_reps")
        rows.append({"team_match": name, "n_turnovers": int(is_t.sum()),
                     "n_controls": int(is_c.sum()), "late_change_mean": np.nanmean(late), **s})
        curves.append(c.assign(team_match=name))
    d = ev[ok].assign(late=tc.late_change(w[ok], offsets_s, tuple(tcfg["late_window_s"])),
                      team_match=tm[ok])
    icc = {"metric": metric, "perspective": persp, **tc.icc_turnovers(d, "late")}
    return pd.DataFrame(rows), pd.concat(curves, ignore_index=True), pd.DataFrame([icc])


def sensitivity(ev, data, windows, offsets_s, cfg) -> pd.DataFrame:
    """Area, losing team: late effect and half-change time under alternative choices."""
    def run(name, win, mask):
        sub = {k: v for k, v in win.items() if k == ("area", "lost")}
        _, t50, models, _ = analyse(ev, sub, offsets_s, cfg, mask)
        m, t = models.iloc[0], t50.iloc[0]
        return {"variant": name, "n_turnovers": m["n_turnovers"], "model": m["model"],
                "late_effect": m["effect"], "ci_low": m["ci_low"], "ci_high": m["ci_high"],
                "converged": m["converged"],
                "t50_s": t["t50_s"], "t50_lo": t["t50_lo"], "t50_hi": t["t50_hi"]}

    rows = [run("primary", windows, None)]
    not_gk = ~ev["won_by_goalkeeper"].to_numpy()
    rows.append(run("exclude turnovers won by goalkeeper", windows, not_gk))
    alt, _ = build_windows(ev, data, cfg, baseline_s=(-5.0, -3.0))
    rows.append(run("baseline -5 to -3 s", alt, None))
    for zone in ("defensive", "middle", "attacking"):
        rows.append(run(f"ball lost in own {zone} third", windows,
                        (ev["zone_lost"] == zone).to_numpy()))
    for mid in sorted(ev["match_id"].unique()):
        rows.append(run(f"only {mid}", windows, (ev["match_id"] == mid).to_numpy()))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- figures


def _band(ax, c, key, color, label):
    ax.fill_between(c["t_s"], c[f"{key}_lo"], c[f"{key}_hi"], color=color, alpha=0.18, lw=0)
    ax.plot(c["t_s"], c[key], color=color, label=label)


def _decorate(ax, cfg):
    b = cfg["timecourse"]["baseline_window_s"]
    ax.axvspan(b[0], b[1], color=viz.GRID, alpha=0.6, lw=0)
    ax.axvline(0, color=viz.TEXT_SECONDARY, lw=1)
    ax.axhline(0, color=viz.TEXT_SECONDARY, lw=0.8, ls=":")
    ax.set_xlabel("Time relative to turnover t0 (s)")


def plot_area(curves, t50, cfg):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, persp in zip(axes, PERSPECTIVES, strict=True):
        c = curves[(curves["metric"] == "area") & (curves["perspective"] == persp)]
        _band(ax, c, "control", viz.TEXT_SECONDARY, "control (no turnover)")
        _band(ax, c, "turnover", viz.SERIES[0], "turnover")
        _decorate(ax, cfg)
        t = t50[(t50["metric"] == "area") & (t50["perspective"] == persp)].iloc[0]
        if np.isfinite(t["t50_s"]):
            ax.axvline(t["t50_s"], color=viz.SERIES[0], lw=1, ls="--")
            ax.text(t["t50_s"] + 0.2, ax.get_ylim()[1] * 0.92 if persp == "won" else
                    ax.get_ylim()[0] * 0.92,
                    f"50 % of change at {t['t50_s']:.1f} s\n[{t['t50_lo']:.1f}, {t['t50_hi']:.1f}]",
                    fontsize=8, color=viz.TEXT_SECONDARY, va="center")
        ax.set_title(PERSPECTIVES[persp].capitalize(), fontsize=10)
    axes[0].set_ylabel("Change in hull area from baseline (m²)")
    axes[0].legend(loc="upper left")
    fig.suptitle("Team area after a turnover vs matched open-play moments (mean, 95% bootstrap "
                 "band; grey shading = baseline)", x=0.01, ha="left", fontsize=11,
                 fontweight="bold")
    fig.tight_layout()
    viz.save(fig, "h2_timecourse_area", cfg)


def plot_effects(curves, cfg):
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), layout="constrained")
    for ax, metric in zip(axes, SHAPE_METRICS, strict=True):
        for persp, color in zip(PERSPECTIVES, viz.SERIES[:2], strict=True):
            c = curves[(curves["metric"] == metric) & (curves["perspective"] == persp)]
            _band(ax, c, "effect", color, PERSPECTIVES[persp])
        _decorate(ax, cfg)
        ax.set_title(LABELS[metric], fontsize=10)
    axes[0].set_ylabel("Turnover − control change")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower left", ncol=2)
    fig.suptitle("Turnover effect on every shape metric (turnover minus control, 95% band)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    viz.save(fig, "h2_effect_all_metrics", cfg)


def plot_team_matches(tm_curves, overall, tm_rows, cfg):
    names = sorted(tm_curves["team_match"].unique())
    ncols = 3 if len(names) <= 6 else 4
    nrows = int(np.ceil(len(names) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.9 * ncols, 2.9 * nrows + 0.6),
                             sharex=True, sharey=True, squeeze=False)
    ref = overall[(overall["metric"] == "area") & (overall["perspective"] == "lost")]
    rows = tm_rows.set_index("team_match")
    for ax, name in zip(axes.flat, names, strict=False):
        c = tm_curves[tm_curves["team_match"] == name]
        ax.plot(ref["t_s"], ref["effect"], color=viz.TEXT_SECONDARY, lw=1.2, label="all teams")
        _band(ax, c, "effect", viz.SERIES[0], "this team-match")
        _decorate(ax, cfg)
        r = rows.loc[name]
        ax.set_title(f"{name} (n={int(r['n_turnovers'])}), t50 {r['t50_s']:.1f} s", fontsize=9)
    for ax in axes.flat[len(names):]:
        ax.set_visible(False)
    for ax in axes[:-1].flat:
        ax.set_xlabel("")
    for ax in axes[:, 0]:
        ax.set_ylabel("Area effect (m²)")
    axes[0, 0].legend(loc="lower left", fontsize=8)
    fig.suptitle("Losing team's area contraction, per team-match (turnover − control, 95% band)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    viz.save(fig, "h3_team_match_area", cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    rng = set_seed(cfg.seed)  # control sampling; bootstraps use per-metric streams
    tables = cfg.path("tables")

    ev, data = build_events(cfg, rng)
    windows, offsets_s = build_windows(ev, data, cfg)
    curves, t50, models, asym = analyse(ev, windows, offsets_s, cfg)
    tm_rows, tm_curves, icc = team_match_analysis(ev, windows, offsets_s, cfg)
    sens = sensitivity(ev, data, windows, offsets_s, cfg)

    ev.to_csv(tables / "h2_events.csv", index=False)
    curves.to_csv(tables / "h2_curves.csv", index=False)
    models.to_csv(tables / "h2_late_change.csv", index=False)
    t50.to_csv(tables / "h2_half_change_time.csv", index=False)
    asym.to_csv(tables / "h2_asymmetry.csv", index=False)
    tm_rows.to_csv(tables / "h3_team_match.csv", index=False)
    icc.to_csv(tables / "h3_icc.csv", index=False)
    sens.to_csv(tables / "h2_sensitivity.csv", index=False)

    viz.apply_style()
    plot_area(curves, t50, cfg)
    plot_effects(curves, cfg)
    plot_team_matches(tm_curves, curves, tm_rows, cfg)

    print(ev.groupby(["match_id", "condition"]).size().unstack())
    w, ok = windows[("area", "lost")]
    print("events with enough baseline:", ev[ok].groupby("condition").size().to_dict())
    with pd.option_context("display.width", 200, "display.float_format", "{:.3g}".format):
        for name, df in (("late change", models.drop(columns="warnings")),
                         ("half-change time", t50), ("asymmetry (won - lost)", asym),
                         ("team-matches", tm_rows), ("ICC", icc), ("sensitivity", sens)):
            print(f"\n== {name}\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
