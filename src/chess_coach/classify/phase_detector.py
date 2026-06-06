"""Game phase detection: opening / middlegame / endgame.

SOTA 2026 phase boundaries (Lichess convention):
  - Opening: moves 1-12 OR no piece traded
  - Middlegame: move 13 to phase-transition
  - Endgame: total pieces <= 8 OR queens off
"""

from __future__ import annotations

import enum
from typing import Iterable

import chess


class GamePhase(str, enum.Enum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


OPENING_MAX_PLY = 24  # 12 full moves
ENDGAME_MAX_PIECES = 8  # total pieces excluding kings


def detect_phase(board: chess.Board, ply: int) -> GamePhase:
    """Detect the current game phase from board + ply count."""
    piece_count = len(board.piece_map())
    if ply <= OPENING_MAX_PLY and piece_count >= 24:
        return GamePhase.OPENING
    if piece_count <= ENDGAME_MAX_PIECES or _queens_off(board):
        return GamePhase.ENDGAME
    return GamePhase.MIDDLEGAME


def _queens_off(board: chess.Board) -> bool:
    """True if both queens are missing or one is missing and the other too."""
    queens = board.pieces(chess.QUEEN, chess.WHITE) | board.pieces(chess.QUEEN, chess.BLACK)
    return len(queens) < 2


def phase_buckets(history: Iterable[tuple[int, chess.Board]]) -> dict[GamePhase, int]:
    """Count the number of plies spent in each phase."""
    out: dict[GamePhase, int] = {p: 0 for p in GamePhase}
    for ply, board in history:
        out[detect_phase(board, ply)] += 1
    return out
