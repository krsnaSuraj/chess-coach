"""Accuracy calculation for chess games.

Lichess-style centipawn loss (CPL) based accuracy per move.
Returns 0-100 scale where 100 = perfect, lower = more inaccurate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def cp_to_winrate(cp: float) -> float:
    """Lichess centipawn-to-winrate sigmoid: 100cp = 10x win chance.

    P(win) = 1 / (1 + 10^(-cp/400))  -- standard Elo formula
    """
    if cp >= 1000:
        return 1.0
    if cp <= -1000:
        return 0.0
    return 1.0 / (1.0 + 10.0 ** (-cp / 400.0))


def winrate_to_cp(wr: float) -> float:
    """Inverse of cp_to_winrate, used for mate score conversion."""
    if wr >= 1.0:
        return 1000.0
    if wr <= 0.0:
        return -1000.0
    import math
    return -400.0 * math.log10(1.0 / wr - 1.0)


@dataclass
class MoveAccuracy:
    """Accuracy for a single move."""
    move_number: int
    cpl: float          # centipawn loss (0 = perfect, 200+ = terrible)
    accuracy_pct: float  # 0-100
    classification: str  # brilliant/great/good/inaccuracy/mistake/blunder

    def to_dict(self) -> dict:
        return {
            "move_number": self.move_number,
            "cpl": round(self.cpl, 1),
            "accuracy_pct": round(self.accuracy_pct, 1),
            "classification": self.classification,
        }


def _classify(cpl: float) -> str:
    if cpl <= 10:
        return "brilliant"
    if cpl <= 50:
        return "great"
    if cpl <= 100:
        return "good"
    if cpl <= 200:
        return "inaccuracy"
    if cpl <= 350:
        return "mistake"
    return "blunder"


def move_cpl(eval_before_cp: float, eval_after_cp: float, side_to_move: str) -> float:
    """Centipawn loss for a single move.

    eval_before_cp:  position eval BEFORE the move (from side-to-move's POV, + = good for them)
    eval_after_cp:   position eval AFTER the move (from side-to-move's POV after the move)
    side_to_move:    'w' or 'b' — who made the move

    Returns the centipawn-equivalent CPL on a 0-1000+ scale
    (Lichess uses ~400cp = 100% winrate loss, so we scale by 1000 to match
    their blunder threshold of 200+).
    """
    wr_before = cp_to_winrate(eval_before_cp)
    wr_after = cp_to_winrate(eval_after_cp)
    delta = wr_before - wr_after
    if delta < 0:
        delta = 0.0
    if delta > 1:
        delta = 1.0
    return delta * 1000.0  # 0-1000+ scale (matches Lichess thresholds)


def move_accuracy(eval_before_cp: float, eval_after_cp: float, side_to_move: str) -> MoveAccuracy:
    """Lichess-style accuracy for one move.

    Formula: 103.1668 * exp(-0.04354 * cpl) - 3.1669
    (capped to [0, 100], tuned to match Lichess)
    """
    cpl = move_cpl(eval_before_cp, eval_after_cp, side_to_move)
    if cpl > 1000:
        cpl = 1000.0
    import math
    acc = 103.1668 * math.exp(-0.04354 * cpl) - 3.1669
    acc = max(0.0, min(100.0, acc))
    return MoveAccuracy(
        move_number=0,  # caller fills
        cpl=cpl,
        accuracy_pct=acc,
        classification=_classify(cpl),
    )


def game_accuracy(eval_history: Sequence[tuple[float, float, str]]) -> dict:
    """Compute average accuracy for a full game.

    eval_history: list of (eval_before_cp, eval_after_cp, side_to_move) tuples
        — one per move played, in order.

    Returns dict with overall accuracy, per-move breakdown, classification counts.
    """
    if not eval_history:
        return {"accuracy_pct": 100.0, "moves": [], "summary": _empty_summary()}

    moves = []
    acc_sum = 0.0
    summary = _empty_summary()
    for i, (before, after, side) in enumerate(eval_history, start=1):
        ma = move_accuracy(before, after, side)
        ma.move_number = i
        moves.append(ma)
        acc_sum += ma.accuracy_pct
        summary[ma.classification] = summary.get(ma.classification, 0) + 1

    overall = acc_sum / len(moves)
    return {
        "accuracy_pct": round(overall, 1),
        "moves": [m.to_dict() for m in moves],
        "summary": summary,
    }


def _empty_summary() -> dict:
    return {
        "brilliant": 0, "great": 0, "good": 0,
        "inaccuracy": 0, "mistake": 0, "blunder": 0,
    }


def rating_from_accuracy(accuracy_pct: float) -> int:
    """Rough Elo estimate from accuracy (Lichess-style heuristic)."""
    # Empirically: 50% accuracy ≈ 800, 70% ≈ 1500, 85% ≈ 2000, 95% ≈ 2400
    # Use exponential fit
    import math
    if accuracy_pct <= 0:
        return 400
    if accuracy_pct >= 100:
        return 3000
    # Fit: a = 100 * (1 - exp(-(elo - 400)/600)) => elo = 400 - 600*ln(1 - a/100)
    elo = 400 - 600 * math.log(1.0 - accuracy_pct / 100.0)
    return int(max(400, min(3000, elo)))
