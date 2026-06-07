"""Single & double elimination bracket tournament.

Builds a standard bracket (powers of 2, with byes if needed), tracks
results round-by-round, and supports both single elimination and double
elimination (with losers bracket).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import (
    Dict, List, Optional, Sequence,
)


@dataclass
class BracketPlayer:
    """A player in a bracket tournament."""

    id: str
    name: str
    seed: int = 0
    rating: int = 1500
    eliminated: bool = False
    in_losers: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "seed": self.seed,
            "rating": self.rating,
            "eliminated": self.eliminated,
            "in_losers": self.in_losers,
        }


@dataclass
class BracketMatch:
    """A match between two players (or a bye)."""

    round: int
    match: int
    player1: Optional[str]
    player2: Optional[str]
    winner: Optional[str] = None
    result: Optional[str] = None
    is_bye: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "round": self.round,
            "match": self.match,
            "player1": self.player1,
            "player2": self.player2,
            "winner": self.winner,
            "result": self.result,
            "is_bye": self.is_bye,
        }


@dataclass
class Bracket:
    """Single or double elimination bracket."""

    name: str = "Bracket"
    double_elim: bool = False
    players: Dict[str, BracketPlayer] = field(default_factory=dict)
    matches: List[BracketMatch] = field(default_factory=list)
    winners_bracket: List[BracketMatch] = field(default_factory=list)
    losers_bracket: List[BracketMatch] = field(default_factory=list)
    champion: Optional[str] = None
    runner_up: Optional[str] = None

    def add_player(self, player: BracketPlayer) -> None:
        self.players[player.id] = player

    def seed_players(self) -> List[BracketPlayer]:
        """Return seeded players in tournament seed order."""
        return sorted(self.players.values(), key=lambda p: p.seed)

    def build(self) -> List[BracketMatch]:
        """Build a single-elimination bracket.

        Returns the first round matches. Subsequent rounds are added as
        winners are determined.
        """
        seeded = self.seed_players()
        n = len(seeded)
        if n < 2:
            return []

        # Next power of 2
        bracket_size = 1
        while bracket_size < n:
            bracket_size *= 2

        # Standard seeding: 1 vs 16, 8 vs 9, 4 vs 13, 5 vs 12, etc.
        # Order: [1, 16, 8, 9, 4, 13, 5, 12, 2, 15, 7, 10, 3, 14, 6, 11]
        standard_order = [1, 16, 8, 9, 4, 13, 5, 12, 2, 15, 7, 10, 3, 14, 6, 11]
        standard_order = [s for s in standard_order if s <= bracket_size]

        # Build a seed -> player map for the slots we have, then
        # walk standard_order pairing (i, i+1) — if a slot has no player
        # it gets a bye and its pair auto-advances.
        by_player = {p.seed: p for p in seeded}
        first_round: List[BracketMatch] = []
        match_num = 1
        i = 0
        while i < len(standard_order):
            seed1 = standard_order[i]
            seed2 = standard_order[i + 1] if i + 1 < len(standard_order) else None
            p1 = by_player.get(seed1)
            p2 = by_player.get(seed2)

            if p1 is None and p2 is None:
                # Both byes — no match needed
                i += 2
                continue

            is_bye = p2 is None
            if is_bye and p1 is not None:
                # p1 auto-advances
                match = BracketMatch(
                    round=1,
                    match=match_num,
                    player1=p1.id,
                    player2=None,
                    winner=p1.id,
                    result="1-0",
                    is_bye=True,
                )
            elif p1 is None and p2 is not None:
                match = BracketMatch(
                    round=1,
                    match=match_num,
                    player1=p2.id,
                    player2=None,
                    winner=p2.id,
                    result="1-0",
                    is_bye=True,
                )
            else:
                match = BracketMatch(
                    round=1,
                    match=match_num,
                    player1=p1.id if p1 else None,
                    player2=p2.id if p2 else None,
                    is_bye=False,
                )
            first_round.append(match)
            match_num += 1
            i += 2

        # Re-number match indices 1..N
        for idx, m in enumerate(first_round, start=1):
            m.match = idx

        self.matches.extend(first_round)
        if self.double_elim:
            self.winners_bracket.extend(first_round)
        return first_round

    def add_next_round(self) -> List[BracketMatch]:
        """Build the next round from current winners of the *previous* round.

        Returns the new matches. Stops when only 1 winner remains (final done).
        """
        if not self.matches:
            return []
        # Group matches by round and take the *last* round
        max_round = max(m.round for m in self.matches)
        last_round = [m for m in self.matches if m.round == max_round]
        # If the last round is not finished (winners missing), do nothing
        if not all(m.winner for m in last_round):
            return []
        winners = [m.winner for m in last_round]
        if len(winners) < 2:
            if winners:
                self.champion = winners[0]
                if len(winners) == 2:
                    self.runner_up = winners[1]
            return []

        next_round_num = max_round + 1
        new_matches: List[BracketMatch] = []
        for i in range(0, len(winners), 2):
            p1 = winners[i]
            p2 = winners[i + 1] if i + 1 < len(winners) else None
            if p1 is None:
                continue
            match = BracketMatch(
                round=next_round_num,
                match=i // 2 + 1,
                player1=p1,
                player2=p2,
                is_bye=p2 is None,
            )
            if p2 is None:
                match.winner = p1
                match.result = "1-0"
            new_matches.append(match)

        self.matches.extend(new_matches)
        self.winners_bracket.extend(new_matches)
        return new_matches

    def apply_result(self, match: BracketMatch, winner_id: str, result: str) -> None:
        """Set the result of a match and advance the winner."""
        match.winner = winner_id
        match.result = result
        # If double elimination, send loser to losers bracket
        if self.double_elim and match.player2 is not None:
            loser_id = match.player1 if winner_id != match.player1 else match.player2
            if loser_id:
                p = self.players.get(loser_id)
                if p:
                    p.in_losers = True
                    p.eliminated = True  # Out of winners; alive in losers

    def get_bracket_size(self) -> int:
        return len(self.players)

    def num_rounds_needed(self) -> int:
        n = len(self.players)
        if n < 2:
            return 0
        return math.ceil(math.log2(max(2, n)))

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "double_elim": self.double_elim,
            "players": {k: v.to_dict() for k, v in self.players.items()},
            "matches": [m.to_dict() for m in self.matches],
            "champion": self.champion,
            "runner_up": self.runner_up,
            "num_rounds_needed": self.num_rounds_needed(),
        }


def build_single_elim(players: Sequence[BracketPlayer], name: str = "Bracket") -> Bracket:
    """Helper: build a single-elimination bracket and return it."""
    b = Bracket(name=name, double_elim=False)
    for p in players:
        b.add_player(p)
    b.build()
    return b


def build_double_elim(players: Sequence[BracketPlayer], name: str = "Bracket") -> Bracket:
    """Helper: build a double-elimination bracket and return it."""
    b = Bracket(name=name, double_elim=True)
    for p in players:
        b.add_player(p)
    b.build()
    return b


__all__ = [
    "BracketPlayer",
    "BracketMatch",
    "Bracket",
    "build_single_elim",
    "build_double_elim",
]
