"""Lichess Simuls (simultaneous exhibitions) and TV channels.

A simul is when a strong player plays many opponents at once.
TV channels show the best live games on Lichess.
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
class Simul:
    """A simultaneous exhibition."""
    id: str = ""
    name: str = ""
    host: str = ""
    created_at: int = 0
    started_at: int = 0
    finished_at: int | None = None
    nb_players: int = 0
    nb_finished: int = 0
    nb_wins: int = 0
    nb_losses: int = 0
    nb_draws: int = 0
    variants: list[dict[str, Any]] = field(default_factory=list)
    time_control: dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    url: str = ""

    @property
    def is_live(self) -> bool:
        return self.status == "started"

    @property
    def is_finished(self) -> bool:
        return self.status == "finished"

    @property
    def progress_pct(self) -> float:
        if self.nb_players == 0:
            return 0.0
        return self.nb_finished / self.nb_players * 100

    @property
    def host_score(self) -> int:
        return self.nb_wins + (self.nb_draws // 2)


@dataclass
class TVChannel:
    """A Lichess TV channel showing live games."""
    name: str = ""  # best/bullet/blitz/rapid/classical/atom/antichess/chess960/kingofthehill/3check/horde/racing/ultraBullet
    title: str = ""
    game_id: str = ""
    fen: str = ""
    white: dict[str, Any] = field(default_factory=dict)
    black: dict[str, Any] = field(default_factory=dict)
    last_move: str = ""
    clocks: dict[str, int] = field(default_factory=dict)
    is_finished: bool = False
    url: str = ""


class LichessSimuls:
    """Client for simuls endpoints."""

    def __init__(self, base_url: str = LICHESS_API) -> None:
        self._base = base_url

    def _request(self, endpoint: str) -> Any:
        url = f"{self._base}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def list_active(self, nb: int = 20) -> list[Simul]:
        """List currently active simuls."""
        obj = self._request(f"/simul?nb={nb}&status=active")
        return [self._to_simul(s) for s in obj]

    def get(self, simul_id: str) -> Simul:
        obj = self._request(f"/simul/{simul_id}")
        return self._to_simul(obj)

    def _to_simul(self, obj: dict[str, Any]) -> Simul:
        return Simul(
            id=obj.get("id", ""),
            name=obj.get("name", ""),
            host=obj.get("host", {}).get("name", "") if isinstance(obj.get("host"), dict) else obj.get("host", ""),
            created_at=obj.get("createdAt", 0),
            started_at=obj.get("startedAt", 0),
            finished_at=obj.get("finishedAt"),
            nb_players=obj.get("nbPlayers", 0),
            nb_finished=obj.get("nbFinished", 0),
            nb_wins=obj.get("wins", 0),
            nb_losses=obj.get("losses", 0),
            nb_draws=obj.get("draws", 0),
            variants=obj.get("variants", []),
            time_control=obj.get("clock", {}),
            status=obj.get("status", "created"),
            url=obj.get("url", ""),
        )


class LichessTV:
    """Client for Lichess TV channels."""

    CHANNELS = (
        "best", "bullet", "blitz", "rapid", "classical", "ultraBullet",
        "atom", "antichess", "chess960", "kingOfTheHill", "threeCheck",
        "horde", "racingKings", "crazyhouse",
    )

    def __init__(self, base_url: str = LICHESS_API) -> None:
        self._base = base_url

    def _request(self, endpoint: str) -> Any:
        url = f"{self._base}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def get_channel(self, channel: str = "best") -> TVChannel:
        """Get the current game on a TV channel.

        Channels: best, bullet, blitz, rapid, classical, ultraBullet,
        atom, antichess, chess960, kingOfTheHill, threeCheck, horde,
        racingKings, crazyhouse.
        """
        if channel not in self.CHANNELS:
            raise ValueError(f"Unknown channel: {channel}. Valid: {self.CHANNELS}")
        obj = self._request(f"/tv/{channel}")
        return TVChannel(
            name=channel,
            title=obj.get("title", ""),
            game_id=obj.get("game", {}).get("id", ""),
            fen=obj.get("fen", ""),
            white=obj.get("player", {}).get("color", "white"),
            black={},
            last_move=obj.get("lastMove", ""),
            is_finished=False,
            url=obj.get("url", ""),
        )
