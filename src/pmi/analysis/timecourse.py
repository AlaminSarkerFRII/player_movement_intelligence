"""H2/H3: how team shape changes in the seconds around a turnover.

For each event (a turnover, or a matched control moment without one) we take a
window of per-frame shape values for both teams, from ``window_before_s``
before to ``window_after_s`` after ``t0``, and subtract each event's own
baseline (mean over ``baseline_window_s``). Averaging these change curves
across events gives the time course.

**Controls.** For every turnover, ``n_control_samples_per_turnover`` moments
are drawn from the same match where the same rules hold *except* that
possession does not change: the team in possession has had the ball for at
least ``min_possession_length_s`` and keeps it for at least that long
afterwards, no turnover is within ``min_gap_between_turnovers_s``, and the
ball is in the same pitch third from that team's perspective. The control
curve shows how shape drifts in comparable open play; the turnover effect is
the turnover curve minus the control curve.

Perspectives: ``lost`` is the team that loses the ball (for controls, the team
in possession), ``won`` is the other team.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

from pmi.possession import attacking_x, pitch_third


def _nanmean(a: np.ndarray, axis: int) -> np.ndarray:
    """nanmean without the 'mean of empty slice' warning (all-NaN rows give NaN)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=axis)


# ---------------------------------------------------------------- events


def turnover_events(turnovers: pd.DataFrame, gk_ids: set[tuple[str, str]],
                    length_m: float) -> pd.DataFrame:
    """Included turnovers as events; flags those won by a goalkeeper."""
    t = turnovers[turnovers["included"]].copy()
    t["condition"] = "turnover"
    t["zone_lost"] = pitch_third(-t["x_att_won"].to_numpy(), length_m)
    t["won_by_goalkeeper"] = [
        (m, p) in gk_ids for m, p in zip(t["match_id"], t["trigger_player_id"], strict=True)
    ]
    return t[["match_id", "t0_frame", "lost_team", "won_team", "zone_lost", "condition",
              "won_by_goalkeeper"]]


def control_events(turnovers: pd.DataFrame, spells: pd.DataFrame, frames: pd.DataFrame,
                   possession: pd.DataFrame, n_per_turnover: int, min_spell_s: float,
                   min_gap_s: float, fps: int, length_m: float,
                   rng: np.random.Generator) -> pd.DataFrame:
    """Draw matched control moments for one match (see module docstring)."""
    min_len = int(round(min_spell_s * fps))
    gap = int(round(min_gap_s * fps))
    f = frames[["frame", "in_play", "ball_x"]].merge(
        possession[["frame", "spell_id", "possession"]], on="frame"
    )
    f = f[f["in_play"] & f["possession"].notna()].merge(
        spells[["spell_id", "start_frame", "end_frame"]], on="spell_id"
    )
    ok = (f["frame"] - f["start_frame"] >= min_len) & (f["end_frame"] - f["frame"] >= min_len)
    all_t0 = np.sort(turnovers["t0_frame"].to_numpy())  # all open-play turnovers, not just included
    if len(all_t0):
        idx = np.clip(np.searchsorted(all_t0, f["frame"].to_numpy()), 1, len(all_t0) - 1)
        nearest = np.minimum(np.abs(f["frame"].to_numpy() - all_t0[idx - 1]),
                             np.abs(f["frame"].to_numpy() - all_t0[idx]))
        ok &= nearest >= gap
    cand = f[ok].copy()
    cand["zone_lost"] = pitch_third(attacking_x(cand["ball_x"], cand["possession"]), length_m)

    rows = []
    included = turnovers[turnovers["included"]]
    zones = pitch_third(-included["x_att_won"].to_numpy(), length_m)
    for zone in np.unique(zones):
        pool = cand[cand["zone_lost"] == zone]
        n = int((zones == zone).sum()) * n_per_turnover
        if pool.empty:
            continue
        pick = pool.iloc[rng.choice(len(pool), size=min(n, len(pool)), replace=False)]
        rows.append(pick)
    c = pd.concat(rows, ignore_index=True)
    return pd.DataFrame({
        "match_id": turnovers["match_id"].iloc[0], "t0_frame": c["frame"],
        "lost_team": c["possession"],
        "won_team": np.where(c["possession"] == "home", "away", "home"),
        "zone_lost": c["zone_lost"], "condition": "control", "won_by_goalkeeper": False,
    })


