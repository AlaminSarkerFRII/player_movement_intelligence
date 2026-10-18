# Local workflow uses uv; Docker targets run the same commands in a container.
export UID := $(shell id -u)
export GID := $(shell id -g)

.PHONY: setup lock data interim preprocess possession pipeline test test-data lint jupyter docker-build docker-test docker-shell docker-jupyter

setup:            ## Create .venv and install locked dependencies
	uv sync

lock:             ## Update uv.lock after changing pyproject.toml
	uv lock

data:             ## Download raw datasets into data/raw
	bash scripts/download_data.sh

interim:          ## Load, validate and convert raw data to data/interim (parquet)
	uv run python scripts/build_interim.py

preprocess:       ## Direction, velocities + QC, ball in play -> data/processed
	uv run python scripts/preprocess.py

possession:       ## Possession spells, turnovers, EDA figures -> data/processed, reports/
	uv run python scripts/build_possession.py

pipeline: interim preprocess possession  ## Run every step from raw data

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
