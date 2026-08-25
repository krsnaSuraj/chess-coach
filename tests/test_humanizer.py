from __future__ import annotations

import chess
import chess.engine
import pytest

from chess_coach.humanizer import (
    Humanizer,
    ComplexityDetector,
    SessionMetrics,
    _accuracy_for_elo,
    _top1_rate_for_elo,
    _top3_cumulative_for_elo,
    _expected_score,
)


class TestAccuracyCalibration:
    def test_formula_matches_gm_study_data(self):
        assert abs(_accuracy_for_elo(1600) - 0.80) < 0.02
        assert abs(_accuracy_for_elo(2000) - 0.84) < 0.02
        assert abs(_accuracy_for_elo(2400) - 0.88) < 0.035
        assert abs(_accuracy_for_elo(2800) - 0.92) < 0.04

    def test_1500_accuracy_implies_78_percent(self):
        acc = _accuracy_for_elo(1500)
        assert 0.77 <= acc <= 0.81

    def test_top1_monotonic_increasing(self):
        previous = _top1_rate_for_elo(700)
        for elo in [1000, 1500, 2000, 2500, 2900]:
            current = _top1_rate_for_elo(elo)
            assert current >= previous
            previous = current

    def test_top3_always_greater_than_top1(self):
        for elo in [800, 1200, 1500, 2000, 2500]:
            assert _top3_cumulative_for_elo(elo) > _top1_rate_for_elo(elo)

    def test_expected_score(self):
        assert _expected_score(1500, 1500) == pytest.approx(0.5, abs=0.01)
        assert _expected_score(2000, 1500) > 0.90


class TestSessionMetrics:
    def test_initial_state(self):
        s = SessionMetrics()
        assert s.games_played == 0
        assert s.wins == 0
        assert s.avg_accuracy == 0.0

    def test_record_game_updates_stats(self):
        s = SessionMetrics()
        s.record_game(0.80, "win")
        assert s.games_played == 1
        assert s.wins == 1
        assert s.avg_accuracy == 0.80

    def test_win_rate(self):
        s = SessionMetrics()
        s.record_game(0.80, "win")
        s.record_game(0.75, "win")
        s.record_game(0.72, "loss")
        assert s.win_rate() == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_coherence_low_with_variance(self):
        s = SessionMetrics()
        s.record_game(0.40, "loss")
        s.record_game(0.95, "win")
        s.record_game(0.35, "loss")
        s.record_game(0.50, "loss")
        s.record_game(0.90, "win")
        c = s.coherence_score()
        assert c < 0.15