# ---------------------------------------------------------------- windows


def metric_series(shape: pd.DataFrame, frames: pd.DataFrame, metric: str,
                  required_players: int) -> tuple[int, dict[str, np.ndarray]]:
    """Per-team arrays indexed by ``frame - f0``; NaN where a frame is not usable."""
    f0 = int(frames["frame"].min())
    n = int(frames["frame"].max()) - f0 + 1
    usable = frames.set_index("frame")[["in_play", "qc_ok"]].all(axis=1)
    out = {}
    for team, s in shape.groupby("team", observed=True):
        arr = np.full(n, np.nan)
        good = (s["n_players"] == required_players) & s["frame"].map(usable).fillna(False)
        arr[s.loc[good, "frame"].to_numpy() - f0] = s.loc[good, metric].to_numpy()
        out[team] = arr
    return f0, out


def extract_windows(series: np.ndarray, f0: int, t0: np.ndarray,
                    offsets: np.ndarray) -> np.ndarray:
    """Rows = events, columns = offsets (frames); NaN outside the recording."""
    idx = t0[:, None] - f0 + offsets[None, :]
    valid = (idx >= 0) & (idx < len(series))
    out = np.full(idx.shape, np.nan)
    out[valid] = series[idx[valid]]
    return out


def baseline_correct(w: np.ndarray, offsets_s: np.ndarray, baseline_s: tuple[float, float],
                     min_coverage: float) -> tuple[np.ndarray, np.ndarray]:
    """Subtract each row's baseline mean; return (corrected, rows with enough baseline)."""
    cols = (offsets_s >= baseline_s[0]) & (offsets_s <= baseline_s[1])
    base = w[:, cols]
    coverage = np.mean(~np.isnan(base), axis=1)
    mean = _nanmean(base, axis=1)
    return w - mean[:, None], coverage >= min_coverage


# ---------------------------------------------------------------- curves




def bootstrap_curve(w: np.ndarray, strata: np.ndarray, n_boot: int,
                    rng: np.random.Generator) -> np.ndarray:
    """Bootstrap replicates of the mean curve, resampling rows within each stratum (match)."""
    reps = np.zeros((n_boot, w.shape[1]))
    groups = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    for b in range(n_boot):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        reps[b] = _nanmean(w[idx], axis=0)
    return reps


def half_change_time(curve: np.ndarray, offsets_s: np.ndarray, search_from_s: float,
                     late_s: tuple[float, float], reference: str = "late") -> float:
    """First time (s, relative to t0) the curve reaches half of its total change.

    ``reference="late"``: total change = mean over the late window.
    ``reference="peak"``: total change = the largest absolute value after
    ``search_from_s`` (robust to a partial rebound inside the late window).
    Searches from ``search_from_s`` (the end of the baseline) onward. NaN if the
    curve never gets there.
    """
    after = offsets_s >= search_from_s
    if reference == "late":
        late = (offsets_s >= late_s[0]) & (offsets_s <= late_s[1])
        target = np.nanmean(curve[late]) / 2
    elif reference == "peak":
        seg = np.where(after, curve, np.nan)
        if np.all(np.isnan(seg)):
            return np.nan
        target = seg[np.nanargmax(np.abs(seg))] / 2
    else:
        raise ValueError(f"unknown reference: {reference}")
    reached = (curve <= target) if target < 0 else (curve >= target)
    hits = np.flatnonzero(after & reached)
    return float(offsets_s[hits[0]]) if len(hits) else np.nan


