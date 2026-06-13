"""Tests for anti-detection system (12 signals, ML classifier, session tracker)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load chess_coach.anti_detect modules without triggering the
# main chess_coach/__init__.py which pulls in PyQt6 and the full GUI stack.
# ---------------------------------------------------------------------------
_SRC = Path(__file__).resolve().parent.parent / "src"

def _load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _SRC / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Create lightweight package stubs so relative imports inside the modules work
for _pkg in ("chess_coach", "chess_coach.anti_detect"):
    if _pkg not in sys.modules:
        pkg_mod = type(sys)(_pkg)
        pkg_mod.__path__ = [str(_SRC / _pkg.replace(".", "/"))]
        sys.modules[_pkg] = pkg_mod

_signals = _load_module("chess_coach.anti_detect.signals", "chess_coach/anti_detect/signals.py")
_classifier = _load_module("chess_coach.anti_detect.classifier", "chess_coach/anti_detect/classifier.py")
_session_tracker = _load_module("chess_coach.anti_detect.session_tracker", "chess_coach/anti_detect/session_tracker.py")

SignalAnalyzer = _signals.SignalAnalyzer
SignalResult = _signals.SignalResult
RiskClassifier = _classifier.RiskClassifier
RiskAssessment = _classifier.RiskAssessment
SessionTracker = _session_tracker.SessionTracker
SessionMetrics = _session_tracker.SessionMetrics

# ---------------------------------------------------------------------------
# Now pull in test dependencies
# ---------------------------------------------------------------------------
import pytest
import chess
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# SignalAnalyzer Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSignalResult:
    def test_dataclass_fields(self):
        sr = SignalResult(name="test", value=0.5, weight=0.1, confidence=0.9)
        assert sr.name == "test"
        assert sr.value == 0.5
        assert sr.weight == 0.1
        assert sr.confidence == 0.9


class TestSignalAnalyzerEmpty:
    def test_empty_returns_low_values(self):
        sa = SignalAnalyzer()
        results = sa.analyze_all()
        assert len(results) == 12
        for r in results:
            assert 0.0 <= r.value <= 1.0

    def test_empty_weighted_score_is_zero(self):
        sa = SignalAnalyzer()
        score = sa.get_weighted_score()
        assert score == 0.0


class TestSignalAnalyzerHuman:
    """Simulate a human player: ~30% SF top-1 match, high CPL, varied times."""

    def _build_human_signals(self):
        sa = SignalAnalyzer()
        rng = np.random.default_rng(42)
        board = chess.Board()
        for i in range(50):
            legal = list(board.legal_moves)
            top_moves = legal[:5] if len(legal) >= 5 else legal
            # 30% chance of top-1, rest random
            if rng.random() < 0.30 and top_moves:
                move = top_moves[0]
            else:
                move = rng.choice(legal)
            think_time = max(0.5, rng.normal(8.0, 4.0))
            eval_before = rng.normal(0.0, 0.5)
            sa.record_move(move, think_time, eval_before, top_moves)
            board.push(move)
        return sa

    def test_human_low_suspicion(self):
        sa = self._build_human_signals()
        score = sa.get_weighted_score()
        assert score < 0.7  # should not be extremely suspicious

    def test_human_sf_top1_below_threshold(self):
        sa = self._build_human_signals()
        r = sa.sf_top1_match_rate()
        assert r.value < 1.0  # human won't always match top-1


class TestSignalAnalyzerEngine:
    """Simulate engine play: ~95% SF top-1 match, low CV, low blunders."""

    def _build_engine_signals(self):
        sa = SignalAnalyzer()
        rng = np.random.default_rng(99)
        board = chess.Board()
        for i in range(50):
            legal = list(board.legal_moves)
            top_moves = legal[:5] if len(legal) >= 5 else legal
            # 95% of the time, play SF top-1
            if rng.random() < 0.95 and top_moves:
                move = top_moves[0]
            else:
                move = rng.choice(legal)
            think_time = max(0.3, rng.normal(2.0, 0.3))  # very uniform
            eval_before = rng.normal(0.0, 0.3)
            sa.record_move(move, think_time, eval_before, top_moves)
            board.push(move)
        return sa

    def test_engine_high_suspicion(self):
        sa = self._build_engine_signals()
        score = sa.get_weighted_score()
        assert score > 0.3  # should be more suspicious than human

    def test_engine_time_cv_signal(self):
        sa = self._build_engine_signals()
        r = sa.move_time_cv()
        assert r.value > 0.0  # low variance = suspicious


class TestSFTop1MatchRate:
    def test_few_moves_returns_zero(self):
        sa = SignalAnalyzer()
        for i in range(5):
            sa.record_move(chess.Move(chess.E2, chess.E4), 1.0, 0.0, [])
        r = sa.sf_top1_match_rate()
        assert r.value == 0.0
        assert r.confidence == 0.0

    def test_all_top1_returns_high(self):
        sa = SignalAnalyzer()
        move = chess.Move(chess.E2, chess.E4)
        for _ in range(20):
            sa.record_move(move, 1.0, 0.0, [move])
        r = sa.sf_top1_match_rate()
        assert r.value == 1.0
        assert r.weight == 0.15


class TestAverageCPL:
    def test_zero_cpl_returns_high(self):
        sa = SignalAnalyzer()
        for _ in range(15):
            sa.eval_history.append(0.5)
        r = sa.average_cpl()
        assert r.value > 0.0  # low CPL = suspicious

    def test_high_cpl_returns_low(self):
        sa = SignalAnalyzer()
        for i in range(15):
            sa.eval_history.append(float(i * 10))  # big jumps = high CPL
        r = sa.average_cpl()
        assert r.value == 0.0  # high CPL = not suspicious


class TestMoveTimeCV:
    def test_uniform_times_high_suspicion(self):
        sa = SignalAnalyzer()
        for _ in range(15):
            sa.time_history.append(3.0)  # all same
        r = sa.move_time_cv()
        assert r.value == 1.0  # CV=0, max suspicion

    def test_varied_times_low_suspicion(self):
        sa = SignalAnalyzer()
        rng = np.random.default_rng(0)
        for _ in range(15):
            sa.time_history.append(max(0.5, rng.normal(8.0, 5.0)))
        r = sa.move_time_cv()
        assert r.value < 0.5


class TestBlunderFrequency:
    def test_no_blunders_returns_high(self):
        sa = SignalAnalyzer()
        for _ in range(15):
            sa.eval_history.append(1.0)
        r = sa.blunder_frequency()
        assert r.value == 1.0  # zero blunders = suspicious

    def test_many_blunders_returns_low(self):
        sa = SignalAnalyzer()
        sa.eval_history = [10.0] + [0.0] * 14  # many big drops
        r = sa.blunder_frequency()
        assert r.value == 0.0


class TestMoveOrderingEntropy:
    def test_low_entropy_high_suspicion(self):
        sa = SignalAnalyzer()
        move = chess.Move(chess.E2, chess.E4)
        for _ in range(20):
            sa.move_history.append(move)
            sa.engine_top_moves.append([move, chess.Move(chess.D2, chess.D4)])
        r = sa.move_ordering_entropy()
        assert r.value > 0.5  # always picking rank 0 = low entropy

    def test_high_entropy_low_suspicion(self):
        sa = SignalAnalyzer()
        moves = [chess.Move(i, i + 8) for i in range(6)]
        for i in range(20):
            mv = moves[i % 6]
            sa.move_history.append(mv)
            sa.engine_top_moves.append(list(moves))
        r = sa.move_ordering_entropy()
        assert r.value < 0.5


# ═══════════════════════════════════════════════════════════════════════════
# RiskClassifier Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRiskClassifier:
    def test_rule_based_all_zero(self):
        rc = RiskClassifier.__new__(RiskClassifier)
        rc.model = None
        rc.model_path = Path("dummy")
        signals = [0.0] * 12
        a = rc.assess_risk(signals)
        assert a.score == 0
        assert a.level == "SAFE"
        assert a.recommendation == "No action needed"

    def test_rule_based_all_one(self):
        rc = RiskClassifier.__new__(RiskClassifier)
        rc.model = None
        rc.model_path = Path("dummy")
        signals = [1.0] * 12
        a = rc.assess_risk(signals)
        assert a.score == 100
        assert a.level == "CRITICAL"
        assert a.recommendation == "Abort session"

    def test_rule_based_caution(self):
        rc = RiskClassifier.__new__(RiskClassifier)
        rc.model = None
        rc.model_path = Path("dummy")
        # Mid-range signals -> score ~50
        signals = [0.5] * 12
        a = rc.assess_risk(signals)
        assert a.level == "CAUTION"

    def test_rule_based_warning(self):
        rc = RiskClassifier.__new__(RiskClassifier)
        rc.model = None
        rc.model_path = Path("dummy")
        # High signals -> score 70-79
        signals = [0.7] * 12
        a = rc.assess_risk(signals)
        assert a.level == "WARNING"

    def test_signals_above_threshold(self):
        rc = RiskClassifier.__new__(RiskClassifier)
        rc.model = None
        rc.model_path = Path("dummy")
        signals = [0.8, 0.9, 0.5, 0.3, 0.8, 0.75, 0.6, 0.4, 0.2, 0.1, 0.0, 0.0]
        a = rc.assess_risk(signals)
        assert a.signals_above_threshold == 4  # 0.8, 0.9, 0.8, 0.75


class TestRiskAssessment:
    def test_dataclass(self):
        ra = RiskAssessment(score=65, level="WARNING", signals_above_threshold=3, recommendation="Increase timing noise")
        assert ra.score == 65
        assert ra.level == "WARNING"


# ═══════════════════════════════════════════════════════════════════════════
# SessionTracker Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionTracker:
    def test_start_session(self):
        st = SessionTracker()
        st.start_session()
        assert st.current_session is not None
        assert st.current_session["games"] == []

    def test_record_game_auto_start(self):
        st = SessionTracker()
        st.record_game(moves=40, cv=0.35, cpl=45.0, blunders=2, accuracy=72.5)
        assert st.current_session is not None
        assert len(st.current_session["games"]) == 1

    def test_record_multiple_games(self):
        st = SessionTracker()
        st.start_session()
        st.record_game(moves=40, cv=0.35, cpl=45.0, blunders=2, accuracy=72.5)
        st.record_game(moves=35, cv=0.40, cpl=50.0, blunders=1, accuracy=68.0)
        assert len(st.current_session["games"]) == 2

    def test_coherence_score_no_games(self):
        st = SessionTracker()
        assert st.get_coherence_score() == 0.0

    def test_coherence_score_single_game(self):
        st = SessionTracker()
        st.start_session()
        st.record_game(moves=40, cv=0.35, cpl=45.0, blunders=2, accuracy=72.5)
        assert st.get_coherence_score() == 0.0  # need 2+ games

    def test_coherence_score_high_variance(self):
        st = SessionTracker()
        st.start_session()
        st.record_game(moves=40, cv=0.35, cpl=45.0, blunders=2, accuracy=30.0)
        st.record_game(moves=35, cv=0.40, cpl=50.0, blunders=1, accuracy=90.0)
        score = st.get_coherence_score()
        assert score == 0.8  # std > 15

    def test_coherence_score_low_cv(self):
        st = SessionTracker()
        st.start_session()
        st.record_game(moves=40, cv=0.15, cpl=45.0, blunders=2, accuracy=72.0)
        st.record_game(moves=35, cv=0.10, cpl=50.0, blunders=1, accuracy=70.0)
        score = st.get_coherence_score()
        assert score == 0.9  # mean_cv < 0.2

    def test_session_metrics_none(self):
        st = SessionTracker()
        assert st.get_session_metrics() is None

    def test_session_metrics(self):
        st = SessionTracker()
        st.start_session()
        st.record_game(moves=40, cv=0.35, cpl=45.0, blunders=2, accuracy=72.5)
        st.record_game(moves=35, cv=0.40, cpl=50.0, blunders=1, accuracy=68.0)
        m = st.get_session_metrics()
        assert m is not None
        assert m.total_moves == 75
        assert m.games_played == 2
        assert m.peak_accuracy == 72.5
        assert m.average_cv == pytest.approx(0.375, abs=0.01)


class TestSessionMetrics:
    def test_dataclass(self):
        m = SessionMetrics(total_moves=100, average_cv=0.35, average_cpl=45.0, blunder_rate=0.05, peak_accuracy=80.0, duration_minutes=15.0, games_played=3)
        assert m.total_moves == 100
        assert m.games_played == 3
