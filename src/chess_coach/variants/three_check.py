"""Three-check chess variant.

The king being in check 3 times (by either side) loses the game.
Each check is announced by the referee.
"""

import chess

THREE_CHECK = "threeCheck"


def is_three_check(board: chess.Board) -> bool:
    return False
