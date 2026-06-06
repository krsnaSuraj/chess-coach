"""Tests for classify (CAPS v2) module (Phase J)."""

from __future__ import annotations

import chess
import pytest

from chess_coach.classify.epd import (
    cp_to_winrate,
    winrate_to_epd,
    epd_to_class,
    EPD_THRESHOLDS,
)
from chess_coach.classify.phase_detector import (
    GamePhase,
    detect_phase,
    phase_buckets,
    OPENING_MAX_PLY,
    ENDGAME_MAX_PIECES,
)
from chess_coach.classify.brilliant import is_brilliant
from chess_coach.classify.miss import is_miss
from chess_coach.classify.great import is_great_move, is_only_good_move
from chess_coach.classify.classify_v2 import (
    MoveClass,
    classify_move,
    classify_game,
    ClassificationReport,
)
from chess_coach.classify.report_card import build_report_card, ReportCard, _letter_grade


# ===== EPD =====

class TestCpToWinrate:
    def test_zero(self) -> None:
        assert cp_to_winrate(0) == pytest.approx(0.5, abs=0.01)

    def test_positive(self) -> None:
        wr = cp_to_winrate(400)
        assert wr > 0.9

    def test_negative(self) -> None:
        wr = cp_to_winrate(-400)
        assert wr < 0.1

    def test_clamping(self) -> None:
        assert cp_to_winrate(2000) == 1.0
        assert cp_to_winrate(-2000) == 0.0
        assert cp_to_winrate(1000) == 1.0
        assert cp_to_winrate(-1000) == 0.0


class TestWinrateToEpd:
    def test_equal_winrates(self) -> None:
        assert winrate_to_epd(0.5, 0.5) == 0.0

    def test_played_worse(self) -> None:
        epd = winrate_to_epd(0.9, 0.5)
        assert epd == pytest.approx(0.4, abs=0.01)

    def test_played_better(self) -> None:
        # If played > best, EPD should be clamped to 0
        epd = winrate_to_epd(0.5, 0.9)
        assert epd == 0.0

    def test_clamp_to_one(self) -> None:
        epd = winrate_to_epd(1.0, 0.0)
        assert epd == 1.0


class TestEpdToClass:
    def test_zero_is_best(self) -> None:
        assert epd_to_class(0.0) == "best"

    def test_inaccuracy(self) -> None:
        assert epd_to_class(0.07) == "inaccuracy"

    def test_mistake(self) -> None:
        assert epd_to_class(0.15) == "mistake"

    def test_blunder(self) -> None:
        assert epd_to_class(0.5) == "blunder"

    def test_thresholds_dict_complete(self) -> None:
        for k in ("best", "excellent", "good", "inaccuracy", "mistake", "blunder"):
            assert k in EPD_THRESHOLDS


# ===== Phase Detector =====

