"""Lichess Op1 - Partial 8-piece tablebase (released 2026-02-07).

Available at https://tablebase.lichess.ovh and the analysis board.
Covers a large subset of practical 8-piece positions.
63 TiB total download size.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_8P_URL = "https://tablebase.lichess.ovh"
OP1_MAX_PIECES = 8
OP1_PIECE_COUNTS = (3, 4, 5, 6, 7, 8)


@dataclass
class Op1Result:
    """Lichess 8-piece probe result."""
    fen: str
    category: str = "unknown"
    dtz: int | None = None
    dtm: int | None = None
    available: bool = False
    source: str = "lichess-op1"
    moves: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.moves is None:
            self.moves = []

    @property
    def is_won(self) -> bool:
        return "win" in self.category

    @property
    def is_lost(self) -> bool:
        return "loss" in self.category

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


class Lichess8pProbe:
    """Probe Lichess Op1 8-piece tablebase via the tablebase API.

    Note: As of 2026-02-07, the API only covers a large subset of
    practical 8-piece positions (not all). For positions not in the
    database, the API returns a 404 and we return available=False.
    """

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def probe(self, fen: str) -> Op1Result:
        """Probe an 8-piece position via the Lichess Op1 tablebase."""
        url = f"{LICHESS_8P_URL}/standard?fen={quote(fen)}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.debug("Lichess 8p probe failed: %s", e)
            return Op1Result(fen=fen, available=False, source="error")

        moves = data.get("moves", [])
        return Op1Result(
            fen=fen,
            category=data.get("category", "unknown"),
            dtz=data.get("dtz"),
            dtm=data.get("dtm"),
            available=True,
            moves=[{
                "uci": m.get("uci", ""),
                "san": m.get("san", ""),
                "category": m.get("category", "unknown"),
            } for m in moves],
        )

    def best_move(self, fen: str) -> dict[str, Any] | None:
        """Return the best move, or None if drawn / unavailable."""
        r = self.probe(fen)
        if not r.available or r.is_draw or not r.moves:
            return None
        return r.moves[0] if r.moves else None
