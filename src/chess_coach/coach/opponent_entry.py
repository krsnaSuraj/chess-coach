"""Opponent move entry for chess coaching."""
from __future__ import annotations
import chess
from dataclasses import dataclass
from typing import Optional

@dataclass
class OpponentMoveResult:
    move: chess.Move
    is_valid: bool
    error: Optional[str] = None

class OpponentEntry:
    def __init__(self):
        self.last_opponent_move: Optional[chess.Move] = None
    
    def parse_move(self, uci: str, board: chess.Board) -> OpponentMoveResult:
        try:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                return OpponentMoveResult(move=move, is_valid=False, error=f"Illegal move: {uci}")
            self.last_opponent_move = move
            return OpponentMoveResult(move=move, is_valid=True)
        except ValueError:
            return OpponentMoveResult(move=chess.Move(0, 0), is_valid=False, error=f"Invalid UCI format: {uci}")
    
    def parse_san(self, san: str, board: chess.Board) -> OpponentMoveResult:
        try:
            move = board.parse_san(san)
            self.last_opponent_move = move
            return OpponentMoveResult(move=move, is_valid=True)
        except ValueError:
            return OpponentMoveResult(move=chess.Move(0, 0), is_valid=False, error=f"Invalid SAN: {san}")
