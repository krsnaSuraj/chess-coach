"""Blunder classification — categorize WHY a move was bad.

Categories:
- hanging_piece: left a piece undefended that can be captured
- missed_tactic: missed a fork/pin/skewer/discovered attack
- time_pressure: blunder in last 10% of clock
- positional: weakening own pawn structure / king safety
- opening: deviates from book in first 10 moves without justification
- endgame_technique: endgame-specific mistake (e.g., not pushing passed pawn)
- piece_misplacement: piece on bad square (Nc6e2-style)
- king_safety: king walked into danger
"""

from __future__ import annotations

import chess
from dataclasses import dataclass


PIECE_VALUES = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.0,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,
}


@dataclass
class BlunderReport:
    """Analysis of a single blunder."""
    category: str
    severity: float         # 0-1, 1 = catastrophic
    explanation: str
    suggestion: str
    involved_squares: list[str]

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": round(self.severity, 2),
            "explanation": self.explanation,
            "suggestion": self.suggestion,
            "involved_squares": self.involved_squares,
        }


def classify_blunder(
    board: chess.Board,
    move: chess.Move,
    eval_before_cp: float,
    eval_after_cp: float,
    best_move: chess.Move | None = None,
    best_eval_cp: float | None = None,
    time_remaining_s: float | None = None,
) -> BlunderReport:
    """Classify a blunder into a category and generate human-friendly advice.

    Args:
        board: position BEFORE the move was played
        move: the move that was played
        eval_before_cp: eval before the move (from moving side's POV)
        eval_after_cp: eval after the move (from moving side's POV)
        best_move: engine's top choice
        best_eval_cp: eval after best move
        time_remaining_s: seconds left on clock when move was played
    """
    # Compute swing
    swing = max(0, eval_before_cp - eval_after_cp) / 100.0  # in pawns

    # 1. Time pressure
    if time_remaining_s is not None and time_remaining_s < 30:
        if swing >= 1.5:
            return BlunderReport(
                category="time_pressure",
                severity=min(1.0, swing / 5.0),
                explanation=f"Major blunder with only {int(time_remaining_s)}s on the clock. "
                            f"Lost {swing:.1f} pawns of advantage.",
                suggestion="In time pressure, focus on simple threats and avoid piece blunders. "
                          "Use the increment to think one move ahead.",
                involved_squares=[],
            )

    # 2. Hanging piece detection
    move_result = _check_hanging_piece(board, move)
    if move_result:
        return move_result

    # 3. Missed tactic
    if best_move is not None and best_eval_cp is not None:
        missed_swing = (eval_after_cp - best_eval_cp) / 100.0
        if missed_swing >= 2.0:
            tactic_type = _detect_tactic(board, best_move)
            if tactic_type:
                return BlunderReport(
                    category="missed_tactic",
                    severity=min(1.0, missed_swing / 6.0),
                    explanation=f"Missed a {tactic_type}. Your move lost {missed_swing:.1f} pawns "
                                f"compared to the engine's choice.",
                    suggestion=f"Look for {tactic_type} patterns: double attacks, pieces on the same line, "
                              f"undefended enemy pieces.",
                    involved_squares=[chess.square_name(best_move.from_square),
                                      chess.square_name(best_move.to_square)],
                )

    # 4. King safety
    ks_result = _check_king_safety(board, move)
    if ks_result:
        return ks_result

    # 5. Positional / pawn structure
    pos_result = _check_positional(board, move)
    if pos_result:
        return pos_result

    # 6. Opening
    if board.fullmove_number <= 10 and swing >= 1.5:
        return BlunderReport(
            category="opening",
            severity=min(1.0, swing / 6.0),
            explanation=f"In the opening (move {board.fullmove_number}), this move lost {swing:.1f} pawns.",
            suggestion="Stick to opening principles: control the center, develop minor pieces, "
                      "castle early, connect rooks.",
            involved_squares=[],
        )

    # 7. Endgame
    if _is_endgame(board):
        return BlunderReport(
            category="endgame_technique",
            severity=min(1.0, swing / 6.0),
            explanation=f"Endgame inaccuracy losing {swing:.1f} pawns.",
            suggestion="In the endgame: activate your king, push passed pawns, "
                      "place rooks on the 7th rank or behind passed pawns.",
            involved_squares=[],
        )

    # 8. Default
    return BlunderReport(
        category="piece_misplacement",
        severity=min(1.0, swing / 6.0),
        explanation=f"Move lost {swing:.1f} pawns. Consider the engine's top choice.",
        suggestion="Look for the most active square for each piece. "
                  "Avoid passive moves that don't create threats or improve piece coordination.",
        involved_squares=[],
    )


