"""Centipawn Loss (CPL) and Average CPL (ACPL) calculator.

CPL measures how far a move was from the engine's best in centipawns.
ACPL averages CPL over a game (or part of it) to summarize accuracy.

This module is engine-agnostic — it expects an evaluation function
that takes a board and returns a centipawn score from White's perspective.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import (
    Callable, List, Sequence,
)

import chess


EvalFn = Callable[[chess.Board], float]


def _clamp_cp(value: float) -> float:
    """Clamp a centipawn value to [-1000, 1000] (mate-like)."""
    return max(-1000.0, min(1000.0, value))


def centipawn_loss(
    board: chess.Board,
    played_move: chess.Move,
    best_move: chess.Move,
    eval_fn: EvalFn,
) -> float:
    """Compute CPL for a single move.

    If played_move == best_move, returns 0. Otherwise computes
    max(0, |eval_after_best| - |eval_after_played|) from the side's perspective.
    """
    if played_move == best_move:
        return 0.0

    board.push(played_move)
    eval_after_played = eval_fn(board)
    board.pop()

    board.push(best_move)
    eval_after_best = eval_fn(board)
    board.pop()

    # Perspective: if it's White to move in the original board
    perspective = 1.0 if board.turn == chess.WHITE else -1.0
    best_for_player = perspective * _clamp_cp(eval_after_best)
    played_for_player = perspective * _clamp_cp(eval_after_played)
    loss = best_for_player - played_for_player
    return max(0.0, loss)


def cpl_from_pair(best_cp_for_player: float, played_cp_for_player: float) -> float:
    """CPL given two centipawn values from the player's perspective (best, played)."""
    return max(0.0, best_cp_for_player - played_cp_for_player)


def average_cpl(cpls: Sequence[float]) -> float:
    """Arithmetic mean CPL. Returns 0.0 for empty input."""
    if not cpls:
        return 0.0
    return statistics.fmean(cpls)


def median_cpl(cpls: Sequence[float]) -> float:
    """Median CPL. Returns 0.0 for empty input."""
    if not cpls:
        return 0.0
    return statistics.median(cpls)


def accuracy_percent(cpl_value: float) -> float:
    """Convert CPL to an accuracy percentage using a sigmoid.

    accuracy = 103.1668 * exp(-0.04354 * cpl) - 3.1669

    (Lichess's published formula, valid for 0..100 CPL.)
    Result is clamped to [0, 100].
    """
    raw = 103.1668 * math.exp(-0.04354 * cpl_value) - 3.1669
    return max(0.0, min(100.0, raw))


def accuracy_from_cpls(cpls: Sequence[float]) -> float:
    """Average accuracy over a sequence of CPL values (0..100)."""
    if not cpls:
        return 100.0
    return statistics.fmean(accuracy_percent(c) for c in cpls)


def classify_cpl(cpl_value: float) -> str:
    """Classify a single move's CPL into a category."""
    if cpl_value < 5:
        return "best"
    if cpl_value < 20:
        return "excellent"
    if cpl_value < 50:
        return "good"
    if cpl_value < 100:
        return "inaccuracy"
    if cpl_value < 200:
        return "mistake"
    if cpl_value < 500:
        return "blunder"
    return "severe-blunder"


@dataclass
class GameAccuracy:
    """Aggregated accuracy stats for a single game."""

    white_cpls: List[float]
    black_cpls: List[float]
    white_accuracy: float
    black_accuracy: float
    white_acpl: float
    black_acpl: float
    white_blunders: int
    black_blunders: int
    white_mistakes: int
    black_mistakes: int
    # Original ordering preserved for round-trip / reporting.
    _ordered_cpls: List[float] = None  # type: ignore[assignment]

    @property
    def total_cpls(self) -> List[float]:
        if self._ordered_cpls is not None:
            return list(self._ordered_cpls)
        return self.white_cpls + self.black_cpls

    @property
    def total_moves(self) -> int:
        return len(self.white_cpls) + len(self.black_cpls)


def game_accuracy(cpls: Sequence[float], colors: Sequence[chess.Color]) -> GameAccuracy:
    """Build a GameAccuracy from a flat list of CPLs and the color of each move.

    cpls: CPL of each move (length = number of plies in the game)
    colors: chess.WHITE or chess.BLACK for each ply.
    """
    white_cpls: List[float] = [c for c, color in zip(cpls, colors) if color == chess.WHITE]
    black_cpls: List[float] = [c for c, color in zip(cpls, colors) if color == chess.BLACK]

    def count(category: str, plist: List[float]) -> int:
        return sum(1 for c in plist if classify_cpl(c) == category)

    return GameAccuracy(
        white_cpls=white_cpls,
        black_cpls=black_cpls,
        white_accuracy=accuracy_from_cpls(white_cpls),
        black_accuracy=accuracy_from_cpls(black_cpls),
        white_acpl=average_cpl(white_cpls),
        black_acpl=average_cpl(black_cpls),
        white_blunders=count("blunder", white_cpls) + count("severe-blunder", white_cpls),
        black_blunders=count("blunder", black_cpls) + count("severe-blunder", black_cpls),
        white_mistakes=count("mistake", white_cpls),
        black_mistakes=count("mistake", black_cpls),
        _ordered_cpls=list(cpls),
    )


__all__ = [
    "EvalFn",
    "centipawn_loss",
    "cpl_from_pair",
    "average_cpl",
    "median_cpl",
    "accuracy_percent",
    "accuracy_from_cpls",
    "classify_cpl",
    "GameAccuracy",
    "game_accuracy",
]
