"""Lichess FIDE player lookup.

FIDE ratings are now served by Lichess (since FIDE blocked the old sources).
Use this client to look up any FIDE-registered player.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"


@dataclass
class FidePlayer:
    """FIDE-registered chess player with current ratings."""
    id: str = ""
    name: str = ""
    federation: str = ""  # country code (IND, USA, etc.)
    standard: int | None = None
    rapid: int | None = None
    blitz: int | None = None
    classical: int | None = None
    year_of_birth: int | None = None
    title: str | None = None  # GM, IM, FM, etc.
    sex: str = ""  # M/F
    rating_history: dict[str, list[dict[str, int]]] = field(default_factory=dict)
    fetched_at: int = 0

    @property
    def display_name(self) -> str:
        return f"{self.title + ' ' if self.title else ''}{self.name}"

    @property
    def highest_rating(self) -> int:
        return max((r for r in (self.standard, self.rapid, self.blitz) if r is not None), default=0)

    @property
    def is_titled(self) -> bool:
        return self.title in ("GM", "IM", "FM", "CM", "WGM", "WIM", "WFM", "WCM")

    @property
    def age(self) -> int | None:
        if not self.year_of_birth:
            return None
        from datetime import datetime
        return datetime.now().year - self.year_of_birth


class LichessFide:
    """FIDE player lookup via Lichess."""

    def __init__(self, base_url: str = LICHESS_API) -> None:
        self._base = base_url

    def _request(self, endpoint: str) -> Any:
        url = f"{self._base}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def get(self, fide_id: str) -> FidePlayer:
        """Get a FIDE player by FIDE ID."""
        obj = self._request(f"/fide/player/{fide_id}")
        history: dict[str, list[dict[str, int]]] = {}
        for series in obj.get("history", []):
            name = series.get("name", "standard")
            history[name] = [
                {"year": h.get("year", 0), "rating": h.get("rating", 0), "games": h.get("games", 0)}
                for h in series.get("points", [])
            ]
        return FidePlayer(
            id=str(obj.get("id", "")),
            name=obj.get("name", ""),
            federation=obj.get("federation", ""),
            standard=obj.get("rating"),
            rapid=obj.get("rapid"),
            blitz=obj.get("blitz"),
            classical=obj.get("classical"),
            year_of_birth=obj.get("yearOfBirth"),
            title=obj.get("title"),
            sex=obj.get("sex", ""),
            rating_history=history,
        )

    def search(self, name: str, max_results: int = 10) -> list[FidePlayer]:
        """Search FIDE players by name (case-insensitive substring)."""
        url = f"{self._base}/fide?q={quote(name)}&max={max_results}"
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10.0) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        return [
            FidePlayer(
                id=str(p.get("id", "")),
                name=p.get("name", ""),
                federation=p.get("federation", ""),
                standard=p.get("rating"),
                rapid=p.get("rapid"),
                blitz=p.get("blitz"),
                title=p.get("title"),
            )
            for p in data
        ]
