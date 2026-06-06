"""Tests for anti_cheat_risk module."""

from __future__ import annotations

import pytest

from chess_coach.anti_cheat_risk import (
    RiskLevel,
    RISK_LABELS,
    RiskSignals,
    RiskResult,
    compute_risk,
    update_risk_from_history,
)


class TestRiskSignalsDefaults:
    def test_defaults_safe(self) -> None:
        s = RiskSignals()
        r = compute_risk(s)
        # Default signals are human-like
        assert r.score < 50


class TestComputeRisk:
    def test_low_top1_match_safe(self) -> None:
        s = RiskSignals(top1_match_rate=0.30, avg_cpl=50, target_elo=1500,
                       move_time_variance=3.0, blunder_frequency=0.10)
        r = compute_risk(s)
        assert r.level in (RiskLevel.SAFE, RiskLevel.LOW)

    def test_high_top1_match_unsafe(self) -> None:
        s = RiskSignals(top1_match_rate=0.95, avg_cpl=10, target_elo=1500,
                       move_time_variance=1.0, blunder_frequency=0.0)
        r = compute_risk(s)
        # Many top-1 matches, low CPL, low time variance, zero blunders = bot
        assert r.score > 50
        assert r.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_low_time_variance_unsafe(self) -> None:
        s = RiskSignals(top1_match_rate=0.30, avg_cpl=50, target_elo=1500,
                       move_time_variance=0.3, blunder_frequency=0.10)
        r = compute_risk(s)
        # <1s time variance is a strong bot signal — even with mild other signals
        assert r.score > 25

    def test_zero_blunder_unsafe(self) -> None:
        s = RiskSignals(top1_match_rate=0.30, avg_cpl=50, target_elo=1500,
                       move_time_variance=3.0, blunder_frequency=0.0)
        r = compute_risk(s)
        # Zero blunders at 1500 ELO is suspicious
        assert r.score > 20

    def test_score_in_range(self) -> None:
        s = RiskSignals()
        r = compute_risk(s)
        assert 0.0 <= r.score <= 100.0

    def test_recommendation_non_empty(self) -> None:
        s = RiskSignals(top1_match_rate=0.95, avg_cpl=10, target_elo=1500,
                       move_time_variance=1.0, blunder_frequency=0.0)
        r = compute_risk(s)
        assert r.recommendation

    def test_contributions_sum_to_score(self) -> None:
        s = RiskSignals(top1_match_rate=0.85, avg_cpl=15, target_elo=1500,
                       move_time_variance=1.0, blunder_frequency=0.0)
        r = compute_risk(s)
        # All contributions should be non-negative and sum ≈ score
        total = sum(r.contributions.values())
        assert abs(total - r.score) < 0.5

    def test_levels_progression(self) -> None:
        # Increasing top1_match should monotonically increase score
        scores = []
        for rate in (0.1, 0.3, 0.5, 0.7, 0.9):
            s = RiskSignals(top1_match_rate=rate)
            scores.append(compute_risk(s).score)
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1]


class TestUpdateRiskFromHistory:
    def test_empty_history(self) -> None:
        r = update_risk_from_history([])
        assert r.score >= 0
        assert r.score <= 100

    def test_with_history(self) -> None:
        history = [
            {"cpl": 50, "time_s": 5.0, "is_top1": False, "phase": "opening"},
            {"cpl": 60, "time_s": 6.0, "is_top1": False, "phase": "middlegame"},
            {"cpl": 40, "time_s": 4.0, "is_top1": True, "phase": "endgame"},
        ]
        r = update_risk_from_history(history, target_elo=1500)
        assert r.score > 0

    def test_suspicious_history_high_risk(self) -> None:
        # All top-1, zero CPL, uniform timing
        history = [
            {"cpl": 10, "time_s": 5.0, "is_top1": True, "phase": "opening"},
            {"cpl": 8, "time_s": 5.1, "is_top1": True, "phase": "middlegame"},
            {"cpl": 12, "time_s": 5.0, "is_top1": True, "phase": "endgame"},
        ]
        r = update_risk_from_history(history, target_elo=1500)
        assert r.score > 50


class TestRiskLabels:
    def test_all_levels_have_labels(self) -> None:
        for level in RiskLevel:
            assert level in RISK_LABELS
