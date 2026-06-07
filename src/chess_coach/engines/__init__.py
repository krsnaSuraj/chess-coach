"""Engine adapters for the world's strongest open-source chess engines.

All engines are UCI-compliant. Each module exposes a small ABC subclass
plus engine-specific UCI option presets.
"""
from __future__ import annotations

from .base import Engine, EngineError, EngineInfo, Evaluation
from .stockfish import SF18_NNUE_NAME, SF18_DEFAULT_OPTIONS, Stockfish18Engine, find_stockfish
from .lc0 import Lc0Engine
from .maia2 import Maia2Engine, deterministic_maia_choice
from .berserk import BerserkEngine
from .caissa import CaissaEngine
from .crystal import CrystalEngine
from .patricia import PatriciaEngine
from .shashchess import ShashChessEngine
from .multi_engine_pool import EngineWeight, MultiEnginePool, make_default_pool

__all__ = [
    "Engine",
    "EngineError",
    "EngineInfo",
    "Evaluation",
    "SF18_NNUE_NAME",
    "SF18_DEFAULT_OPTIONS",
    "Stockfish18Engine",
    "find_stockfish",
    "Lc0Engine",
    "Maia2Engine",
    "deterministic_maia_choice",
    "BerserkEngine",
    "CaissaEngine",
    "CrystalEngine",
    "PatriciaEngine",
    "ShashChessEngine",
    "EngineWeight",
    "MultiEnginePool",
    "make_default_pool",
]
