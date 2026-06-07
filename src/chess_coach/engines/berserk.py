"""Berserk - Strong open-source chess engine (C++23, SMP, NNUE).

Project: https://github.com/jhonnold/berserk
License: GPL-3.0
ELO: ~3550 CCRL Blitz (mid-2026)
"""
from __future__ import annotations

import logging
from typing import Any

from .base import EngineInfo

from .stockfish import Stockfish18Engine  # Berserk is UCI-compatible, reuse Stockfish adapter

logger = logging.getLogger(__name__)

BERSERK_NNUE_NAME = "berserk-net.nnue"
BERSERK_DEFAULT_OPTIONS: dict[str, Any] = {
    "Threads": 1,
    "Hash": 16,
    "MultiPV": 1,
    "Ponder": False,
    "Use NNUE": True,
    "EvalFile": BERSERK_NNUE_NAME,
    "Slow Mover": 100,
    "UCI_LimitStrength": False,
    "UCI_Elo": 3200,
}


class BerserkEngine(Stockfish18Engine):
    """Berserk - UCI wrapper. Inherits Stockfish adapter (UCI protocol is universal)."""

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="Berserk",
            version="2026-05",
            author="Jhonnold",
            elo_ceiling=3550,
            elo_floor=1500,
            type="uci",
            url="https://github.com/jhonnold/berserk",
            option_presets=tuple(BERSERK_DEFAULT_OPTIONS.items()),
            requires=["berserk", "berserk-net.nnue"],
        )

    @property
    def option_presets(self) -> dict[str, Any]:
        return BERSERK_DEFAULT_OPTIONS.copy()
