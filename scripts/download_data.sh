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

# IDSSE (Bassek et al., 2025, Sci Data 12:195; CC-BY 4.0), 7 Bundesliga matches.
# Mirror maintained by PySport (used by kloppy), pinned to one dataset revision.
# Files are checked against scripts/idsse_sha256.txt; set SKIP_IDSSE=1 to skip (~2.6 GB).
if [ "${SKIP_IDSSE:-0}" != "1" ]; then
    IDSSE_REV="a715a38dfbaf5f58e431727c2b78d174101a703c"
    IDSSE_URL="https://huggingface.co/datasets/pysport/idsse-data/resolve/$IDSSE_REV"
    mkdir -p "$RAW/idsse"
    while read -r sha name; do
        [ -z "$name" ] && continue
        dest="$RAW/idsse/$name"
        if [ -f "$dest" ] && echo "$sha  $dest" | sha256sum --check --status; then
            continue
        fi
        echo "Downloading $name ..."
        curl -fL --retry 5 --retry-delay 5 -C - -o "$dest" "$IDSSE_URL/$name"
        echo "$sha  $dest" | sha256sum --check --quiet
    done < "$ROOT/scripts/idsse_sha256.txt"
    echo "IDSSE: $(ls "$RAW/idsse" | wc -l) files verified"
fi
