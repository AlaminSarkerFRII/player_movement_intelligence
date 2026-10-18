"""Load the YAML config and resolve project paths.

Every module receives a ``Config`` object instead of reading globals, so an
experiment is fully described by the YAML file it was run with.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "default.yaml"


@dataclass(frozen=True)
class Config:
    """Thin wrapper around the parsed YAML with resolved absolute paths."""

    raw: dict[str, Any]
    source: Path

    @property
    def seed(self) -> int:
        return int(self.raw["seed"])

    def path(self, key: str) -> Path:
        """Absolute path for an entry under ``paths:`` (e.g. ``cfg.path("raw")``)."""
        return PROJECT_ROOT / self.raw["paths"][key]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def dataset(self) -> str:
        return self.raw["dataset"]

    @property
    def match_ids(self) -> list[str]:
        """Match ids of the active dataset, e.g. ``metrica_1`` or ``idsse_J03WMX``."""
        ds = self.raw["datasets"][self.dataset]
        return [f"{self.dataset}_{m}" for m in ds["matches"]]


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _read(source: Path) -> dict[str, Any]:
    """Read YAML; a top-level ``base:`` key names a file whose values this one overrides."""
    with source.open() as f:
        raw = yaml.safe_load(f) or {}
    base = raw.pop("base", None)
    if base:
        raw = _deep_merge(_read((source.parent / base).resolve()), raw)
    return raw


def load_config(path: str | Path | None = None) -> Config:
    """Read a YAML config file; defaults to ``configs/default.yaml``."""
    source = Path(path) if path else DEFAULT_CONFIG
    return Config(raw=_read(source), source=source.resolve())


def set_seed(seed: int) -> np.random.Generator:
    """Seed Python and NumPy, and return a NumPy Generator for explicit use.

    Prefer passing the returned Generator to functions over relying on global state.
    """
    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)
