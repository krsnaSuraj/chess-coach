"""Lomonosov 7-piece tablebase probe (Lichess API).

The Lomonosov tablebases cover 7-piece positions and are served via
the Lichess tablebase subdomain (separate from Syzygy).

API: https://tablebase.lichess.ovh/{variant}?fen=...
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LOMONOSOV_URL = "https://tablebase.lichess.ovh"


@dataclass
class LomonosovResult:
    """Lomonosov 7-piece probe result."""
    fen: str
    category: str = "unknown"  # win/loss/draw/cursed-win/blessed-loss
    dtz: int | None = None
    dtm: int | None = None
    precise_dtm: int | None = None
    dtm_to_mate_in_n: int | None = None
    available: bool = False
    source: str = "lichess-lomonosov"
    moves: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.moves is None:
            self.moves = []

    @property
    def is_won(self) -> bool:
        return self.category in ("win", "cursed-win", "maybe-win")

    @property
    def is_lost(self) -> bool:
        return self.category in ("loss", "blessed-loss", "maybe-loss")

    @property
    def is_draw(self) -> bool:
        return self.category == "draw"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fen": self.fen,
            "category": self.category,
            "dtz": self.dtz,
            "dtm": self.dtm,
            "available": self.available,
            "moves": self.moves,
        }


class LomonosovProbe:
    """Probe Lichess's Lomonosov 7-piece tablebase API."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def probe(self, fen: str) -> LomonosovResult:
        """Probe a 7-piece position via the Lichess API.

        Returns a LomonosovResult with category, dtz, dtm, and best moves.
        Falls back gracefully if the API is unreachable.
        """
        url = f"{LOMONOSOV_URL}/standard?fen={quote(fen)}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.debug("Lomonosov probe failed: %s", e)
            return LomonosovResult(fen=fen, available=False, source="error")

        category = data.get("category", "unknown")
        moves_raw = data.get("moves", [])
        moves: list[dict[str, Any]] = []
        for m in moves_raw:
            moves.append({
                "uci": m.get("uci", ""),
                "san": m.get("san", ""),
                "category": m.get("category", "unknown"),
                "dtz": m.get("dtz"),
                "dtm": m.get("dtm"),
            })

        dtz = data.get("dtz")
        dtm = data.get("dtm")
        return LomonosovResult(
            fen=fen,
            category=category,
            dtz=int(dtz) if dtz is not None else None,
            dtm=int(dtm) if dtm is not None else None,
            available=True,
            moves=moves,
        )

    def best_move(self, fen: str) -> dict[str, Any] | None:
        """Return the best move dict, or None if position is drawn or API fails."""
        r = self.probe(fen)
        if not r.available or r.is_draw or not r.moves:
            return None
        # First move is best
        return r.moves[0] if r.moves else None
