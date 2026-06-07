"""Swiss tournament pairings.

FIDE-style Swiss pairing: in each round, players are paired with others
having the same (or nearest) score group. Top half plays bottom half
within each group. No rematches within the tournament.

This is a simplified Swiss pairings implementation suitable for casual
or club tournaments (up to ~50 players). For official FIDE events,
use the official JaVaFo software.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Dict, List, Optional, Sequence, Set,
)


@dataclass
class SwissPlayer:
    """A player in a Swiss tournament."""

    id: str
    name: str
    rating: int = 1500
    score: float = 0.0
    has_bye: bool = False
    opponents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "rating": self.rating,
            "score": self.score,
            "has_bye": self.has_bye,
            "opponents": list(self.opponents),
        }


@dataclass
class SwissPairing:
    """A Swiss pairing (board 1, board 2, etc)."""

    board: int
    white: str
    black: Optional[str]  # None = bye
    result: Optional[str] = None  # "1-0" | "0-1" | "1/2-1/2"

    @property
    def is_bye(self) -> bool:
        return self.black is None

    def to_dict(self) -> Dict[str, object]:
        return {
            "board": self.board,
            "white": self.white,
            "black": self.black,
            "result": self.result,
            "is_bye": self.is_bye,
        }


@dataclass
class SwissRound:
    """A round of Swiss pairings."""

    number: int
    pairings: List[SwissPairing] = field(default_factory=list)


@dataclass
class SwissTournament:
    """A Swiss tournament."""

    name: str = "Swiss"
    num_rounds: int = 5
    players: Dict[str, SwissPlayer] = field(default_factory=dict)
    rounds: List[SwissRound] = field(default_factory=list)
    current_round: int = 0

    def add_player(self, player: SwissPlayer) -> None:
        self.players[player.id] = player

    def standings(self) -> List[SwissPlayer]:
        """Players sorted by score, then rating."""
        return sorted(
            self.players.values(),
            key=lambda p: (-p.score, -p.rating, p.id),
        )

    def make_round(self, round_number: Optional[int] = None) -> SwissRound:
        """Generate Swiss pairings for the next round.

        Algorithm:
        1. Sort by score, then rating.
        2. Group into score groups.
        3. Within each group, top half plays bottom half.
        4. Skip if opponent was already played (try next in group).
        5. If odd player, lowest score gets a bye.
        """
        rn = round_number or self.current_round + 1
        sorted_players = self.standings()
        if not sorted_players:
            return SwissRound(number=rn)

        # Build score groups
        groups: Dict[float, List[SwissPlayer]] = defaultdict(list)
        for p in sorted_players:
            groups[p.score].append(p)

        pairings: List[SwissPairing] = []
        paired: Set[str] = set()
        bye_given = False
        board = 1

        # Iterate score groups in descending order
        for score in sorted(groups.keys(), reverse=True):
            group = groups[score]
            random.shuffle(group)  # For fairness within groups
            # Split into top half + bottom half
            n = len(group)
            if n == 0:
                continue
            top = group[: n // 2]
            bottom = group[n // 2 :]
            # Pad if odd count
            if (n - len(top) - len(bottom)) > 0:
                # extra player — goes to bottom half
                pass

            # Pair top vs bottom
            for i, t in enumerate(top):
                if t.id in paired:
                    continue
                if i < len(bottom):
                    b = bottom[i]
                    if b.id in paired:
                        # Try to find another opponent in same group
                        for alt in bottom[i + 1 :]:
                            if alt.id not in paired and alt.id not in t.opponents:
                                b = alt
                                break
                        else:
                            continue
                    if b.id in paired or b.id in t.opponents:
                        continue
                    pairings.append(SwissPairing(board=board, white=t.id, black=b.id))
                    paired.add(t.id)
                    paired.add(b.id)
                    board += 1
                else:
                    # No opponent in group — defer
                    pass

        # Handle unpaired players (carry over to next group)
        unpaired = [p for p in sorted_players if p.id not in paired and not p.has_bye]
        if unpaired:
            # Pair among themselves
            i = 0
            while i < len(unpaired) - 1:
                p1 = unpaired[i]
                p2 = unpaired[i + 1]
                if p2.id not in p1.opponents:
                    pairings.append(SwissPairing(board=board, white=p1.id, black=p2.id))
                    paired.add(p1.id)
                    paired.add(p2.id)
                    board += 1
                    i += 2
                else:
                    i += 1

        # Bye
        if len(self.players) % 2 == 1 and not bye_given:
            unpaired = [p for p in sorted_players if p.id not in paired and not p.has_bye]
            if unpaired:
                bye_player = unpaired[-1]  # Lowest score
                pairings.append(SwissPairing(board=board, white=bye_player.id, black=None, result="1-0"))
                bye_player.has_bye = True
                paired.add(bye_player.id)

        rnd = SwissRound(number=rn, pairings=pairings)
        self.rounds.append(rnd)
        self.current_round = rn
        return rnd

    def apply_result(self, pairing: SwissPairing) -> None:
        if pairing.is_bye or pairing.result is None:
            return
        p1 = self.players[pairing.white]
        p2 = self.players[pairing.black] if pairing.black else None
        if p2 is None:
            return
        if pairing.result == "1-0":
            p1.score += 1.0
        elif pairing.result == "0-1":
            p2.score += 1.0
        elif pairing.result == "1/2-1/2":
            p1.score += 0.5
            p2.score += 0.5
        # Track opponents
        if p2.id not in p1.opponents:
            p1.opponents.append(p2.id)
        if p1.id not in p2.opponents:
            p2.opponents.append(p1.id)

    def is_complete(self) -> bool:
        return self.current_round >= self.num_rounds

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "num_rounds": self.num_rounds,
            "current_round": self.current_round,
            "standings": [p.to_dict() for p in self.standings()],
            "rounds": [[p.to_dict() for p in r.pairings] for r in self.rounds],
        }


def simulate_swiss(players: Sequence[SwissPlayer], num_rounds: int = 5, seed: int = 42) -> SwissTournament:
    """Run a simulated Swiss tournament with random results."""
    random.seed(seed)
    tour = SwissTournament(num_rounds=num_rounds)
    for p in players:
        tour.add_player(p)
    for r in range(1, num_rounds + 1):
        rnd = tour.make_round(r)
        for pairing in rnd.pairings:
            if pairing.is_bye:
                tour.apply_result(SwissPairing(board=pairing.board, white=pairing.white, black=None, result="1-0"))
                continue
            p1 = tour.players[pairing.white]
            p2 = tour.players[pairing.black]
            e = 1.0 / (1.0 + 10 ** ((p2.rating - p1.rating) / 400.0))
            roll = random.random()
            if roll < e - 0.1:
                res = "1-0"
            elif roll > e + 0.1:
                res = "0-1"
            else:
                res = "1/2-1/2"
            tour.apply_result(SwissPairing(board=pairing.board, white=p1.id, black=p2.id, result=res))
    return tour


__all__ = [
    "SwissPlayer",
    "SwissPairing",
    "SwissRound",
    "SwissTournament",
    "simulate_swiss",
]
