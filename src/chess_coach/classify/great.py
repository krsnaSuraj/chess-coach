"""Great / only-good-move detector.

SOTA 2026 definition of Great (chess.com):
  - The played move is the ONLY good move in the position
  - All other moves lose significant eval (>= 5% EPD)
  - Result: there was essentially one move and you found it
"""

from __future__ import annotations

import chess

from chess_coach.classify.epd import winrate_to_epd, cp_to_winrate


def is_great_move(
    board: chess.Board,
    played_move: chess.Move,
    multipv_evals: list[tuple[chess.Move, int]],
) -> bool:
    """Return True if the move is the only good move (Great class)."""
    if not multipv_evals:
        return False
    # Find best eval
    best_cp = max(cp for _, cp in multipv_evals)
    best_winrate = cp_to_winrate(best_cp)

    # Check the played move
    played_cp = next((cp for m, cp in multipv_evals if m == played_move), None)
    if played_cp is None:
        return False
    played_winrate = cp_to_winrate(played_cp)

    # If played is the best, check that all other moves are significantly worse
    if played_move != multipv_evals[0][0]:
        return False

    # Count "good" alternatives (within 2% EPD of best)
    good_count = 0
    for mv, cp in multipv_evals:
        epd = winrate_to_epd(best_winrate, cp_to_winrate(cp))
        if epd < 0.02:
            good_count += 1
    return good_count == 1  # only the played move is "good"


def is_only_good_move(
    board: chess.Board,
    multipv_evals: list[tuple[chess.Move, int]],
) -> chess.Move | None:
    """Return the only-good-move if there is one, else None."""
    if not multipv_evals or len(multipv_evals) < 2:
        return None
    best_cp = max(cp for _, cp in multipv_evals)
    best_winrate = cp_to_winrate(best_cp)
    good_moves: list[chess.Move] = []
    for mv, cp in multipv_evals:
        epd = winrate_to_epd(best_winrate, cp_to_winrate(cp))
        if epd < 0.05:
            good_moves.append(mv)
    if len(good_moves) == 1:
        return good_moves[0]
    return None
