"""Lichess Opening Explorer client.

Three databases: Masters / Lichess (all rated games) / Player (specific user).
Free, public, no auth required (rate-limited).
Docs: https://lichess.org/api#tag/Opening-Explorer
"""

from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

EXPLORER_URL = "https://explorer.lichess.ORG"


class ExplorerSource(str, enum.Enum):
    MASTERS = "masters"
    LICHESS = "lichess"
    PLAYER = "player"


@dataclass
class MoveStats:
    """Win/draw/loss stats for a single move from a position."""
    uci: str
    san: str
    white_wins: int
    draws: int
    black_wins: int
    average_rating: int
    performance: int | None = None
    game_count: int = 0

    @property
    def total(self) -> int:
        return self.white_wins + self.draws + self.black_wins

    @property
    def white_winrate(self) -> float:
        return self.white_wins / self.total if self.total else 0.0

    @property
    def drawrate(self) -> float:
        return self.draws / self.total if self.total else 0.0

    @property
    def black_winrate(self) -> float:
        return self.black_wins / self.total if self.total else 0.0


@dataclass
class ExplorerResponse:
    fen: str
    moves: list[MoveStats] = field(default_factory=list)
    top_games: list[dict[str, Any]] = field(default_factory=list)
    source: ExplorerSource = ExplorerSource.LICHESS
    cached: bool = False

    def best_move(self) -> MoveStats | None:
        return max(self.moves, key=lambda m: m.total, default=None) if self.moves else None

    def best_by_winrate(self) -> MoveStats | None:
        if not self.moves:
            return None
        return max(self.moves, key=lambda m: m.white_wins / max(1, m.total))


class LichessExplorer:
    """Client for Lichess Opening Explorer API (3 sources)."""

    def __init__(self, cache: Any = None) -> None:
        self._cache = cache
        self._rate_limit_remaining = 20

    def query(
        self,
        fen: str,
        source: ExplorerSource = ExplorerSource.LICHESS,
        player: str | None = None,
        speeds: list[str] | None = None,
        ratings: list[int] | None = None,
        top_n: int = 12,
    ) -> ExplorerResponse:
        """Query the explorer for a position.

        Args:
            fen: FEN string.
            source: masters / lichess / player.
            player: required for source=player.
            speeds: filter by speed (bullet, blitz, rapid, classical).
            ratings: filter by rating range, e.g. [1000, 1200, 1400, 1600, 1800, 2000, 2200].
            top_n: number of top moves to return.
        """
        from chess_coach.lichess.cache import LichessCache  # late import to avoid cycle

        if self._cache is None:
            self._cache = LichessCache()
        if source == ExplorerSource.PLAYER and not player:
            raise ValueError("source=player requires player name")

        # Cache check
        cache_key = f"{source.value}:{player or '-'}:{fen}:{','.join(map(str, ratings or []))}"
        cached_resp = self._cache.get(cache_key)
        if cached_resp is not None:
            cached_resp.cached = True
            return cached_resp

        params = [f"fen={quote(fen)}", f"topGames=0", f"moves={top_n}"]
        if speeds:
            for s in speeds:
                params.append(f"speeds[]={quote(s)}")
        if ratings:
            for r in ratings:
                params.append(f"ratings[]={r}")

        variant = "standard"
        url = f"{EXPLORER_URL}/{variant}?{'&'.join(params)}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10.0) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
                self._rate_limit_remaining = int(
                    resp.headers.get("X-RateLimit-Remaining", "20")
                )
        except Exception as e:  # noqa: BLE001
            logger.debug("Lichess explorer query failed: %s", e)
            return ExplorerResponse(fen=fen, source=source)

        moves: list[MoveStats] = []
        for m in data.get("moves", []):
            white = int(m.get("white", 0))
            draws = int(m.get("draws", 0))
            black = int(m.get("black", 0))
            game = m.get("game", "")
            moves.append(MoveStats(
                uci=m.get("uci", ""),
                san=m.get("san", ""),
                white_wins=white,
                draws=draws,
                black_wins=black,
                average_rating=int(m.get("averageRating", 1500)),
                game_count=white + draws + black,
            ))

        resp = ExplorerResponse(
            fen=fen,
            moves=sorted(moves, key=lambda x: -x.total)[:top_n],
            source=source,
        )
        # Cache for 3 days (per Lichess TOS)
        self._cache.set(cache_key, resp, ttl_s=3 * 24 * 3600)
        return resp
