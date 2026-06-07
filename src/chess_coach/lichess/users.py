"""Lichess Users API client.

Endpoints:
- GET /api/user/{username} - public profile
- GET /api/users/status - status of multiple users
- GET /api/user/{username}/rating-history - rating progression
- GET /api/user/{username}/stats - game stats (wins/losses by time control)
- GET /api/user/{username}/activity - activity feed
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


@dataclass
class UserProfile:
    """Lichess public user profile."""
    id: str = ""
    username: str = ""
    title: str | None = None
    patron: bool = False
    online: bool = False
    rating_blitz: int | None = None
    rating_bullet: int | None = None
    rating_rapid: int | None = None
    rating_classical: int | None = None
    rating_correspondence: int | None = None
    rating_puzzle: int | None = None
    nb_games: int = 0
    nb_wins: int = 0
    nb_losses: int = 0
    nb_draws: int = 0
    created_at: int = 0
    seen_at: int = 0

    @property
    def win_rate(self) -> float:
        if self.nb_games == 0:
            return 0.0
        return self.nb_wins / self.nb_games


@dataclass
class RatingHistory:
    """A single rating over time for one variant."""
    name: str = "blitz"  # bullet/blitz/rapid/classical/correspondence/puzzle
    points: list[tuple[int, int]] = field(default_factory=list)  # (year+month, rating)

    @property
    def current(self) -> int:
        return self.points[-1][1] if self.points else 0

    @property
    def peak(self) -> int:
        return max((p[1] for p in self.points), default=0)

    @property
    def trend(self) -> int:
        if len(self.points) < 2:
            return 0
        return self.points[-1][1] - self.points[-2][1]


@dataclass
class UserStats:
    """Lichess user statistics by time control and variant."""
    chess_bullet: dict[str, int] = field(default_factory=dict)
    chess_blitz: dict[str, int] = field(default_factory=dict)
    chess_rapid: dict[str, int] = field(default_factory=dict)
    chess_classical: dict[str, int] = field(default_factory=dict)
    chess960: dict[str, int] = field(default_factory=dict)
    atomic: dict[str, int] = field(default_factory=dict)
    antichess: dict[str, int] = field(default_factory=dict)
    puzzles: dict[str, int] = field(default_factory=dict)

    @property
    def total_games(self) -> int:
        total = 0
        for v in (self.chess_bullet, self.chess_blitz, self.chess_rapid,
                  self.chess_classical, self.chess960, self.atomic, self.antichess):
            total += v.get("games", 0)
        return total

    @property
    def total_wins(self) -> int:
        return sum(v.get("win", 0) for v in (self.chess_bullet, self.chess_blitz,
                                              self.chess_rapid, self.chess_classical,
                                              self.chess960, self.atomic, self.antichess))


class LichessUsers:
    """Client for Lichess public user endpoints (no auth required for public data)."""

    def __init__(self, base_url: str = LICHESS_API) -> None:
        self._base = base_url

    def _request(self, endpoint: str) -> Any:
        url = f"{self._base}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def profile(self, username: str) -> UserProfile:
        """Get public profile by username."""
        data = self._request(f"/user/{username}")
        perfs = data.get("perfs", {})
        count = data.get("count", {})
        return UserProfile(
            id=data.get("id", ""),
            username=data.get("username", ""),
            title=data.get("title"),
            patron=data.get("patron", False),
            online=data.get("online", False),
            rating_blitz=perfs.get("blitz", {}).get("rating"),
            rating_bullet=perfs.get("bullet", {}).get("rating"),
            rating_rapid=perfs.get("rapid", {}).get("rating"),
            rating_classical=perfs.get("classical", {}).get("rating"),
            rating_correspondence=perfs.get("correspondence", {}).get("rating"),
            rating_puzzle=perfs.get("puzzle", {}).get("rating"),
            nb_games=count.get("all", 0),
            nb_wins=count.get("win", 0),
            nb_losses=count.get("loss", 0),
            nb_draws=count.get("draw", 0),
            created_at=data.get("createdAt", 0),
            seen_at=data.get("seenAt", 0),
        )

    def status(self, usernames: list[str]) -> list[dict[str, Any]]:
        """Get online status of up to 100 users."""
        ids = ",".join(usernames[:100])
        return self._request(f"/users/status?ids={ids}")

    def rating_history(self, username: str) -> list[RatingHistory]:
        """Get rating history (one entry per variant)."""
        data = self._request(f"/user/{username}/rating-history")
        histories: list[RatingHistory] = []
        for entry in data:
            points = [(p[0] + p[1] * 100, p[2]) for p in entry.get("points", [])]
            histories.append(RatingHistory(name=entry.get("name", "blitz"), points=points))
        return histories

    def stats(self, username: str) -> UserStats:
        """Get user statistics by variant."""
        data = self._request(f"/user/{username}/stats")
        return UserStats(
            chess_bullet=data.get("chess", {}).get("bullet", {}),
            chess_blitz=data.get("chess", {}).get("blitz", {}),
            chess_rapid=data.get("chess", {}).get("rapid", {}),
            chess_classical=data.get("chess", {}).get("classical", {}),
            chess960=data.get("chess960", {}),
            atomic=data.get("atomic", {}),
            antichess=data.get("antichess", {}),
            puzzles=data.get("puzzles", {}),
        )
