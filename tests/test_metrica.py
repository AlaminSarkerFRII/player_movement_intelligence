"""Tests for the Metrica loader.

Unit tests use small synthetic files in the Metrica layout. Tests marked
``data`` load the real files and check them against docs/01_dataset_audit.md;
run them with ``make test-data``.
"""

import json

import pytest

from pmi.config import load_config
from pmi.io import metrica
from pmi.io.common import summarize_match

TRACKING_CSV = """\
,,,Home,,Home,,,
,,,11,,26,,,
Period,Frame,Time [s],Player11,,Player 26,,Ball,
1,1,0.04,0.1,0.5,0.6,0.4,0.5,0.5
1,2,0.08,0.1,0.5,NaN,NaN,NaN,NaN
"""

EVENTS_CSV = (
    "Team,Type,Subtype,Period,Start Frame,Start Time [s],End Frame,End Time [s],"
    "From,To,Start X,Start Y,End X,End Y\n"
    "Away,SET PIECE,KICK OFF,1,1,0.04,0,0,Player19,,NaN,NaN,NaN,NaN\n"
    "Home,PASS,,1,2,0.08,3,0.12,Player 26,Player11,0.5,0.5,0.6,0.4\n"
)


def test_read_csv_tracking_parses_pairs_and_cleans_names(tmp_path):
    path = tmp_path / "tracking.csv"
    path.write_text(TRACKING_CSV)
    wide, players = metrica.read_csv_tracking(path, "home")
    assert players == {"Player11": "home", "Player26": "home"}
    assert list(wide.columns) == [
        "period", "frame", "Player11_x", "Player11_y", "Player26_x", "Player26_y",
        "ball_x", "ball_y",
    ]
    assert wide.loc[0, "Player26_y"] == 0.4
    assert wide["ball_x"].isna().sum() == 1


def test_read_csv_events_cleans_ids_and_kickoff_end_frame(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text(EVENTS_CSV)
    ev = metrica.read_csv_events(path)
    assert list(ev["team"]) == ["away", "home"]
    assert ev.loc[1, "player_id"] == "Player26"
    assert ev["end_frame"].isna().tolist() == [True, False]  # kick-off End Frame = 0


def test_read_json_events_joins_list_subtypes(tmp_path):
    record = {
        "team": {"id": "T1"}, "type": {"name": "CHALLENGE"},
        "subtypes": [{"name": "GROUND"}, {"name": "LOST"}],
        "start": {"frame": 10, "x": 0.5, "y": 0.5}, "end": {"frame": 10, "x": None, "y": None},
        "period": 1, "from": {"id": "P1"}, "to": None,
    }
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"data": [record]}))
    ev = metrica.read_json_events(path, {"T1": "home"})
    assert ev.loc[0, "subtype"] == "GROUND-LOST"
    assert ev.loc[0, "team"] == "home"
    assert ev.loc[0, "to_player_id"] is None


# ---- Real data (checked against docs/01_dataset_audit.md) ----

AUDIT = {
    # game: (frames, events, home goalkeeper, away goalkeeper)
    1: (145_006, 1_745, "Player11", "Player25"),
    2: (141_156, 1_935, "Player11", "Player25"),
    3: (143_761, 3_620, "P3578", "P3595"),
}


@pytest.fixture(scope="module", params=sorted(AUDIT))
def match(request):
    cfg = load_config()
    if not (cfg.path("raw") / "metrica").exists():
        pytest.skip("Metrica data not downloaded (run `make data`)")
    return request.param, metrica.load_match(request.param, cfg)


@pytest.mark.data
def test_real_match_matches_audit(match):
    game, m = match
    frames, events, gk_home, gk_away = AUDIT[game]
    m.validate()
    s = summarize_match(m)
    assert s["frames"] == frames
    assert s["events"] == events
    assert s["gk_home"] == gk_home
    assert s["gk_away"] == gk_away


@pytest.mark.data
def test_real_match_time_and_coordinates(match):
    _, m = match
    assert (m.ball.groupby("period")["time_s"].min() == 0).all()
    assert m.ball["frame"].diff().dropna().eq(1).all()  # no missing frames
    # Positions within the pitch plus a margin for players standing off it.
    assert m.tracking["x"].abs().max() < 52.5 + 10
    assert m.tracking["y"].abs().max() < 34 + 10
    # 11 players per team on the pitch (12 for one frame at a substitution).
    per_frame = m.tracking.groupby(["frame", "team"], observed=True).size()
    assert per_frame.between(11, 12).all()


@pytest.mark.data
def test_game3_goalkeepers_match_provider_labels(match):
    game, m = match
    if game != 3:
        pytest.skip("provider goalkeeper labels exist only for Game 3")
    detected = sorted(m.tracking.loc[m.tracking["is_goalkeeper"], "player_id"].unique())
    assert detected == m.meta["provider_goalkeepers"]
