from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import chess


@dataclass
class PvLine:
    move: chess.Move
    centipawns: float
    mate: int | None
    rank: int


@dataclass
class SessionMetrics:
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    avg_accuracy: float = 0.0
    games: list[float] = field(default_factory=list)

    def record_game(self, accuracy: float, result: str) -> None:
        self.games.append(accuracy)
        self.games_played += 1
        self.avg_accuracy = sum(self.games) / len(self.games)
        if result == "win":
            self.wins += 1
        elif result == "loss":
            self.losses += 1
        else:
            self.draws += 1

    def coherence_score(self) -> float:
        if len(self.games) < 3:
            return 0.0
        mean = sum(self.games) / len(self.games)
        variance = sum((g - mean) ** 2 for g in self.games) / len(self.games)
        return 1.0 / (1.0 + variance * 100)

    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played


def _accuracy_for_elo(elo: float) -> float:
    return (elo / 100.0 + 64.0) / 100.0


def _top1_rate_for_elo(elo: float) -> float:
    if elo <= 800:
        return 0.12
    if elo <= 1200:
        return 0.16
    if elo <= 1500:
        return 0.22
    if elo <= 1800:
        return 0.30
    if elo <= 2100:
        return 0.40
    if elo <= 2400:
        return 0.52
    return 0.65


def _top3_cumulative_for_elo(elo: float) -> float:
    if elo <= 800:
        return 0.30
    if elo <= 1200:
        return 0.42
    if elo <= 1500:
        return 0.55
    if elo <= 1800:
        return 0.65
    if elo <= 2100:
        return 0.75
    if elo <= 2400:
        return 0.84
    return 0.92


def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


