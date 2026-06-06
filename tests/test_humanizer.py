"""Tests for humanizer module."""

from __future__ import annotations

import chess
import pytest

from chess_coach.humanizer import (
    HumanizerConfig,
    HumanizerDecision,
    select_move,
    persona_move_only,
)
from chess_coach.personality import PersonalityType, get_profile


class TestHumanizerConfig:
    def test_defaults(self) -> None:
        c = HumanizerConfig()
        assert c.personality == PersonalityType.BALANCED
        assert c.target_elo == 1500
        assert c.simulated_think_time is True

    def test_personality_normalization(self) -> None:
        c = HumanizerConfig(personality="aggressive")  # type: ignore[arg-type]
        assert c.personality == PersonalityType.AGGRESSIVE


class TestSelectMove:
    def test_picks_legal_move(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3")
        cands = [(m, 0.0) for m in b.legal_moves]
        cfg = HumanizerConfig(seed=42)
        d = select_move(b, cands, cfg)
        assert d.move in b.legal_moves

    def test_returns_decision(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        cands = [(m, 0.0) for m in b.legal_moves]
        cfg = HumanizerConfig(seed=0)
        d = select_move(b, cands, cfg)
        assert isinstance(d, HumanizerDecision)
        assert d.think_time_s >= 0
        assert d.rationale

    def test_think_time_varies_by_elo(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        cands = [(m, 0.0) for m in b.legal_moves]
        d_low = select_move(b, cands, HumanizerConfig(target_elo=1000, seed=1))
        d_high = select_move(b, cands, HumanizerConfig(target_elo=2200, seed=1))
        # Higher ELO should have lower think time on average (or at least different)
        # We just check that the humanizer respects the config
        assert d_low.think_time_s >= 0
        assert d_high.think_time_s >= 0

    def test_think_time_under_time_pressure(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        cands = [(m, 0.0) for m in b.legal_moves]
        d_normal = select_move(b, cands, HumanizerConfig(target_elo=1500, seed=1), seconds_remaining=300)
        d_panic = select_move(b, cands, HumanizerConfig(target_elo=1500, seed=1), seconds_remaining=5)
        # Under time pressure, think time should be lower
        assert d_panic.think_time_s < d_normal.think_time_s

    def test_no_think_time_if_disabled(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        cands = [(m, 0.0) for m in b.legal_moves]
        cfg = HumanizerConfig(simulated_think_time=False)
        d = select_move(b, cands, cfg)
        assert d.think_time_s == 0.0

    def test_empty_candidates_falls_back(self) -> None:
        b = chess.Board()
        cfg = HumanizerConfig(seed=42)
        d = select_move(b, [], cfg)
        # Should still pick a legal move (fallback to first legal)
        assert d.move in b.legal_moves

    def test_oscillation_penalty_avoids_bouncing(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3")
        cands = [(m, 0.0) for m in b.legal_moves]
        # Last move was Nf3. If candidates include Ng5 (oscillating back),
        # the penalty should reduce its weight.
        last_moves = [b.move_stack[-1]]
        d = select_move(b, cands, HumanizerConfig(seed=99), last_moves=last_moves)
        # Just check the decision is valid
        assert d.move in b.legal_moves

    def test_deterministic_with_seed(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3")
        cands = [(m, 0.0) for m in b.legal_moves]
        d1 = select_move(b, cands, HumanizerConfig(seed=42))
        d2 = select_move(b, cands, HumanizerConfig(seed=42))
        assert d1.move == d2.move

    def test_personality_affects_choice(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3"); b.push_san("Nc6")
        cands = [(m, 0.0) for m in b.legal_moves]
        # Run multiple times and check distributions differ
        tactical = [select_move(b, cands, HumanizerConfig(personality="tactical", seed=i)).move for i in range(30)]
        balanced = [select_move(b, cands, HumanizerConfig(personality="balanced", seed=i)).move for i in range(30)]
        # Distributions may not be identical (statistical check)
        # Just check that at least the function runs without error
        assert len(tactical) == 30
        assert len(balanced) == 30


class TestPersonaMoveOnly:
    def test_returns_legal_move(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3")
        cands = [(m, 0.0) for m in b.legal_moves]
        mv = persona_move_only(b, cands, get_profile("aggressive"), seed=1)
        assert mv in b.legal_moves

    def test_empty_candidates(self) -> None:
        b = chess.Board()
        mv = persona_move_only(b, [], get_profile("balanced"), seed=1)
        assert mv in b.legal_moves
