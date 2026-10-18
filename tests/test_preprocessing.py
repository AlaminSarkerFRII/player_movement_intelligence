"""Tests for preprocessing: synthetic unit tests plus real-data checks (marker ``data``)."""

import numpy as np
import pandas as pd
import pytest

from pmi.config import load_config
from pmi.io.common import MatchData
from pmi.preprocessing import (
    add_velocity,
    event_live_mask,
    fill_short_ball_gaps,
    normalize_direction,
    preprocess_match,
)

FPS = 25
BIP = load_config()["ball_in_play"]


def _player(pid, xs, team="home", period=1, start_frame=1, gk=False):
    n = len(xs)
    return pd.DataFrame({
        "match_id": "m", "period": period, "frame": np.arange(start_frame, start_frame + n),
        "time_s": np.arange(n) / FPS, "team": team, "player_id": pid,
        "is_goalkeeper": gk, "x": np.asarray(xs, dtype=float), "y": 0.0,
    })


# ---------------------------------------------------------------- direction


def test_normalize_direction_rotates_only_periods_where_home_attacks_minus_x():
    # Period 1: home GK at -45 (attacks +x). Period 2: home GK at +45 (attacks -x).
    tracking = pd.concat([
        _player("gk", [-45.0] * 5, period=1, gk=True),
        _player("gk", [45.0] * 5, period=2, start_frame=6, gk=True),
    ], ignore_index=True)
    tracking.loc[tracking["period"] == 2, "y"] = 10.0
    ball = pd.DataFrame({"match_id": "m", "period": [1, 2], "frame": [1, 6], "time_s": 0.0,
                         "x": [5.0, 5.0], "y": [1.0, 1.0]})
    events = pd.DataFrame({"period": [2], "x": [20.0], "y": [3.0], "end_x": [30.0],
                           "end_y": [-3.0]})
    out = normalize_direction(MatchData("m", FPS, tracking, ball, events))

    assert out.meta["flipped_periods"] == [2]
    p2 = out.tracking[out.tracking["period"] == 2]
    assert (p2["x"] == -45.0).all() and (p2["y"] == -10.0).all()  # 180° rotation
    assert out.ball["x"].tolist() == [5.0, -5.0]
    assert out.events.loc[0, ["x", "y", "end_x", "end_y"]].tolist() == [-20.0, -3.0, -30.0, 3.0]


# ---------------------------------------------------------------- velocity


def test_velocity_recovers_constant_speed():
    xs = np.arange(50) * (5.0 / FPS)  # 5 m/s along x
    out = add_velocity(_player("a", xs), FPS, window_s=0.28, polyorder=2, max_speed=12)
    np.testing.assert_allclose(out["speed"], 5.0, atol=1e-6)
    assert out["qc_ok"].all()


def test_velocity_flags_jump_and_blanks_nearby_velocities():
    xs = np.arange(50) * (2.0 / FPS)
    xs[25:] += 10.0  # 10 m jump in one frame = 250 m/s
    out = add_velocity(_player("a", xs), FPS, window_s=0.28, polyorder=2, max_speed=12)
    assert out.loc[~out["qc_ok"], "frame"].tolist() == [26]
    assert out.loc[out["frame"].between(23, 29), "speed"].isna().all()  # ±3 frames
    assert out.loc[out["frame"] < 20, "speed"].notna().all()


def test_velocity_is_nan_for_segments_shorter_than_window():
    out = add_velocity(_player("a", [0.0, 0.1, 0.2]), FPS, 0.28, 2, 12)
    assert out["speed"].isna().all()


def test_velocity_does_not_mix_players():
    a = _player("a", np.zeros(20))
    b = _player("b", np.full(20, 30.0))  # far away, but a separate player
    out = add_velocity(pd.concat([a, b]), FPS, 0.28, 2, 12)
    assert out["qc_ok"].all()
    np.testing.assert_allclose(out["speed"], 0.0, atol=1e-9)


# ---------------------------------------------------------------- ball in play


def test_fill_short_ball_gaps_fills_short_and_keeps_long():
    x = np.arange(100, dtype=float)
    x[10:15] = np.nan  # 5-frame gap -> filled
    x[40:80] = np.nan  # 40-frame gap -> stays missing
    ball = pd.DataFrame({"period": 1, "frame": np.arange(100), "x": x, "y": 0.0})
    out = fill_short_ball_gaps(ball, max_gap_frames=25)
    np.testing.assert_allclose(out["x"].iloc[10:15], np.arange(10, 15))
    assert out["x"].iloc[40:80].isna().all()
    assert out["ball_tracked"].sum() == 60


def test_event_live_mask_dead_between_stop_and_restart():
    frames = pd.DataFrame({"period": 1, "frame": np.arange(1, 101)})
    events = pd.DataFrame({
        "period": 1,
        "frame": [5, 30, 50, 60, 90],
        "type": ["SET PIECE", "PASS", "BALL OUT", "SET PIECE", "PASS"],
        "subtype": ["KICK OFF", None, None, "THROW IN", None],
    })
    live = event_live_mask(frames, events, BIP)
    f = frames["frame"].to_numpy()
    assert not live[f < 5].any()                  # before kick-off
    assert live[(f >= 5) & (f < 50)].all()
    assert not live[(f >= 50) & (f < 60)].any()   # ball out until throw-in
    assert live[(f >= 60) & (f <= 90)].all()
    assert not live[f > 90].any()                 # after the last event


def test_goal_kick_coded_as_pass_counts_as_restart():
    frames = pd.DataFrame({"period": 1, "frame": np.arange(1, 51)})
    events = pd.DataFrame({
        "period": 1, "frame": [1, 10, 20, 40],
        "type": ["SET PIECE", "SHOT", "PASS", "PASS"],
        "subtype": ["KICK OFF", "OFF TARGET-OUT", "GOAL KICK", None],
    })
    live = event_live_mask(frames, events, BIP)
    assert not live[9:19].any() and live[19:40].all()


# ---------------------------------------------------------------- real data


@pytest.fixture(scope="module", params=[1, 2, 3])
def processed(request):
    from pmi.io import read_interim

    cfg = load_config()
    if not (cfg.path("interim") / f"metrica_{request.param}_tracking.parquet").exists():
        pytest.skip("interim data missing (run `make interim`)")
    return preprocess_match(read_interim(f"metrica_{request.param}", cfg), cfg)


@pytest.mark.data
def test_real_home_always_defends_minus_x(processed):
    gk = processed.tracking[processed.tracking["is_goalkeeper"]]
    mean_x = gk.groupby(["period", "team"], observed=True)["x"].mean()
    assert (mean_x.xs("home", level="team") < 0).all()
    assert (mean_x.xs("away", level="team") > 0).all()


@pytest.mark.data
def test_real_quality_is_within_expected_bounds(processed):
    f, t = processed.frames, processed.tracking
    assert (~t["qc_ok"]).mean() < 0.001             # < 0.1 % of player rows fail QC
    assert 45 < f["in_play"].sum() / FPS / 60 < 70  # minutes of ball in play
    live_speed = t.loc[t["frame"].isin(f.loc[f["in_play"], "frame"]), "speed"]
    assert live_speed.max() <= 12.0 + 1e-6
    assert 1.0 < live_speed.median() < 3.0
