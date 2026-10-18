# Player Movement Intelligence

**How soccer teams reorganize their shape after a change of possession: a
reproducible analysis of open positional tracking data.**

> Status: work in progress (Phase 2, project setup). No results yet.

## Quick start (Ubuntu)

```bash
python3 -m venv venv
make setup     # install package + dev tools
make data      # download Metrica Sports sample data into data/raw/
make test      # verify the environment
```

## Documentation

- [Dataset audit](docs/01_dataset_audit.md)
- [Literature notes](docs/02_literature_notes.md)
- [Research proposal](docs/03_research_proposal.md)
- [Architecture](docs/04_architecture.md)

## Data acknowledgement

Tracking and event data: [Metrica Sports sample data](https://github.com/metrica-sports/sample-data).
Raw data is not redistributed in this repository.
