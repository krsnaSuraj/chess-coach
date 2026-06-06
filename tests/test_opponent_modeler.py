"""Tests for opponent_modeler module."""

from __future__ import annotations

import chess
import pytest

from chess_coach.opponent_modeler import (
    OpponentStyle,
    OpponentModel,
    OpponentMoveRecord,
    STYLE_LABELS,
    model_opponent_from_moves,
)


class TestOpponentModel:
    def test_empty_model(self) -> None:
        m = OpponentModel()
        assert m.avg_cpl == 0.0
        assert m.capture_rate == 0.0
        assert m.check_rate == 0.0
        assert m.blunder_rate == 0.0
        assert m.classify_style() == OpponentStyle.UNKNOWN

    def test_record_move_updates_stats(self) -> None:
        m = OpponentModel()
        for i in range(5):
            m.record_move(OpponentMoveRecord(
                move_number=i + 1, cpl=50.0, is_capture=True, is_check=False,
                is_castle=False, phase="opening",
            ))
        assert m.moves.__len__() == 5
        assert m.captures == 5
        assert m.avg_cpl == 50.0

    def test_blunder_counting(self) -> None:
        m = OpponentModel()
        m.record_move(OpponentMoveRecord(1, 50, False, False, False, "opening"))
        m.record_move(OpponentMoveRecord(2, 250, False, False, False, "opening"))
        assert m.blunders == 1
        assert m.blunder_rate == 0.5

    def test_noisy_classification_high_blunder(self) -> None:
        m = OpponentModel()
        for i in range(10):
            m.record_move(OpponentMoveRecord(i + 1, 300, True, False, False, "middlegame"))
        assert m.classify_style() == OpponentStyle.NOISY

    def test_precise_classification(self) -> None:
        m = OpponentModel()
        for i in range(10):
            m.record_move(OpponentMoveRecord(i + 1, 10, False, False, False, "middlegame"))
        assert m.classify_style() == OpponentStyle.PRECISE

    def test_elo_estimator_updates(self) -> None:
        m = OpponentModel()
        for _ in range(20):
            m.record_move(OpponentMoveRecord(1, 20, False, False, False, "opening"))
        assert m.elo.mean_elo > 1500  # low CPL → high ELO

    def test_summary(self) -> None:
        m = OpponentModel()
        m.record_move(OpponentMoveRecord(1, 50, True, True, False, "middlegame"))
        s = m.summary()
        assert "estimated_elo" in s
        assert "style" in s
        assert s["n_moves"] == 1


class TestModelOpponentFromMoves:
    def test_basic(self) -> None:
        # Build positions for opponent moves (black makes 2 moves)
        b1 = chess.Board()
        b1.push_san("e4")  # white plays e4
        b2 = b1.copy()
        b2.push_san("e5")  # black plays e5 (opponent move 1)
        b3 = b2.copy()
        b3.push_san("Nf3")  # white plays Nf3
        boards = [b1, b2, b3]
        mvs = [
            (chess.Move.from_uci("e7e5"), 50.0),  # black played e5
            (chess.Move.from_uci("b8c6"), 30.0),  # black played Nc6
        ]
        model = model_opponent_from_moves(mvs, boards[:-1])
        assert len(model.moves) == 2
        assert model.moves[0].cpl == 50.0

    def test_empty(self) -> None:
        model = model_opponent_from_moves([])
        assert model.moves == []
