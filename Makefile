# Local workflow uses uv; Docker targets run the same commands in a container.
export UID := $(shell id -u)
export GID := $(shell id -g)

# Analysis config; replicate on IDSSE with: make pipeline CONFIG=configs/idsse.yaml
CONFIG ?= configs/default.yaml

.PHONY: setup lock data interim preprocess possession shape h1 h2 pipeline replicate replicate-sensitivity test test-data lint jupyter docker-build docker-test docker-shell docker-jupyter

setup:            ## Create .venv and install locked dependencies
	uv sync

lock:             ## Update uv.lock after changing pyproject.toml
	uv lock

data:             ## Download raw datasets into data/raw
	bash scripts/download_data.sh

interim:          ## Load, validate and convert raw data to data/interim (parquet)
	uv run python scripts/build_interim.py --config $(CONFIG)

preprocess:       ## Direction, velocities + QC, ball in play -> data/processed
	uv run python scripts/preprocess.py --config $(CONFIG)

possession:       ## Possession spells, turnovers, EDA figures -> data/processed, reports/
	uv run python scripts/build_possession.py --config $(CONFIG)

shape:            ## Per-frame team shape metrics + example frame figure
	uv run python scripts/build_shape.py --config $(CONFIG)

h1:               ## H1: shape in vs out of possession (mixed models, tables, figure)
	uv run python scripts/run_h1.py --config $(CONFIG)

h2:               ## H2/H3: turnover time course vs controls (tables, figures)
	uv run python scripts/run_h2.py --config $(CONFIG)

pipeline: interim preprocess possession shape h1 h2  ## Run every step from raw data

replicate:        ## Same pipeline on IDSSE (~10 min; outputs in reports/idsse/)
	$(MAKE) pipeline CONFIG=configs/idsse.yaml

replicate-sensitivity:  ## IDSSE without event sync, and with provider possession
	$(MAKE) pipeline CONFIG=configs/idsse_nosync.yaml
	$(MAKE) preprocess possession shape h1 h2 CONFIG=configs/idsse_provider.yaml

test:             ## Run the fast unit tests
	uv run pytest -q

test-data:        ## Check the real datasets against the audit (slow, ~1 min)
	uv run pytest -q -m data

lint:             ## Check code style
	uv run ruff check src tests scripts

jupyter:          ## Start JupyterLab locally
	uv run jupyter lab

docker-build:     ## Build the Docker image
	docker compose build

docker-test:      ## Run the test suite inside Docker
	docker compose run --rm app

docker-shell:     ## Open a shell inside the container
	docker compose run --rm app bash

docker-jupyter:   ## JupyterLab in Docker at http://127.0.0.1:8888 (token: pmi)
	docker compose up jupyter
