"""ShashChess - Strong open-source chess engine (C++, NNUE).

Project: https://github.com/rosenthj/ShashChess
License: GPL-3.0
ELO: ~3540 CCRL Blitz
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EngineInfo
from .stockfish import Stockfish18Engine

logger = logging.getLogger(__name__)

SHASHCHESS_NNUE_NAME = "shashchess-net.nnue"
SHASHCHESS_DEFAULT_OPTIONS: dict[str, Any] = {
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Ponder": False,
    "Use NNUE": True,
    "EvalFile": SHASHCHESS_NNUE_NAME,
    "Slow Mover": 100,
    "UseBook": True,
}


class ShashChessEngine(Stockfish18Engine):
    """ShashChess - UCI wrapper via Stockfish adapter."""

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="ShashChess",
            version="37.0",
            author="rosenthj",
            elo_ceiling=3540,
            elo_floor=1500,
            type="uci",
            url="https://github.com/rosenthj/ShashChess",
            option_presets=tuple(SHASHCHESS_DEFAULT_OPTIONS.items()),
            requires=["shashchess", "shashchess-net.nnue"],
        )

    @property
    def option_presets(self) -> dict[str, Any]:
        return SHASHCHESS_DEFAULT_OPTIONS.copy()