class Humanizer:
    def __init__(self, config: dict) -> None:
        hc = config.get("humanizer", {})
        self.enabled: bool = hc.get("enabled", True)
        self.target_elo: int = hc.get("target_elo", 1500)
        self.personality: str = hc.get("personality", "balanced")
        self.aggression: float = hc.get("aggression", 0.5)

        ei = hc.get("error_injection", {})
        self.inaccuracy_rate: float = ei.get("inaccuracy_rate", 0.10)
        self.mistake_rate: float = ei.get("mistake_rate", 0.03)
        self.blunder_rate: float = ei.get("blunder_rate", 0.005)

        self._move_count: int = 0
        self._session = SessionMetrics()
        self._games_played: int = 0
        self._progressive_elo: float = float(self.target_elo)
        self._effective_elo: float = float(self.target_elo)

    def new_game(self) -> None:
        self._move_count = 0
        self._games_played += 1

        climb = random.randint(20, 50)
        if random.random() < 0.15:
            dip = -random.randint(30, 100)
            self._progressive_elo = max(
                float(self.target_elo) - 100,
                self._progressive_elo + dip,
            )
        self._progressive_elo = min(
            float(self.target_elo) + 500,
            self._progressive_elo + climb,
        )

    def select_move(
        self,
        multi_pv: list[dict],
        board: chess.Board,
        is_complex: bool = False,
        eval_score: float = 0.0,
    ) -> chess.Move | None:
        if not self.enabled or not multi_pv:
            pv = multi_pv[0].get("pv") if multi_pv else None
            return pv[0] if pv else None

        candidates = self._build_ranked(multi_pv)
        if not candidates:
            return None

        self._move_count += 1
        self._effective_elo = self._progressive_elo + random.randint(-30, 30)

        if is_complex:
            self._effective_elo += random.randint(15, 50)
        if eval_score > 2.5:
            drop = random.randint(40, 120)
            self._effective_elo = max(
                float(self.target_elo) - 100, self._effective_elo - drop
            )

        effective_inaccuracy = self.inaccuracy_rate
        effective_mistake = self.mistake_rate
        effective_blunder = self.blunder_rate

        if is_complex:
            effective_inaccuracy *= 1.6
            effective_mistake *= 2.0

        error_type = self._roll_error(
            effective_inaccuracy, effective_mistake, effective_blunder
        )
        if error_type:
            return self._inject_error(candidates, board, error_type)

        return self._accuracy_weighted_select(candidates, board)

    def _build_ranked(self, multi_pv: list[dict]) -> list[PvLine]:
        ranked: list[PvLine] = []
        for i, info in enumerate(multi_pv):
            pv = info.get("pv")
            if not pv:
                continue
            score = info.get("score")
            cp = 0.0
            mate = None
            if score:
                cp_val = score.relative.score(mate_score=10000)
                mate = score.relative.mate()
                cp = cp_val if cp_val is not None else 0.0
            ranked.append(PvLine(
                move=pv[0],
                centipawns=cp,
                mate=mate,
                rank=i + 1,
            ))
        return ranked

    def _roll_error(
        self, inaccuracy_rate: float, mistake_rate: float, blunder_rate: float
    ) -> str | None:
        roll = random.random()
        if roll < blunder_rate:
            return "blunder"
        if roll < blunder_rate + mistake_rate:
            return "mistake"
        if roll < blunder_rate + mistake_rate + inaccuracy_rate:
            return "inaccuracy"
        return None

    def _inject_error(
        self,
        candidates: list[PvLine],
        board: chess.Board,
        error_type: str,
    ) -> chess.Move | None:
        if error_type == "blunder":
            return self._human_blunder(candidates, board)
        if error_type == "mistake":
            return self._human_mistake(candidates, board)
        if error_type == "inaccuracy":
            return self._human_inaccuracy(candidates)
        return None

    def _human_inaccuracy(self, candidates: list[PvLine]) -> chess.Move | None:
        if len(candidates) >= 2:
            pool = [c for c in candidates if c.rank >= 2]
            if pool:
                weights = [1.0 / c.rank for c in pool]
                return random.choices(pool, weights=weights, k=1)[0].move
        return candidates[0].move if candidates else None

    def _human_mistake(
        self, candidates: list[PvLine], board: chess.Board
    ) -> chess.Move | None:
        if len(candidates) >= 3:
            pool = [c for c in candidates if c.rank >= 3]
            if pool:
                return random.choice(pool).move
        legal = list(board.legal_moves)
        engine_moves = {c.move for c in candidates[:3]}
        non_engine = [m for m in legal if m not in engine_moves]
        if non_engine:
            return random.choice(non_engine)
        return candidates[-1].move if candidates else None

    def _human_blunder(
        self, candidates: list[PvLine], board: chess.Board
    ) -> chess.Move | None:
        legal = list(board.legal_moves)
        blunders: list[chess.Move] = []
        for move in legal:
            board_copy = board.copy()
            board_copy.push(move)
            if board_copy.is_checkmate():
                continue
            attackers = board_copy.attackers(
                board_copy.turn, board_copy.king(not board_copy.turn)
            )
            if attackers:
                continue
            pieces_after = len(board_copy.piece_map())
            pieces_before = len(board.piece_map())
            if pieces_after < pieces_before:
                if board_copy.is_check():
                    blunders.append(move)
                    continue
        if blunders:
            return random.choice(blunders)
        if len(candidates) >= 2:
            return candidates[-1].move
        return random.choice(legal)

    def _accuracy_weighted_select(
        self, candidates: list[PvLine], board: chess.Board
    ) -> chess.Move | None:
        if not candidates:
            return None

        n = len(candidates)
        if n == 1:
            return candidates[0].move

        elo = self._effective_elo
        target_accuracy = _accuracy_for_elo(elo)
        top1_rate = _top1_rate_for_elo(elo)
        top3_cum = _top3_cumulative_for_elo(elo)

        remaining_after_top1 = top3_cum - top1_rate
        weights = [top1_rate]
        if n >= 2 and remaining_after_top1 > 0:
            weights.append(remaining_after_top1 * 0.55)
            if n >= 3:
                weights.append(remaining_after_top1 * 0.28)
                if n >= 4:
                    weights.append(remaining_after_top1 * 0.12)
                    if n >= 5:
                        weights.append(remaining_after_top1 * 0.05)

        raw_total = sum(weights)
        if raw_total <= 0:
            return random.choice(candidates).move

        target = min(0.94, max(0.30, target_accuracy))
        pick_engine = random.random() < target

        if pick_engine:
            probs = [w / raw_total for w in weights]
            r = random.random()
            cumulative = 0.0
            for i in range(min(len(probs), len(candidates))):
                cumulative += probs[i]
                if r <= cumulative:
                    return candidates[i].move
            return candidates[0].move

        engine_moves = {c.move for c in candidates[:min(3, len(candidates))]}
        non_engine = [m for m in board.legal_moves if m not in engine_moves]
        if non_engine:
            return random.choice(non_engine)
        return candidates[-1].move

    @property
    def effective_elo(self) -> float:
        return self._progressive_elo

    def record_result(self, result: str, estimated_accuracy: float = 0.0) -> None:
        self._session.record_game(estimated_accuracy, result)

    def get_risk_assessment(self) -> dict:
        accuracy = self._session.avg_accuracy
        expected = _accuracy_for_elo(self._progressive_elo)
        deviation = accuracy - expected
        coherence = self._session.coherence_score()

        if deviation > 0.12 or coherence > 0.95:
            level = "CRITICAL"
        elif deviation > 0.08 or coherence > 0.85:
            level = "WARNING"
        elif deviation > 0.04 or coherence > 0.70:
            level = "CAUTION"
        else:
            level = "SAFE"

        return {
            "level": level,
            "deviation": round(deviation, 4),
            "accuracy": round(accuracy, 4),
            "expected": round(expected, 4),
            "coherence": round(coherence, 4),
            "games": self._session.games_played,
            "effective_elo": round(self._progressive_elo),
            "win_rate": round(self._session.win_rate(), 3),
        }


class ComplexityDetector:
    @staticmethod
    def is_complex(board: chess.Board) -> bool:
        pieces = len(board.piece_map())
        if pieces <= 16:
            return False
        if board.fullmove_number <= 8 and pieces >= 28:
            return False
        attack_count = sum(
            len(board.attackers(chess.WHITE, sq))
            + len(board.attackers(chess.BLACK, sq))
            for sq in chess.SQUARES if board.piece_at(sq)
        )
        if attack_count >= 40:
            return True
        legal = len(list(board.legal_moves))
        if legal >= 35:
            return True
        captures = sum(1 for m in board.legal_moves if board.is_capture(m))
        if captures >= 10:
            return True
        checks = sum(1 for m in board.legal_moves if board.gives_check(m))
        return checks >= 5

    @staticmethod
    def is_time_pressure(remaining_seconds: float | None = None) -> bool:
        if remaining_seconds is not None:
            return remaining_seconds < 60.0
        return random.random() > 0.7
