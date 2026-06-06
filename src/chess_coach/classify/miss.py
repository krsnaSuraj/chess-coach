"""Miss detector.

SOTA 2026 definition of Miss (chess.com + Lichess):
  - Opponent just blundered (their eval dropped >= 20%)
  - The current move does not capitalize on it
  - The current move does not find the best winning continuation
  - Result: winning opportunity was squandered
"""

from __future__ import annotations

import chess


def is_miss(
    prev_eval_cp: int,
    current_eval_cp: int,
    best_move_after_opp_blunder: chess.Move | None,
    played_move: chess.Move,
) -> bool:
    """Return True if the move is a Miss."""
    # Opponent blundered (eval swing >= 200cp in our favor)
    swing = current_eval_cp - prev_eval_cp
    if swing < 200:
        return False
    # We had a winning opportunity but didn't find the best move
    if best_move_after_opp_blunder is None:
        return False
    if played_move == best_move_after_opp_blunder:
        return False  # found it, not a miss
    return True