class TestHumanizerV3:
    def test_disabled_returns_first_move(self):
        h = Humanizer({"humanizer": {"enabled": False}})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
        ]
        move = h.select_move(candidates, board)
        assert move is not None
        assert move.uci() == "e2e4"

    def test_select_move_returns_valid_move(self):
        h = Humanizer({})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
        ]
        move = h.select_move(candidates, board)
        assert move is not None
        assert move in board.legal_moves

    def test_1500_accuracy_calibrated(self):
        h = Humanizer({"humanizer": {"target_elo": 1500}})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("b1c3")],
                "score": chess.engine.PovScore(chess.engine.Cp(5), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("c2c4")],
                "score": chess.engine.PovScore(chess.engine.Cp(3), chess.WHITE),
            },
        ]
        from collections import Counter

        counts = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board)
            counts[m.uci()] += 1
        top1_pct = counts.get("e2e4", 0) / 5
        assert 12 <= top1_pct <= 36

    def test_magnus_level_high_top1(self):
        h = Humanizer({"humanizer": {"target_elo": 2800}})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("b1c3")],
                "score": chess.engine.PovScore(chess.engine.Cp(5), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("c2c4")],
                "score": chess.engine.PovScore(chess.engine.Cp(3), chess.WHITE),
            },
        ]
        from collections import Counter

        counts = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board)
            counts[m.uci()] += 1
        top1_pct = counts.get("e2e4", 0) / 5
        assert top1_pct >= 45

    def test_time_pressure_increases_errors(self):
        h = Humanizer({"humanizer": {"target_elo": 1500}})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("b1c3")],
                "score": chess.engine.PovScore(chess.engine.Cp(5), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("c2c4")],
                "score": chess.engine.PovScore(chess.engine.Cp(3), chess.WHITE),
            },
        ]
        from collections import Counter

        complex_counts = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board, is_complex=True)
            complex_counts[m.uci()] += 1
        normal = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board, is_complex=False)
            normal[m.uci()] += 1
        cplx_errors = 100 - complex_counts.get("e2e4", 0) / 5
        normal_errors = 100 - normal.get("e2e4", 0) / 5
        assert cplx_errors > normal_errors * 0.7

    def test_select_move_empty_list(self):
        h = Humanizer({})
        board = chess.Board()
        move = h.select_move([], board)
        assert move is None

    def test_select_move_single_pv(self):
        h = Humanizer({})
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
        ]
        seen = set()
        for _ in range(200):
            move = h.select_move(candidates, board)
            assert move is not None
            assert move in board.legal_moves
            seen.add(move.uci())
        assert "e2e4" in seen

    def test_new_game_resets_move_count(self):
        h = Humanizer({})
        h._move_count = 42
        h.new_game()
        assert h._move_count == 0

    def test_new_game_progressive_elo_climbs(self):
        h = Humanizer({"humanizer": {"target_elo": 1500}})
        elos = []
        for _ in range(20):
            h.new_game()
            elos.append(h.effective_elo)
        assert elos[-1] >= 1500
        assert elos[-1] <= 2000
        assert elos[-1] > elos[0]

    def test_progressive_elo_capped(self):
        h = Humanizer({"humanizer": {"target_elo": 1500}})
        for _ in range(100):
            h.new_game()
        assert h.effective_elo <= 2000

    def test_large_eval_drops_effective_elo(self):
        h = Humanizer({"humanizer": {"target_elo": 1500}})
        h._progressive_elo = 1700
        board = chess.Board()
        candidates = [
            {
                "pv": [chess.Move.from_uci("e2e4")],
                "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("d2d4")],
                "score": chess.engine.PovScore(chess.engine.Cp(15), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("g1f3")],
                "score": chess.engine.PovScore(chess.engine.Cp(10), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("b1c3")],
                "score": chess.engine.PovScore(chess.engine.Cp(5), chess.WHITE),
            },
            {
                "pv": [chess.Move.from_uci("c2c4")],
                "score": chess.engine.PovScore(chess.engine.Cp(3), chess.WHITE),
            },
        ]
        from collections import Counter

        winning = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board, eval_score=3.5)
            winning[m.uci()] += 1
        normal = Counter()
        for _ in range(500):
            m = h.select_move(candidates, board, eval_score=0.0)
            normal[m.uci()] += 1
        win_top1 = winning.get("e2e4", 0) / 5
        normal_top1 = normal.get("e2e4", 0) / 5
        assert win_top1 < normal_top1 + 10

    def test_risk_assessment_safe_initially(self):
        h = Humanizer({})
        risk = h.get_risk_assessment()
        assert risk["level"] == "SAFE"
        assert risk["games"] == 0

    def test_record_result(self):
        h = Humanizer({})
        h.record_result("win", 0.82)
        risk = h.get_risk_assessment()
        assert risk["games"] == 1
        assert risk["win_rate"] == 1.0


class TestComplexityDetector:
    def test_starting_position_not_complex(self):
        board = chess.Board()
        assert not ComplexityDetector.is_complex(board)

    def test_complex_middlegame_position(self):
        board = chess.Board(
            "r1b2rk1/ppp1qppp/2np1n2/2b1p1B1/2B1P3/2NP1N2/PPP2PPP/R2Q1RK1 w - - 4 10"
        )
        assert ComplexityDetector.is_complex(board)

    def test_endgame_not_complex(self):
        board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        assert not ComplexityDetector.is_complex(board)

    def test_time_pressure_below_60_seconds(self):
        assert ComplexityDetector.is_time_pressure(30.0)

    def test_no_time_pressure_above_60_seconds(self):
        assert not ComplexityDetector.is_time_pressure(180.0)
