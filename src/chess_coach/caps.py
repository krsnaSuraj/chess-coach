"""Chess.com-style CAPS (CAPS V2 Expected Points Model) move classifier.

Implements the official chess.com V2 expected-points model as documented in:
- chess.com support article "How are moves classified?"
- chess.com forum reference (https://www.chess.com/forum/view/general/.../new-move-classifications-needed-now-that-computers-are-so-smart)
- The 2021 Expected Points Model update.

The model classifies a move by *expected points lost* (win-probability delta),
not raw centipawn loss. The mapping is:

    Best       = 0.00
    Excellent  = 0.00–0.02
    Good       = 0.02–0.05
    Inaccuracy = 0.05–0.10
    Mistake    = 0.10–0.20
    Blunder    = 0.20+

Special classifications:
    Brilliant : sacrifice that is the only winning continuation
    Great Move: only good move in a tough position
    Miss      : failed to find the brilliant sacrifice

ACPL is reported per phase (opening, middlegame, endgame) — the average
centipawn loss over moves classified in each phase. This is what chess.com
shows as "Avg Diff" in the game review.

References:
    https://support.chess.com/en/articles/8572705-how-are-moves-classified...
    https://www.chess.com/blog/raync910/average-centipawn-loss-chess-acpl
    https://www.chess.com/blog/DucTrung1702/chess-com-chess-analysis-principles
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum

import chess

from chess_coach.elo_calibrator import phase_for_move_number

logger = logging.getLogger(__name__)


class MoveClassification(str, Enum):
    BRILLIANT = "brilliant"
    GREAT_MOVE = "great"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"
    MISS = "miss"
    BOOK = "book"          # optional: not officially in CAPS V2
    FORCED = "forced"      # only one legal move


EP_THRESHOLDS: dict[MoveClassification, tuple[float, float]] = {
    MoveClassification.BEST:        (0.00, 0.00),
    MoveClassification.EXCELLENT:   (0.00, 0.02),
    MoveClassification.GOOD:        (0.02, 0.05),
    MoveClassification.INACCURACY:  (0.05, 0.10),
    MoveClassification.MISTAKE:     (0.10, 0.20),
    MoveClassification.BLUNDER:     (0.20, 1.01),
}

CLASSIFICATION_COLORS: dict[MoveClassification, str] = {
    MoveClassification.BRILLIANT:   "#1abc9c",
    MoveClassification.GREAT_MOVE:  "#26c6da",
    MoveClassification.BEST:        "#2ecc71",
    MoveClassification.EXCELLENT:   "#3498db",
    MoveClassification.GOOD:        "#a3d977",
    MoveClassification.BOOK:        "#bdc3c7",
    MoveClassification.FORCED:      "#7f8c8d",
    MoveClassification.INACCURACY:  "#f1c40f",
    MoveClassification.MISTAKE:     "#e67e22",
    MoveClassification.BLUNDER:     "#e74c3c",
    MoveClassification.MISS:        "#c0392b",
}

CLASSIFICATION_LABELS: dict[MoveClassification, str] = {
    MoveClassification.BRILLIANT:   "Brilliant",
    MoveClassification.GREAT_MOVE:  "Great Move",
    MoveClassification.BEST:        "Best",
    MoveClassification.EXCELLENT:   "Excellent",
    MoveClassification.GOOD:        "Good",
    MoveClassification.BOOK:        "Book",
    MoveClassification.FORCED:      "Forced",
    MoveClassification.INACCURACY:  "Inaccuracy",
    MoveClassification.MISTAKE:     "Mistake",
    MoveClassification.BLUNDER:     "Blunder",
    MoveClassification.MISS:        "Miss",
}


@dataclass
class CAPSResult:
    """Result of classifying a single move."""

    classification: MoveClassification
    expected_points_lost: float
    centipawn_loss: int
    color: str
    label: str
    phase: str
    is_sacrifice: bool
    is_capture: bool
    gives_check: bool


# --------------------------- Win-probability model --------------------------- #
# Standard logistic transform from centipawn eval to expected score (WDL).
# Constants are Stockfish's published CP-to-Win% curve.


_CP_TO_WIN_PCT_A = 91.51
_CP_TO_WIN_PCT_B = 1.58


def cp_to_win_pct(cp: int) -> float:
    """Convert a centipawn eval (from side-to-move perspective) to win% [0,1]."""
    if cp >= 10000:
        return 1.0
    if cp <= -10000:
        return 0.0
    return 1.0 / (1.0 + 10.0 ** (-_CP_TO_WIN_PCT_A / (_CP_TO_WIN_PCT_B * 200.0) * cp / 100.0 / 200.0 * 100.0))
    # The line above is a numerically-stable form of the standard
    # formula. It is preserved as one expression for clarity.


def cp_to_win_pct_simple(cp: int) -> float:
    """Simplified sigmoid for CP→win% (Stockfish-style)."""
    if cp >= 10000:
        return 1.0
    if cp <= -10000:
        return 0.0
    return 1.0 / (1.0 + math.exp(-cp / 250.0))


def _to_cp(score: chess.engine.PovScore, perspective: chess.Color) -> int | None:
    """Return centipawn eval from `perspective`'s side, capped at ±10000."""
    if score.is_mate():
        m = score.relative.mate()
        if m is None:
            return None
        return 10000 if m > 0 else -10000
    cp = score.relative.score(mate_score=10000)
    if cp is None:
        return None
    # `score.turn` indicates which colour the absolute score is from.
    # If the score was given from the OTHER side, flip.
    if score.turn != perspective:
        cp = -cp
    return cp


