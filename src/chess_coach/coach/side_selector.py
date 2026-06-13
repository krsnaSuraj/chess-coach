"""Side selection logic for chess coaching."""
from __future__ import annotations
import chess
from dataclasses import dataclass
from typing import Optional

@dataclass
class SideSelection:
    side: str  # "w" or "b"
    rating: int
    classical: float
    aggression: float

class SideSelector:
    def __init__(self):
        self.selected_side: Optional[str] = None
        self.rating: int = 1500
        self.classical: float = 0.5
        self.aggression: float = 0.5
    
    def select_side(self, side: str, rating: int = 1500, classical: float = 0.5, aggression: float = 0.5) -> SideSelection:
        if side not in ("w", "b"):
            raise ValueError(f"Invalid side: {side}. Must be 'w' or 'b'.")
        self.selected_side = side
        self.rating = rating
        self.classical = classical
        self.aggression = aggression
        return SideSelection(side=side, rating=rating, classical=classical, aggression=aggression)
    
    def is_user_turn(self, board: chess.Board) -> bool:
        if self.selected_side is None:
            return False
        return board.turn == (self.selected_side == "w")
    
    def get_opponent_side(self) -> str:
        if self.selected_side is None:
            return "w"
        return "b" if self.selected_side == "w" else "w"
