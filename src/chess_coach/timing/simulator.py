"""Timing simulator for anti-detection."""
from __future__ import annotations
import numpy as np
from chess_coach.timing.model import ThinkTimeModel, ThinkTimeConfig
from chess_coach.anti_detect.signals import SignalAnalyzer

class TimingSimulator:
    def __init__(self, config: ThinkTimeConfig):
        self.config = config
        self.model = ThinkTimeModel(config)
        self.signal_analyzer = SignalAnalyzer()
    
    def get_think_time(self, board, remaining_time: float, move_number: int) -> float:
        base_time = self.model.calculate_think_time(board, remaining_time, move_number)
        current_cv = self._estimate_cv()
        if current_cv < 0.25:
            noise = np.random.uniform(0.5, 2.0)
            base_time *= noise
        return base_time
    
    def _estimate_cv(self) -> float:
        if self.model.move_count < 2:
            return 1.0
        return self.model.get_cv()
    
    def record_move(self, move, think_time: float, eval_before: float, engine_top: list):
        self.signal_analyzer.record_move(move, think_time, eval_before, engine_top)