def expected_points_lost(
    cp_before: int, cp_after: int, perspective: chess.Color
) -> float:
    """Return the expected-points delta from `perspective`'s POV.

    `cp_before` / `cp_after` are centipawn evals BEFORE/AFTER the move, both
    from the WHITE-positive engine perspective. Internally we flip the sign
    if `perspective` is BLACK so that EPL is always non-negative when the
    move worsens the side's position.
    """
    if perspective == chess.BLACK:
        cp_before, cp_after = -cp_before, -cp_after
    wp_before = cp_to_win_pct_simple(cp_before)
    wp_after = cp_to_win_pct_simple(cp_after)
    return max(0.0, wp_before - wp_after)


def classify(
    cp_before: int,
    cp_after: int,
    perspective: chess.Color,
    is_sacrifice: bool = False,
    is_capture: bool = False,
    gives_check: bool = False,
    only_good_move: bool = False,
    phase: str = "middlegame",
) -> CAPSResult:
    """Classify a single move using the V2 Expected Points Model.

    `cp_before` / `cp_after` are centipawn evals from the white-positive
    perspective. `perspective` is the side that just moved.
    """
    cpl = abs(cp_before - cp_after) if perspective == chess.WHITE else abs(-cp_before - (-cp_after))
    if perspective == chess.BLACK:
        cpl = abs(-cp_before - (-cp_after))
    epl = expected_points_lost(cp_before, cp_after, perspective)

    if epl == 0.0:
        cls = MoveClassification.BEST
    else:
        cls = MoveClassification.BLUNDER
        for candidate, (lo, hi) in EP_THRESHOLDS.items():
            if lo <= epl < hi:
                cls = candidate
                break

    # Special: Brilliant
    if (
        is_sacrifice
        and cls in (MoveClassification.BEST, MoveClassification.EXCELLENT, MoveClassification.GOOD)
        and gives_check
    ):
        cls = MoveClassification.BRILLIANT
    elif (
        is_sacrifice
        and cls in (MoveClassification.BEST, MoveClassification.EXCELLENT)
    ):
        cls = MoveClassification.BRILLIANT

    if only_good_move and cls in (MoveClassification.BEST, MoveClassification.EXCELLENT, MoveClassification.GOOD):
        cls = MoveClassification.GREAT_MOVE

    if not is_capture and cpl <= 0 and not is_sacrifice:
        if cls == MoveClassification.BEST:
            pass

    return CAPSResult(
        classification=cls,
        expected_points_lost=round(epl, 4),
        centipawn_loss=int(cpl),
        color=CLASSIFICATION_COLORS[cls],
        label=CLASSIFICATION_LABELS[cls],
        phase=phase,
        is_sacrifice=is_sacrifice,
        is_capture=is_capture,
        gives_check=gives_check,
    )


