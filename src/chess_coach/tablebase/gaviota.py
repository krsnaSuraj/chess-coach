"""Gaviota endgame tablebase probe (3-5 piece).

Gaviota uses 4-bit-per-piece compression and is faster than Syzygy for
3-4 piece positions on cold cache. Up to 5-piece files are ~150MB total.

Falls back to python-chess' built-in chess.gaviota if the files are present.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

GAVIOTA_DTZ_BLESSED_LOSS = -2
GAVIOTA_DTZ_DRAW = 0
GAVIOTA_DTZ_BLESSED_WIN_LOSS_OFFSET = 100  # distance-to-zero for win/loss


@dataclass
class GaviotaResult:
    """Result of a Gaviota tablebase probe."""
    fen: str
    dtz: int = 0  # distance to zero (moves until pawn move or capture)
    dtm: int = 0  # distance to mate
    wdl: int = 0  # -2 lost, -1 maybe lost, 0 draw, 1 maybe won, 2 won
    available: bool = False
    source: str = "gaviota"
    error: str | None = None

    @property
    def is_won(self) -> bool:
        return self.wdl == 2

    @property
    def is_lost(self) -> bool:
        return self.wdl == -2

    @property
    def is_draw(self) -> bool:
        return self.wdl == 0

    @property
    def outcome(self) -> str:
        if self.wdl == 2:
            return "win"
        if self.wdl == -2:
            return "loss"
        return "draw"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fen": self.fen,
            "dtz": self.dtz,
            "dtm": self.dtm,
            "wdl": self.wdl,
            "outcome": self.outcome,
            "available": self.available,
            "source": self.source,
        }


def empty_gaviota_result(fen: str) -> GaviotaResult:
    """Return a sentinel GaviotaResult for unavailable positions."""
    return GaviotaResult(fen=fen, available=False, source="none")


class GaviotaProbe:
    """Probe Gaviota 3-5 piece tablebases (local file-based).

    Uses python-chess' built-in chess.gaviota module when available.
    """

    def __init__(self, path: str | None = None) -> None:
        """Args:
        path: path to Gaviota directory (with .gtb.cp4/.gtb.cp5 files).
              If None, probes are unavailable.
        """
        self._path = path
        self._reader: Any = None
        self._try_open()

    def _try_open(self) -> None:
        if not self._path:
            return
        try:
            import chess.gaviota  # type: ignore
            self._reader = chess.gaviota.open_tablebase(self._path)
        except (ImportError, OSError) as e:
            logger.debug("Gaviota tablebase not available: %s", e)
            self._reader = None

    @property
    def available(self) -> bool:
        return self._reader is not None

    def probe_wdl(self, board: Any) -> GaviotaResult:
        """Probe WDL (Win/Draw/Loss) for a position."""
        fen = board.fen() if hasattr(board, "fen") else str(board)
        if not self.available:
            return empty_gaviota_result(fen)
        try:
            wdl = self._reader.probe_wdl(board)
            return GaviotaResult(
                fen=fen,
                wdl=wdl,
                available=True,
                source="gaviota",
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Gaviota WDL probe failed: %s", e)
            return GaviotaResult(fen=fen, available=False, error=str(e))

    def probe_dtz(self, board: Any) -> GaviotaResult:
        """Probe DTZ (Distance To Zero) for a position."""
        fen = board.fen() if hasattr(board, "fen") else str(board)
        if not self.available:
            return empty_gaviota_result(fen)
        try:
            dtz = self._reader.probe_dtz(board)
            wdl = self._reader.probe_wdl(board)
            return GaviotaResult(
                fen=fen,
                dtz=dtz,
                wdl=wdl,
                available=True,
                source="gaviota",
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Gaviota DTZ probe failed: %s", e)
            return GaviotaResult(fen=fen, available=False, error=str(e))

    def probe(self, board: Any) -> GaviotaResult:
        """Full probe (WDL + DTZ)."""
        fen = board.fen() if hasattr(board, "fen") else str(board)
        if not self.available:
            return empty_gaviota_result(fen)
        r = self.probe_dtz(board)
        r.fen = fen
        return r
