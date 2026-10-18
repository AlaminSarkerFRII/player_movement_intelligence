"""Load every configured Metrica game, validate it, and write it to data/interim/.

Usage:
    uv run python scripts/build_interim.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import pandas as pd

from pmi.config import load_config
from pmi.io import metrica, write_interim
from pmi.io.common import summarize_match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)

    summaries = []
    for game in cfg["datasets"]["metrica"]["games"]:
        print(f"Loading Metrica game {game} ...", flush=True)
        match = metrica.load_match(game, cfg)
        match.validate()
        for path in write_interim(match, cfg):
            print(f"  wrote {path.relative_to(cfg.path('interim').parent.parent)}")
        summaries.append(summarize_match(match))
        del match  # free memory before the next game

    print()
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__ == "__main__":
    main()
