"""Session coherence tracker for anti-detection."""
from __future__ import annotations
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SessionMetrics:
    total_moves: int
    average_cv: float
    average_cpl: float
    blunder_rate: float
    peak_accuracy: float
    duration_minutes: float
    games_played: int

@dataclass
class GameRecord:
    moves: int
    cv: float
    cpl: float
    blunder_rate: float
    accuracy: float
    timestamp: datetime

class SessionTracker:
    def __init__(self):
        self.sessions: list[dict] = []
        self.current_session: Optional[dict] = None
    
    def start_session(self):
        self.current_session = {"start_time": datetime.now(), "games": []}
    
    def record_game(self, moves: int, cv: float, cpl: float, blunders: int, accuracy: float):
        if self.current_session is None:
            self.start_session()
        self.current_session["games"].append(GameRecord(moves=moves, cv=cv, cpl=cpl, blunder_rate=blunders/moves if moves > 0 else 0, accuracy=accuracy, timestamp=datetime.now()))
    
    def get_coherence_score(self) -> float:
        if self.current_session is None or len(self.current_session["games"]) < 2:
            return 0.0
        games = self.current_session["games"]
        accuracies = [g.accuracy for g in games]
        if np.std(accuracies) > 15:
            return 0.8
        mean_cv = np.mean([g.cv for g in games])
        if mean_cv < 0.2:
            return 0.9
        return max(0.0, min(1.0, 0.2 + (mean_cv - 0.25) * 0.5))
    
    def get_session_metrics(self) -> Optional[SessionMetrics]:
        if self.current_session is None or not self.current_session["games"]:
            return None
        games = self.current_session["games"]
        duration = (datetime.now() - self.current_session["start_time"]).total_seconds() / 60
        return SessionMetrics(total_moves=sum(g.moves for g in games), average_cv=np.mean([g.cv for g in games]), average_cpl=np.mean([g.cpl for g in games]), blunder_rate=np.mean([g.blunder_rate for g in games]), peak_accuracy=max(g.accuracy for g in games), duration_minutes=duration, games_played=len(games))
