"""Engine adapters for chess analysis.

SOTA 2026 engine pool:
  - Stockfish 18 (NNUE + Threat Inputs)
  - Berserk 13
  - Caissa 1.22
  - Crystal 9
  - Patricia 4
  - Viridithas 18
  - ShashChess 38
  - Koivisto 9.2
  - RubiChess
  - Lc0 0.32.2 (Leela Chess Zero)
  - Maia-2 unified (NeurIPS 2024)

All engines implement the `Engine` ABC (this/base.py).
"""

from chess_coach.engines.base import Engine, EngineInfo, Evaluation
from chess_coach.engines.stockfish import Stockfish18Engine
from chess_coach.engines.lc0 import Lc0Engine
from chess_coach.engines.maia2 import Maia2Engine
from chess_coach.engines.multi_engine_pool import MultiEnginePool

__all__ = [
    "Engine",
    "EngineInfo",
    "Evaluation",
    "Stockfish18Engine",
    "Lc0Engine",
    "Maia2Engine",
    "MultiEnginePool",
]
