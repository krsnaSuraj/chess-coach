"""Tests for Nova engine adapter."""

from __future__ import annotations

import pytest
import chess
from unittest.mock import patch, MagicMock
import numpy as np

from chess_coach.engines.nova import NovaEngine, NovaConfig


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


class TestNovaEngine:
    @patch("chess_coach.engines.nova.NovaEngine._ensure_model")
    def test_get_move_returns_legal_move(self, mock_ensure):
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

    @patch("chess_coach.engines.nova.NovaEngine._ensure_model")
    def test_get_top_moves_returns_n_moves(self, mock_ensure):
        engine = NovaEngine.__new__(NovaEngine)
        engine.session = MagicMock()
        engine.config = NovaConfig()

        # Mock ONNX output with multiple high values
        # e2e4=796, d2d4=731, Nf3(g1f3)=405
        logits = np.zeros(16384)
        logits[796] = 10.0
        logits[731] = 9.0
        logits[405] = 8.0
        engine.session.run.return_value = [np.array([logits])]

        board = chess.Board()
        moves = engine.get_top_moves(board, n=3)

        assert len(moves) == 3
        assert all(mv in board.legal_moves for mv, _ in moves)
