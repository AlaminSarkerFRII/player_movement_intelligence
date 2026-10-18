"""H1 spell aggregation and model on synthetic data with a known effect."""

import numpy as np
import pandas as pd
import pytest

from pmi.analysis.static import fit_state_model, run_h1, spell_shape_table, team_match_summary


def _inputs():
    """Two spells (home then away), 100 frames each; frame 150 fails QC."""
    frames = pd.DataFrame({"frame": np.arange(1, 201), "in_play": True, "qc_ok": True,
                           "ball_x": 0.0})
    frames.loc[frames["frame"] == 150, "qc_ok"] = False
    possession = pd.DataFrame({"frame": frames["frame"],
                               "spell_id": np.repeat([0, 1], 100),
                               "possession": np.repeat(["home", "away"], 100)})
    shape = pd.DataFrame([
        {"match_id": "m", "frame": f, "team": t, "n_players": 10, "length": 30.0,
         "width": 40.0 if t == ("home" if f <= 100 else "away") else 35.0,
         "area": 900.0, "stretch": 15.0, "centroid_x_att": 0.0}
        for f in range(1, 201) for t in ("home", "away")
    ])
    return shape, possession, frames


def test_spell_shape_table_aggregates_per_spell_and_team():
    shape, possession, frames = _inputs()
    t = spell_shape_table(shape, possession, frames, fps=25, min_spell_s=2.0,
                          required_players=10, length_m=105)
    assert len(t) == 4
    assert set(t["state"]) == {"in", "out"}
    assert (t.loc[t["state"] == "in", "width"] == 40).all()
    assert (t.loc[t["state"] == "out", "width"] == 35).all()
    assert t.loc[t["spell_id"] == 1, "n_frames"].tolist() == [99, 99]  # QC frame dropped
    assert (t["ball_zone"] == "middle").all()


def test_short_spells_are_dropped():
    shape, possession, frames = _inputs()
    t = spell_shape_table(shape, possession, frames, fps=25, min_spell_s=5.0,
                          required_players=10, length_m=105)
    assert t.empty  # 100 frames = 4 s < 5 s


def _synthetic_table(effect=5.0, n=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for tm in [f"m{i}:{t}" for i in range(3) for t in ("home", "away")]:
        offset = rng.normal(0, 2)
        for k in range(n):
            state = "in" if k % 2 else "out"
            rows.append({
                "team_match": tm, "team": tm.split(":")[1], "state": state,
                "ball_zone": ["defensive", "middle", "attacking"][k % 3],
                "length": 30 + offset + effect * (state == "in") + rng.normal(0, 3),
                "width": 40 + rng.normal(0, 3), "area": 900 + rng.normal(0, 50),
                "stretch": 15 + rng.normal(0, 1),
            })
    return pd.DataFrame(rows)


def test_mixed_model_recovers_known_effect():
    r = fit_state_model(_synthetic_table(effect=5.0), "length")
    assert r["ci_low"] < 5.0 < r["ci_high"]
    assert r["p_value"] < 1e-6


def test_mixed_model_finds_no_effect_when_none_exists():
    r = fit_state_model(_synthetic_table(effect=0.0), "length")
    assert r["ci_low"] < 0 < r["ci_high"]


def test_run_h1_reports_all_variants_and_consistency():
    table = _synthetic_table(effect=5.0)
    res = run_h1(table)
    assert set(res["variant"]) == {"primary", "no_zone_adjustment", "home_rows_only",
                                   "away_rows_only"}
    assert len(res) == 16
    length = res[(res["variant"] == "primary") & (res["metric"] == "length")].iloc[0]
    assert length["team_matches_in_gt_out"] == "6/6"
    assert (res["p_holm"] >= res["p_value"]).all()


def test_team_match_summary_cohens_d_sign():
    s = team_match_summary(_synthetic_table(effect=5.0)).set_index("team_match")
    assert (s["length_d"] > 0).all()
    assert s["length_diff"].mean() == pytest.approx(5.0, abs=1.0)
