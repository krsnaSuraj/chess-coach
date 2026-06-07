"""Caissa - Strong open-source chess engine (Rust, NNUE).

Project: https://github.com/MartinThoma/caissa
License: GPL-3.0
ELO: ~3500 CCRL Blitz
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EngineInfo
from .stockfish import Stockfish18Engine

logger = logging.getLogger(__name__)

CAISSA_NNUE_NAME = "caissa-net.nnue"
CAISSA_DEFAULT_OPTIONS: dict[str, Any] = {
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Ponder": False,
    "Use NNUE": True,
    "EvalFile": CAISSA_NNUE_NAME,
    "Slow Mover": 100,
}


class CaissaEngine(Stockfish18Engine):
    """Caissa - UCI wrapper via Stockfish adapter."""

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Caissa",
            version="0.10.0",
            author="MartinThoma",
            elo_ceiling=3500,
            elo_floor=1500,
            type="uci",
            url="https://github.com/MartinThoma/caissa",
            option_presets=tuple(CAISSA_DEFAULT_OPTIONS.items()),
            requires=["caissa", "caissa-net.nnue"],
        )

    @property
    def option_presets(self) -> dict[str, Any]:
        return CAISSA_DEFAULT_OPTIONS.copy()
