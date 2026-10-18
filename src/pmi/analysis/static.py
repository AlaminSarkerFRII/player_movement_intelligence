"""H1: team shape in possession vs out of possession.

Unit of analysis: one possession spell seen from one team. Each spell gives two
rows, one for the team in possession (``state = "in"``) and one for its
opponent (``state = "out"``), each holding the team's mean shape over the
spell's usable frames. Consecutive 25 Hz frames are nearly identical, so
testing frames directly would treat thousands of dependent values as
independent and give falsely small p-values.

Model per metric (linear mixed model, random intercept per team-match):

    metric ~ state + ball_zone + (1 | team_match)

``ball_zone`` is the pitch third the ball is in, from the team's own
perspective, so the comparison is not just "in possession teams are higher up
the pitch".
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from pmi.metrics import SHAPE_METRICS
from pmi.possession import attacking_x, pitch_third


def spell_shape_table(
    shape: pd.DataFrame,
    possession: pd.DataFrame,
    frames: pd.DataFrame,
    fps: int,
    min_spell_s: float,
    required_players: int,
    length_m: float,
) -> pd.DataFrame:
    """Aggregate per-frame shape to one row per (spell, team).

    Frames are used only if the ball is in play, the frame passed QC, the
    frame belongs to a spell, and the team has ``required_players`` outfield
    players. Spells with fewer than ``min_spell_s`` seconds of usable frames
    are dropped.
    """
    f = frames[["frame", "in_play", "qc_ok", "ball_x"]].merge(
        possession[["frame", "spell_id", "possession"]], on="frame"
    )
    f = f[f["in_play"] & f["qc_ok"] & f["spell_id"].notna()]
    d = shape.merge(f, on="frame")
    d = d[d["n_players"] == required_players].copy()
    d["state"] = np.where(d["team"] == d["possession"], "in", "out")
    d["ball_x_att"] = attacking_x(d["ball_x"], d["team"])

    agg = {m: (m, "mean") for m in [*SHAPE_METRICS, "centroid_x_att", "ball_x_att"]}
    out = (
        d.groupby(["match_id", "spell_id", "team"], observed=True)
        .agg(state=("state", "first"), n_frames=("frame", "size"), **agg)
        .reset_index()
    )
    out["duration_s"] = out["n_frames"] / fps
    out = out[out["duration_s"] >= min_spell_s].reset_index(drop=True)
    out["ball_zone"] = pitch_third(out["ball_x_att"].to_numpy(), length_m)
    out["team_match"] = out["match_id"] + ":" + out["team"]
    return out


def team_match_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Mean and SD of each metric per team-match and state, plus Cohen's d (in vs out)."""
    rows = []
    for tm, g in table.groupby("team_match"):
        row = {"team_match": tm, "n_in": int((g["state"] == "in").sum()),
               "n_out": int((g["state"] == "out").sum())}
        for m in SHAPE_METRICS:
            a, b = g.loc[g["state"] == "in", m], g.loc[g["state"] == "out", m]
            pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var())
                             / (len(a) + len(b) - 2))
            row |= {f"{m}_in": a.mean(), f"{m}_out": b.mean(),
                    f"{m}_diff": a.mean() - b.mean(), f"{m}_d": (a.mean() - b.mean()) / pooled}
        rows.append(row)
    return pd.DataFrame(rows)


def fit_state_model(table: pd.DataFrame, metric: str, adjust_zone: bool = True) -> dict:
    """Fit the mixed model for one metric; return the in-vs-out estimate and its CI."""
    rhs = "C(state, Treatment('out'))"
    if adjust_zone:
        rhs += " + C(ball_zone, Treatment('middle'))"
    model = smf.mixedlm(f"{metric} ~ {rhs}", table, groups=table["team_match"])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fit = model.fit(reml=True)
    term = "C(state, Treatment('out'))[T.in]"
    ci = fit.conf_int().loc[term]
    return {
        "metric": metric,
        "adjusted_for_zone": adjust_zone,
        "estimate_in_minus_out": fit.params[term],
        "ci_low": ci[0],
        "ci_high": ci[1],
        "p_value": fit.pvalues[term],
        "group_var": float(fit.cov_re.iloc[0, 0]),
        "residual_var": float(fit.scale),
        "converged": bool(fit.converged),
        "warnings": "; ".join(sorted({str(w.message)[:80] for w in caught})),
        "n_rows": int(fit.nobs),
    }


H1_VARIANTS = {
    # name: (rows used, adjust for ball zone)
    "primary": ("all", True),
    "no_zone_adjustment": ("all", False),
    # Each spell appears twice in "all" (once per team) and both rows share the
    # same ball position; using one team's rows makes every spell appear once.
    "home_rows_only": ("home", True),
    "away_rows_only": ("away", True),
}


def run_h1(table: pd.DataFrame) -> pd.DataFrame:
    """Fit every metric under each variant; Holm-correct across metrics within a variant."""
    summary = team_match_summary(table)
    rows = []
    for variant, (team, adjust) in H1_VARIANTS.items():
        data = table if team == "all" else table[table["team"] == team]
        block = [fit_state_model(data, m, adjust) | {"variant": variant} for m in SHAPE_METRICS]
        p_holm = multipletests([r["p_value"] for r in block], method="holm")[1]
        for r, p in zip(block, p_holm, strict=True):
            diffs = summary[f"{r['metric']}_diff"]
            r |= {
                "p_holm": p,
                "team_matches_in_gt_out": f"{int((diffs > 0).sum())}/{len(diffs)}",
                "median_cohens_d": summary[f"{r['metric']}_d"].median(),
            }
        rows += block
    cols = ["variant", "metric"] + [c for c in rows[0] if c not in ("variant", "metric")]
    return pd.DataFrame(rows)[cols]
