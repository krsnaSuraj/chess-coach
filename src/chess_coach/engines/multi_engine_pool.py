"""Multi-engine pool: aggregate evals from many engines in parallel.

This is the SOTA-2026 way to do analysis (used by Lichess, Chessify, etc.):
run 9+ engines in parallel and combine their top PVs with weighted scores.

Aggregation strategy:
  - Each engine produces its own MultiPV lines
  - Pool returns ALL unique PVs sorted by aggregate weight
  - Weight = 1.0 by default, can be set per-engine (e.g. SF=1.0, Maia=0.5)
  - Threads run engines concurrently, each in its own subprocess
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass

from chess_coach.engines.base import Engine, Evaluation

logger = logging.getLogger(__name__)


@dataclass
class EngineWeight:
    engine: Engine
    weight: float = 1.0
    enabled: bool = True
    timeout_s: float = 30.0


class MultiEnginePool:
    """Parallel pool of chess engines. Aggregates top PV lines from all of them."""

    def __init__(self, weights: list[EngineWeight] | None = None) -> None:
        self._weights: list[EngineWeight] = weights or []
        self._started: set[int] = set()

    def add(self, engine: Engine, weight: float = 1.0, timeout_s: float = 30.0) -> None:
        self._weights.append(EngineWeight(engine=engine, weight=weight, timeout_s=timeout_s))

    def engines(self) -> list[Engine]:
        return [w.engine for w in self._weights if w.enabled]

    def start_all(self) -> None:
        for w in self._weights:
            if not w.enabled or w.engine in [e for e in self.engines() if id(e) in self._started]:
                continue
            try:
                w.engine.start()
                self._started.add(id(w.engine))
            except Exception as e:  # noqa: BLE001
                logger.warning("Engine %s failed to start: %s", w.engine.info().name, e)
                w.enabled = False

    def stop_all(self) -> None:
        for w in self._weights:
            try:
                w.engine.stop()
            except Exception:  # noqa: BLE001
                pass
        self._started.clear()

    def evaluate(self, fen: str, depth: int = 18, multipv: int = 3) -> list[Evaluation]:
        """Run all engines in parallel and aggregate their PVs."""
        if not any(w.enabled for w in self._weights):
            return []
        # Lazy start
        self.start_all()

        evals: list[Evaluation] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self._weights)) as ex:
            futures = {
                ex.submit(self._safe_eval, w, fen, depth, multipv): w
                for w in self._weights
                if w.enabled
            }
            for fut in concurrent.futures.as_completed(futures, timeout=60):
                w = futures[fut]
                try:
                    ev = fut.result(timeout=w.timeout_s)
                    if ev is not None:
                        evals.append(ev)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Engine %s failed: %s", w.engine.info().name, e)
                    # Mark broken engine as disabled (in-place, not via _weights copy)
                    for ww in self._weights:
                        if ww is w:
                            ww.enabled = False
                            break

        return self._aggregate(evals, multipv)

    def _safe_eval(self, w: EngineWeight, fen: str, depth: int, multipv: int) -> Evaluation | None:
        try:
            return w.engine.evaluate(fen, depth=depth, multipv=multipv)
        except Exception as e:  # noqa: BLE001
            logger.warning("Engine %s evaluation failed: %s", w.engine.info().name, e)
            # Disable the broken engine
            w.enabled = False
            return None

    def _aggregate(self, evals: list[Evaluation], multipv: int) -> list[Evaluation]:
        """Sort and de-dup PVs by aggregate weight."""
        if not evals:
            return []

        # Build a dict: pv_signature -> (engine, score, weight, multipv_lines)
        all_lines: list[dict] = []
        for ev in evals:
            engine_weight = next(
                (w.weight for w in self._weights if w.engine.info().name in ev.source_engine),
                1.0,
            )
            if not ev.multipv:
                all_lines.append({
                    "engine": ev.source_engine,
                    "cp": ev.score_cp,
                    "mate": ev.mate,
                    "pv": ev.pv,
                    "weight": engine_weight,
                })
            else:
                for line in ev.multipv:
                    all_lines.append({
                        "engine": ev.source_engine,
                        "cp": ev.score_cp,
                        "mate": ev.mate,
                        "pv": line.get("pv", []),
                        "prob": line.get("prob", 1.0),
                        "weight": engine_weight,
                    })

        # Sort by (weight desc, cp desc)
        def sort_key(line: dict) -> tuple[float, int, int]:
            cp = line.get("cp", 0) or 0
            mate = line.get("mate")
            if mate is not None:
                cp = 100000 if mate > 0 else -100000
            return (-line.get("weight", 1.0), -cp, 0)

        all_lines.sort(key=sort_key)
        # Dedupe by PV tuple
        seen: set = set()
        unique: list[dict] = []
        for line in all_lines:
            sig = tuple(line.get("pv", []))
            if sig and sig not in seen:
                seen.add(sig)
                unique.append(line)
            if len(unique) >= multipv * 2:
                break

        # Convert to Evaluation list
        out: list[Evaluation] = []
        for i, line in enumerate(unique[:multipv]):
            out.append(Evaluation(
                score_cp=line.get("cp", 0) or 0,
                mate=line.get("mate"),
                depth=0,
                pv=line.get("pv", []),
                source_engine=f"Pool[{line.get('engine', '?')}]",
                multipv=[{"multipv": i + 1, "move": (line.get("pv") or [""])[0],
                         "weight": line.get("weight", 1.0)}],
            ))
        return out


def make_default_pool() -> MultiEnginePool:
    """Default SOTA 2026 pool: SF18 + Maia-2. Add more via add()."""
    from chess_coach.engines.maia2 import make_maia2_heuristic
    from chess_coach.engines.stockfish import find_stockfish, Stockfish18Engine

    pool = MultiEnginePool()
    try:
        sf = Stockfish18Engine(binary=find_stockfish())
        pool.add(sf, weight=1.0)
    except Exception as e:  # noqa: BLE001
        logger.warning("Stockfish not available: %s", e)
    pool.add(make_maia2_heuristic(elo_self=1500, elo_opp=1500), weight=0.5)
    return pool
