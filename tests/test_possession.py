"""Tests for possession spells and turnovers: synthetic unit tests plus real-data checks."""

import numpy as np
import pandas as pd
import pytest

from pmi.config import load_config
from pmi.possession import (
    attacking_x,
    find_turnovers,
    frame_possession,
    pitch_third,
    possession_spells,
    turnover_funnel,
)

CFG = load_config()
CONTROL = CFG["possession"]["control_event_types"]
FPS = 25


def _frames(n=300, dead=()):
    in_play = np.ones(n, dtype=bool)
    for a, b in dead:
        in_play[a - 1:b] = False  # frames a..b (1-based, inclusive) are dead
    return pd.DataFrame({
        "match_id": "m", "period": 1, "frame": np.arange(1, n + 1), "in_play": in_play,
        "ball_x": -30.0, "ball_y": 0.0,
    })


def _events(rows):
    return pd.DataFrame(
        [{"match_id": "m", "period": 1, "frame": f, "team": t, "type": ty, "subtype": None,
          "player_id": f"{t}_player"} for f, t, ty in rows]
    )


def test_attacking_x_and_thirds():
    x_att = attacking_x(np.array([-30.0, -30.0, 0.0]), np.array(["home", "away", "home"]))
    np.testing.assert_allclose(x_att, [-30.0, 30.0, 0.0])
    assert pitch_third(x_att, 105.0).tolist() == ["defensive", "attacking", "middle"]


def test_simple_open_play_turnover():
    ev = _events([(1, "home", "SET PIECE"), (50, "home", "PASS"), (100, "home", "BALL LOST"),
                  (140, "away", "RECOVERY"), (200, "away", "PASS")])
    sp = possession_spells(ev, _frames(), CONTROL, FPS)
    assert sp["team"].tolist() == ["home", "away"]
    assert sp["start_frame"].tolist() == [1, 140]
    assert sp["end_frame"].tolist() == [139, 300]
    assert sp["end_reason"].tolist() == ["turnover", "stoppage"]
    assert sp["open_play_change"].tolist() == [False, True]
    assert sp.loc[0, "in_play_s"] == pytest.approx(139 / FPS)


def test_change_across_a_stoppage_is_not_an_open_play_turnover():
    # Ball dead in frames 110-129; away restarts with a throw-in at 130.
    ev = _events([(1, "home", "SET PIECE"), (100, "home", "PASS"), (130, "away", "SET PIECE")])
    sp = possession_spells(ev, _frames(dead=[(110, 129)]), CONTROL, FPS)
    assert sp["open_play_change"].tolist() == [False, False]
    assert sp.loc[0, "end_frame"] == 109  # spell stops when play stops
    assert sp.loc[0, "end_reason"] == "stoppage"


def test_same_team_after_stoppage_starts_new_spell():
    ev = _events([(1, "home", "SET PIECE"), (100, "home", "PASS"), (130, "home", "SET PIECE")])
    sp = possession_spells(ev, _frames(dead=[(110, 129)]), CONTROL, FPS)
    assert len(sp) == 2 and not sp["open_play_change"].any()


def test_non_control_events_do_not_change_possession():
    ev = _events([(1, "home", "SET PIECE"), (50, "away", "CHALLENGE"), (60, "away", "CARRY"),
                  (100, "home", "PASS")])
    sp = possession_spells(ev, _frames(), CONTROL, FPS)
    assert len(sp) == 1


def test_frame_possession_blank_when_out_of_play():
    ev = _events([(1, "home", "SET PIECE"), (140, "away", "RECOVERY")])
    frames = _frames(dead=[(200, 220)])
    fp = frame_possession(possession_spells(ev, frames, CONTROL, FPS), frames)
    assert fp.loc[fp["frame"] < 140, "possession"].eq("home").all()
    assert fp.loc[fp["frame"].between(140, 199), "possession"].eq("away").all()
    assert fp.loc[fp["frame"].between(200, 220), "possession"].isna().all()


def test_turnover_filters_and_zone():
    # home: 1-139 (5.6 s) -> away 140-159 (0.8 s) -> home 160-300.
    ev = _events([(1, "home", "SET PIECE"), (100, "home", "BALL LOST"),
                  (140, "away", "RECOVERY"), (150, "away", "BALL LOST"),
                  (160, "home", "RECOVERY")])
    frames = _frames()
    to = find_turnovers(possession_spells(ev, frames, CONTROL, FPS), frames, ev, CFG)
    assert to["t0_frame"].tolist() == [140, 160]
    first, second = to.iloc[0], to.iloc[1]
    assert first["ok_prev_spell"] and not first["ok_next_spell"]  # away kept it < 2 s
    assert not second["ok_prev_spell"]
    assert second["gap_prev_s"] == pytest.approx(20 / FPS) and not second["ok_gap"]
    assert not to["included"].any()
    # Ball at x = -30: the away team (attacking -x) won it in its attacking third.
    assert first["zone_won"] == "attacking" and second["zone_won"] == "defensive"
    assert turnover_funnel(to)["n"].tolist() == [2, 1, 0, 0, 0]


# ---------------------------------------------------------------- real data

EXPECTED_INCLUDED = {1: 121, 2: 96, 3: 137}  # regression values, see reports/tables


@pytest.fixture(scope="module", params=[1, 2, 3])
def real(request):
    from pmi.preprocessing import read_processed

    if not (CFG.path("processed") / f"metrica_{request.param}_frames.parquet").exists():
        pytest.skip("processed data missing (run `make preprocess`)")
    pm = read_processed(f"metrica_{request.param}", CFG)
    sp = possession_spells(pm.events, pm.frames, CONTROL, FPS)
    return request.param, pm, sp, find_turnovers(sp, pm.frames, pm.events, CFG)


@pytest.mark.data
def test_real_in_play_frames_have_possession(real):
    _, pm, sp, _ = real
    fp = frame_possession(sp, pm.frames)
    # Game 2 has one isolated in-play frame before any control event; allow <= 0.1 %.
    assert fp.loc[pm.frames["in_play"].to_numpy(), "possession"].isna().mean() <= 0.001
    share = fp["possession"].value_counts(normalize=True)
    assert 0.3 < share["home"] < 0.7


@pytest.mark.data
def test_real_turnovers_are_open_play_and_stable(real):
    game, pm, _, to = real
    assert to["won_team"].ne(to["lost_team"]).all()
    live = pm.frames.set_index("frame")["in_play"]
    assert live.reindex(to.loc[to["included"], "t0_frame"]).all()
    assert not to["trigger_subtype"].fillna("").str.contains("OFFSIDE").any()
    assert int(to["included"].sum()) == EXPECTED_INCLUDED[game]
