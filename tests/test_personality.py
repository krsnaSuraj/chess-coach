"""Tests for personality module."""

from __future__ import annotations

import chess
import pytest

from chess_coach.personality import (
    PersonalityType,
    PersonalityProfile,
    AGGRESSIVE,
    POSITIONAL,
    TACTICAL,
    DEFENSIVE,
    BALANCED,
    PROFILES,
    get_profile,
    list_personalities,
    bias_move,
)


class TestProfiles:
    def test_all_5_profiles_present(self) -> None:
        assert len(PROFILES) == 5
        for pt in PersonalityType:
            assert pt in PROFILES

    def test_get_profile_by_enum(self) -> None:
        assert get_profile(PersonalityType.AGGRESSIVE) is AGGRESSIVE

    def test_get_profile_by_string(self) -> None:
        assert get_profile("aggressive") is AGGRESSIVE
        assert get_profile("BALANCED") is BALANCED

    def test_get_profile_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            get_profile("nonexistent")

    def test_list_personalities_returns_all(self) -> None:
        plist = list_personalities()
        assert len(plist) == 5
        assert all(isinstance(p, PersonalityProfile) for p in plist)


class TestProfileProperties:
    @pytest.mark.parametrize("profile_name,key,expected_gt", [
        ("AGGRESSIVE", "check_weight", 1.0),
        ("TACTICAL", "recapture_weight", 1.0),
        ("POSITIONAL", "pawn_structure_weight", 1.0),
        ("DEFENSIVE", "king_safety_weight", 1.0),
    ])
    def test_known_strengths(self, profile_name: str, key: str, expected_gt: float) -> None:
        p = globals()[profile_name]
        assert getattr(p, key) > expected_gt, f"{profile_name}.{key} should be > {expected_gt}"

    def test_balanced_has_neutral_weights(self) -> None:
        assert BALANCED.capture_weight == 1.0
        assert BALANCED.check_weight == 1.0
        assert BALANCED.pawn_structure_weight == 1.0

    def test_preferred_openings_are_3char_eco(self) -> None:
        for p in PROFILES.values():
            for eco in p.preferred_openings:
                assert len(eco) == 3
                assert eco[0] in "ABCDE"

    def test_consistency_in_range(self) -> None:
        for p in PROFILES.values():
            assert 0.0 <= p.consistency <= 1.0

    def test_blend_factor_in_range(self) -> None:
        for p in PROFILES.values():
            assert 0.0 <= p.blend_factor <= 1.0


class TestBiasMove:
    def test_returns_in_range(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5"); b.push_san("Nf3")
        for mv in b.legal_moves:
            b_ = b.copy()
            val = bias_move(AGGRESSIVE, b_, mv, phase="middlegame")
            assert 0.5 <= val <= 1.6

    def test_capture_higher_under_aggressive(self) -> None:
        # Set up a position with a clear capture option (white captures a black piece)
        b = chess.Board("r1bqkbnr/ppp1pppp/2n5/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3")
        b2 = b.copy()
        captures = [m for m in b2.legal_moves if b2.is_capture(m)]
        non_caps = [m for m in b2.legal_moves if not b2.is_capture(m)]
        if captures and non_caps:
            cap = captures[0]
            v_cap = bias_move(AGGRESSIVE, b2, cap, phase="middlegame")
            v_ncap = bias_move(AGGRESSIVE, b2, non_caps[0], phase="middlegame")
            assert v_cap > v_ncap, "Aggressive profile should prefer captures"

    def test_phase_changes_bias(self) -> None:
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        moves = list(b.legal_moves)
        if moves:
            v_op = bias_move(AGGRESSIVE, b.copy(), moves[0], phase="opening")
            v_mg = bias_move(AGGRESSIVE, b.copy(), moves[0], phase="middlegame")
            v_eg = bias_move(AGGRESSIVE, b.copy(), moves[0], phase="endgame")
            # Same move, different phase — different bias
            assert not (v_op == v_mg == v_eg)

    def test_recapture_boosts_tactical(self) -> None:
        # Use a simple test: compare bias with/without recapture flag directly
        b2 = chess.Board()
        b2.push_san("e4"); b2.push_san("e5"); b2.push_san("Nf3"); b2.push_san("Nc6")
        for mv in b2.legal_moves:
            if not b2.is_capture(mv):
                v_no = bias_move(TACTICAL, b2, mv, phase="middlegame", is_recapture=False)
                v_yes = bias_move(TACTICAL, b2, mv, phase="middlegame", is_recapture=True)
                assert v_yes > v_no
                break
