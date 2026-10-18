PYTHON := venv/bin/python

.PHONY: setup data test lint freeze

setup:            ## Install the package and dev tools into ./venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

data:             ## Download raw datasets into data/raw
	bash scripts/download_data.sh

test:             ## Run the test suite
	$(PYTHON) -m pytest -q

lint:             ## Check code style
	$(PYTHON) -m ruff check src tests

freeze:           ## Record exact installed versions for reproducibility
	$(PYTHON) -m pip freeze --exclude-editable > requirements-lock.txt