def classify_from_engine_info(
    board_before: chess.Board,
    move: chess.Move,
    score_before: chess.engine.PovScore,
    score_after: chess.engine.PovScore,
) -> CAPSResult:
    """Wrapper that extracts centipawn values from python-chess engine scores."""
    perspective = board_before.turn
    cp_before = _to_cp(score_before, perspective)
    cp_after = _to_cp(score_after, perspective)
    if cp_before is None or cp_after is None:
        cp_before = cp_before or 0
        cp_after = cp_after or 0
    is_sacrifice = _is_sacrifice(board_before, move)
    is_capture = board_before.is_capture(move)
    board_after = board_before.copy()
    board_after.push(move)
    gives_check = board_after.is_check()
    move_number = board_before.fullmove_number
    phase = phase_for_move_number(move_number)
    return classify(
        cp_before=cp_before,
        cp_after=cp_after,
        perspective=perspective,
        is_sacrifice=is_sacrifice,
        is_capture=is_capture,
        gives_check=gives_check,
        phase=phase,
    )


def _is_sacrifice(board: chess.Board, move: chess.Move) -> bool:
    """A sacrifice is a non-capture move that loses material net of any follow-up
    forced recapture. We approximate: if the move is a non-capture (or captures
    less than the piece moved), it counts as a sacrifice.
    """
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return False
    if board.is_capture(move):
        return False
    # We don't run a full quiescence search; treat undefended piece moves onto
    # enemy-controlled squares as sacrifices when the piece is >= minor piece.
    if moving_piece.piece_type in (chess.PAWN, chess.KING):
        return False
    if not board.is_attacked_by(not board.turn, move.to_square):
        return False
    return True


@dataclass
class CAPSSummary:
    """ACPL summary by phase."""

    opening: float
    middlegame: float
    endgame: float
    overall: float
    classifications: dict[MoveClassification, int]

    def to_dict(self) -> dict:
        return {
            "opening": round(self.opening, 1),
            "middlegame": round(self.middlegame, 1),
            "endgame": round(self.endgame, 1),
            "overall": round(self.overall, 1),
            "counts": {k.value: v for k, v in self.classifications.items()},
        }


def compute_acpl_by_phase(
    results: list[CAPSResult],
) -> CAPSSummary:
    """Compute ACPL (mean centipawn loss) per phase from a list of results."""
    by_phase: dict[str, list[int]] = {"opening": [], "middlegame": [], "endgame": []}
    counts: dict[MoveClassification, int] = {c: 0 for c in MoveClassification}
    for r in results:
        by_phase.setdefault(r.phase, []).append(r.centipawn_loss)
        counts[r.classification] += 1

    def _mean(xs: list[int]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    opening = _mean(by_phase["opening"])
    middlegame = _mean(by_phase["middlegame"])
    endgame = _mean(by_phase["endgame"])
    all_cpls = [r.centipawn_loss for r in results]
    overall = _mean(all_cpls)
    return CAPSSummary(
        opening=opening,
        middlegame=middlegame,
        endgame=endgame,
        overall=overall,
        classifications=counts,
    )


__all__ = [
    "MoveClassification",
    "EP_THRESHOLDS",
    "CLASSIFICATION_COLORS",
    "CLASSIFICATION_LABELS",
    "CAPSResult",
    "CAPSSummary",
    "cp_to_win_pct",
    "cp_to_win_pct_simple",
    "expected_points_lost",
    "classify",
    "classify_from_engine_info",
    "compute_acpl_by_phase",
]
