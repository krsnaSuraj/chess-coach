"""Abstract base class for all chess engine adapters.

The SOTA 2026 chess engine ecosystem is large (Stockfish, Lc0, Maia, Berserk, etc.).
We define a uniform interface so the multi-engine pool can aggregate across all
of them and the coach UI can swap engines on the fly.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EngineInfo:
    name: str
    version: str
    author: str
    elo_ceiling: int
    elo_floor: int
    type: str  # "uci" | "maia" | "lc0" | "neural"
    requires: list[str] = field(default_factory=list)
    url: str = ""
    option_presets: tuple[tuple[str, Any], ...] = ()


@dataclass
class Evaluation:
    score_cp: int  # centipawns from side-to-move perspective
    mate: int | None = None  # mate in N, positive = winning
    depth: int = 0
    nodes: int = 0
    nps: int = 0
    time_ms: int = 0
    pv: list[str] = field(default_factory=list)  # principal variation
    multipv: list[dict[str, Any]] = field(default_factory=list)  # all PV lines
    wdl: tuple[int, int, int] | None = None  # (win, draw, loss) per-mille
    threats: list[str] = field(default_factory=list)  # Threat inputs
    source_engine: str = ""  # which engine produced this

    @property
    def winrate(self) -> float:
        """Estimated win probability for side-to-move (0.0 to 1.0)."""
        if self.mate is not None:
            return 1.0 if self.mate > 0 else 0.0
        if self.wdl is not None:
            w, d, l = self.wdl
            return (w + d * 0.5) / 1000.0
        # Sigmoid cp-to-winrate: 400cp = 10x winrate
        # Use 800 as the saturation point so 1000+cp = exactly 1.0
        cp = max(min(self.score_cp, 1000), -1000)
        if cp >= 1000:
            return 1.0
        if cp <= -1000:
            return 0.0
        return 1.0 / (1.0 + 10 ** (-cp / 400.0))


class Engine(abc.ABC):
    """All engine adapters implement this interface."""

    @abc.abstractmethod
    def info(self) -> EngineInfo: ...

    @abc.abstractmethod
    def start(self) -> None: ...

    @abc.abstractmethod
    def stop(self) -> None: ...

    @abc.abstractmethod
    def is_ready(self) -> bool: ...

    @abc.abstractmethod
    def evaluate(self, fen: str, depth: int = 20, multipv: int = 1) -> Evaluation: ...

    @abc.abstractmethod
    def set_option(self, name: str, value: Any) -> None: ...

    @abc.abstractmethod
    def get_options(self) -> dict[str, Any]: ...


class EngineError(RuntimeError):
    """Raised when an engine subprocess fails or returns malformed data."""
