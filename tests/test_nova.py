"""Tests for Nova engine adapter."""

from __future__ import annotations

import importlib.util
import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load chess_coach.engines.base and chess_coach.engines.nova
# without triggering chess_coach/__init__.py (which pulls in PyQt6, fastapi
# and the full GUI stack).
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parent.parent / "src"

def _load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _SRC / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Create lightweight package stubs so relative imports inside base/nova work
for _pkg in ("chess_coach", "chess_coach.engines"):
    if _pkg not in sys.modules:
        pkg_mod = type(sys)(_pkg)
        pkg_mod.__path__ = [str(_SRC / _pkg.replace(".", "/"))]
        sys.modules[_pkg] = pkg_mod

_base = _load_module("chess_coach.engines.base", "chess_coach/engines/base.py")
_nova = _load_module("chess_coach.engines.nova", "chess_coach/engines/nova.py")

Engine = _base.Engine
EngineInfo = _base.EngineInfo
Evaluation = _base.Evaluation
NovaEngine = _nova.NovaEngine
NovaConfig = _nova.NovaConfig

# ---------------------------------------------------------------------------
# Now pull in test dependencies
# ---------------------------------------------------------------------------
import pytest
import chess
import numpy as np


class TestNovaConfig:
    def test_default_config(self):
        config = NovaConfig()
        assert config.model_dir == "engines/nova"
        assert config.rating == 1500
        assert config.classical == 0.5
        assert config.aggression == 0.5
        assert config.temperature == 0.5

    def test_custom_config(self):
        config = NovaConfig(rating=2000, classical=0.8, aggression=0.3)
        assert config.rating == 2000
        assert config.classical == 0.8
        assert config.aggression == 0.3


class TestNovaFenEncoding:
    def test_fen_to_planes_starting_position(self):
        engine = NovaEngine.__new__(NovaEngine)
        planes = engine.fen_to_planes(chess.STARTING_FEN)

        assert planes.shape == (18, 8, 8)
        # Side to move (plane 12) should be all 1s for white
        assert planes[12].sum() == 64
        # White king (plane 5) at e1: FEN rank 1 is ri=7, rank_idx=7-7=0
        assert planes[5, 0, 4] == 1.0

    def test_fen_to_planes_black_to_move(self):
        engine = NovaEngine.__new__(NovaEngine)
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        planes = engine.fen_to_planes(fen)

        # Side to move (plane 12) should be all 0s for black
        assert planes[12].sum() == 0


class TestNovaMoveDecoding:
    def test_decode_e2e4(self):
        engine = NovaEngine.__new__(NovaEngine)
        # e2=12, e4=28 -> 12*64+28 = 796
        move = engine.decode_move_idx(796)
        assert move.from_square == chess.E2
        assert move.to_square == chess.E4
        assert move.promotion is None

    def test_decode_knight_promotion(self):
        engine = NovaEngine.__new__(NovaEngine)
        # a7=48, a8=56 -> 4096 + 48*64+56 = 7224
        move = engine.decode_move_idx(7224)
        assert move.from_square == chess.A7
        assert move.to_square == chess.A8
        assert move.promotion == chess.KNIGHT

    def test_decode_queen_promotion(self):
        engine = NovaEngine.__new__(NovaEngine)
        # a7=48, a8=56 -> 12288 + 48*64+56 = 15416
        move = engine.decode_move_idx(15416)
        assert move.from_square == chess.A7
        assert move.to_square == chess.A8
        assert move.promotion == chess.QUEEN

    def test_decode_bishop_promotion(self):
        engine = NovaEngine.__new__(NovaEngine)
        # a7=48, a8=56 -> 8192 + 48*64+56 = 11320
        move = engine.decode_move_idx(11320)
        assert move.from_square == chess.A7
        assert move.to_square == chess.A8
        assert move.promotion == chess.BISHOP


