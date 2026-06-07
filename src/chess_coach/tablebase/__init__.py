"""Endgame tablebase probing.

Supports:
- Syzygy 3-7 piece (local + Lichess API fallback)
- Gaviota 3-5 piece (local only, faster than Syzygy for some)
- Lomonosov 7-piece (Lichess API)
- Lichess 8-piece (Op1, 2026 release)
"""
from __future__ import annotations

from .syzygy import (
    SyzygyProbe,
    WDL_WIN,
    WDL_CURSED_WIN,
    WDL_DRAW,
    WDL_BLESSED_LOSS,
    WDL_LOSS,
    WDL_UNKNOWN,
    WDL_NAMES,
    empty_tablebase_result,
    TablebaseResult,
)
from .gaviota import GaviotaProbe, GaviotaResult, empty_gaviota_result
from .lomonosov import LomonosovProbe, LomonosovResult
from .lichess_8p import Lichess8pProbe, Op1Result, OP1_PIECE_COUNTS

__all__ = [
    "SyzygyProbe",
    "WDL_WIN",
    "WDL_CURSED_WIN",
    "WDL_DRAW",
    "WDL_BLESSED_LOSS",
    "WDL_LOSS",
    "WDL_UNKNOWN",
    "WDL_NAMES",
    "empty_tablebase_result",
    "TablebaseResult",
    "GaviotaProbe",
    "GaviotaResult",
    "empty_gaviota_result",
    "LomonosovProbe",
    "LomonosovResult",
    "Lichess8pProbe",
    "Op1Result",
    "OP1_PIECE_COUNTS",
]
