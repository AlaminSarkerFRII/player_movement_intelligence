"""Shape metrics on hand-made formations with known answers."""

import numpy as np
import pandas as pd
import pytest

from pmi.metrics import hull_area, team_shape


def _frame(points, team="home", frame=1, gk=None):
    rows = [{"match_id": "m", "period": 1, "frame": frame, "team": team,
             "player_id": f"{team}{i}", "is_goalkeeper": False, "x": x, "y": y}
            for i, (x, y) in enumerate(points)]
    if gk is not None:
        rows.append({"match_id": "m", "period": 1, "frame": frame, "team": team,
                     "player_id": f"{team}_gk", "is_goalkeeper": True, "x": gk[0], "y": gk[1]})
    return pd.DataFrame(rows)


SQUARE = [(0, 0), (10, 0), (0, 10), (10, 10), (5, 5)]  # 10 m square plus a centre player


def test_square_formation():
    s = team_shape(_frame(SQUARE, gk=(-45, 0))).iloc[0]
    assert s["n_players"] == 5  # goalkeeper excluded
    assert s["length"] == 10 and s["width"] == 10
    assert s["area"] == pytest.approx(100)
    # four corners at 5*sqrt(2) from the centroid (5, 5), one player at 0
    assert s["stretch"] == pytest.approx(4 * 5 * np.sqrt(2) / 5)
    assert (s["centroid_x"], s["centroid_y"]) == (5, 5)


def test_goalkeeper_included_when_requested():
    s = team_shape(_frame(SQUARE, gk=(-45, 0)), exclude_goalkeeper=False).iloc[0]
    assert s["n_players"] == 6 and s["length"] == 55


def test_centroid_x_att_flips_for_away():
    shape = team_shape(pd.concat([_frame(SQUARE), _frame(SQUARE, team="away")]))
    att = shape.set_index("team")["centroid_x_att"]
    assert att["home"] == 5 and att["away"] == -5


def test_frames_and_teams_are_kept_separate():
    a = _frame(SQUARE, frame=1)
    b = _frame([(x * 2, y * 2) for x, y in SQUARE], frame=2)  # same shape, doubled
    shape = team_shape(pd.concat([b, a])).set_index("frame")  # unsorted input
    assert shape.loc[1, "area"] == pytest.approx(100)
    assert shape.loc[2, "area"] == pytest.approx(400)


def test_hull_area_edge_cases():
    assert np.isnan(hull_area(np.array([[0, 0], [1, 1]])))
    assert hull_area(np.array([[0, 0], [1, 1], [2, 2]])) == 0.0  # collinear
    tri = np.array([[0, 0], [4, 0], [0, 3]])
    assert hull_area(tri) == pytest.approx(6)
