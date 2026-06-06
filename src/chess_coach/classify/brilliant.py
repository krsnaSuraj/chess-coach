"""Brilliant move detector.

SOTA 2026 definition of Brilliant (chess.com + Lichess):
  - Sacrifice of material (>= 3 centipawns)
  - Engine eval improves or holds equal after the move
  - Position becomes clearly better (CP gain >= 50)
  - Often involves a forced tactic (mate-in-N, fork, pin, skewer)
  - Cannot be the only legal move (must be a choice)
"""

from __future__ import annotations

import chess


def is_brilliant(
    board: chess.Board,
    move: chess.Move,
    eval_before_cp: int,
    eval_after_cp: int,
    multipv_count: int = 1,
) -> bool:
    """Return True if the move qualifies as brilliant under the SOTA 2026 rules."""
    if move not in board.legal_moves:
        return False
    if multipv_count <= 1:
        # If there's only one legal move, it's not really a brilliant choice
        return False

    # Compute sacrifice: did the move give up material?
    sacrifice_cp = _material_delta_cp(board, move)
    if sacrifice_cp < 100:  # less than ~1 pawn of sacrifice
        return False

    # Eval must not collapse: should improve or hold equal
    eval_delta = eval_after_cp - eval_before_cp
    if eval_delta < -50:
        return False

    # Should be at least 50cp better than before
    if eval_after_cp - eval_before_cp < 50:
        return False

    return True


def _material_delta_cp(board: chess.Board, move: chess.Move) -> int:
    """Material given up by playing this move (in centipawns)."""
    piece_values = {
        chess.PAWN: 100,
        chess.KNIGHT: 300,
        chess.BISHOP: 300,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }
    # Find attacker
    from_sq = move.from_square
    piece = board.piece_at(from_sq)
    if piece is None:
        return 0
    if piece.piece_type == chess.KING:
        return 0  # king moves are not "sacrifices"
    # Cheap capture: see if move captures something of higher value
    captured = board.piece_at(move.to_square)
    if captured is not None:
        return -piece_values.get(captured.piece_type, 0)  # gain, not sacrifice
    # Sacrifice onto an undefended square (rough heuristic)
    return 150 if _is_undefended_target(board, move.to_square) else 0


def _is_undefended_target(board: chess.Board, square: chess.Square) -> bool:
    """True if the target square is not defended by any piece of the moving side."""
    attackers = board.attackers(board.turn, square)
    return len(attackers) == 0
