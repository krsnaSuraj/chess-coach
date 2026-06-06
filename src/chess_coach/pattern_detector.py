"""Pattern detection — identify tactical motifs on the board.

Detects: forks, pins, skewers, discovered attacks, double attacks, back-rank
weakness, and hanging pieces. Used by the humanizer to add educational
annotations and by blunder_explainer to explain missed opportunities.
"""

from __future__ import annotations

import chess
from dataclasses import dataclass


@dataclass
class Pattern:
    """A detected tactical pattern."""
    type: str              # fork / pin / skewer / discovered / back_rank / hanging
    squares: list[str]     # involved squares
    attacker: str | None   # square of attacking piece (or None for hanging)
    target: str | None     # square of main target
    severity: float        # 0-1

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "squares": self.squares,
            "attacker": self.attacker,
            "target": self.target,
            "severity": round(self.severity, 2),
        }


def detect_all_patterns(board: chess.Board) -> list[Pattern]:
    """Run all pattern detectors and return a combined list."""
    patterns: list[Pattern] = []
    patterns.extend(detect_hanging_pieces(board))
    patterns.extend(detect_pins(board))
    patterns.extend(detect_skewers(board))
    patterns.extend(detect_forks(board))
    patterns.extend(detect_back_rank_weakness(board))
    return patterns


def _non_king_pieces(board: chess.Board, color: bool) -> chess.SquareSet:
    """All non-king, non-pawn piece squares for a color (returns SquareSet)."""
    mask = (board.pieces_mask(chess.KNIGHT, color) |
            board.pieces_mask(chess.BISHOP, color) |
            board.pieces_mask(chess.ROOK, color) |
            board.pieces_mask(chess.QUEEN, color))
    return chess.SquareSet(mask)


def _sliders(board: chess.Board, color: bool) -> chess.SquareSet:
    """All sliding piece squares (bishop/rook/queen) for a color."""
    mask = (board.pieces_mask(chess.BISHOP, color) |
            board.pieces_mask(chess.ROOK, color) |
            board.pieces_mask(chess.QUEEN, color))
    return chess.SquareSet(mask)


def detect_hanging_pieces(board: chess.Board) -> list[Pattern]:
    """Find pieces that are attacked and undefended (both colors)."""
    patterns: list[Pattern] = []
    for color in (chess.WHITE, chess.BLACK):
        # All non-pawn, non-king pieces
        pieces_mask = (board.pieces_mask(chess.KNIGHT, color) |
                       board.pieces_mask(chess.BISHOP, color) |
                       board.pieces_mask(chess.ROOK, color) |
                       board.pieces_mask(chess.QUEEN, color))
        for sq in chess.SquareSet(pieces_mask):
            attackers = board.attackers(not color, sq)
            defenders = board.attackers(color, sq)
            if attackers and not defenders:
                piece = board.piece_at(sq)
                severity = {chess.PAWN: 0.2, chess.KNIGHT: 0.4, chess.BISHOP: 0.4,
                            chess.ROOK: 0.6, chess.QUEEN: 0.9}.get(piece.piece_type, 0.3)
                patterns.append(Pattern(
                    type="hanging",
                    squares=[chess.square_name(sq)],
                    attacker=None,
                    target=chess.square_name(sq),
                    severity=severity,
                ))
    return patterns


def detect_pins(board: chess.Board) -> list[Pattern]:
    """Find absolute pins (a piece pinned to its king on a line)."""
    patterns: list[Pattern] = []
    for color in (chess.WHITE, chess.BLACK):
        king_sq = board.king(color)
        if king_sq is None:
            continue
        for pinner_sq in _sliders(board, not color):
            if not board.is_pinned(color, pinner_sq):
                continue
            between = chess.SquareSet.between(pinner_sq, king_sq)
            for sq in between:
                piece = board.piece_at(sq)
                if piece and piece.color == color:
                    patterns.append(Pattern(
                        type="pin",
                        squares=[chess.square_name(pinner_sq), chess.square_name(sq),
                                 chess.square_name(king_sq)],
                        attacker=chess.square_name(pinner_sq),
                        target=chess.square_name(sq),
                        severity=0.5,
                    ))
                    break
    return patterns


