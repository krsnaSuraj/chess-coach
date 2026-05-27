from __future__ import annotations

import chess
from chess_coach.eco_data import ECO_DATABASE


def get_opening(board: chess.Board) -> tuple[str, str] | None:
    moves: list[str] = []
    b = chess.Board()
    for move in board.move_stack:
        san = b.san(move)
        b.push(move)
        moves.append(san)
    if not moves:
        return None
    move_str = " ".join(moves)
    best_match: tuple[str, str] | None = None
    best_len = -1
    for entry in ECO_DATABASE:
        if len(entry) != 3:
            continue
        eco_code, name, prefix = entry
        if move_str.startswith(prefix):
            prefix_words = prefix.split()
            if len(prefix_words) > best_len:
                best_len = len(prefix_words)
                best_match = (eco_code, name)
    return best_match
