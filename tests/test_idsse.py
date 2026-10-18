"""IDSSE loader helpers on synthetic inputs, plus a real-data check (marker ``data``)."""

import numpy as np
import pandas as pd
import pytest

from pmi.config import load_config
from pmi.io import idsse


@pytest.mark.parametrize("args, expected", [
    (("PASS", "Play", {}, "T1", None), ("PASS", None, "T1")),
    (("PASS", "Play", {}, "T1", "THROW_IN"), ("SET PIECE", "THROW_IN", "T1")),
    (("RECOVERY", "BallClaiming", {}, "T1", None), ("RECOVERY", None, "T1")),
    (("GENERIC", "TacklingGame",
      {"WinnerTeam": "T2", "WinnerRole": "withBallControl", "Type": "ground"}, None, None),
     ("DUEL WON", "ground", "T2")),
    (("GENERIC", "TacklingGame",
      {"WinnerTeam": "T2", "WinnerRole": "withoutBallControl", "Type": "air"}, None, None),
     ("DUEL", "air", "T2")),
    (("GENERIC", "OtherBallAction", {}, "T1", None), ("OTHER BALL ACTION", None, "T1")),
    (("GENERIC", "Delete", {}, None, None), ("DELETE", None, None)),
])
def test_map_event(args, expected):
    assert idsse.map_event(*args) == expected


def test_estimate_lag_recovers_known_shift():
    n = 2000
    t = np.arange(n)
    ball = pd.DataFrame({"period": 1, "frame": t + 1,
                         "x": 0.5 + 0.4 * np.sin(t / 40), "y": 0.5 + 0.4 * np.cos(t / 55)})
    true_frames = np.arange(100, 1900, 37)
    events = pd.DataFrame({
        "period": 1, "type": "PASS",
        "frame": true_frames + 1 + 15,  # events stamped 15 frames late
        "x": ball["x"].to_numpy()[true_frames], "y": ball["y"].to_numpy()[true_frames],
    })
    lag = idsse.estimate_lag(events, ball, max_lag=50, length_m=105, width_m=68)[1]
    assert lag["lag_frames"] == -15
    assert lag["median_dist_m"] == pytest.approx(0, abs=1e-9)
    assert lag["median_dist_unsynced_m"] > 1


def test_provider_possession_events_at_changes_and_restarts():
    period = np.array([1] * 8 + [2] * 3)
    frame = np.arange(1, 12)
    alive = np.array([1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1], dtype=bool)
    owner = np.array(["home", "home", "away", "away", "away", "away", "away", "home",
                      "home", "home", "away"], dtype=object)
    ev = idsse.provider_possession_events(period, frame, alive, owner)
    # start of play, change at 3, restart at 6, change at 8, new period at 9, change at 11
    assert ev["frame"].tolist() == [1, 3, 6, 8, 9, 11]
    assert ev["team"].tolist() == ["home", "away", "away", "home", "home", "away"]


@pytest.mark.data
def test_real_idsse_match_loads_and_validates():
    cfg = load_config("configs/idsse.yaml")
    if not (cfg.path("raw") / "idsse").exists():
        pytest.skip("IDSSE data not downloaded (run `make data`)")
    m = idsse.load_match("J03WMX", cfg)
    m.validate()
    assert m.ball["frame"].diff().dropna().eq(1).all()
    detected = sorted(m.tracking.loc[m.tracking["is_goalkeeper"], "player_id"].unique())
    assert detected == m.meta["provider_goalkeepers"]
    for lag in m.meta["sync_lags"].values():
        assert lag["median_dist_m"] < lag["median_dist_unsynced_m"]
