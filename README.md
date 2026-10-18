# Player Movement Intelligence

**How soccer teams reorganize their shape after a change of possession: a
reproducible analysis of open positional tracking data.**

> Status: work in progress. H1 (replication) and H2/H3 analyses complete on 3 Metrica matches; replication on a second dataset pending.

## Quick start

**Option A: local, with [uv](https://docs.astral.sh/uv/)**

```bash
make setup     # create .venv with the exact locked dependencies (uv sync)
make data      # download Metrica Sports sample data into data/raw/
make test      # verify the environment
make pipeline  # raw data -> results tables and figures (~1.5 min)
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

## Data acknowledgement

Tracking and event data: [Metrica Sports sample data](https://github.com/metrica-sports/sample-data).
Raw data is not redistributed in this repository.
