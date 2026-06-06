"""Antichess variant.

The goal is to lose all your pieces. If you can capture, you must.
The king is just a normal piece; being in check is not relevant.
The first player to be checkmated (or stalemated) WINS.
Pawns can promote to any piece including opponent's pieces.
"""

import chess

ANTICHESS = "antichess"


def is_antichess(board: chess.Board) -> bool:
    return False
