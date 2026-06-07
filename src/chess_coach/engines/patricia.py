"""Patricia - Strong open-source chess engine (C++, NNUE).

Project: https://github.com/patricia-chess/patricia
License: GPL-3.0
ELO: ~3520 CCRL Blitz
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EngineInfo
from .stockfish import Stockfish18Engine

logger = logging.getLogger(__name__)

PATRICIA_NNUE_NAME = "patricia-net.nnue"
PATRICIA_DEFAULT_OPTIONS: dict[str, Any] = {
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Ponder": False,
    "Use NNUE": True,
    "EvalFile": PATRICIA_NNUE_NAME,
    "Slow Mover": 100,
}


class PatriciaEngine(Stockfish18Engine):
    """Patricia - UCI wrapper via Stockfish adapter."""

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Patricia",
            version="1.5.0",
            author="Patricia Chess",
            elo_ceiling=3520,
            elo_floor=1500,
            type="uci",
            url="https://github.com/patricia-chess/patricia",
            option_presets=tuple(PATRICIA_DEFAULT_OPTIONS.items()),
            requires=["patricia", "patricia-net.nnue"],
        )

    @property
    def option_presets(self) -> dict[str, Any]:
        return PATRICIA_DEFAULT_OPTIONS.copy()
