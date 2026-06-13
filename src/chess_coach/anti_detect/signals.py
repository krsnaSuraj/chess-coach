"""12-signal anti-detection analyzer."""
from __future__ import annotations
import numpy as np
import chess
from dataclasses import dataclass

@dataclass
class SignalResult:
    name: str
    value: float  # 0-1
    weight: float
    confidence: float

class SignalAnalyzer:
    def __init__(self):
        self.move_history: list[chess.Move] = []
        self.time_history: list[float] = []
        self.eval_history: list[float] = []
        self.engine_top_moves: list[list[chess.Move]] = []
    
    def record_move(self, move: chess.Move, think_time: float, eval_before: float, engine_top: list[chess.Move]):
        self.move_history.append(move)
        self.time_history.append(think_time)
        self.eval_history.append(eval_before)
        self.engine_top_moves.append(engine_top)
    
    def sf_top1_match_rate(self) -> SignalResult:
        if len(self.move_history) < 10:
            return SignalResult("sf_top1_match", 0.0, 0.15, 0.0)
        matches = sum(1 for i, mv in enumerate(self.move_history) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and mv == self.engine_top_moves[i][0])
        rate = matches / len(self.move_history)
        suspicion = max(0, (rate - 0.6) / 0.4)
        return SignalResult("sf_top1_match", min(1.0, suspicion), 0.15, 1.0)
    
    def average_cpl(self) -> SignalResult:
        if len(self.eval_history) < 10:
            return SignalResult("avg_cpl", 0.0, 0.12, 0.0)
        cpls = [min(abs(self.eval_history[i] - self.eval_history[i-1]) * 100, 500) for i in range(1, len(self.eval_history))]
        avg_cpl = np.mean(cpls)
        suspicion = max(0, (50 - avg_cpl) / 50)
        return SignalResult("avg_cpl", min(1.0, suspicion), 0.12, 1.0)
    
    def move_time_cv(self) -> SignalResult:
        if len(self.time_history) < 10:
            return SignalResult("time_cv", 0.0, 0.15, 0.0)
        times = np.array(self.time_history)
        mean, std = np.mean(times), np.std(times)
        if mean == 0:
            return SignalResult("time_cv", 1.0, 0.15, 1.0)
        cv = std / mean
        suspicion = max(0, (0.25 - cv) / 0.25)
        return SignalResult("time_cv", min(1.0, suspicion), 0.15, 1.0)
    
    def style_consistency(self) -> SignalResult:
        if len(self.move_history) < 20:
            return SignalResult("style_consistency", 0.0, 0.10, 0.0)
        phase_accuracies = []
        for start in [0, 10, 30]:
            phase = self.move_history[start:start+10]
            if len(phase) < 5: continue
            matches = sum(1 for i, mv in enumerate(phase) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and mv == self.engine_top_moves[i][0])
            phase_accuracies.append(matches / len(phase))
        if len(phase_accuracies) < 2:
            return SignalResult("style_consistency", 0.0, 0.10, 0.0)
        variance = np.var(phase_accuracies)
        suspicion = max(0, (0.05 - variance) / 0.05)
        return SignalResult("style_consistency", min(1.0, suspicion), 0.10, 1.0)
    
    def tactical_accuracy(self) -> SignalResult:
        if len(self.move_history) < 10:
            return SignalResult("tactical_accuracy", 0.0, 0.08, 0.0)
        forced_moves, forced_matches = 0, 0
        for i, move in enumerate(self.move_history):
            if i > 0 and i < len(self.engine_top_moves) and len(self.engine_top_moves[i]) > 1:
                if self.eval_history[i] - self.eval_history[i-1] > 1.0:
                    forced_moves += 1
                    if move == self.engine_top_moves[i][0]:
                        forced_matches += 1
        if forced_moves < 5:
            return SignalResult("tactical_accuracy", 0.0, 0.08, 0.0)
        accuracy = forced_matches / forced_moves
        suspicion = max(0, (0.9 - accuracy) / 0.1)
        return SignalResult("tactical_accuracy", min(1.0, suspicion), 0.08, 1.0)
    
    def blunder_frequency(self) -> SignalResult:
        if len(self.eval_history) < 10:
            return SignalResult("blunder_freq", 0.0, 0.08, 0.0)
        blunders = sum(1 for i in range(1, len(self.eval_history)) if (self.eval_history[i-1] - self.eval_history[i]) * 100 > 200)
        rate = blunders / len(self.eval_history)
        suspicion = max(0, (0.05 - rate) / 0.05)
        return SignalResult("blunder_freq", min(1.0, suspicion), 0.08, 1.0)
    
    def phase_conditional_accuracy(self) -> SignalResult:
        if len(self.move_history) < 30:
            return SignalResult("phase_accuracy", 0.0, 0.07, 0.0)
        accuracies = []
        for phase in [self.move_history[:15], self.move_history[15:35], self.move_history[35:]]:
            if len(phase) < 5: continue
            matches = sum(1 for i, mv in enumerate(phase) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and mv == self.engine_top_moves[i][0])
            accuracies.append(matches / len(phase))
        if len(accuracies) < 2:
            return SignalResult("phase_accuracy", 0.0, 0.07, 0.0)
        std_dev = np.std(accuracies)
        suspicion = max(0, (0.1 - std_dev) / 0.1)
        return SignalResult("phase_accuracy", min(1.0, suspicion), 0.07, 1.0)
    
    def move_ordering_entropy(self) -> SignalResult:
        if len(self.move_history) < 10:
            return SignalResult("entropy", 0.0, 0.10, 0.0)
        move_ranks = []
        for i, mv in enumerate(self.move_history):
            if i < len(self.engine_top_moves) and self.engine_top_moves[i]:
                try: move_ranks.append(self.engine_top_moves[i].index(mv))
                except ValueError: move_ranks.append(5)
        if not move_ranks:
            return SignalResult("entropy", 0.0, 0.10, 0.0)
        counts = np.bincount(move_ranks, minlength=6)
        probs = counts[counts > 0] / counts.sum()
        entropy = -np.sum(probs * np.log2(probs))
        suspicion = max(0, (2.0 - entropy) / 2.0)
        return SignalResult("entropy", min(1.0, suspicion), 0.10, 1.0)
    
    def positional_novelty_rate(self) -> SignalResult:
        if len(self.move_history) < 10:
            return SignalResult("novelty_rate", 0.0, 0.05, 0.0)
        novelty = sum(1 for i, mv in enumerate(self.move_history) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and mv not in self.engine_top_moves[i][:5])
        rate = novelty / len(self.move_history)
        suspicion = max(0, (0.2 - rate) / 0.2)
        return SignalResult("novelty_rate", min(1.0, suspicion), 0.05, 1.0)
    
    def temporal_pattern(self) -> SignalResult:
        if len(self.time_history) < 20:
            return SignalResult("temporal_pattern", 0.0, 0.05, 0.0)
        mid = len(self.time_history) // 2
        first_half, second_half = np.mean(self.time_history[:mid]), np.mean(self.time_history[mid:])
        ratio = second_half / first_half if first_half > 0 else 1.0
        suspicion = max(0, (1.1 - ratio) / 0.3)
        return SignalResult("temporal_pattern", min(1.0, suspicion), 0.05, 1.0)
    
    def opening_reertoire_deviation(self) -> SignalResult:
        if len(self.move_history) < 10:
            return SignalResult("opening_deviation", 0.0, 0.03, 0.0)
        book = sum(1 for i in range(min(10, len(self.move_history))) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and self.move_history[i] in self.engine_top_moves[i][:3])
        rate = book / min(10, len(self.move_history))
        suspicion = max(0, (0.8 - rate) / 0.2)
        return SignalResult("opening_deviation", min(1.0, suspicion), 0.03, 1.0)
    
    def endgame_technique(self) -> SignalResult:
        if len(self.move_history) < 40:
            return SignalResult("endgame_technique", 0.0, 0.02, 0.0)
        endgame = self.move_history[35:]
        if len(endgame) < 5:
            return SignalResult("endgame_technique", 0.0, 0.02, 0.0)
        matches = sum(1 for i, mv in enumerate(endgame) if i < len(self.engine_top_moves) and self.engine_top_moves[i] and mv == self.engine_top_moves[i][0])
        accuracy = matches / len(endgame)
        suspicion = max(0, (0.7 - accuracy) / 0.3)
        return SignalResult("endgame_technique", min(1.0, suspicion), 0.02, 1.0)
    
    def analyze_all(self) -> list[SignalResult]:
        return [self.sf_top1_match_rate(), self.average_cpl(), self.move_time_cv(), self.style_consistency(), self.tactical_accuracy(), self.blunder_frequency(), self.phase_conditional_accuracy(), self.move_ordering_entropy(), self.positional_novelty_rate(), self.temporal_pattern(), self.opening_reertoire_deviation(), self.endgame_technique()]
    
    def get_weighted_score(self) -> float:
        signals = self.analyze_all()
        total_weight = sum(s.weight for s in signals)
        return sum(s.value * s.weight for s in signals) / total_weight if total_weight > 0 else 0.0