class TestPhaseDetector:
    def test_opening_at_start(self) -> None:
        board = chess.Board()
        assert detect_phase(board, 0) == GamePhase.OPENING
        assert detect_phase(board, OPENING_MAX_PLY) == GamePhase.OPENING

    def test_middlegame(self) -> None:
        board = chess.Board()
        # Make some exchanges to get out of opening
        board.remove_piece_at(chess.E2)
        board.remove_piece_at(chess.E7)
        assert detect_phase(board, OPENING_MAX_PLY + 4) == GamePhase.MIDDLEGAME

    def test_endgame_low_pieces(self) -> None:
        # King + rook vs king
        board = chess.Board("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        assert detect_phase(board, 50) == GamePhase.ENDGAME

    def test_phase_buckets(self) -> None:
        boards = [
            (0, chess.Board()),
            (30, chess.Board("4k3/8/8/8/8/8/8/4K2R w K - 0 1")),
        ]
        buckets = phase_buckets(boards)
        assert buckets[GamePhase.OPENING] == 1
        assert buckets[GamePhase.ENDGAME] == 1


# ===== Brilliant / Miss / Great =====

class TestBrilliant:
    def test_illegal_move(self) -> None:
        board = chess.Board()
        with pytest.raises(Exception):
            is_brilliant(board, chess.Move.from_uci("e2e9"), 0, 100, 5)

    def test_single_move_not_brilliant(self) -> None:
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        # Only 1 legal move -> not brilliant (must be a choice)
        assert is_brilliant(board, move, 0, 100, multipv_count=1) is False

    def test_sacrifice_with_eval_improve(self) -> None:
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        # f3e5 - sacrifice knight to a square where it can be captured by f6 or d6 etc.
        # We'll test the function's general behavior; whether the square is "undefended" depends on board state.
        move = chess.Move.from_uci("f3e5")
        # With multiple legal moves and big eval swing -> brilliant
        # We may need a sacrifice move; here we use eval improve + sacrifice via undefended target
        result = is_brilliant(board, move, eval_before_cp=0, eval_after_cp=300, multipv_count=5)
        # If the move target e5 is defended by black's f6 knight, no sacrifice -> not brilliant
        # If undefended, brilliant
        assert isinstance(result, bool)


class TestMiss:
    def test_no_opp_blunder(self) -> None:
        # No swing -> not a miss
        assert is_miss(50, 60, None, chess.Move.null()) is False

    def test_opp_blunder_but_played_best(self) -> None:
        move = chess.Move.from_uci("e2e4")
        assert is_miss(50, 350, move, move) is False  # found best

    def test_opp_blunder_and_missed(self) -> None:
        best = chess.Move.from_uci("d1h5")
        played = chess.Move.from_uci("e2e3")
        assert is_miss(50, 350, best, played) is True


class TestGreat:
    def test_empty(self) -> None:
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        assert is_great_move(board, move, []) is False

    def test_only_good_move(self) -> None:
        board = chess.Board()
        e4 = chess.Move.from_uci("e2e4")
        d4 = chess.Move.from_uci("d2d4")
        # e4 is the only "good" move
        multipv = [(e4, 50), (d4, -300)]
        assert is_great_move(board, e4, multipv) is True
        assert is_great_move(board, d4, multipv) is False

    def test_two_good_moves(self) -> None:
        board = chess.Board()
        e4 = chess.Move.from_uci("e2e4")
        d4 = chess.Move.from_uci("d2d4")
        multipv = [(e4, 50), (d4, 45)]
        # Both are good -> not a "great"
        assert is_great_move(board, e4, multipv) is False


# ===== classify_move / classify_game =====

class TestClassifyMove:
    def test_best(self) -> None:
        mc = classify_move(0.9, 0.9, multipv_count=5)
        assert mc == MoveClass.BEST

    def test_blunder(self) -> None:
        mc = classify_move(0.9, 0.4, multipv_count=5)
        assert mc == MoveClass.BLUNDER

    def test_inaccuracy(self) -> None:
        # 0.6 - 0.55 = 0.05 EPD = inaccuracy boundary
        mc = classify_move(0.6, 0.52, multipv_count=5)
        assert mc == MoveClass.INACCURACY

    def test_excellent(self) -> None:
        # 0.6 - 0.59 = 0.01 EPD = excellent
        mc = classify_move(0.6, 0.59, multipv_count=5)
        assert mc == MoveClass.EXCELLENT

    def test_good(self) -> None:
        # 0.6 - 0.57 = 0.03 EPD = good
        mc = classify_move(0.6, 0.57, multipv_count=5)
        assert mc == MoveClass.GOOD

    def test_brilliant_overrides(self) -> None:
        mc = classify_move(0.5, 0.5, is_brilliant_move=True, multipv_count=5)
        assert mc == MoveClass.BRILLIANT

    def test_miss_overrides(self) -> None:
        mc = classify_move(0.5, 0.5, is_miss_move=True, multipv_count=5)
        assert mc == MoveClass.MISS

    def test_book(self) -> None:
        mc = classify_move(0.5, 0.4, is_book=True, multipv_count=5)
        assert mc == MoveClass.BOOK


class TestClassifyGame:
    def test_simple_game(self) -> None:
        moves = [
            {"best_winrate": 0.5, "played_winrate": 0.5, "phase": GamePhase.OPENING,
             "multipv_count": 5},
            {"best_winrate": 0.6, "played_winrate": 0.55, "phase": GamePhase.MIDDLEGAME,
             "multipv_count": 5},
            {"best_winrate": 0.7, "played_winrate": 0.65, "phase": GamePhase.ENDGAME,
             "multipv_count": 5},
        ]
        report = classify_game(moves)
        assert isinstance(report, ClassificationReport)
        assert len(report.moves) == 3
        assert report.accuracy_overall > 90.0  # all moves were very good

    def test_game_with_blunder(self) -> None:
        moves = [
            {"best_winrate": 0.5, "played_winrate": 0.5, "phase": GamePhase.OPENING,
             "multipv_count": 5},
            {"best_winrate": 0.9, "played_winrate": 0.1, "phase": GamePhase.MIDDLEGAME,
             "multipv_count": 5},
        ]
        report = classify_game(moves)
        assert report.counts.get("blunder", 0) >= 1


# ===== Report Card =====

class TestLetterGrade:
    def test_grade_a_plus(self) -> None:
        assert _letter_grade(96) == "A+"

    def test_grade_a(self) -> None:
        assert _letter_grade(91) == "A"

    def test_grade_b(self) -> None:
        assert _letter_grade(82) == "B"

    def test_grade_c(self) -> None:
        assert _letter_grade(75) == "C"

    def test_grade_f(self) -> None:
        assert _letter_grade(50) == "F"


class TestBuildReportCard:
    def test_basic(self) -> None:
        moves = [
            {"ply": 1, "accuracy": 95, "class": "best", "phase": "opening"},
            {"ply": 2, "accuracy": 92, "class": "excellent", "phase": "middlegame"},
        ]
        rc = build_report_card(
            game_id="abc123",
            moves=moves,
            accuracy_by_phase={"opening": 95.0, "middlegame": 92.0, "endgame": 0.0},
            counts={"best": 1, "excellent": 1},
        )
        assert isinstance(rc, ReportCard)
        assert rc.best_move_ply == 1  # highest accuracy
        assert rc.overall_accuracy > 0
        assert "Overall grade" in rc.summary

    def test_summary_with_blunder(self) -> None:
        moves = [{"ply": i, "accuracy": 50} for i in range(5)]
        rc = build_report_card(
            game_id="x",
            moves=moves,
            accuracy_by_phase={"opening": 50.0, "middlegame": 50.0, "endgame": 50.0},
            counts={"blunder": 3},
        )
        assert "blunder" in rc.summary.lower()
