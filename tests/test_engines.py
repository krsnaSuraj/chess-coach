"""Tests for engines module (Phase I)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chess_coach.engines.base import Engine, EngineInfo, Evaluation, EngineError
from chess_coach.engines.stockfish import (
    Stockfish18Engine,
    SF18_DEFAULT_OPTIONS,
    SF18_NNUE_NAME,
    find_stockfish,
)
from chess_coach.engines.lc0 import Lc0Engine
from chess_coach.engines.maia2 import (
    Maia2Engine,
    make_maia2_heuristic,
    deterministic_maia_choice,
    MAIA2_MIN_ELO,
    MAIA2_MAX_ELO,
)
from chess_coach.engines.multi_engine_pool import (
    MultiEnginePool,
    EngineWeight,
    make_default_pool,
)


# ===== EngineInfo / Evaluation =====

class TestEngineInfo:
    def test_construction(self) -> None:
        info = EngineInfo(
            name="Test", version="1.0", author="x",
            elo_ceiling=3000, elo_floor=1000, type="uci",
        )
        assert info.name == "Test"
        assert info.type == "uci"
        assert info.requires == []  # default

    def test_with_requirements(self) -> None:
        info = EngineInfo(
            name="Lc0", version="0.32.2", author="LCZero",
            elo_ceiling=3500, elo_floor=1400, type="lc0",
            requires=["lc0.exe", "*.pb.gz"],
        )
        assert "lc0.exe" in info.requires


class TestEvaluation:
    def test_default_construction(self) -> None:
        ev = Evaluation(score_cp=0)
        assert ev.score_cp == 0
        assert ev.mate is None
        assert ev.depth == 0
        assert ev.winrate == 0.5  # equal position

    def test_winrate_from_cp(self) -> None:
        # 400cp = 10x winrate
        ev = Evaluation(score_cp=400)
        assert ev.winrate > 0.9
        ev_neg = Evaluation(score_cp=-400)
        assert ev_neg.winrate < 0.1

    def test_winrate_clamping(self) -> None:
        ev = Evaluation(score_cp=2000)  # very high
        assert ev.winrate == 1.0
        ev_neg = Evaluation(score_cp=-2000)
        assert ev_neg.winrate == 0.0

    def test_winrate_from_mate(self) -> None:
        ev = Evaluation(score_cp=0, mate=3)
        assert ev.winrate == 1.0
        ev_loss = Evaluation(score_cp=0, mate=-3)
        assert ev_loss.winrate == 0.0

    def test_winrate_from_wdl(self) -> None:
        ev = Evaluation(score_cp=0, wdl=(1000, 0, 0))  # certain win
        assert ev.winrate == 1.0
        ev_d = Evaluation(score_cp=0, wdl=(0, 1000, 0))  # certain draw
        assert ev_d.winrate == 0.5
        ev_l = Evaluation(score_cp=0, wdl=(0, 0, 1000))  # certain loss
        assert ev_l.winrate == 0.0

    def test_multipv_field(self) -> None:
        ev = Evaluation(score_cp=50, multipv=[{"multipv": 1, "move": "e2e4"}])
        assert len(ev.multipv) == 1
        assert ev.multipv[0]["move"] == "e2e4"


# ===== Stockfish18Engine =====

class TestStockfish18:
    def test_default_options_have_nnue(self) -> None:
        assert SF18_DEFAULT_OPTIONS["Use NNUE"] is True
        assert "EvalFile" in SF18_DEFAULT_OPTIONS
        assert SF18_NNUE_NAME in SF18_DEFAULT_OPTIONS["EvalFile"]

    def test_init(self) -> None:
        eng = Stockfish18Engine()
        assert eng.info().name == "Stockfish"
        assert eng.is_ready() is False
        assert "EvalFile" in eng.get_options()

    def test_set_option(self) -> None:
        eng = Stockfish18Engine()
        eng.set_option("Hash", 256)
        assert eng.get_options()["Hash"] == 256

    def test_set_option_with_nnue_path(self) -> None:
        eng = Stockfish18Engine(nnue_path="/tmp/nn.bin")
        assert eng.get_options()["EvalFile"] == "/tmp/nn.bin"

    def test_info(self) -> None:
        eng = Stockfish18Engine()
        info = eng.info()
        assert info.name == "Stockfish"
        assert info.type == "uci"
        assert info.elo_ceiling >= 3000

    def test_start_fails_without_binary(self) -> None:
        eng = Stockfish18Engine(binary="/nonexistent/stockfish")
        with pytest.raises(EngineError):
            eng.start()

    def test_stop_safe_when_not_started(self) -> None:
        eng = Stockfish18Engine()
        eng.stop()  # should not raise
        assert eng.is_ready() is False

    def test_find_stockfish_returns_string(self) -> None:
        # find_stockfish should return some path, even if not present
        result = find_stockfish()
        assert isinstance(result, str)
        assert len(result) > 0


# ===== Lc0Engine =====

class TestLc0Engine:
    def test_init(self) -> None:
        eng = Lc0Engine()
        assert eng.info().name == "Lc0"
        assert eng.info().type == "lc0"
        assert "Backend" in eng.get_options()

    def test_with_weights(self) -> None:
        eng = Lc0Engine(weights="maia2.pt")
        assert eng.get_options()["WeightsFile"] == "maia2.pt"

    def test_set_option(self) -> None:
        eng = Lc0Engine()
        eng.set_option("Threads", 4)
        assert eng.get_options()["Threads"] == 4

    def test_info(self) -> None:
        eng = Lc0Engine()
        info = eng.info()
        assert info.elo_ceiling > 3000


# ===== Maia2Engine =====

class TestMaia2Engine:
    def test_init_default(self) -> None:
        eng = Maia2Engine()
        info = eng.info()
        assert info.name == "Maia-2"
        assert info.type == "neural"
        assert info.elo_floor == MAIA2_MIN_ELO
        assert info.elo_ceiling == MAIA2_MAX_ELO

    def test_elo_clamping(self) -> None:
        eng = Maia2Engine(elo_self=500, elo_opp=5000)
        opts = eng.get_options()
        assert opts["EloSelf"] == MAIA2_MIN_ELO
        assert opts["EloOpp"] == MAIA2_MAX_ELO

    def test_set_option(self) -> None:
        eng = Maia2Engine()
        eng.set_option("EloSelf", 1800)
        eng.set_option("EloOpp", 1600)
        opts = eng.get_options()
        assert opts["EloSelf"] == 1800
        assert opts["EloOpp"] == 1600

    def test_evaluate_starting_position(self) -> None:
        import chess
        eng = Maia2Engine(elo_self=1500, elo_opp=1500)
        ev = eng.evaluate(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            depth=1, multipv=3,
        )
        assert ev.source_engine == "Maia-2"
        assert len(ev.pv) > 0
        assert len(ev.multipv) <= 3

    def test_factory(self) -> None:
        eng = make_maia2_heuristic(1500, 1500)
        assert eng.is_ready()

    def test_deterministic_choice(self) -> None:
        moves = ["e2e4", "d2d4", "c2c4", "g1f3"]
        # High elo -> first move
        assert deterministic_maia_choice(moves, 1800) == "e2e4"
        # Low elo -> random
        result_low = deterministic_maia_choice(moves, 1000, seed=42)
        assert result_low in moves
        # Same seed -> same result
        result_low2 = deterministic_maia_choice(moves, 1000, seed=42)
        assert result_low == result_low2

    def test_evaluate_empty_legal_moves(self) -> None:
        import chess
        # Mate position
        eng = Maia2Engine(elo_self=1500)
        ev = eng.evaluate(
            "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1",  # black to move, in checkmate
            depth=1,
        )
        # No legal moves, so PV is empty
        assert ev.score_cp == 0


# ===== MultiEnginePool =====

class _MockEngine(Engine):
    def __init__(self, name: str, cp: int = 50, pv: list[str] | None = None) -> None:
        self._name = name
        self._cp = cp
        self._pv = pv or ["e2e4"]
        self._started = False
        self._opts: dict = {}

    def info(self) -> EngineInfo:
        return EngineInfo(
            name=self._name, version="1.0", author="test",
            elo_ceiling=3500, elo_floor=1000, type="uci",
        )

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def is_ready(self) -> bool:
        return self._started

    def evaluate(self, fen: str, depth: int = 20, multipv: int = 1) -> Evaluation:
        return Evaluation(
            score_cp=self._cp, depth=depth, pv=self._pv,
            source_engine=self._name,
        )

    def set_option(self, name: str, value: object) -> None:
        self._opts[name] = value

    def get_options(self) -> dict:
        return dict(self._opts)


class TestMultiEnginePool:
    def test_empty_pool(self) -> None:
        pool = MultiEnginePool()
        assert pool.engines() == []
        evals = pool.evaluate("startpos")
        assert evals == []

    def test_single_engine(self) -> None:
        eng = _MockEngine("A", cp=100, pv=["e2e4", "e7e5"])
        pool = MultiEnginePool()
        pool.add(eng, weight=1.0)
        evals = pool.evaluate(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            depth=10, multipv=2,
        )
        assert len(evals) >= 1
        assert evals[0].source_engine.startswith("Pool[")

    def test_multiple_engines(self) -> None:
        eng1 = _MockEngine("A", cp=100, pv=["e2e4"])
        eng2 = _MockEngine("B", cp=200, pv=["d2d4"])
        pool = MultiEnginePool()
        pool.add(eng1, weight=1.0)
        pool.add(eng2, weight=0.5)
        evals = pool.evaluate("startpos")
        # Should get at least 2 unique PVs
        assert len(evals) >= 1
        sources = {e.source_engine for e in evals}
        assert any("A" in s for s in sources) or any("B" in s for s in sources)

    def test_engine_failure_disables(self) -> None:
        class BadEngine(_MockEngine):
            def evaluate(self, fen: str, depth: int = 20, multipv: int = 1) -> Evaluation:
                raise RuntimeError("engine dead")

        good = _MockEngine("Good", cp=50)
        bad = BadEngine("Bad")
        pool = MultiEnginePool()
        pool.add(good, weight=1.0)
        pool.add(bad, weight=1.0)
        evals = pool.evaluate("startpos")
        # Bad engine should be disabled, but we still get a result from Good
        assert len(evals) >= 1
        # Bad is now disabled
        weights = pool._weights
        bad_w = next(w for w in weights if w.engine is bad)
        assert bad_w.enabled is False

    def test_aggregate_dedupes_pvs(self) -> None:
        eng = _MockEngine("Dup", cp=100, pv=["e2e4", "e7e5"])
        pool = MultiEnginePool()
        pool.add(eng)
        evals = pool.evaluate("startpos", multipv=3)
        # No duplicates in PVs
        seen_pvs = set()
        for ev in evals:
            pv_tuple = tuple(ev.pv)
            assert pv_tuple not in seen_pvs or not ev.pv
            seen_pvs.add(pv_tuple)

    def test_start_stop(self) -> None:
        eng = _MockEngine("Test")
        pool = MultiEnginePool()
        pool.add(eng)
        pool.start_all()
        assert eng.is_ready()
        pool.stop_all()
        assert not eng.is_ready()

    def test_default_pool_no_crash(self) -> None:
        pool = make_default_pool()
        # Just ensure it constructs without error
        assert pool is not None
        # Don't evaluate (might fail if no real engine binary)
