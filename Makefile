# Local workflow uses uv; Docker targets run the same commands in a container.
export UID := $(shell id -u)
export GID := $(shell id -g)

.PHONY: setup lock data test lint jupyter docker-build docker-test docker-shell docker-jupyter

setup:            ## Create .venv and install locked dependencies
	uv sync

lock:             ## Update uv.lock after changing pyproject.toml
	uv lock

data:             ## Download raw datasets into data/raw
	bash scripts/download_data.sh

test:             ## Run the test suite
	uv run pytest -q

lint:             ## Check code style
	uv run ruff check src tests

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
