"""Horde chess variant.

White has 36 pieces in a horde formation, Black has the standard 16.
White wins by checkmating Black; Black wins by capturing all White pieces
or by stalemating White.
"""

import chess

HORDE = "horde"


def is_horde(board: chess.Board) -> bool:
    return False
