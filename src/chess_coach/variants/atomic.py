"""Atomic chess variant.

Capturing a piece causes an explosion: the captured piece and all
non-pawn pieces in adjacent squares (N/S/E/W) are removed from the board.
The capturing piece is not removed (unlike standard chess).
Kings cannot capture each other (no direct king-vs-king captures).
"""

import chess

ATOMIC = "atomic"


def is_atomic(board: chess.Board) -> bool:
    return board.chess960 is False  # Heuristic: atomic uses a dedicated engine in Lichess