def summarize_curves(turn: np.ndarray, ctrl: np.ndarray, turn_strata: np.ndarray,
                     ctrl_strata: np.ndarray, offsets_s: np.ndarray, cfg_tc: dict,
                     rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    """Mean curves with 95 % bootstrap bands, and the half-change time with its CI."""
    n_boot = cfg_tc["n_bootstrap"]
    bt = bootstrap_curve(turn, turn_strata, n_boot, rng)
    bc = bootstrap_curve(ctrl, ctrl_strata, n_boot, rng)
    diff = bt - bc
    mt, mc = _nanmean(turn, 0), _nanmean(ctrl, 0)
    curves = pd.DataFrame({
        "t_s": offsets_s,
        "turnover": mt, "turnover_lo": np.percentile(bt, 2.5, 0),
        "turnover_hi": np.percentile(bt, 97.5, 0),
        "control": mc, "control_lo": np.percentile(bc, 2.5, 0),
        "control_hi": np.percentile(bc, 97.5, 0),
        "effect": mt - mc, "effect_lo": np.percentile(diff, 2.5, 0),
        "effect_hi": np.percentile(diff, 97.5, 0),
    })
    start = cfg_tc["baseline_window_s"][1]
    late = tuple(cfg_tc["late_window_s"])
    stats = {}
    for ref, suffix in (("late", ""), ("peak", "_peak")):
        point = half_change_time(mt - mc, offsets_s, start, late, ref)
        reps = np.array([half_change_time(d, offsets_s, start, late, ref) for d in diff])
        finite = reps[np.isfinite(reps)]
        stats |= {
            f"t50{suffix}_s": point,
            f"t50{suffix}_lo": float(np.percentile(finite, 2.5)) if len(finite) else np.nan,
            f"t50{suffix}_hi": float(np.percentile(finite, 97.5)) if len(finite) else np.nan,
            f"t50{suffix}_reps_undefined": int((~np.isfinite(reps)).sum()),
            f"t50{suffix}_reps": reps,  # kept for paired comparisons; drop before saving
        }
    return curves, stats


# ---------------------------------------------------------------- per-event tests


def late_change(w: np.ndarray, offsets_s: np.ndarray, late_s: tuple[float, float]) -> np.ndarray:
    """Each event's mean change over the late window."""
    cols = (offsets_s >= late_s[0]) & (offsets_s <= late_s[1])
    return _nanmean(w[:, cols], axis=1)


def _fit_mixed(formula: str, d: pd.DataFrame):
    """Fit a random-intercept model per team-match, capturing warnings instead of printing."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fit = smf.mixedlm(formula, d, groups=d["team_match"]).fit(reml=True)
    messages = sorted({str(w.message).split(".")[0][:60] for w in caught})
    return fit, bool(fit.converged) and not messages, "; ".join(messages)


def late_change_model(events: pd.DataFrame, value: str) -> dict:
    """Late change ~ condition, turnover vs control.

    Primary: mixed model with a random intercept per team-match. Cross-check:
    OLS with team-match fixed effects (used as the only estimate when fewer
    than 3 team-matches are present, where a random effect is not estimable).
    """
    d = events.dropna(subset=[value])
    term = "C(condition, Treatment('control'))[T.turnover]"
    out = {"n_turnovers": int((d["condition"] == "turnover").sum()),
           "n_controls": int((d["condition"] == "control").sum()),
           "n_team_matches": int(d["team_match"].nunique())}

    fe = smf.ols(f"{value} ~ C(condition, Treatment('control')) + C(team_match)", d).fit()
    ci_fe = fe.conf_int().loc[term]
    out |= {"effect_fe": fe.params[term], "ci_low_fe": ci_fe[0], "ci_high_fe": ci_fe[1]}

    if out["n_team_matches"] >= 3:
        fit, converged, msg = _fit_mixed(f"{value} ~ C(condition, Treatment('control'))", d)
        ci = fit.conf_int().loc[term]
        out |= {"model": "mixed", "effect": fit.params[term], "ci_low": ci[0],
                "ci_high": ci[1], "p_value": fit.pvalues[term], "converged": converged,
                "warnings": msg}
    else:
        out |= {"model": "fixed_effects", "effect": out["effect_fe"], "ci_low": ci_fe[0],
                "ci_high": ci_fe[1], "p_value": fe.pvalues[term], "converged": True,
                "warnings": ""}
    return out


def icc_turnovers(events: pd.DataFrame, value: str) -> dict:
    """Share of variance in turnover late change that lies between team-matches (H3)."""
    d = events[(events["condition"] == "turnover")].dropna(subset=[value])
    fit, converged, msg = _fit_mixed(f"{value} ~ 1", d)
    between = float(fit.cov_re.iloc[0, 0])
    return {"between_var": between, "within_var": float(fit.scale),
            "icc": between / (between + float(fit.scale)), "converged": converged,
            "warnings": msg}


def holm(p: list[float]) -> np.ndarray:
    return multipletests(p, method="holm")[1]
