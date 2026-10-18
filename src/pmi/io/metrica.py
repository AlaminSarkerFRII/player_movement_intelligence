"""Loader for the Metrica Sports sample data.

- Games 1-2: Metrica CSV (three header rows; two columns per player).
- Game 3: FIFA EPTS tracking (parsed with kloppy) and JSON events.

See ``docs/01_dataset_audit.md`` for the raw format details.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pmi.config import Config
from pmi.io.common import MatchData, build_match

GAME_DIR = "metrica/data/Sample_Game_{game}"


def _clean_player_id(name: pd.Series) -> pd.Series:
    """'Player 26' -> 'Player26' (Game 2 has one column with a space)."""
    return name.str.replace(" ", "", regex=False)


def read_csv_tracking(path: Path, team: str) -> tuple[pd.DataFrame, dict[str, str]]:
    """Read one team's CSV tracking file into a wide table with normalized coordinates.

    Returns the table (``period``, ``frame``, ``{player}_x/_y``, ``ball_x/_y``)
    and a mapping player_id -> team.
    """
    raw = pd.read_csv(path, skiprows=2)
    names = list(raw.columns)
    data = {"period": raw["Period"].to_numpy(), "frame": raw["Frame"].to_numpy()}
    players: dict[str, str] = {}
    # Columns after Period, Frame, Time come in (x, y) pairs; only x has a name.
    for i in range(3, len(names) - 1, 2):
        name = names[i].replace(" ", "")
        key = "ball" if name == "Ball" else name
        if key != "ball":
            players[key] = team
        data[f"{key}_x"] = raw.iloc[:, i].to_numpy(dtype=float)
        data[f"{key}_y"] = raw.iloc[:, i + 1].to_numpy(dtype=float)
    return pd.DataFrame(data), players


def read_csv_events(path: Path) -> pd.DataFrame:
    """Read the CSV event file (normalized coordinates, no time columns yet)."""
    ev = pd.read_csv(path)
    end_frame = ev["End Frame"].where(ev["End Frame"] >= ev["Start Frame"])  # kick-offs use 0
    return pd.DataFrame({
        "period": ev["Period"],
        "frame": ev["Start Frame"],
        "end_frame": end_frame.astype("Int64"),
        "team": ev["Team"].str.lower(),
        "type": ev["Type"],
        "subtype": ev["Subtype"],
        "player_id": _clean_player_id(ev["From"]),
        "to_player_id": _clean_player_id(ev["To"]),
        "x": ev["Start X"], "y": ev["Start Y"], "end_x": ev["End X"], "end_y": ev["End Y"],
    })


def _subtype_name(subtypes: dict | list | None) -> str | None:
    """JSON subtypes are null, one object, or a list (joined like the CSV: 'GROUND-LOST')."""
    if subtypes is None:
        return None
    if isinstance(subtypes, dict):
        return subtypes["name"]
    return "-".join(s["name"] for s in subtypes)


def read_json_events(path: Path, team_grounds: dict[str, str]) -> pd.DataFrame:
    """Read Game 3 JSON events; ``team_grounds`` maps team id to 'home'/'away'."""
    with path.open() as f:
        records = json.load(f)["data"]
    rows = [{
        "period": e["period"],
        "frame": e["start"]["frame"],
        "end_frame": e["end"]["frame"],
        "team": team_grounds[e["team"]["id"]],
        "type": e["type"]["name"],
        "subtype": _subtype_name(e["subtypes"]),
        "player_id": (e["from"] or {}).get("id"),
        "to_player_id": (e["to"] or {}).get("id"),
        "x": e["start"]["x"], "y": e["start"]["y"],
        "end_x": e["end"]["x"], "end_y": e["end"]["y"],
    } for e in records]
    events = pd.DataFrame(rows)
    for col in ("x", "y", "end_x", "end_y"):
        events[col] = events[col].astype(float)
    events["end_frame"] = events["end_frame"].astype("Int64")
    return events


def _load_csv_game(root: Path, game: int):
    prefix = root / f"Sample_Game_{game}"
    home, home_players = read_csv_tracking(Path(f"{prefix}_RawTrackingData_Home_Team.csv"), "home")
    away, away_players = read_csv_tracking(Path(f"{prefix}_RawTrackingData_Away_Team.csv"), "away")
    if not np.array_equal(home["frame"].to_numpy(), away["frame"].to_numpy()):
        raise ValueError(f"Game {game}: home and away tracking frames differ")
    if home_players.keys() & away_players.keys():
        raise ValueError(f"Game {game}: player ids shared between teams")
    wide = pd.concat(
        [home, away.drop(columns=["period", "frame", "ball_x", "ball_y"])], axis=1
    )
    events = read_csv_events(Path(f"{prefix}_RawEventsData.csv"))
    return wide, {**home_players, **away_players}, events, {}


def _load_epts_game(root: Path):
    from kloppy import metrica  # imported lazily: slow import, only needed for Game 3

    dataset = metrica.load_tracking_epts(
        meta_data=root / "Sample_Game_3_metadata.xml",
        raw_data=root / "Sample_Game_3_tracking.txt",
        coordinates="metrica",  # keep the provider's [0, 1] coordinates
    )
    teams = dataset.metadata.teams
    grounds = {t.team_id: str(t.ground).lower() for t in teams}
    players = {p.player_id: grounds[t.team_id] for t in teams for p in t.players}
    provider_gks = sorted(
        p.player_id for t in teams for p in t.players
        if p.starting_position is not None and p.starting_position.name == "Goalkeeper"
    )

    df = dataset.to_df()
    players = {pid: team for pid, team in players.items() if f"{pid}_x" in df.columns}
    cols = ["ball_x", "ball_y"] + [f"{pid}_{a}" for pid in players for a in ("x", "y")]
    wide = df[["period_id", "frame_id", *cols]].rename(
        columns={"period_id": "period", "frame_id": "frame"}
    )
    wide[cols] = wide[cols].astype(float)
    events = read_json_events(root / "Sample_Game_3_events.json", grounds)
    return wide, players, events, {"provider_goalkeepers": provider_gks}


def load_match(game: int, cfg: Config) -> MatchData:
    """Load Metrica sample game 1, 2 or 3 into the common format."""
    root = cfg.path("raw") / GAME_DIR.format(game=game)
    if game in (1, 2):
        wide, players, events, meta = _load_csv_game(root, game)
    elif game == 3:
        wide, players, events, meta = _load_epts_game(root)
    else:
        raise ValueError(f"Unknown Metrica game: {game}")

    return build_match(f"metrica_{game}", wide, players, events, meta, cfg)
