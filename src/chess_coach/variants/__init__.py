"""Real chess variant implementations.

Each variant has its own move-validation, capture mechanics, and
win-condition. Wraps python-chess's chess.variant module for the
heavy lifting and adds SOTA features:
- Atomic: explosion on capture (king capture is checkmate-like)
- Antichess: forced captures, you win when you have no pieces
- Horde: 36 white pawns vs 16 black pieces
- King of the Hill: king to e4/d4/e5/d5 wins
- Three-Check: 3 checks to deliver = win
- Crazyhouse: drops of captured pieces
- Racing Kings: race both kings to 8th rank
- Chess960: 960 random starting positions (Fischer Random)
"""
from __future__ import annotations

import random
from typing import Any, ClassVar

import chess
import chess.variant

from .registry import VariantInfo, get_variant, variant_names


def board_for(variant: str, fen: str | None = None, chess960: bool = False) -> chess.Board:
    """Create a board for a variant. FEN is optional.

    Raises ValueError for unknown variants.
    """
    cls = chess.variant.find_variant(variant)
    if fen is None:
        return cls(chess960=chess960) if "chess960" in variant.lower() or chess960 else cls()
    return cls(fen=fen, chess960=chess960)


def is_variant_win(board: chess.Board) -> bool:
    """Check if the current position is a variant-specific win."""
    return board.is_variant_win()


def is_variant_loss(board: chess.Board) -> bool:
    """Check if the current position is a variant-specific loss."""
    return board.is_variant_loss()


def is_variant_draw(board: chess.Board) -> bool:
    """Check if the current position is a variant-specific draw."""
    return board.is_variant_draw()


def outcome(board: chess.Board) -> str:
    """Get the outcome as 'win' / 'loss' / 'draw' / 'ongoing' for the side-to-move."""
    if board.is_variant_win():
        return "win"
    if board.is_variant_loss():
        return "loss"
    if board.is_variant_draw():
        return "draw"
    if board.is_checkmate():
        return "win" if board.turn == chess.WHITE else "loss"
    if board.is_stalemate() or board.is_insufficient_material():
        return "draw"
    return "ongoing"


# -- Atomic --

ATOMIC_INFO = VariantInfo(
    name="atomic",
    display_name="Atomic",
    description="Capturing a piece causes an explosion that destroys the captured piece and all non-pawns on adjacent squares. King can be captured.",
    fen_includes_check=False,
    has_drops=False,
    winner_by="king_capture_or_explosion",
)


def atomic_explosion_squares(board: chess.Board, move: chess.Move) -> list[int]:
    """Return squares affected by an atomic capture explosion."""
    if not board.is_capture(move):
        return []
    target = move.to_square
    affected = [target]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            file = chess.square_file(target) + dx
            rank = chess.square_rank(target) + dy
            if 0 <= file < 8 and 0 <= rank < 8:
                affected.append(chess.square(file, rank))
    return affected


# -- Antichess --

ANTICHESS_INFO = VariantInfo(
    name="antichess",
    display_name="Antichess",
    description="You must capture if you can. The player who has no legal moves wins (by being captured) or who gets all their pieces captured wins.",
    fen_includes_check=False,
    has_drops=False,
    winner_by="lose_all_pieces",
)


def antichess_must_capture(board: chess.Board) -> bool:
    """In Antichess, a player must capture if any capture is available."""
    return any(board.is_capture(m) for m in board.legal_moves)


# -- Horde --

HORDE_INFO = VariantInfo(
    name="horde",
    display_name="Horde",
    description="White starts with 36 pawns, Black has normal pieces. White wins by checkmating the black king; Black wins by capturing all white pawns.",
    fen_includes_check=False,
    has_drops=False,
    winner_by="checkmate",
)


def horde_white_pieces(board: chess.Board) -> int:
    """Count white pawns remaining in a Horde position."""
    return sum(1 for p in board.piece_map().values()
               if p.color == chess.WHITE and p.piece_type == chess.PAWN)


# -- King of the Hill --

KOTH_CENTER = {chess.E4, chess.D4, chess.E5, chess.D5}


def koth_king_in_center(board: chess.Board) -> chess.Color | None:
    """Return the color whose king is in the center (or None)."""
    king_squares = {chess.WHITE: None, chess.BLACK: None}
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            king_squares[piece.color] = sq
    for color, sq in king_squares.items():
        if sq in KOTH_CENTER:
            return color
    return None


KOTH_INFO = VariantInfo(
    name="kingOfTheHill",
    display_name="King of the Hill",
    description="Be the first to get your king to one of the four center squares (d4/d5/e4/e5).",
    fen_includes_check=False,
    has_drops=False,
    winner_by="king_to_center",
)


# -- Three-Check --

THREECHECK_INFO = VariantInfo(
    name="threeCheck",
    display_name="Three-Check",
    description="Deliver (or receive) three checks to win (or lose).",
    fen_includes_check=True,
    has_drops=False,
    winner_by="three_checks",
)


