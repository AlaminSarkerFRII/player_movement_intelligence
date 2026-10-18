# Player Movement Intelligence

**How soccer teams reorganize their shape after a change of possession: a
reproducible analysis of open positional tracking data.**

> Status: work in progress. H1–H3 analysed on 3 Metrica matches and replicated on 7 IDSSE Bundesliga matches. Write-up (Phases 4–5) pending.

## Quick start

**Option A: local, with [uv](https://docs.astral.sh/uv/)**

```bash
make setup     # create .venv with the exact locked dependencies (uv sync)
make data      # download Metrica + IDSSE into data/raw/ (2.5 GB; SKIP_IDSSE=1 for Metrica only)
make test      # verify the environment
make pipeline  # raw data -> results tables and figures (~1.5 min)
make replicate              # same analysis on IDSSE (~10 min; needs `make data`, 2.5 GB)
make replicate-sensitivity  # IDSSE without event sync / with DFL possession (~14 min)
make jupyter   # optional: JupyterLab
```

**Option B: Docker (no local Python needed)**

```bash
make data            # needs only git; data is mounted into the container
make docker-build
make docker-test
make docker-jupyter  # http://127.0.0.1:8888, token: pmi
```

Run any command in the container with `docker compose run --rm app <command>`.
After changing dependencies: `make lock`, then `make setup` or `make docker-build`.

## Documentation

- [Dataset audit](docs/01_dataset_audit.md)
- [Literature notes](docs/02_literature_notes.md)
- [Research proposal](docs/03_research_proposal.md)
- [Architecture](docs/04_architecture.md)
- [Results](docs/05_results.md)
- [Literature review](docs/06_literature_review.md)

## Data acknowledgement

- Tracking and event data: [Metrica Sports sample data](https://github.com/metrica-sports/sample-data).
- Replication data: IDSSE, Bassek, M., Rein, R., Weber, H., & Memmert, D. (2025).
  An integrated dataset of spatiotemporal and event data in elite soccer.
  *Scientific Data* 12, 195. doi:10.1038/s41597-025-04505-y (CC-BY 4.0).

Raw data is not redistributed in this repository.
