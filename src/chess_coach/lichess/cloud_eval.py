"""Lichess Cloud Evaluation.

Lichess maintains a database of ~320M pre-evaluated positions served
via /api/cloud-eval. When a position is cached, this is faster than
running a local engine.

Docs: https://lichess.org/api#tag/Analysis
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LICHESS_API = "https://lichess.org/api"
CLOUD_EVAL_URL = f"{LICHESS_API}/cloud-eval"


@dataclass
class CloudEvalResult:
    """A cached evaluation from Lichess's cloud-eval database."""
    fen: str = ""
    depth: int = 0
    knodes: int = 0  # thousands of nodes searched
    cp: int | None = None  # centipawns
    mate: int | None = None  # mate-in-N (positive = side-to-mate wins)
    pvs: list[dict[str, Any]] = None  # type: ignore[assignment]
    cached: bool = False

    def __post_init__(self) -> None:
        if self.pvs is None:
            self.pvs = []

    @property
    def eval_cp(self) -> int:
        """Centipawn evaluation (positive = side-to-mate better)."""
        if self.cp is not None:
            return self.cp
        if self.mate is not None and self.mate > 0:
            return 10000 - self.mate
        if self.mate is not None and self.mate < 0:
            return -10000 + self.mate
        return 0

    @property
    def best_move(self) -> str | None:
        """UCI of the best move, or None if not in pvs."""
        if self.pvs and "moves" in self.pvs[0]:
            moves_str = self.pvs[0].get("moves", "")
            if moves_str:
                return moves_str.split()[0]
        return None

    @property
    def is_mate(self) -> bool:
        return self.mate is not None and self.mate != 0

    @property
    def mate_in(self) -> int | None:
        return self.mate

    def to_dict(self) -> dict[str, Any]:
        return {
            "fen": self.fen,
            "depth": self.depth,
            "knodes": self.knodes,
            "cp": self.cp,
            "mate": self.mate,
            "pvs": self.pvs,
        }


class LichessCloudEval:
    """Cloud-eval client. Faster than local engine for cached positions."""

    def __init__(self, base_url: str = CLOUD_EVAL_URL) -> None:
        self._base = base_url

    def eval(self, fen: str, multi_pv: int = 1, variant: str = "standard") -> CloudEvalResult | None:
        """Look up evaluation for a FEN. Returns None if not in cache."""
        url = f"{self._base}?fen={quote(fen)}&multiPv={multi_pv}&variant={variant}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10.0) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.debug("Cloud eval lookup failed: %s", e)
            return None

        return CloudEvalResult(
            fen=data.get("fen", fen),
            depth=data.get("depth", 0),
            knodes=data.get("knodes", 0),
            cp=data.get("cp"),
            mate=data.get("mate"),
            pvs=data.get("pvs", []),
            cached=True,
        )