def threecheck_count(board: chess.Board, color: chess.Color) -> int:
    """Count how many checks have been delivered to a side.

    python-chess stores this in board.remaining_checks[color].
    """
    if hasattr(board, "remaining_checks"):
        return 3 - board.remaining_checks[color]  # type: ignore[attr-defined]
    return 0


# -- Crazyhouse --

CRAZYHOUSE_INFO = VariantInfo(
    name="crazyhouse",
    display_name="Crazyhouse",
    description="Captured pieces can be dropped back on the board as your own pieces (as a move instead of a regular move).",
    fen_includes_check=False,
    has_drops=True,
    winner_by="checkmate",
)


def crazyhouse_pocket(board: chess.Board, color: chess.Color) -> dict[chess.PieceType, int]:
    """Return a dict of piece_type -> count in the pocket for the given color."""
    pocket: dict[chess.PieceType, int] = {}
    if not hasattr(board, "pockets"):
        return pocket
    p = board.pockets[color]  # type: ignore[attr-defined]
    for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        n = p.count(piece_type)
        if n:
            pocket[piece_type] = n
    return pocket


# -- Racing Kings --

RACINGKINGS_INFO = VariantInfo(
    name="racingKings",
    display_name="Racing Kings",
    description="Both kings race to the 8th rank. The first to get their king to row 8 wins. No checks allowed.",
    fen_includes_check=False,
    has_drops=False,
    winner_by="king_to_8th_rank",
)


def racingkings_king_reached(board: chess.Board, color: chess.Color) -> bool:
    """Check if the given color's king has reached the 8th rank (row 7)."""
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.KING and piece.color == color:
            if chess.square_rank(sq) == 7:
                return True
    return False


# -- Chess960 --

CHESS960_INFO = VariantInfo(
    name="chess960",
    display_name="Chess 960 (Fischer Random)",
    description="960 possible starting positions. The king is between the two rooks, and bishops are on opposite colors.",
    fen_includes_check=False,
    has_drops=False,
    winner_by="checkmate",
)


def random_chess960_position(rng: random.Random | None = None) -> int:
    """Generate a valid random Chess960 starting position index (0-959).

    Algorithm:
    1. Place bishops on opposite-colored squares (4 light + 4 dark options)
    2. Place queen in one of 6 remaining squares
    3. Place knights in 2 of 5 remaining squares
    4. Place rooks + king in the 3 remaining squares (must be RKR)
    """
    r = rng or random
    back_rank = ["."] * 8

    # Step 1: Place bishops on opposite colors
    light = [0, 2, 4, 6]
    dark = [1, 3, 5, 7]
    b1 = r.choice(light)
    b2 = r.choice(dark)
    back_rank[b1] = "B"
    back_rank[b2] = "B"

    # Step 2: Queen
    remaining = [i for i, v in enumerate(back_rank) if v == "."]
    q = r.choice(remaining)
    back_rank[q] = "Q"

    # Step 3: Knights
    remaining = [i for i, v in enumerate(back_rank) if v == "."]
    r.shuffle(remaining)
    n1, n2 = remaining[0], remaining[1]
    back_rank[n1] = "N"
    back_rank[n2] = "N"

    # Step 4: Rook-King-Rook in remaining 3 squares
    remaining = [i for i, v in enumerate(back_rank) if v == "."]
    # Must be R-K-R ordering; the middle one is the king
    back_rank[remaining[0]] = "R"
    back_rank[remaining[1]] = "K"
    back_rank[remaining[2]] = "R"

    # Compute the index (0-959) from the position
    return chess960_index_from_back_rank(back_rank)


def chess960_index_from_back_rank(back_rank: list[str]) -> int:
    """Convert a back-rank piece list to Chess960 index (0-959)."""
    from .chess960 import index_from_back_rank
    return index_from_back_rank(back_rank)


def back_rank_from_chess960_index(idx: int) -> list[str]:
    """Convert Chess960 index to back-rank piece list."""
    from .chess960 import back_rank_from_index
    return back_rank_from_index(idx)


def is_legal_chess960_position(back_rank: list[str]) -> bool:
    """Check if a back-rank arrangement is a valid Chess960 starting position.

    Rules:
    - King is between the two rooks
    - Bishops are on opposite-colored squares
    - Exactly 1 king, 1 queen, 2 rooks, 2 bishops, 2 knights
    """
    if len(back_rank) != 8:
        return False
    if back_rank.count("K") != 1 or back_rank.count("Q") != 1:
        return False
    if back_rank.count("R") != 2 or back_rank.count("B") != 2 or back_rank.count("N") != 2:
        return False
    # King between rooks
    rook_positions = [i for i, p in enumerate(back_rank) if p == "R"]
    king_pos = back_rank.index("K")
    if not (rook_positions[0] < king_pos < rook_positions[1]):
        return False
    # Bishops on opposite colors
    bishop_positions = [i for i, p in enumerate(back_rank) if p == "B"]
    if (bishop_positions[0] + bishop_positions[1]) % 2 == 0:
        return False
    return True
