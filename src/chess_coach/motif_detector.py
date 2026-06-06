"""Tactical motif detection.

Detects the eight most common tactical themes:
- Pin           : a piece cannot move without exposing a more-valuable piece.
- Fork          : a single piece attacks two or more enemy pieces.
- Skewer        : like a pin, but the FRONT piece is more valuable.
- Discovered    : a move opens a line for another piece to attack.
- Deflection    : forces a defending piece to abandon a key square.
- Decoy         : lures an enemy piece to a bad square.
- Back-rank     : king trapped on the 8th rank behind its own pieces.
- Zwischenzug   : an in-between move that interrupts the expected sequence.

These are *hints* the humanizer can use to flavour personality explanations
and to teach the user what they missed.

Implementation strategy:
    For each theme we apply a focused pattern matcher over the board. None of
    the detectors perform full quiescence search — they're meant to be fast
    and good-enough, not replace a chess engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import chess

logger = logging.getLogger(__name__)


class Motif(str, Enum):
    PIN = "pin"
    FORK = "fork"
    SKEWER = "skewer"
    DISCOVERED = "discovered_attack"
    DEFLECTION = "deflection"
    DECOY = "decoy"
    BACK_RANK = "back_rank_weakness"
    ZWISCHENZUG = "zwischenzug"
    COLOR_COMPLEX = "color_complex"


MOTIF_LABELS: dict[Motif, str] = {
    Motif.PIN:           "Pin",
    Motif.FORK:          "Fork",
    Motif.SKEWER:        "Skewer",
    Motif.DISCOVERED:    "Discovered Attack",
    Motif.DEFLECTION:    "Deflection",
    Motif.DECOY:         "Decoy",
    Motif.BACK_RANK:     "Back Rank Weakness",
    Motif.ZWISCHENZUG:   "Zwischenzug",
    Motif.COLOR_COMPLEX: "Color Complex",
}


@dataclass
class MotifDetection:
    motif: Motif
    squares: list[chess.Square]
    description: str
    attacker: chess.Square | None = None
    victim: chess.Square | None = None


_PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


def _piece_value(p: chess.Piece | None) -> int:
    if p is None:
        return 0
    return _PIECE_VALUE.get(p.piece_type, 0)


def _ray_attackers(
    board: chess.Board, sq: chess.Square, by_color: chess.Color
) -> list[tuple[chess.Square, int]]:
    """Return (attacker_sq, value) pairs that attack `sq` along rook/bishop rays."""
    out: list[tuple[chess.Square, int]] = []
    for direction in (
        chess.BB_FILE_A,  # not used; kept to remind directions
    ):
        pass
    for attacker_sq in board.attackers(by_color, sq):
        piece = board.piece_at(attacker_sq)
        if piece is None:
            continue
        pt = piece.piece_type
        if pt in (chess.ROOK, chess.BISHOP, chess.QUEEN):
            out.append((attacker_sq, _piece_value(piece)))
    return out


def detect_pins(
    board: chess.Board, color_to_move: chess.Color
) -> list[MotifDetection]:
    """Find absolute pins affecting `color_to_move`."""
    out: list[MotifDetection] = []
    own_king = board.king(color_to_move)
    if own_king is None:
        return out
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color != color_to_move:
            continue
        if sq == own_king:
            continue
        if not board.is_pinned(color_to_move, sq):
            continue
        # Pin confirmed — find the pinning piece
        for attacker_sq in board.attackers(not color_to_move, sq):
            ap = board.piece_at(attacker_sq)
            if ap is None:
                continue
            if ap.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN):
                out.append(MotifDetection(
                    motif=Motif.PIN,
                    squares=[sq, attacker_sq, own_king],
                    attacker=attacker_sq,
                    victim=sq,
                    description=f"{chess.piece_name(p.piece_type).title()} on {chess.square_name(sq)} is pinned against the king",
                ))
                break
    return out


def detect_forks(
    board: chess.Board, move: chess.Move
) -> list[MotifDetection]:
    """Detect whether the move creates a fork (a piece now attacks 2+ enemy pieces)."""
    out: list[MotifDetection] = []
    color = board.turn
    board.push(move)
    mover_dest = move.to_square
    mover_piece = board.piece_at(mover_dest)
    if mover_piece is None:
        board.pop()
        return out
    targets: list[chess.Square] = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color == color:
            continue
        if board.is_attacked_by(color, sq):
            targets.append(sq)
    if len(targets) >= 2:
        target_pieces = []
        for t in targets[:3]:
            tp = board.piece_at(t)
            if tp is not None:
                target_pieces.append(f"{chess.piece_name(tp.piece_type)} on {chess.square_name(t)}")
        desc = f"{chess.piece_name(mover_piece.piece_type).title()} on {chess.square_name(mover_dest)} forks {', '.join(target_pieces)}"
        out.append(MotifDetection(
            motif=Motif.FORK,
            squares=[mover_dest] + targets[:2],
            attacker=mover_dest,
            description=desc,
        ))
    board.pop()
    return out


def detect_skewers(
    board: chess.Board, color_to_move: chess.Color
) -> list[MotifDetection]:
    """Detect a skewer: a piece attacks a more-valuable piece that, if it moves,
    exposes a less-valuable piece behind it.
    """
    out: list[MotifDetection] = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color == color_to_move:
            continue
        attackers = _ray_attackers(board, sq, color_to_move)
        if not attackers:
            continue
        attacker_sq, attacker_value = attackers[0]
        # Walk one square past sq in the same direction
        ap = board.piece_at(attacker_sq)
        if ap is None or ap.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        from_sq = sq
        to_sq = attacker_sq
        df = chess.square_file(to_sq) - chess.square_file(from_sq)
        dr = chess.square_rank(to_sq) - chess.square_rank(from_sq)
        step_f = 0 if df == 0 else (1 if df > 0 else -1)
        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        next_f = chess.square_file(from_sq) + step_f
        next_r = chess.square_rank(from_sq) + step_r
        if not (0 <= next_f < 8 and 0 <= next_r < 8):
            continue
        behind = chess.square(next_f, next_r)
        behind_piece = board.piece_at(behind)
        if behind_piece is None or behind_piece.color == color_to_move:
            continue
        front_value = _piece_value(p)
        back_value = _piece_value(behind_piece)
        if front_value > back_value:
            out.append(MotifDetection(
                motif=Motif.SKEWER,
                squares=[attacker_sq, sq, behind],
                attacker=attacker_sq,
                victim=sq,
                description=f"Skewer: {chess.piece_name(p.piece_type).title()} on {chess.square_name(sq)} forced to expose {chess.piece_name(behind_piece.piece_type).title()} on {chess.square_name(behind)}",
            ))
    return out


def detect_discovered_attack(board: chess.Board, move: chess.Move) -> list[MotifDetection]:
    """Detect if a move uncovers a previously-blocked attack on an enemy piece."""
    out: list[MotifDetection] = []
    color = board.turn
    board_before = board.copy()
    board.push(move)
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color == color:
            continue
        attacked_now = board.is_attacked_by(color, sq)
        attacked_before = board_before.is_attacked_by(color, sq)
        if attacked_now and not attacked_before:
            # Find the new attacker (along a ray)
            for asq in board.attackers(color, sq):
                ap = board.piece_at(asq)
                if ap is None:
                    continue
                if ap.piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN) and asq != move.to_square:
                    out.append(MotifDetection(
                        motif=Motif.DISCOVERED,
                        squares=[move.from_square, asq, sq],
                        attacker=asq,
                        victim=sq,
                        description=f"Discovered attack: moving the {chess.piece_name(board.piece_at(move.from_square).piece_type).title()} reveals {chess.piece_name(ap.piece_type).title()} attack on {chess.square_name(sq)}",
                    ))
                    break
    board.pop()
    return out


def detect_back_rank_weakness(board: chess.Board, color: chess.Color) -> list[MotifDetection]:
    """Detect back-rank weakness: king on the back rank with own pawns in front
    and insufficient escape squares under enemy attack.

    Heuristic: king is on its back rank, has own pawns on the pawn rank, and
    has ≤ 1 safe flight square (empty, not attacked by enemy).
    """
    out: list[MotifDetection] = []
    king_sq = board.king(color)
    if king_sq is None:
        return out
    king_rank = chess.square_rank(king_sq)
    king_file = chess.square_file(king_sq)
    is_white = color == chess.WHITE
    back_rank = 0 if is_white else 7
    if king_rank != back_rank:
        return out

    # White's back rank is in front of white pawns on rank 1 (2nd rank).
    # Black's back rank is in front of black pawns on rank 6 (7th rank).
    pawn_rank = 1 if is_white else 6
    own_pawn_files: set[int] = set()
    for f in range(8):
        sq = chess.square(f, pawn_rank)
        p = board.piece_at(sq)
        if p is not None and p.piece_type == chess.PAWN and p.color == color:
            own_pawn_files.add(f)
    if not own_pawn_files:
        return out
    if not any(abs(f - king_file) <= 2 for f in own_pawn_files):
        return out

    # Count safe flight squares (empty + not attacked by enemy)
    safe_flights = 0
    for delta in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
        nf = king_file + delta[0]
        nr = king_rank + delta[1]
        if 0 <= nf < 8 and 0 <= nr < 8:
            target = chess.square(nf, nr)
            if board.piece_at(target) is None and not board.is_attacked_by(not color, target):
                safe_flights += 1
    # Back-rank weakness is exploitable only when the opponent has a long-range
    # attacker (rook or queen) on the king's file or rank.
    exploitable = False
    enemy = not color
    for f in range(8):
        sq = chess.square(f, back_rank)
        p = board.piece_at(sq)
        if p is not None and p.color == enemy and p.piece_type in (chess.ROOK, chess.QUEEN):
            exploitable = True
            break
    if not exploitable:
        for r in range(8):
            sq = chess.square(king_file, r)
            p = board.piece_at(sq)
            if p is not None and p.color == enemy and p.piece_type in (chess.ROOK, chess.QUEEN):
                exploitable = True
                break
    if exploitable and safe_flights <= 0:
        out.append(MotifDetection(
            motif=Motif.BACK_RANK,
            squares=[king_sq],
            description=f"King on {chess.square_name(king_sq)} is trapped on the back rank by own pawns",
            ))
    return out


def detect_zwischenzug(board: chess.Board, move: chess.Move) -> list[MotifDetection]:
    """Approximate zwischenzug: the move is a check or capture that interrupts a
    forced sequence.
    """
    out: list[MotifDetection] = []
    color = board.turn
    board.push(move)
    if board.is_check() or board.is_capture(move):
        # If opponent's last move was a recapture/setup, this move is a zwischenzug
        if board.move_stack and len(board.move_stack) >= 2:
            prev_move = board.move_stack[-2]
            prev_piece = board.piece_at(prev_move.to_square) if board.move_stack else None
            if prev_piece is not None and board.gives_check(move):
                out.append(MotifDetection(
                    motif=Motif.ZWISCHENZUG,
                    squares=[move.to_square],
                    description="Zwischenzug: in-between move that interrupts the expected sequence",
                ))
    board.pop()
    return out


def detect_color_complex(board: chess.Board, color: chess.Color) -> list[MotifDetection]:
    """Detect a one-sided bishop color complex: one side has 2+ bishops of same color, opponent has none of that color."""
    out: list[MotifDetection] = []
    own_dark = 0
    own_light = 0
    opp_dark = 0
    opp_light = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.piece_type != chess.BISHOP:
            continue
        is_dark = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
        if p.color == color:
            if is_dark:
                own_dark += 1
            else:
                own_light += 1
        else:
            if is_dark:
                opp_dark += 1
            else:
                opp_light += 1
    if (own_dark >= 2 and opp_dark == 0) or (own_light >= 2 and opp_light == 0):
        complex_color = "dark" if own_dark >= 2 else "light"
        out.append(MotifDetection(
            motif=Motif.COLOR_COMPLEX,
            squares=[],
            description=f"Owns both {complex_color}-square bishops; opponent has none on that color",
        ))
    return out


def detect_all_motifs(
    board: chess.Board, last_move: chess.Move | None = None
) -> list[MotifDetection]:
    """Run all motif detectors and return a deduplicated list."""
    color = board.turn
    results: list[MotifDetection] = []
    results.extend(detect_pins(board, color))
    results.extend(detect_skewers(board, color))
    results.extend(detect_back_rank_weakness(board, color))
    results.extend(detect_color_complex(board, color))
    if last_move is not None:
        results.extend(detect_forks(board, last_move))
        results.extend(detect_discovered_attack(board, last_move))
        results.extend(detect_zwischenzug(board, last_move))
    return results


__all__ = [
    "Motif",
    "MOTIF_LABELS",
    "MotifDetection",
    "detect_pins",
    "detect_forks",
    "detect_skewers",
    "detect_discovered_attack",
    "detect_back_rank_weakness",
    "detect_zwischenzug",
    "detect_color_complex",
    "detect_all_motifs",
]
