"""Dataset loaders. Every loader returns a :class:`MatchData` in the common format."""

from pmi.config import Config
from pmi.io.common import MatchData, read_interim, write_interim

__all__ = ["MatchData", "load_match", "read_interim", "write_interim"]


def load_match(match_id: str, cfg: Config) -> MatchData:
    """Load one match by id (``metrica_1``, ``idsse_J03WMX``) with the right loader."""
    dataset, _, key = match_id.partition("_")
    if dataset == "metrica":
        from pmi.io import metrica

        return metrica.load_match(int(key), cfg)
    if dataset == "idsse":
        from pmi.io import idsse

        return idsse.load_match(key, cfg)
    raise ValueError(f"unknown dataset in match id: {match_id}")
