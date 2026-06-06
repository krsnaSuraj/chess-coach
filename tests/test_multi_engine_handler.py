"""Tests for multi_engine_handler module — uses mocks to avoid real subprocesses."""

from __future__ import annotations

import pytest
import chess
from unittest.mock import MagicMock, patch

from chess_coach.multi_engine_handler import (
    MultiEngineConfig,
    MultiEngineHandler,
    StockfishAnalysisThread,
    MaiaAnalysisThread,
)


class TestMultiEngineConfig:
    def test_defaults(self) -> None:
        c = MultiEngineConfig()
        assert c.sf_path == "stockfish.exe"
        assert c.sf_threads == 2
        assert c.sf_hash_mb == 64
        assert c.enable_maia is True

    def test_maia_config_optional(self) -> None:
        c = MultiEngineConfig(enable_maia=False)
        assert c.enable_maia is False
        assert c.maia is None


class TestMultiEngineHandler:
    def test_init(self) -> None:
        h = MultiEngineHandler(MultiEngineConfig(enable_maia=False))
        assert h.maia_available is False
        assert h.last_maia_distribution == {}

    def test_close_safe(self) -> None:
        h = MultiEngineHandler(MultiEngineConfig(enable_maia=False))
        h.close()

    def test_maia_property_returns_none_when_disabled(self) -> None:
        h = MultiEngineHandler(MultiEngineConfig(enable_maia=False))
        assert h.maia is None


class TestStockfishAnalysisThread:
    def test_can_construct(self) -> None:
        engine = MagicMock()
        board = chess.Board()
        t = StockfishAnalysisThread(engine, board, movetime_s=0.1)
        assert t.is_running is True
        t.stop()
        assert t.is_running is False


class TestMaiaAnalysisThread:
    def test_can_construct(self) -> None:
        maia = MagicMock()
        maia.get_move_probabilities.return_value = {}
        board = chess.Board()
        t = MaiaAnalysisThread(maia, board)
        assert t.is_running is True
        t.stop()
        assert t.is_running is False
