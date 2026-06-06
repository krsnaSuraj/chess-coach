"""Lichess game sync (auto-import your games).

SOTA 2026: NDJSON stream of your last N games, with optional PGN.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class GameSummary:
    """A summarized Lichess game."""
    id: str
    pgn: str
    rated: bool
    speed: str  # bullet, blitz, rapid, classical, correspondence
    perf: str  # "blitz", "rapid", etc.
    created_at: int
    last_move_at: int
    status: str
    players: dict[str, str] = field(default_factory=dict)  # {"white": "user1", "black": "user2"}
    winner: str | None = None  # "white" | "black" | None
    opening: dict[str, Any] = field(default_factory=dict)  # {eco, name, ply}
    moves: str = ""  # SAN moves
    clock: str = ""  # initial clock
    increment: int = 0


class GameSync:
    """Sync games from Lichess (NDJSON stream)."""

    def __init__(self, oauth_token: str | None = None) -> None:
        self._token = oauth_token

    def stream_user_games(
        self,
        user: str,
        max_games: int = 50,
        rated_only: bool = True,
        with_pgn: bool = True,
    ) -> Iterator[GameSummary]:
        """Stream user games from Lichess (NDJSON)."""
        if not self._token:
            return
        url = (
            f"https://lichess.org/api/games/user/{user}"
            f"?max={max_games}&rated={str(rated_only).lower()}"
            f"&pgn={str(with_pgn).lower()}&clocks=true&evals=false&opening=true&literate=false"
        )
        try:
            req = Request(
                url,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/x-ndjson"},
            )
            with urlopen(req, timeout=30.0) as resp:  # noqa: S310
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield self._parse_game(data)
                    if max_games and len([1]) >= max_games:
                        return
        except Exception as e:  # noqa: BLE001
            logger.debug("Game sync stream failed: %s", e)

    def list_recent(self, user: str, n: int = 10) -> list[GameSummary]:
        """Fetch last N games (returns list, not iterator)."""
        return list(self.stream_user_games(user, max_games=n, with_pgn=False))[:n]

    def _parse_game(self, data: dict[str, Any]) -> GameSummary:
        players = data.get("players", {})
        white = players.get("white", {}).get("user", {}).get("name", "?")
        black = players.get("black", {}).get("user", {}).get("name", "?")
        winner: str | None = data.get("winner")
        if winner and winner not in ("white", "black"):
            winner = None
        clock = data.get("clock", {})
        return GameSummary(
            id=data.get("id", ""),
            pgn=data.get("pgn", ""),
            rated=data.get("rated", False),
            speed=data.get("speed", "blitz"),
            perf=data.get("perf", "blitz"),
            created_at=int(data.get("createdAt", 0)),
            last_move_at=int(data.get("lastMoveAt", 0)),
            status=data.get("status", "?"),
            players={"white": white, "black": black},
            winner=winner,
            opening=data.get("opening", {}),
            moves=data.get("moves", ""),
            clock=f"{clock.get('limit', 0)}s+{clock.get('increment', 0)}s",
            increment=int(clock.get("increment", 0)),
        )
