#!/usr/bin/env bash
# Download the public datasets into data/raw/. Safe to re-run.
# Raw data is never committed to git (see .gitignore) and never modified.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

# Metrica Sports sample data. Pinned to the audited commit (docs/01_dataset_audit.md).
METRICA_COMMIT="e706dd5"
if [ ! -d "$RAW/metrica/.git" ]; then
    git clone https://github.com/metrica-sports/sample-data.git "$RAW/metrica"
fi
git -C "$RAW/metrica" fetch --quiet --depth 50 origin || true
git -C "$RAW/metrica" checkout --quiet "$METRICA_COMMIT"
echo "Metrica: $(git -C "$RAW/metrica" log --oneline -1)"

# IDSSE (Bassek et al., 2025) will be added in the replication step.
