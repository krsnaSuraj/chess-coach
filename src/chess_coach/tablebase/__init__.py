"""Endgame tablebase support.

SOTA 2026 endgame play uses Syzygy tablebases (smaller + faster than Nalimov).
We support:
  - Local Syzygy 3-5 piece (default, ~1GB)
  - Local Syzygy 6-7 piece (opt-in, ~70GB-1.2TB)
  - Lichess Tablebase API fallback for 7-piece remote probe (free)
"""

from chess_coach.tablebase.syzygy import SyzygyProbe, TablebaseResult

__all__ = ["SyzygyProbe", "TablebaseResult"]
