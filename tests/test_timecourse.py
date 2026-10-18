"""Time-course helpers on synthetic data with known answers."""

import numpy as np
import pandas as pd
import pytest

from pmi.analysis import timecourse as tc

FPS = 25
OFFSETS = np.arange(-125, 251)
OFFSETS_S = OFFSETS / FPS


def test_extract_windows_pads_outside_recording():
    series = np.arange(100, dtype=float)
    w = tc.extract_windows(series, f0=1, t0=np.array([3, 50]), offsets=np.array([-5, 0, 5]))
    assert np.isnan(w[0, 0]) and w[0, 1] == 2 and w[0, 2] == 7  # frame 3 -> index 2
    assert w[1].tolist() == [44, 49, 54]


def test_baseline_correct_and_coverage():
    w = np.vstack([np.full(len(OFFSETS), 10.0), np.full(len(OFFSETS), np.nan)])
    corrected, ok = tc.baseline_correct(w, OFFSETS_S, (-5.0, -2.0), 0.5)
    assert np.allclose(corrected[0], 0) and ok.tolist() == [True, False]


def _step_curve(t_change=2.0, size=-100.0):
    """Linear ramp from 0 at t0 to `size` at 2*t_change, then flat: half reached at t_change."""
    ramp = np.clip(OFFSETS_S / (2 * t_change), 0, 1)
    return size * ramp


@pytest.mark.parametrize("size", [-100.0, 50.0])
def test_half_change_time_on_known_ramp(size):
    t = tc.half_change_time(_step_curve(2.0, size), OFFSETS_S, -2.0, (5.0, 10.0))
    assert t == pytest.approx(2.0, abs=1 / FPS)


def test_half_change_time_peak_reference_ignores_rebound():
    curve = _step_curve(1.0, -100.0)
    curve[OFFSETS_S > 5] = -40.0  # rebound lowers the late-window mean
    late = tc.half_change_time(curve, OFFSETS_S, -2.0, (5.0, 10.0), "late")
    peak = tc.half_change_time(curve, OFFSETS_S, -2.0, (5.0, 10.0), "peak")
    assert late < peak == pytest.approx(1.0, abs=1 / FPS)


def test_bootstrap_curve_resamples_within_strata():
    w = np.vstack([np.zeros((10, 5)), np.ones((10, 5))])
    strata = np.repeat(["a", "b"], 10)
    reps = tc.bootstrap_curve(w, strata, 50, np.random.default_rng(0))
    assert np.allclose(reps, 0.5)  # each stratum keeps its size, so the mean never moves


def _events_with_effect(effect=-100.0, n_groups=6, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        for cond, n in (("turnover", 30), ("control", 90)):
            for _ in range(n):
                rows.append({"team_match": f"g{g}", "condition": cond,
                             "late": (effect if cond == "turnover" else 0) + rng.normal(0, 50)
                             + g * 5})
    return pd.DataFrame(rows)


def test_late_change_model_recovers_effect():
    r = tc.late_change_model(_events_with_effect(-100.0), "late")
    assert r["model"] == "mixed" and r["ci_low"] < -100 < r["ci_high"]
    assert r["effect_fe"] == pytest.approx(r["effect"], abs=5)


def test_late_change_model_falls_back_to_fixed_effects_with_few_groups():
    r = tc.late_change_model(_events_with_effect(-100.0, n_groups=2), "late")
    assert r["model"] == "fixed_effects" and r["ci_low"] < -100 < r["ci_high"]


def _control_inputs():
    """One period, 2000 frames, all in play; home has the ball 1-999, away 1000-2000."""
    frames = pd.DataFrame({"frame": np.arange(1, 2001), "in_play": True, "ball_x": 0.0})
    possession = pd.DataFrame({"frame": frames["frame"],
                               "spell_id": np.where(frames["frame"] < 1000, 0, 1),
                               "possession": np.where(frames["frame"] < 1000, "home", "away")})
    spells = pd.DataFrame({"spell_id": [0, 1], "start_frame": [1, 1000],
                           "end_frame": [999, 2000]})
    turnovers = pd.DataFrame({"match_id": ["m"], "t0_frame": [1000], "included": [True],
                              "x_att_won": [0.0]})
    return turnovers, spells, frames, possession


def test_control_events_respect_rules():
    turnovers, spells, frames, possession = _control_inputs()
    c = tc.control_events(turnovers, spells, frames, possession, n_per_turnover=50,
                          min_spell_s=2.0, min_gap_s=3.0, fps=FPS, length_m=105,
                          rng=np.random.default_rng(0))
    assert len(c) == 50 and (c["condition"] == "control").all()
    f = c["t0_frame"].to_numpy()
    assert (np.abs(f - 1000) >= 75).all()  # >= 3 s from the turnover
    home = c["lost_team"] == "home"
    assert (f[home] - 1 >= 50).all() and (999 - f[home] >= 50).all()  # 2 s inside the spell
    assert (c.loc[home, "won_team"] == "away").all()
    assert (c["zone_lost"] == "middle").all()