def detect_skewers(board: chess.Board) -> list[Pattern]:
    """Find skewers: a piece attacks through a more-valuable piece to a less-valuable one."""
    patterns: list[Pattern] = []
    PIECE_VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                 chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

    for color in (chess.WHITE, chess.BLACK):
        for slider_sq in _sliders(board, not color):
            # Try all 4 diagonal/file/rank directions
            for direction in [1, -1, 8, -8, 7, -7, 9, -9]:
                if not slider_sq + direction in chess.SQUARES:
                    continue
                # Walk along the direction
                cur = slider_sq + direction
                first_target = None
                second_target = None
                while cur in chess.SQUARES:
                    p = board.piece_at(cur)
                    if p is None:
                        cur += direction
                        continue
                    if p.color == (not color):  # friendly, stop
                        break
                    # enemy piece
                    if first_target is None:
                        first_target = cur
                    elif second_target is None:
                        second_target = cur
                        break
                    cur += direction
                if first_target and second_target:
                    first_piece = board.piece_at(first_target)
                    second_piece = board.piece_at(second_target)
                    if PIECE_VAL[first_piece.piece_type] > PIECE_VAL[second_piece.piece_type]:
                        patterns.append(Pattern(
                            type="skewer",
                            squares=[chess.square_name(slider_sq),
                                     chess.square_name(first_target),
                                     chess.square_name(second_target)],
                            attacker=chess.square_name(slider_sq),
                            target=chess.square_name(first_target),
                            severity=0.6,
                        ))
    return patterns


def detect_forks(board: chess.Board) -> list[Pattern]:
    """Find knight forks: a knight attacks 2+ valuable pieces at once."""
    patterns: list[Pattern] = []
    VALUABLE = {chess.KING, chess.QUEEN, chess.ROOK}

    for color in (chess.WHITE, chess.BLACK):
        for knight_sq in chess.SquareSet(board.pieces_mask(chess.KNIGHT, color)):
            attacks = board.attacks(knight_sq)
            valuable_targets = []
            for target_sq in attacks:
                p = board.piece_at(target_sq)
                if p and p.color == (not color) and p.piece_type in VALUABLE:
                    valuable_targets.append(target_sq)
            if len(valuable_targets) >= 2:
                patterns.append(Pattern(
                    type="fork",
                    squares=[chess.square_name(knight_sq)] + \
                            [chess.square_name(t) for t in valuable_targets],
                    attacker=chess.square_name(knight_sq),
                    target=chess.square_name(valuable_targets[0]),
                    severity=0.8,
                ))
    return patterns


def detect_back_rank_weakness(board: chess.Board) -> list[Pattern]:
    """Find back-rank mates or weak back rank (king on back rank with pieces trapped)."""
    patterns: list[Pattern] = []
    for color in (chess.WHITE, chess.BLACK):
        king_sq = board.king(color)
        if king_sq is None:
            continue
        rank = chess.square_rank(king_sq)
        if (color == chess.WHITE and rank == 0) or (color == chess.BLACK and rank == 7):
            own_pawns = board.pieces_mask(chess.PAWN, color)
            on_file = 0
            for sq in chess.SquareSet(own_pawns):
                f = chess.square_file(sq)
                r = chess.square_rank(sq)
                if (color == chess.WHITE and r in (1, 2)) or (color == chess.BLACK and r in (5, 6)):
                    on_file += 1
            if on_file >= 3:
                enemy_rq_mask = (board.pieces_mask(chess.ROOK, not color) |
                                 board.pieces_mask(chess.QUEEN, not color))
                for attacker_sq in chess.SquareSet(enemy_rq_mask):
                    if chess.square_file(attacker_sq) == chess.square_file(king_sq):
                        between = chess.SquareSet.between(attacker_sq, king_sq)
                        if not any(board.piece_at(sq) for sq in between):
                            patterns.append(Pattern(
                                type="back_rank",
                                squares=[chess.square_name(attacker_sq),
                                         chess.square_name(king_sq)],
                                attacker=chess.square_name(attacker_sq),
                                target=chess.square_name(king_sq),
                                severity=0.95,
                            ))
    return patterns


def summarize_for_humanizer(patterns: list[Pattern]) -> list[str]:
    """Convert patterns into short humanizer-friendly annotations."""
    annotations = []
    for p in patterns:
        if p.type == "hanging" and p.target:
            annotations.append(f"hanging piece on {p.target}")
        elif p.type == "pin" and p.target:
            annotations.append(f"pin: {p.attacker}→{p.target}→king")
        elif p.type == "skewer" and p.target:
            annotations.append(f"skewer through {p.target}")
        elif p.type == "fork" and p.attacker:
            annotations.append(f"knight fork from {p.attacker}")
        elif p.type == "back_rank" and p.target:
            annotations.append(f"back-rank weakness on {p.target}")
    return annotations