def _check_hanging_piece(board: chess.Board, move: chess.Move) -> BlunderReport | None:
    """Detect if the move left a piece hanging (undefended and capturable)."""
    board.push(move)
    moving_side = not board.turn  # who just moved
    opponent = board.turn

    # All non-king pieces of the moving side
    moving_mask = (board.pieces_mask(chess.PAWN, moving_side) |
                   board.pieces_mask(chess.KNIGHT, moving_side) |
                   board.pieces_mask(chess.BISHOP, moving_side) |
                   board.pieces_mask(chess.ROOK, moving_side) |
                   board.pieces_mask(chess.QUEEN, moving_side))
    for square in chess.SquareSet(moving_mask):
        attackers = board.attackers(opponent, square)
        defenders = board.attackers(moving_side, square)
        if attackers and not defenders:
            piece = board.piece_at(square)
            val = PIECE_VALUES.get(piece.piece_type, 0)
            board.pop()
            piece_name = chess.piece_name(piece.piece_type)
            return BlunderReport(
                category="hanging_piece",
                severity=min(1.0, val / 5.0),
                explanation=f"{piece_name.capitalize()} on {chess.square_name(square)} is now "
                            f"hanging — attacked and undefended.",
                suggestion=f"Either defend {chess.square_name(square)} with another piece, "
                          f"or move the {piece_name} before the opponent captures it.",
                involved_squares=[chess.square_name(square)],
            )
        if attackers and len(attackers) > len(defenders):
            piece = board.piece_at(square)
            val = PIECE_VALUES.get(piece.piece_type, 0)
            board.pop()
            piece_name = chess.piece_name(piece.piece_type)
            return BlunderReport(
                category="hanging_piece",
                severity=min(1.0, val / 6.0),
                explanation=f"{piece_name.capitalize()} on {chess.square_name(square)} is "
                            f"overloaded — attacked by more pieces than it can be defended.",
                suggestion=f"Trade off the {piece_name} for one of the attackers, "
                          f"or retreat before losing material.",
                involved_squares=[chess.square_name(square)],
            )
    board.pop()
    return None


def _detect_tactic(board: chess.Board, best_move: chess.Move) -> str | None:
    """Identify what tactical motif the best move exploits."""
    if best_move.promotion:
        return "underpromotion"
    board.push(best_move)
    tactic = None
    # Fork: best move gives a piece that attacks 2+ valuable enemy pieces
    to_sq = best_move.to_square
    attackers = list(board.attackers(board.turn, to_sq))
    if attackers:
        piece = board.piece_at(to_sq)
        if piece and piece.piece_type in (chess.KNIGHT, chess.PAWN):
            victim_mask = (board.pieces_mask(chess.KING, not board.turn) |
                           board.pieces_mask(chess.QUEEN, not board.turn) |
                           board.pieces_mask(chess.ROOK, not board.turn))
            valuable_targets = []
            for victim_sq in chess.SquareSet(victim_mask):
                if board.is_attacked_by(board.turn, victim_sq):
                    valuable_targets.append(victim_sq)
            if len(valuable_targets) >= 2:
                tactic = "fork"
    board.pop()
    if tactic:
        return tactic
    return "tactical resource"


def _check_king_safety(board: chess.Board, move: chess.Move) -> BlunderReport | None:
    """Detect king safety violations."""
    # Moving king into open file
    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type == chess.KING:
        board.push(move)
        # King in middle of board
        king_sq = board.king(not board.turn)
        file = chess.square_file(king_sq)
        rank = chess.square_rank(king_sq)
        if 2 <= file <= 5 and 2 <= rank <= 5:
            board.pop()
            return BlunderReport(
                category="king_safety",
                severity=0.6,
                explanation="King walked into the center — exposed to attacks.",
                suggestion="Keep the king safe on the back rank or in a castled position. "
                          "In the endgame, centralize the king only when safe.",
                involved_squares=[chess.square_name(move.from_square),
                                  chess.square_name(move.to_square)],
            )
        # Castle through check is illegal in chess, so this is a defensive move
        # to a dangerous square (e.g., into a discovered check)
        if board.is_attacked_by(board.turn, king_sq):
            board.pop()
            return BlunderReport(
                category="king_safety",
                severity=0.8,
                explanation="King moved into an attacked square.",
                suggestion="Never move the king to a square attacked by an enemy piece.",
                involved_squares=[chess.square_name(king_sq)],
            )
        board.pop()
    return None


def _check_positional(board: chess.Board, move: chess.Move) -> BlunderReport | None:
    """Detect positional/structural issues."""
    # Doubled pawns created
    if board.piece_at(move.from_square) and \
       board.piece_at(move.from_square).piece_type == chess.PAWN:
        to_file = chess.square_file(move.to_square)
        same_file_pawns = 0
        for sq in chess.SquareSet(chess.BB_FILES[to_file]):
            if board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN:
                if board.piece_at(sq).color == board.turn:
                    same_file_pawns += 1
        if same_file_pawns >= 3:  # 2 of own pawns + the one we just placed = 3
            return BlunderReport(
                category="positional",
                severity=0.4,
                explanation="Created doubled (or tripled) pawns on the same file.",
                suggestion="Avoid creating doubled pawns. They are easier to attack and "
                          "limit the pawn's mobility.",
                involved_squares=[chess.square_name(move.to_square)],
            )
    return None


def _is_endgame(board: chess.Board) -> bool:
    """Crude endgame detection: few pieces remaining."""
    return len(board.piece_map()) <= 10
