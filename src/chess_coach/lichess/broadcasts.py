"""Lichess Broadcasts - real-time tournament broadcasting (Lichess-style).

Broadcasts are the Lichess way of streaming elite tournaments (Tata Steel,
Norway Chess, etc.) with commentary, multiple rounds, and PGN updates.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


@dataclass
class BroadcastPlayer:
    """A player in a broadcast round."""
    name: str = ""
    fide_id: str | None = None
    rating: int | None = None
    title: str | None = None
    country: str | None = None
    score: float = 0.0
    rank: int = 0


@dataclass
class BroadcastRound:
    """A round in a broadcast tournament."""
    id: str = ""
    name: str = ""
    status: str = "created"  # created/started/finished
    starts_at: int = 0
    finishes_at: int = 0
    games: list[dict[str, Any]] = field(default_factory=list)
    url: str = ""


@dataclass
class Broadcast:
    """A Lichess broadcast - a real-time commentary on a chess tournament."""
    id: str = ""
    name: str = ""
    description: str = ""
    tour: str | None = None
    format: str = "round-robin"
    location: str = ""
    country: str | None = None
    timezone: str = "UTC"
    starts_at: int = 0
    finishes_at: int = 0
    status: str = "created"
    rounds: list[BroadcastRound] = field(default_factory=list)
    players: list[BroadcastPlayer] = field(default_factory=list)
    url: str = ""
    image: str = ""
    pgn: str = ""

    @property
    def current_round(self) -> BroadcastRound | None:
        for r in self.rounds:
            if r.status == "started":
                return r
        return None

    @property
    def is_live(self) -> bool:
        return any(r.status == "started" for r in self.rounds)


class LichessBroadcasts:
    """Client for broadcast endpoints. Public reads; writes require scope: 'broadcast:write'."""

    def __init__(self, token: str | None = None, base_url: str = LICHESS_API) -> None:
        self._token = token
        self._base = base_url

    def _request(self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{endpoint}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        body = urlencode(data).encode() if data else None
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def list_active(self, nb: int = 20) -> list[Broadcast]:
        """List currently active broadcasts."""
        obj = self._request(f"/broadcast?nb={nb}&status=active")
        return [self._to_broadcast(b) for b in obj]

    def list_all(self, nb: int = 50) -> list[Broadcast]:
        """List all broadcasts (newest first)."""
        obj = self._request(f"/broadcast?nb={nb}")
        return [self._to_broadcast(b) for b in obj]

    def get(self, broadcast_id: str) -> Broadcast:
        """Get a specific broadcast with rounds."""
        obj = self._request(f"/broadcast/{broadcast_id}.json")
        return self._to_broadcast(obj, with_rounds=True)

    def get_round_pgn(self, round_id: str) -> str:
        """Get all games PGN from a round."""
        url = f"{self._base}/broadcast/round/{round_id}.pgn"
        req = Request(url)
        with urlopen(req, timeout=15.0) as resp:  # noqa: S310
            return resp.read().decode("utf-8")

    def push_pgn(self, round_id: str, pgn: str) -> bool:
        """Push PGN update to a round. Requires OAuth scope: 'broadcast:write'."""
        if not self._token:
            raise PermissionError("Push PGN requires authentication")
        url = f"{self._base}/broadcast/round/{round_id}/push"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/x-www-form-urlencoded"}
        req = Request(url, data=urlencode({"pgn": pgn}).encode(), headers=headers, method="POST")
        with urlopen(req, timeout=10.0):  # noqa: S310
            return True
        return True

    def _to_broadcast(self, obj: dict[str, Any], with_rounds: bool = False) -> Broadcast:
        rounds: list[BroadcastRound] = []
        if with_rounds and "rounds" in obj:
            for r in obj["rounds"]:
                rounds.append(BroadcastRound(
                    id=r.get("id", ""),
                    name=r.get("name", ""),
                    status=r.get("status", "created"),
                    starts_at=r.get("startsAt", 0),
                    finishes_at=r.get("finishesAt", 0),
                    url=r.get("url", ""),
                ))
        players: list[BroadcastPlayer] = []
        for p in obj.get("players", []):
            players.append(BroadcastPlayer(
                name=p.get("name", ""),
                fide_id=p.get("fideId"),
                rating=p.get("rating"),
                title=p.get("title"),
                country=p.get("country"),
                score=p.get("score", 0.0),
                rank=p.get("rank", 0),
            ))
        return Broadcast(
            id=obj.get("id", ""),
            name=obj.get("name", ""),
            description=obj.get("description", ""),
            tour=obj.get("tour"),
            format=obj.get("format", "round-robin"),
            location=obj.get("location", ""),
            country=obj.get("country"),
            timezone=obj.get("timezone", "UTC"),
            starts_at=obj.get("startsAt", 0),
            finishes_at=obj.get("finishesAt", 0),
            status=obj.get("status", "created"),
            rounds=rounds,
            players=players,
            url=obj.get("url", ""),
            image=obj.get("image", ""),
        )
