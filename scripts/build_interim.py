"""Load every match of the configured dataset, validate it, and write it to data/interim/.

Usage:
    uv run python scripts/build_interim.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import pandas as pd

from pmi.config import load_config
from pmi.io import load_match, write_interim
from pmi.io.common import summarize_match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)

    summaries, sync_rows = [], []
    for match_id in cfg.match_ids:
        print(f"Loading {match_id} ...", flush=True)
        match = load_match(match_id, cfg)
        match.validate()
        for path in write_interim(match, cfg):
            print(f"  wrote {path.relative_to(cfg.path('interim').parent.parent)}")
        summaries.append(summarize_match(match))
        for period, lag in match.meta.get("sync_lags", {}).items():
            sync_rows.append({"match_id": match_id, "period": period, **lag,
                              "applied": bool(cfg["idsse"]["sync_events"]),
                              "events_outside_tracking": match.meta["events_outside_tracking"]})
        del match  # free memory before the next game

    tables = cfg.path("tables")
    tables.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).to_csv(tables / "interim_summary.csv", index=False)
    if sync_rows:  # event-vs-tracking lag per half (IDSSE)
        pd.DataFrame(sync_rows).to_csv(tables / "event_sync_lags.csv", index=False)
    print()
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
