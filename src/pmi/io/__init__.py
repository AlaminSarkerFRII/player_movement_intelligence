"""Dataset loaders. Every loader returns a :class:`MatchData` in the common format."""

from pmi.io.common import MatchData, read_interim, write_interim

__all__ = ["MatchData", "read_interim", "write_interim"]
