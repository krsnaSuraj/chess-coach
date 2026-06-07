"""Arena tournament scheduler.

Lichess-style arena tournament: players are paired with anyone available
regardless of score. After each game, the new pairings are determined by
a stream of available players. This module provides a simplified round-by-
round scheduler that pairs all available players in each round.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass
class ArenaPlayer:
    """A player in an arena tournament."""

    id: str
    name: str
    rating: int = 1500
    score: float = 0.0
    games_played: int = 0
    berserkable: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "rating": self.rating,
            "score": self.score,
            "games_played": self.games_played,
        }


@dataclass
class ArenaPairing:
    """A single pairing in an arena round."""

    player1: str
    player2: Optional[str]  # None = bye
    result: Optional[str] = None  # "1-0" | "0-1" | "1/2-1/2" | None

    @property
    def is_bye(self) -> bool:
        return self.player2 is None

    def to_dict(self) -> Dict[str, object]:
        return {
            "player1": self.player1,
            "player2": self.player2,
            "result": self.result,
            "is_bye": self.is_bye,
        }


@dataclass
class ArenaRound:
    """A round of arena pairings."""

    number: int
    pairings: List[ArenaPairing] = field(default_factory=list)
    start_time: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "pairings": [p.to_dict() for p in self.pairings],
        }


@dataclass
class ArenaTournament:
    """Arena tournament state."""

    name: str = "Arena"
    minutes: int = 60
    players: Dict[str, ArenaPlayer] = field(default_factory=dict)
    rounds: List[ArenaRound] = field(default_factory=list)
    current_round: int = 0
    initial_clock: int = 300  # seconds
    increment: int = 0

    def add_player(self, player: ArenaPlayer) -> None:
        self.players[player.id] = player

    def standings(self) -> List[ArenaPlayer]:
        """Return players sorted by score, then rating, then games played."""
        return sorted(
            self.players.values(),
            key=lambda p: (-p.score, -p.rating, -p.games_played, p.id),
        )

    def total_games(self) -> int:
        return sum(p.games_played for p in self.players.values()) // 2

    def make_round(self, round_number: Optional[int] = None) -> ArenaRound:
        """Generate a new round of pairings.

        If odd number of players, lowest-scored player gets a bye.
        """
        rn = round_number or self.current_round + 1
        available = [p for p in self.players.values() if not self._is_in_active_game(p)]
        # Randomize, but keep top half vs bottom half
        random.shuffle(available)
        # Try to pair by score similarity
        available.sort(key=lambda p: p.score, reverse=True)
        pairs: List[ArenaPairing] = []
        used: set[str] = set()
        i = 0
        while i < len(available):
            p1 = available[i]
            if p1.id in used:
                i += 1
                continue
            # Find first available opponent
            j = i + 1
            opponent: Optional[ArenaPlayer] = None
            while j < len(available):
                p2 = available[j]
                if p2.id not in used:
                    opponent = p2
                    break
                j += 1
            if opponent is None:
                pairs.append(ArenaPairing(player1=p1.id, player2=None))  # bye
            else:
                pairs.append(ArenaPairing(player1=p1.id, player2=opponent.id))
                used.add(opponent.id)
            used.add(p1.id)
            i += 1

        rnd = ArenaRound(number=rn, pairings=pairs)
        self.rounds.append(rnd)
        self.current_round = rn
        return rnd

    def _is_in_active_game(self, player: ArenaPlayer) -> bool:
        """Stub: in a real arena, a player is busy until they finish a game.
        For this simplified model, we assume all are available."""
        return False

    def apply_result(self, pairing: ArenaPairing) -> None:
        """Apply a result to a pairing and update player scores."""
        if pairing.is_bye or pairing.result is None:
            return
        p1 = self.players[pairing.player1]
        p2 = self.players.get(pairing.player2) if pairing.player2 else None
        if p2 is None:
            return
        p1.games_played += 1
        p2.games_played += 1
        if pairing.result == "1-0":
            p1.score += 1.0
        elif pairing.result == "0-1":
            p2.score += 1.0
        elif pairing.result == "1/2-1/2":
            p1.score += 0.5
            p2.score += 0.5

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "minutes": self.minutes,
            "current_round": self.current_round,
            "rounds": [r.to_dict() for r in self.rounds],
            "standings": [p.to_dict() for p in self.standings()],
            "total_games": self.total_games(),
        }


def simulate_arena(players: Sequence[ArenaPlayer], num_rounds: int = 5, seed: int = 42) -> ArenaTournament:
    """Run a simulated arena tournament with random results.

    For testing purposes: uses random outcomes based on rating differences.
    """
    random.seed(seed)
    arena = ArenaTournament()
    for p in players:
        arena.add_player(p)

    def expected(r1: int, r2: int) -> float:
        return 1.0 / (1.0 + 10 ** ((r2 - r1) / 400.0))

    for r in range(1, num_rounds + 1):
        rnd = arena.make_round(r)
        for pairing in rnd.pairings:
            if pairing.is_bye:
                arena.apply_result(ArenaPairing(player1=pairing.player1, player2=None, result="1-0"))
                continue
            p1 = arena.players[pairing.player1]
            p2 = arena.players[pairing.player2]
            e = expected(p1.rating, p2.rating)
            roll = random.random()
            if roll < e - 0.1:
                res = "1-0"
            elif roll > e + 0.1:
                res = "0-1"
            else:
                res = "1/2-1/2"
            arena.apply_result(ArenaPairing(player1=p1.id, player2=p2.id, result=res))

    return arena


__all__ = [
    "ArenaPlayer",
    "ArenaPairing",
    "ArenaRound",
    "ArenaTournament",
    "simulate_arena",
]
