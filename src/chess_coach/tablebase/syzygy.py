"""Syzygy tablebase wrapper.

Uses python-chess's built-in `chess.syzygy` for local tablebase lookups.
Falls back to Lichess Tablebase API for 7-piece positions.

API surface:
  SyzygyProbe(path=None).probe(board) -> TablebaseResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# python-chess WDL codes
WDL_WIN = 2
WDL_CURSED_WIN = 1
WDL_DRAW = 0
WDL_BLESSED_LOSS = -1
WDL_LOSS = -2
WDL_UNKNOWN = -3  # not in tablebase

WDL_NAMES = {
    WDL_WIN: "win",
    WDL_CURSED_WIN: "cursed-win",
    WDL_DRAW: "draw",
    WDL_BLESSED_LOSS: "blessed-loss",
    WDL_LOSS: "loss",
}


@dataclass(frozen=True)
class TablebaseResult:
    wdl: int  # one of WDL_*
    dtz: int | None  # distance to zeroing (plies), None if unknown
    category: str  # human readable: win/cursed-win/draw/blessed-loss/loss
    moves: list[tuple[str, int, int]]  # (san, wdl, dtz) for each legal move
    source: str  # "local" or "lichess-api"

    @property
    def winrate(self) -> float:
        return {
            WDL_WIN: 1.0,
            WDL_CURSED_WIN: 0.95,
            WDL_DRAW: 0.5,
            WDL_BLESSED_LOSS: 0.05,
            WDL_LOSS: 0.0,
        }.get(self.wdl, 0.5)


class SyzygyProbe:
    """Local Syzygy probe with Lichess API fallback."""

    def __init__(self, path: str | None = None, api_endpoint: str | None = None) -> None:
        self._path = Path(path) if path else None
        self._api_endpoint = api_endpoint or "https://tablebase.lichess.ovh"
        self._tablebase: Any = None
        self._open()

    def _open(self) -> None:
        if self._path and self._path.exists():
            try:
                import chess.syzygy  # type: ignore

                self._tablebase = chess.syzygy.open_tablebase(str(self._path))
                logger.info("Syzygy tablebase opened at %s", self._path)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to open local Syzygy: %s", e)
                self._tablebase = None

    def is_available(self) -> bool:
        return self._tablebase is not None

    def probe(self, board: Any) -> TablebaseResult:
        """Probe WDL + DTZ for the given board position."""
        if self._tablebase is not None and self._fits(board):
            return self._probe_local(board)
        # Try Lichess API fallback
        return self._probe_lichess_api(board)

    def _fits(self, board: Any) -> bool:
        # Tablebases support up to N pieces
        return len(board.piece_map()) <= 7

    def _probe_local(self, board: Any) -> TablebaseResult:
        try:
            wdl = self._tablebase.probe_wdl(board)
        except Exception:  # noqa: BLE001
            wdl = WDL_UNKNOWN
        dtz: int | None
        try:
            dtz = self._tablebase.probe_dtz(board)
            dtz = int(dtz) if dtz is not None else None
        except Exception:  # noqa: BLE001
            dtz = None
        category = WDL_NAMES.get(wdl, "unknown")
        moves: list[tuple[str, int, int]] = []
        for move in board.legal_moves:
            board.push(move)
            try:
                m_wdl = self._tablebase.probe_wdl(board)
                m_dtz = self._tablebase.probe_dtz(board)
            except Exception:  # noqa: BLE001
                m_wdl, m_dtz = WDL_UNKNOWN, None
            board.pop()

            san = board.san(move)
            moves.append((san, m_wdl, int(m_dtz) if m_dtz is not None else 0))
        return TablebaseResult(
            wdl=wdl, dtz=dtz, category=category, moves=moves, source="local"
        )

    def _probe_lichess_api(self, board: Any) -> TablebaseResult:
        """Remote probe via Lichess Tablebase API. Returns 'unknown' on failure."""
        import json
        from urllib.parse import quote
        from urllib.request import Request, urlopen

        fen = board.fen()
        url = f"{self._api_endpoint}/standard?fen={quote(fen)}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=5.0) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.debug("Lichess API probe failed: %s", e)
            return TablebaseResult(
                wdl=WDL_UNKNOWN, dtz=None, category="unknown", moves=[], source="lichess-api"
            )

        # Lichess API response shape: { "wdl": "win", "dtz": 5, "moves": [{...}] }
        wdl_str = data.get("wdl", "unknown")
        wdl_map = {
            "win": WDL_WIN,
            "cursed-win": WDL_CURSED_WIN,
            "draw": WDL_DRAW,
            "blessed-loss": WDL_BLESSED_LOSS,
            "loss": WDL_LOSS,
            "unknown": WDL_UNKNOWN,
        }
        wdl = wdl_map.get(wdl_str, WDL_UNKNOWN)
        dtz = data.get("dtz")
        moves: list[tuple[str, int, int]] = []
        for mv in data.get("moves", []):
            san = mv.get("san", "")
            mv_wdl = wdl_map.get(mv.get("wdl", "unknown"), WDL_UNKNOWN)
            mv_dtz = mv.get("dtz", 0) or 0
            moves.append((san, mv_wdl, mv_dtz))
        return TablebaseResult(
            wdl=wdl, dtz=dtz, category=wdl_str, moves=moves, source="lichess-api"
        )


def empty_tablebase_result() -> TablebaseResult:
    """Sentinel for positions with no tablebase (e.g. > 7 pieces)."""
    return TablebaseResult(
        wdl=WDL_UNKNOWN, dtz=None, category="unknown", moves=[], source="none"
    )
