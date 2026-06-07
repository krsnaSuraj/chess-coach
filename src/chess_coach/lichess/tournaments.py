"""Lichess Tournaments API.

Endpoints:
- POST /api/tournament - create Arena tournament
- POST /api/swiss/new - create Swiss tournament
- GET /api/tournament/{id} - get info
- GET /api/tournament/{id}/games - export games (NDJSON)
- GET /api/tournament/{id}/results - results
- GET /api/tournament/{id}/teams - teams
- POST /api/tournament/{id}/join - join (with token)
- POST /api/tournament/{id}/withdraw - withdraw
"""
from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


class TournamentState(str, enum.Enum):
    CREATED = "created"
    STARTED = "started"
    FINISHED = "finished"


@dataclass
class ArenaTournament:
    """Arena (single-elimination) tournament info."""
    id: str = ""
    created_by: str = ""
    system: str = "arena"  # always arena
    name: str = ""
    full_name: str = ""
    description: str = ""
    clock: dict[str, Any] = field(default_factory=dict)
    minutes: int = 0
    variant: str = "standard"
    rated: bool = True
    nb_players: int = 0
    nb_games: int = 0
    status: str = "created"  # created/started/finished
    starts_at: int = 0
    finishes_at: int = 0
    winner: dict[str, Any] | None = None
    podium: list[dict[str, Any]] = field(default_factory=list)
    pairings: list[dict[str, Any]] = field(default_factory=list)
    standings: list[dict[str, Any]] = field(default_factory=list)
    quote: str = ""
    url: str = ""

    @property
    def initial_minutes(self) -> int:
        return self.clock.get("limit", 0) // 60 if self.clock else self.minutes

    @property
    def increment(self) -> int:
        return self.clock.get("increment", 0) if self.clock else 0

    @property
    def is_started(self) -> bool:
        return self.status == "started"

    @property
    def is_finished(self) -> bool:
        return self.status == "finished"


@dataclass
class SwissTournament:
    """Swiss-format tournament info."""
    id: str = ""
    name: str = ""
    nb_players: int = 0
    nb_rounds: int = 0
    current_round: int = 0
    status: str = "created"
    starts_at: int = 0
    finishes_at: int = 0
    clock: dict[str, Any] = field(default_factory=dict)
    round_games: list[dict[str, Any]] = field(default_factory=list)
    standings: list[dict[str, Any]] = field(default_factory=list)
    url: str = ""

    @property
    def rounds_remaining(self) -> int:
        return max(0, self.nb_rounds - self.current_round)

    @property
    def progress_pct(self) -> float:
        if self.nb_rounds == 0:
            return 0.0
        return self.current_round / self.nb_rounds * 100


class LichessTournaments:
    """Client for Lichess tournament endpoints. Requires OAuth scope: 'tournament:write' for create."""

    def __init__(self, token: str, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None,
                 stream: bool = False) -> Any:
        url = f"{self._base}{endpoint}"
        headers = {"Authorization": f"Bearer {self._token}",
                   "Accept": "application/x-ndjson" if stream else "application/json"}
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        if stream:
            return urlopen(req, timeout=None)  # noqa: S310
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def create_arena(self, name: str, time_minutes: int = 10, increment: int = 0,
                     minutes: int = 60, variant: str = "standard", rated: bool = True,
                     description: str = "") -> ArenaTournament:
        """Create an Arena tournament."""
        data: dict[str, Any] = {
            "name": name,
            "clockTime": time_minutes,
            "clockIncrement": increment,
            "minutes": minutes,
            "variant": variant,
            "rated": "true" if rated else "false",
            "description": description,
        }
        obj = self._request("/tournament", method="POST", data=data)
        return self._to_arena(obj)

    def create_swiss(self, name: str, time_minutes: int = 10, increment: int = 0,
                     nb_rounds: int = 7, rated: bool = True,
                     team_id: str | None = None) -> SwissTournament:
        """Create a Swiss tournament."""
        data: dict[str, Any] = {
            "name": name,
            "clock.limit": time_minutes * 60,
            "clock.increment": increment,
            "nbRounds": nb_rounds,
            "rated": "true" if rated else "false",
        }
        if team_id:
            data["teamId"] = team_id
        obj = self._request("/swiss/new", method="POST", data=data)
        return self._to_swiss(obj)

    def get_arena(self, tournament_id: str, page: int = 1) -> ArenaTournament:
        obj = self._request(f"/tournament/{tournament_id}?page={page}")
        return self._to_arena(obj)

    def get_swiss(self, tournament_id: str) -> SwissTournament:
        obj = self._request(f"/swiss/{tournament_id}")
        return self._to_swiss(obj)

    def results(self, tournament_id: str, nb: int = 100) -> list[dict[str, Any]]:
        return self._request(f"/tournament/{tournament_id}/results?nb={nb}")

    def join(self, tournament_id: str, password: str | None = None) -> bool:
        data: dict[str, Any] = {}
        if password:
            data["password"] = password
        self._request(f"/tournament/{tournament_id}/join", method="POST", data=data)
        return True

    def withdraw(self, tournament_id: str) -> bool:
        self._request(f"/tournament/{tournament_id}/withdraw", method="POST")
        return True

    def _to_arena(self, obj: dict[str, Any]) -> ArenaTournament:
        return ArenaTournament(
            id=obj.get("id", ""),
            created_by=obj.get("createdBy", ""),
            system=obj.get("system", "arena"),
            name=obj.get("name", ""),
            full_name=obj.get("fullName", ""),
            description=obj.get("description", ""),
            clock=obj.get("clock", {}),
            minutes=obj.get("minutes", 0),
            variant=obj.get("variant", "standard"),
            rated=obj.get("rated", True),
            nb_players=obj.get("nbPlayers", 0),
            nb_games=obj.get("nbGames", 0),
            status=obj.get("status", "created"),
            starts_at=obj.get("startsAt", 0),
            finishes_at=obj.get("finishesAt", 0),
            winner=obj.get("winner"),
            podium=obj.get("podium", []),
            pairings=obj.get("pairings", []),
            standings=obj.get("standings", []),
            quote=obj.get("quote", ""),
            url=obj.get("url", ""),
        )

    def _to_swiss(self, obj: dict[str, Any]) -> SwissTournament:
        return SwissTournament(
            id=obj.get("id", ""),
            name=obj.get("name", ""),
            nb_players=obj.get("nbPlayers", 0),
            nb_rounds=obj.get("nbRounds", 0),
            current_round=obj.get("round", 0),
            status=obj.get("status", "created"),
            starts_at=obj.get("startsAt", 0),
            finishes_at=obj.get("finishesAt", 0),
            clock=obj.get("clock", {}),
            round_games=obj.get("games", []),
            standings=obj.get("rankings", []),
            url=obj.get("url", ""),
        )