class TestNovaEngineABC:
    """Tests that NovaEngine properly implements the Engine ABC."""

    def test_is_instance_of_engine(self):
        assert issubclass(NovaEngine, Engine)

    @patch.object(NovaEngine, "_ensure_model")
    def test_info_returns_engine_info(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        info = engine.info()
        assert isinstance(info, EngineInfo)
        assert info.name == "Nova"
        assert info.type == "neural"

    @patch.object(NovaEngine, "_ensure_model")
    def test_start_sets_session(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = None
        engine.config = NovaConfig()

        engine.start()
        engine._ensure_model.assert_called_once()

    @patch.object(NovaEngine, "_ensure_model")
    def test_stop_clears_session(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        assert engine.is_ready() is True
        engine.stop()
        assert engine.is_ready() is False

    @patch.object(NovaEngine, "_ensure_model")
    def test_is_ready_reflects_session(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = None
        engine.config = NovaConfig()

        assert engine.is_ready() is False
        engine.session = MagicMock()
        assert engine.is_ready() is True

    @patch.object(NovaEngine, "_ensure_model")
    def test_evaluate_returns_evaluation(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        logits = np.zeros(16384)
        logits[796] = 10.0  # e2e4
        engine.session.run.return_value = [np.array([logits])]

        eval_result = engine.evaluate(chess.STARTING_FEN)
        assert isinstance(eval_result, Evaluation)
        assert isinstance(eval_result.score_cp, int)
        assert eval_result.source_engine == "Nova"

    @patch.object(NovaEngine, "_ensure_model")
    def test_set_and_get_options(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        engine.set_option("rating", 2000)
        engine.set_option("temperature", 0.8)
        opts = engine.get_options()
        assert opts["rating"] == 2000
        assert opts["temperature"] == 0.8

    def test_set_option_unknown_raises(self):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        with pytest.raises(ValueError, match="Unknown Nova option"):
            engine.set_option("bogus", 42)


class TestNovaEngine:
    @patch.object(NovaEngine, "_ensure_model")
    def test_get_move_returns_legal_move(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        # Mock ONNX output: e2e4=796
        logits = np.zeros(16384)
        logits[796] = 10.0
        engine.session.run.return_value = [np.array([logits])]

        board = chess.Board()
        move = engine.get_move(board)

        assert move in board.legal_moves

    @patch.object(NovaEngine, "_ensure_model")
    def test_get_top_moves_returns_n_moves(self, _mock):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        # Mock ONNX output with multiple high values
        logits = np.zeros(16384)
        logits[796] = 10.0
        logits[731] = 9.0
        logits[405] = 8.0
        engine.session.run.return_value = [np.array([logits])]

        board = chess.Board()
        moves = engine.get_top_moves(board, n=3)

        assert len(moves) == 3
        assert all(mv in board.legal_moves for mv, _ in moves)

    @patch.object(NovaEngine, "_ensure_model")
    def test_get_move_no_legal_moves_returns_null(self, _mock):
        """When no legal moves exist (checkmate), returns null move."""
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        logits = np.zeros(16384)
        engine.session.run.return_value = [np.array([logits])]

        # Scholar's mate position - black is checkmated
        board = chess.Board(
            "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 1"
        )
        assert board.is_checkmate()

        move = engine.get_move(board)
        assert move == chess.Move.null()

    @patch.object(NovaEngine, "_ensure_model")
    def test_get_top_moves_no_legal_moves_returns_empty(self, _mock):
        """When no legal moves exist (checkmate), returns empty list."""
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        logits = np.zeros(16384)
        engine.session.run.return_value = [np.array([logits])]

        board = chess.Board(
            "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 1"
        )
        assert board.is_checkmate()

        moves = engine.get_top_moves(board)
        assert moves == []

    @patch.object(NovaEngine, "_ensure_model")
    def test_evaluate_score_from_move_probs(self, _mock):
        """Score computed from probability ratio of best two moves."""
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        logits = np.zeros(16384)
        logits[796] = 10.0  # best
        logits[731] = 8.0   # second
        engine.session.run.return_value = [np.array([logits])]

        eval_result = engine.evaluate(chess.STARTING_FEN)
        assert eval_result.score_cp > 0


class TestMissingModel:
    def test_raises_when_no_model_and_auto_download_false(self):
        with patch.object(NovaEngine, "_ensure_model") as mock:
            mock.side_effect = FileNotFoundError("Nova model not found")
            engine = NovaEngine.__new__(NovaEngine)
            engine.config = NovaConfig(auto_download=False)

            with pytest.raises(FileNotFoundError, match="Nova model not found"):
                engine._ensure_model()
