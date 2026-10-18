"""Smoke tests: the environment is installed and the config is valid."""

import importlib

import pytest

from pmi.config import PROJECT_ROOT, load_config, set_seed

REQUIRED_PACKAGES = [
    "numpy", "pandas", "pyarrow", "scipy", "statsmodels",
    "sklearn", "matplotlib", "plotly", "yaml", "kloppy",
]


@pytest.mark.parametrize("name", REQUIRED_PACKAGES)
def test_package_importable(name):
    importlib.import_module(name)


def test_config_loads():
    cfg = load_config()
    assert cfg.seed == 42
    assert cfg["tracking"]["fps"] == 25
    assert cfg["pitch"]["length_m"] == 105.0
    assert cfg.path("raw") == PROJECT_ROOT / "data" / "raw"


def test_seed_is_reproducible():
    a = set_seed(42).normal(size=5)
    b = set_seed(42).normal(size=5)
    assert (a == b).all()


def test_replication_config_inherits_analysis_settings():
    base, rep = load_config(), load_config(PROJECT_ROOT / "configs" / "idsse.yaml")
    assert rep.dataset == "idsse" and len(rep.match_ids) == 7
    assert rep.match_ids[0] == "idsse_J03WMX"
    for key in ("timecourse", "metrics", "tracking", "pitch", "seed"):
        assert rep[key] == base[key]  # identical analysis settings
    assert rep["possession"]["min_gap_between_turnovers_s"] == base["possession"][
        "min_gap_between_turnovers_s"]
    assert rep.path("tables") != base.path("tables")  # outputs kept apart
