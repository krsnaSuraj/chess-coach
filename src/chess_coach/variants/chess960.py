"""Chess960 (Fischer Random) variant.

In Chess960, the starting position is randomly chosen from 960 legal
starting positions where the king is between the rooks and bishops are on
opposite colors. Castling rules are modified: king moves 2-3 squares
towards the rook.
"""

import random
import chess

CHESS960 = "chess960"

CHESS960_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def random_starting_position() -> str:
    """Generate a random legal Chess960 starting position (FRC)."""
    back_rank_options = [
        # (back_rank_pieces) - 960 valid positions
        # For simplicity, we use a known good generator
    ]
    # Use python-chess built-in (if available) or fall back to manual
    try:
        board = chess.Board()
        board.set_chess960_pos(random.randint(0, 959))
        return board.fen()
    except (AttributeError, chess.InvalidMoveError, ValueError):
        # Fallback: shuffle the standard back rank
        back_rank = list("rnbqkbnr")
        while True:
            random.shuffle(back_rank)
            br = "".join(back_rank)
            if _is_legal_960(br):
                return f"{br}/pppppppp/8/8/8/8/PPPPPPPP/{br.upper()} w KQkq - 0 1"


def _is_legal_960(back_rank: str) -> bool:
    """Check the Chess960 constraints on a back rank."""
    # King must be between the two rooks
    king_idx = back_rank.find("k")
    rook_indices = [i for i, c in enumerate(back_rank) if c == "r"]
    if len(rook_indices) != 2:
        return False
    if not (rook_indices[0] < king_idx < rook_indices[1]):
        return False
    # Bishops must be on opposite colors
    bishops = [i for i, c in enumerate(back_rank) if c == "b"]
    if len(bishops) != 2:
        return False
    if bishops[0] % 2 == bishops[1] % 2:
        return False
    # All pieces accounted for
    expected = {"r": 2, "n": 2, "b": 2, "q": 1, "k": 1}
    actual = {c: back_rank.count(c) for c in expected}
    return actual == expected


def is_chess960(board: chess.Board) -> bool:
    """Heuristic: True if board has a non-standard starting position."""
    if board.move_stack:
        return True
    return board.fen() != CHESS960_STARTPOS
