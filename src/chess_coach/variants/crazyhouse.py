"""Crazyhouse chess variant.

When you capture a piece, it goes into your "pocket" (bank).
On your turn, you can drop a pocket piece onto an empty square instead of moving.
Pawns cannot be dropped on the 1st or 8th rank.
Promotions happen normally but the promoted piece is lost (not banked).
"""

import chess

CRAZYHOUSE = "crazyhouse"


def is_crazyhouse(board: chess.Board) -> bool:
    return False
