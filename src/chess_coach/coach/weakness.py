"""Game-phase-based weakness finder.

Analyses a collection of games and surfaces phases (opening/middlegame/endgame)
and categories (tactics/positional/endgame/time) where the user loses the
most points. This is the foundation for personalized training plans.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Dict, List, Sequence, Tuple,
)

import chess

from ..eval.cpl import classify_cpl


PHASE_OPENING = "opening"
PHASE_MIDDLEGAME = "middlegame"
PHASE_ENDGAME = "endgame"

CATEGORY_TACTICS = "tactics"
CATEGORY_POSITIONAL = "positional"
CATEGORY_ENDGAME = "endgame"
CATEGORY_TIME = "time"


# CPL thresholds used by `classify_category_ply` when no board context is
# available. Same scale as `eval.cpl.classify_cpl` for consistency.
_TACTICS_CPL_THRESHOLD = 100.0
_TIME_CPL_THRESHOLD = 250.0


@dataclass
class GameSample:
    """One game with the move classifications."""

    cpls: List[float]
    colors: List[chess.Color]
    plies: List[int]
    result: str  # "1-0" | "0-1" | "1/2-1/2"


def detect_phase(board: chess.Board) -> str:
    """Detect current game phase from board state.

    Opening: move 1-12 and many pieces
    Endgame: <= 6 non-pawn pieces
    Middlegame: otherwise
    """
    non_pawn = (
        board.occupied
        & ~board.pieces_mask(chess.PAWN, chess.WHITE)
        & ~board.pieces_mask(chess.PAWN, chess.BLACK)
    )
    piece_count = chess.popcount(non_pawn)
    fullmove = board.fullmove_number
    if piece_count <= 6:
        return PHASE_ENDGAME
    if fullmove <= 12:
        return PHASE_OPENING
    return PHASE_MIDDLEGAME


def classify_category(board: chess.Board, move: chess.Move, cpl_value: float) -> str:
    """Classify a single move's category based on the position.

    Heuristic (simple, not engine-deep):
    - time: very high CPL (>200cp) — typical of severe time pressure
    - endgame: end-game phase
    - tactics: position has hanging pieces / captures or large CPL
    - positional: default
    """
    if detect_phase(board) == PHASE_ENDGAME:
        return CATEGORY_ENDGAME
    if cpl_value >= _TIME_CPL_THRESHOLD:
        return CATEGORY_TIME
    if board.is_capture(move):
        return CATEGORY_TACTICS
    if board.gives_check(move):
        return CATEGORY_TACTICS
    if cpl_value > _TACTICS_CPL_THRESHOLD:
        return CATEGORY_TACTICS
    return CATEGORY_POSITIONAL




def classify_category_ply(ply: int, cpl_value: float) -> str:
    """Classify a move into a category using only ply + CPL (no board).

    Useful for batch analysis from ``GameSample`` lists that don't carry a
    chess.Board. The logic mirrors ``classify_category``'s priorities:
    time > endgame (in endgame phase) > tactics > positional.
    """
    if ply >= 60:
        phase = PHASE_ENDGAME
    elif ply < 24:
        phase = PHASE_OPENING
    else:
        phase = PHASE_MIDDLEGAME
    if phase == PHASE_ENDGAME:
        return CATEGORY_ENDGAME
    if cpl_value >= _TIME_CPL_THRESHOLD:
        return CATEGORY_TIME
    if cpl_value > _TACTICS_CPL_THRESHOLD:
        return CATEGORY_TACTICS
    if cpl_value > 50 and phase == PHASE_ENDGAME:
        return CATEGORY_ENDGAME
    return CATEGORY_POSITIONAL if cpl_value <= 50 else CATEGORY_TACTICS


@dataclass
class PhaseStats:
    """Aggregated stats for one phase or category."""

    sample_count: int = 0
    acpl: float = 0.0
    blunder_rate: float = 0.0
    mistake_rate: float = 0.0
    inaccuracy_rate: float = 0.0
    accuracy: float = 0.0
    cpls: List[float] = field(default_factory=list)

    @classmethod
    def from_cpls(cls, cpls: Sequence[float]) -> "PhaseStats":
        if not cpls:
            return cls()
        classifications = [classify_cpl(c) for c in cpls]
        total = len(cpls)
        blunders = sum(1 for c in classifications if c in ("blunder", "severe-blunder"))
        mistakes = sum(1 for c in classifications if c == "mistake")
        inaccs = sum(1 for c in classifications if c == "inaccuracy")
        return cls(
            sample_count=total,
            acpl=statistics.fmean(cpls),
            blunder_rate=blunders / total,
            mistake_rate=mistakes / total,
            inaccuracy_rate=inaccs / total,
            accuracy=_accuracy_from_cpls(cpls),
            cpls=list(cpls),
        )


def _accuracy_from_cpls(cpls: Sequence[float]) -> float:
    if not cpls:
        return 100.0
    accs = [103.1668 * math.exp(-0.04354 * c) - 3.1669 for c in cpls]
    return statistics.fmean(accs)


@dataclass
class WeaknessReport:
    """Per-phase and per-category weakness summary."""

    total_moves: int = 0
    overall_acpl: float = 0.0
    overall_accuracy: float = 0.0
    overall_blunder_rate: float = 0.0
    by_phase: Dict[str, PhaseStats] = field(default_factory=dict)
    by_category: Dict[str, PhaseStats] = field(default_factory=dict)
    worst_phase: str | None = None
    worst_category: str | None = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_moves": self.total_moves,
            "overall_acpl": self.overall_acpl,
            "overall_accuracy": self.overall_accuracy,
            "overall_blunder_rate": self.overall_blunder_rate,
            "by_phase": {k: v.__dict__ for k, v in self.by_phase.items()},
            "by_category": {k: v.__dict__ for k, v in self.by_category.items()},
            "worst_phase": self.worst_phase,
            "worst_category": self.worst_category,
        }


def analyze_weaknesses(samples: Sequence[GameSample]) -> WeaknessReport:
    """Analyze a collection of GameSample and return a WeaknessReport.

    This is a simple analysis that doesn't actually re-parse the games.
    It relies on each GameSample providing cpls + colors + plies.
    """
    if not samples:
        return WeaknessReport()

    by_phase_cpls: Dict[str, List[float]] = defaultdict(list)
    by_category_cpls: Dict[str, List[float]] = defaultdict(list)
    all_cpls: List[float] = []

    for sample in samples:
        for cpl, _color, ply in zip(sample.cpls, sample.colors, sample.plies):
            if cpl < 0 or cpl > 1000:
                continue
            all_cpls.append(cpl)
            # Phase: opening if ply < 24, endgame if ply > 60, else middlegame
            if ply < 24:
                phase = PHASE_OPENING
            elif ply > 60:
                phase = PHASE_ENDGAME
            else:
                phase = PHASE_MIDDLEGAME
            by_phase_cpls[phase].append(cpl)
            by_category_cpls[classify_category_ply(ply, cpl)].append(cpl)

    overall = PhaseStats.from_cpls(all_cpls)
    by_phase = {k: PhaseStats.from_cpls(v) for k, v in by_phase_cpls.items()}
    by_category = {k: PhaseStats.from_cpls(v) for k, v in by_category_cpls.items()}

    worst_phase = max(by_phase.items(), key=lambda kv: kv[1].acpl, default=(None, None))[0]
    worst_category = max(by_category.items(), key=lambda kv: kv[1].acpl, default=(None, None))[0]

    return WeaknessReport(
        total_moves=overall.sample_count,
        overall_acpl=overall.acpl,
        overall_accuracy=overall.accuracy,
        overall_blunder_rate=overall.blunder_rate,
        by_phase=by_phase,
        by_category=by_category,
        worst_phase=worst_phase,
        worst_category=worst_category,
    )


def find_most_improvement_potential(report: WeaknessReport) -> List[Tuple[str, float]]:
    """Rank areas with the highest ACPL (best improvement candidates)."""
    items: List[Tuple[str, float]] = []
    for phase, stats in report.by_phase.items():
        items.append((f"phase:{phase}", stats.acpl))
    for cat, stats in report.by_category.items():
        items.append((f"category:{cat}", stats.acpl))
    items.sort(key=lambda x: -x[1])
    return items


__all__ = [
    "GameSample",
    "PhaseStats",
    "WeaknessReport",
    "PHASE_OPENING",
    "PHASE_MIDDLEGAME",
    "PHASE_ENDGAME",
    "CATEGORY_TACTICS",
    "CATEGORY_POSITIONAL",
    "CATEGORY_ENDGAME",
    "CATEGORY_TIME",
    "detect_phase",
    "classify_category",
    "classify_category_ply",
    "analyze_weaknesses",
    "find_most_improvement_potential",
]
