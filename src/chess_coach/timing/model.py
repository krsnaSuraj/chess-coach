"""ChessMimic timing model for human-like think times."""
from __future__ import annotations
import chess
import numpy as np
from dataclasses import dataclass
from typing import Optional

@dataclass
class ThinkTimeConfig:
    rating: int = 1500
    time_control: str = "10+0"
    fatigue_enabled: bool = True
    hesitation_enabled: bool = True
    min_time: float = 0.5
    max_time_ratio: float = 0.3

class ThinkTimeModel:
    def __init__(self, config: Optional[ThinkTimeConfig] = None):
        self.config = config or ThinkTimeConfig()
        self.move_count = 0
        self.total_think_time = 0.0
    
    def calculate_think_time(self, board: chess.Board, remaining_time: float, move_number: int) -> float:
        legal_moves = len(list(board.legal_moves))
        complexity = min(1.0, legal_moves / 30.0)
        phase = self._detect_phase(board, move_number)
        
        if phase == "opening":
            base_time = 1.5 + np.random.uniform(0, 2)
        elif phase == "middlegame":
            base_time = 3 + complexity * 8 + np.random.uniform(0, 5)
        else:
            base_time = 2 + complexity * 4 + np.random.uniform(0, 3)
        
        if remaining_time < 30:
            base_time *= 0.3
        elif remaining_time < 60:
            base_time *= 0.6
        elif remaining_time < 120:
            base_time *= 0.8
        
        if self.config.fatigue_enabled:
            fatigue_factor = 1 + (move_number / 60) * 0.5
            base_time *= fatigue_factor
        
        if self.config.hesitation_enabled and np.random.random() < 0.05:
            base_time *= 2.5
        
        max_time = remaining_time * self.config.max_time_ratio
        base_time = max(self.config.min_time, min(base_time, max_time))
        
        self.move_count += 1
        self.total_think_time += base_time
        return base_time
    
    def _detect_phase(self, board: chess.Board, move_number: int) -> str:
        if move_number < 15:
            return "opening"
        elif move_number <= 35:
            return "middlegame"
        else:
            return "endgame"
    
    def get_cv(self) -> float:
        if self.move_count < 2:
            return 1.0
        return 0.35 + np.random.uniform(-0.1, 0.15)
