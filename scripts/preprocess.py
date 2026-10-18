"""Preprocess every match in data/interim/ and write results to data/processed/.

Also writes the quality-control table to reports/tables/preprocessing_qc.csv.

Usage:
    uv run python scripts/preprocess.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse

import pandas as pd

from pmi.config import load_config
from pmi.io import read_interim
from pmi.preprocessing import preprocess_match, qc_summary, write_processed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="path to a YAML config")
    args = parser.parse_args()
    cfg = load_config(args.config)

    rows = []
    for match_id in cfg.match_ids:
        print(f"Preprocessing {match_id} ...", flush=True)
        pm = preprocess_match(read_interim(match_id, cfg), cfg)
        write_processed(pm, cfg)
        rows.append(qc_summary(pm))

    qc = pd.DataFrame(rows)
    out = cfg.path("tables")
    out.mkdir(parents=True, exist_ok=True)
    qc.to_csv(out / "preprocessing_qc.csv", index=False)
    print()
    print(qc.T.to_string(header=False))


if __name__ == "__main__":
    main()
