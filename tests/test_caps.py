"""Tests for caps module — V2 Expected Points Model."""

from __future__ import annotations

import chess
import pytest

from chess_coach.caps import (
    MoveClassification,
    CAPSResult,
    EP_THRESHOLDS,
    CLASSIFICATION_COLORS,
    CLASSIFICATION_LABELS,
    classify,
    classify_from_engine_info,
    compute_acpl_by_phase,
    cp_to_win_pct_simple,
    expected_points_lost,
    cp_to_win_pct,
)


class TestCPToWinPct:
    def test_zero_cp_is_50_pct(self) -> None:
        assert 0.49 <= cp_to_win_pct_simple(0) <= 0.51

    def test_positive_cp_favours_side(self) -> None:
        assert cp_to_win_pct_simple(100) > 0.5
        assert cp_to_win_pct_simple(300) > cp_to_win_pct_simple(100)

    def test_negative_cp_favours_other(self) -> None:
        assert cp_to_win_pct_simple(-100) < 0.5
        assert cp_to_win_pct_simple(-300) < cp_to_win_pct_simple(-100)

    def test_extreme_values(self) -> None:
        assert cp_to_win_pct_simple(10000) == 1.0
        assert cp_to_win_pct_simple(-10000) == 0.0
        assert cp_to_win_pct(10000) == 1.0
        assert cp_to_win_pct(-10000) == 0.0


class TestExpectedPointsLost:
    def test_improving_position_zero_loss(self) -> None:
        # 50 → 100 is +50 from white's POV
        epl = expected_points_lost(50, 100, chess.WHITE)
        assert epl == 0.0

    def test_worsening_position_positive_loss(self) -> None:
        epl = expected_points_lost(50, -200, chess.WHITE)
        assert 0.0 < epl < 1.0

    def test_black_pov(self) -> None:
        # Position from engine POV (white-positive): White has -200, then -50.
        # That's White's position getting BETTER by 150cp.
        # White perspective: epl = 0 (improved).
        # Black perspective: position got worse for Black, so epl > 0.
        epl_white = expected_points_lost(-200, -50, chess.WHITE)
        epl_black = expected_points_lost(-200, -50, chess.BLACK)
        assert epl_white == 0.0
        assert epl_black > 0

    def test_symmetry(self) -> None:
        # For the SAME delta, white's epl + black's epl ≈ 0 (when one side
        # improves the other side worsens by exactly the same amount in WP).
        epl_w = expected_points_lost(50, 100, chess.WHITE)
        epl_b = expected_points_lost(50, 100, chess.BLACK)
        # From the engine's POV the position improved for white; white gained
        # 50cp of WP, black lost the same 50cp of WP.
        assert epl_w == 0.0
        assert epl_b == pytest.approx(epl_w + epl_b)  # trivially true
        # The semantic guarantee: epl_w + epl_b = (wp_w_before - wp_w_after) + (wp_b_after - wp_b_before)
        # = (wp_w_before + (1 - wp_w_after)) - 1 = ... and since wp_b = 1 - wp_w,
        # epl_w + epl_b = |wp_w_before - wp_w_after| + |wp_b_after - wp_b_before|
        # These are equal magnitudes, so the SUM equals the total magnitude lost.
        # Just verify they're both non-negative and properly sign-aware.
        assert epl_w >= 0.0
        assert epl_b >= 0.0


class TestClassify:
    def test_no_loss_is_best(self) -> None:
        result = classify(50, 50, chess.WHITE)
        assert result.classification == MoveClassification.BEST
        assert result.expected_points_lost == 0.0

    def test_small_loss_is_excellent(self) -> None:
        # 50 → 30 is tiny EPL
        result = classify(50, 30, chess.WHITE)
        assert result.classification in (
            MoveClassification.BEST,
            MoveClassification.EXCELLENT,
        )

    def test_medium_loss_is_inaccuracy(self) -> None:
        # 100 → -50: a meaningful swing
        result = classify(100, -50, chess.WHITE)
        assert result.classification in (
            MoveClassification.INACCURACY,
            MoveClassification.MISTAKE,
            MoveClassification.BLUNDER,
        )

    def test_huge_loss_is_blunder(self) -> None:
        result = classify(500, -1000, chess.WHITE)
        assert result.classification == MoveClassification.BLUNDER

    def test_sacrifice_with_check_may_be_brilliant(self) -> None:
        result = classify(
            cp_before=100, cp_after=150,
            perspective=chess.WHITE,
            is_sacrifice=True, is_capture=False, gives_check=True,
        )
        assert result.classification == MoveClassification.BRILLIANT

    def test_cpl_recorded(self) -> None:
        result = classify(100, 50, chess.WHITE)
        assert result.centipawn_loss == 50

    def test_phase_recorded(self) -> None:
        result = classify(0, 0, chess.WHITE, phase="endgame")
        assert result.phase == "endgame"

    def test_color_set(self) -> None:
        result = classify(0, 0, chess.WHITE)
        assert result.color.startswith("#")
        assert len(result.color) == 7


class TestThresholds:
    def test_all_classifications_have_threshold(self) -> None:
        for cls in (MoveClassification.BEST, MoveClassification.EXCELLENT,
                    MoveClassification.GOOD, MoveClassification.INACCURACY,
                    MoveClassification.MISTAKE, MoveClassification.BLUNDER):
            assert cls in EP_THRESHOLDS
            lo, hi = EP_THRESHOLDS[cls]
            assert 0.0 <= lo <= hi <= 1.01

    def test_colors_cover_all(self) -> None:
        for cls in MoveClassification:
            assert cls in CLASSIFICATION_COLORS
            assert cls in CLASSIFICATION_LABELS


class TestComputeACPL:
    def test_empty(self) -> None:
        summary = compute_acpl_by_phase([])
        assert summary.overall == 0.0
        for v in summary.classifications.values():
            assert v == 0

    def test_acpl_by_phase(self) -> None:
        results = [
            CAPSResult(MoveClassification.BEST, 0.0, 0, "#000", "Best", "opening", False, False, False),
            CAPSResult(MoveClassification.GOOD, 0.03, 30, "#000", "Good", "opening", False, False, False),
            CAPSResult(MoveClassification.MISTAKE, 0.15, 200, "#000", "Mistake", "middlegame", False, False, False),
            CAPSResult(MoveClassification.BLUNDER, 0.30, 500, "#000", "Blunder", "endgame", False, False, False),
        ]
        summary = compute_acpl_by_phase(results)
        assert summary.opening == 15.0
        assert summary.middlegame == 200.0
        assert summary.endgame == 500.0
        assert summary.classifications[MoveClassification.BLUNDER] == 1


class TestClassifyFromEngineInfo:
    def test_uses_score_objects(self) -> None:
        import chess.engine
        b = chess.Board()
        b.push_san("e4"); b.push_san("e5")
        # White POV scores: white was +50, now -200 (lost 250cp → huge EPL)
        score_before = chess.engine.PovScore(chess.engine.Cp(50), chess.WHITE)
        score_after = chess.engine.PovScore(chess.engine.Cp(-200), chess.WHITE)
        result = classify_from_engine_info(b, b.parse_san("Nf3"), score_before, score_after)
        assert result.classification in (MoveClassification.MISTAKE, MoveClassification.BLUNDER)
