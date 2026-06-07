"""Opponent modeler — estimates the opponent's ELO and playstyle.

We don't have access to the opponent's full game history on chess.com (no API
key), but we DO have:
- Their move-by-move centipawn loss from our engine analysis.
- The game phase and piece activity patterns.
- Time on the clock between moves (if we track it).

From this, we can:
1. Estimate the opponent's effective ELO using a Bayesian update (same model
   as elo_calibrator.BayesianELOEstimator).
2. Categorize their style: "tactical", "positional", "aggressive", "defensive",
   "noisy" (high blunder rate), "precise" (low CPL).
3. Track counters: total moves, average CPL, blunder count, opening deviation.

This module is OPTIONAL and operates in two modes:
- LIVE : receives moves as they happen, updates internal state.
- POST : takes a final move list and produces a summary.

The "style" classification is deliberately simple — six buckets — because more
fine-grained labels are unreliable from a small sample.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import chess

from chess_coach.elo_calibrator import BayesianELOEstimator, phase_for_move_number

logger = logging.getLogger(__name__)


class OpponentStyle(str, Enum):
    PRECISE = "precise"          # low CPL, accurate
    TACTICAL = "tactical"        # prefers captures, checks, attacks
    POSITIONAL = "positional"    # few captures, slow improvement
    AGGRESSIVE = "aggressive"    # high attack moves, sacrifices
    DEFENSIVE = "defensive"      # low attack moves, lots of recaptures
    NOISY = "noisy"              # high blunder rate, inconsistent
    UNKNOWN = "unknown"          # not enough data


STYLE_LABELS: dict[OpponentStyle, str] = {
    OpponentStyle.PRECISE:    "Precise",
    OpponentStyle.TACTICAL:   "Tactical",
    OpponentStyle.POSITIONAL: "Positional",
    OpponentStyle.AGGRESSIVE: "Aggressive",
    OpponentStyle.DEFENSIVE:  "Defensive",
    OpponentStyle.NOISY:      "Inconsistent",
    OpponentStyle.UNKNOWN:    "Unknown",
}


@dataclass
class OpponentMoveRecord:
    move_number: int
    cpl: float
    is_capture: bool
    is_check: bool
    is_castle: bool
    phase: str


@dataclass
class OpponentModel:
    """Live model of the opponent."""

    elo: BayesianELOEstimator = field(default_factory=BayesianELOEstimator)
    moves: list[OpponentMoveRecord] = field(default_factory=list)
    captures: int = 0
    checks: int = 0
    castles: int = 0
    blunders: int = 0          # CPL > 200
    total_cpl: float = 0.0

    def record_move(self, rec: OpponentMoveRecord) -> None:
        self.moves.append(rec)
        if rec.is_capture:
            self.captures += 1
        if rec.is_check:
            self.checks += 1
        if rec.is_castle:
            self.castles += 1
        if rec.cpl > 200:
            self.blunders += 1
        self.total_cpl += rec.cpl
        self.elo.update(rec.cpl)

    @property
    def avg_cpl(self) -> float:
        if not self.moves:
            return 0.0
        return self.total_cpl / len(self.moves)

    @property
    def capture_rate(self) -> float:
        if not self.moves:
            return 0.0
        return self.captures / len(self.moves)

    @property
    def check_rate(self) -> float:
        if not self.moves:
            return 0.0
        return self.checks / len(self.moves)

    @property
    def blunder_rate(self) -> float:
        if not self.moves:
            return 0.0
        return self.blunders / len(self.moves)

    def classify_style(self) -> OpponentStyle:
        if len(self.moves) < 6:
            return OpponentStyle.UNKNOWN
        if self.blunder_rate > 0.30:
            return OpponentStyle.NOISY
        if self.avg_cpl < 25 and self.blunder_rate < 0.10:
            return OpponentStyle.PRECISE
        if self.capture_rate > 0.45 and self.check_rate > 0.15:
            return OpponentStyle.TACTICAL
        if self.capture_rate < 0.20 and self.check_rate < 0.10:
            return OpponentStyle.POSITIONAL
        if self.check_rate > 0.18:
            return OpponentStyle.AGGRESSIVE
        if self.capture_rate > 0.35 and self.check_rate < 0.12:
            return OpponentStyle.DEFENSIVE
        return OpponentStyle.UNKNOWN

    def summary(self) -> dict:
        return {
            "estimated_elo": self.elo.mean_elo,
            "elo_std": self.elo.std_elo,
            "elo_ci95": self.elo.ci95,
            "n_moves": len(self.moves),
            "avg_cpl": round(self.avg_cpl, 1),
            "blunder_rate": round(self.blunder_rate, 3),
            "capture_rate": round(self.capture_rate, 3),
            "check_rate": round(self.check_rate, 3),
            "style": self.classify_style().value,
            "style_label": STYLE_LABELS[self.classify_style()],
        }


def model_opponent_from_moves(
    moves: list[tuple[chess.Move, float]],
    board_at_each: list[chess.Board] | None = None,
) -> OpponentModel:
    """Build an OpponentModel from a list of (move, cpl) pairs.

    If `board_at_each` is provided, we also derive capture/check/castle flags
    from the board state before the move.
    """
    model = OpponentModel()
    for i, (mv, cpl) in enumerate(moves):
        if board_at_each is not None and i < len(board_at_each):
            b = board_at_each[i]
        else:
            b = chess.Board()
        phase = phase_for_move_number(b.fullmove_number, b.legal_moves.count() if b.move_stack else 60)
        rec = OpponentMoveRecord(
            move_number=b.fullmove_number,
            cpl=cpl,
            is_capture=b.is_capture(mv),
            is_check=False,
            is_castle=b.is_castling(mv),
            phase=phase,
        )
        b.push(mv)
        rec.is_check = b.is_check()
        model.record_move(rec)
    return model


__all__ = [
    "OpponentStyle",
    "STYLE_LABELS",
    "OpponentMoveRecord",
    "OpponentModel",
    "model_opponent_from_moves",
]
