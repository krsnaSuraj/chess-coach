"""Crystal - Strong open-source chess engine (C++, NNUE).

Project: https://github.com/crystal-chess/crystal
License: GPL-3.0
ELO: ~3490 CCRL Blitz
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EngineInfo
from .stockfish import Stockfish18Engine

logger = logging.getLogger(__name__)

CRYSTAL_NNUE_NAME = "crystal-net.nnue"
CRYSTAL_DEFAULT_OPTIONS: dict[str, Any] = {
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Ponder": False,
    "Use NNUE": True,
    "EvalFile": CRYSTAL_NNUE_NAME,
    "Slow Mover": 100,
    "Contempt": 0,
}


class CrystalEngine(Stockfish18Engine):
    """Crystal - UCI wrapper via Stockfish adapter."""

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Crystal",
            version="2.1.0",
            author="Crystal Chess",
            elo_ceiling=3490,
            elo_floor=1500,
            type="uci",
            url="https://github.com/crystal-chess/crystal",
            option_presets=tuple(CRYSTAL_DEFAULT_OPTIONS.items()),
            requires=["crystal", "crystal-net.nnue"],
        )

    @property
    def option_presets(self) -> dict[str, Any]:
        return CRYSTAL_DEFAULT_OPTIONS.copy()
