"""Unit tests for the common data format helpers, on tiny synthetic data."""

import numpy as np
import pandas as pd
import pytest

from pmi.io.common import (
    MatchData,
    assign_goalkeepers,
    normalized_to_meters,
    validate_match,
    wide_to_long,
)


def test_normalized_to_meters_corners_and_centre():
    x, y = normalized_to_meters(np.array([0.0, 0.5, 1.0]), np.array([0.0, 0.5, 1.0]), 105, 68)
    np.testing.assert_allclose(x, [-52.5, 0.0, 52.5])
    np.testing.assert_allclose(y, [34.0, 0.0, -34.0])  # top of the image is +y


def _wide():
    # Two periods; p2 is off the pitch (NaN) in frame 2.
    return pd.DataFrame({
        "period": [1, 1, 2, 2],
        "frame": [1, 2, 3, 4],
        "p1_x": [1.0, 2.0, 3.0, 4.0], "p1_y": [0.0, 0.0, 0.0, 0.0],
        "p2_x": [5.0, np.nan, 7.0, 8.0], "p2_y": [1.0, np.nan, 1.0, 1.0],
    })


def test_wide_to_long_drops_off_pitch_and_resets_time_per_period():
    long = wide_to_long(_wide(), {"p1": "home", "p2": "away"}, "m", fps=25)
    assert len(long) == 7
    assert not ((long["player_id"] == "p2") & (long["frame"] == 2)).any()
    assert long.loc[long["frame"] == 3, "time_s"].eq(0.0).all()  # period 2 starts at 0
    assert long.loc[long["frame"] == 2, "time_s"].iloc[0] == pytest.approx(0.04)


def _tracking(gk_x=-48.0):
    rows = []
    for frame in range(1, 11):
        for team, sign in (("home", 1), ("away", -1)):
            rows.append(("m", 1, frame, 0.0, team, f"{team}_gk", False, sign * gk_x, 0.0))
            rows.append(("m", 1, frame, 0.0, team, f"{team}_def", False, sign * -30.0, 0.0))
            rows.append(("m", 1, frame, 0.0, team, f"{team}_fwd", False, sign * 10.0, 0.0))
    cols = ["match_id", "period", "frame", "time_s", "team", "player_id", "is_goalkeeper", "x", "y"]
    return pd.DataFrame(rows, columns=cols)


def test_assign_goalkeepers_picks_deepest_player_per_team():
    out = assign_goalkeepers(_tracking())
    gks = set(out.loc[out["is_goalkeeper"], "player_id"])
    assert gks == {"home_gk", "away_gk"}


def test_assign_goalkeepers_ignores_brief_appearances():
    t = _tracking()
    # A player who appears in one frame only, deeper than the goalkeeper.
    extra = t.iloc[[0]].assign(player_id="home_brief", x=-52.0)
    out = assign_goalkeepers(pd.concat([t, extra], ignore_index=True))
    assert not out.loc[out["player_id"] == "home_brief", "is_goalkeeper"].any()


def _match(tracking):
    ball = pd.DataFrame({"match_id": "m", "period": 1, "frame": range(1, 11),
                         "time_s": 0.0, "x": 0.0, "y": 0.0})
    events = pd.DataFrame([{
        "match_id": "m", "period": 1, "frame": 5, "time_s": 0.16, "end_frame": 6,
        "end_time_s": 0.2, "team": "home", "type": "PASS", "subtype": None,
        "player_id": "home_fwd", "to_player_id": "home_def",
        "x": 0.0, "y": 0.0, "end_x": 1.0, "end_y": 1.0,
    }])
    return MatchData("m", 25, tracking, ball, events)


def test_validate_accepts_clean_match():
    validate_match(_match(assign_goalkeepers(_tracking())))


def test_validate_rejects_duplicate_rows():
    t = assign_goalkeepers(_tracking())
    with pytest.raises(ValueError, match="duplicate"):
        validate_match(_match(pd.concat([t, t.iloc[[0]]], ignore_index=True)))


def test_validate_rejects_missing_goalkeeper():
    with pytest.raises(ValueError, match="goalkeeper"):
        validate_match(_match(_tracking()))  # is_goalkeeper never set
