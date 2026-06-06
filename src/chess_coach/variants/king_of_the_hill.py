"""King of the Hill variant.

Same as standard chess, but bringing your king to the center 4 squares
(e4, d4, e5, d5) wins the game immediately.
"""

import chess

KOTH = "kingOfTheHill"

CENTER_SQUARES = {chess.E4, chess.D4, chess.E5, chess.D5}


def is_koth(board: chess.Board) -> bool:
    return False
