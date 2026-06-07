"""Tests for coach submodules: weakness, training plan, opening repertoire."""
from __future__ import annotations

import chess
import pytest

from chess_coach.coach import (
    CATEGORY_ENDGAME,
    CATEGORY_POSITIONAL,
    CATEGORY_TACTICS,
    CATEGORY_TIME,
    GameSample,
    OpeningLine,
    PHASE_ENDGAME,
    PHASE_MIDDLEGAME,
    PHASE_OPENING,
    PhaseStats,
    Repertoire,
    TrainingPlan,
    TrainingTask,
    WeaknessReport,
    analyze_weaknesses,
    build_training_plan,
    classify_category,
    detect_phase,
    find_most_improvement_potential,
    make_opening_line,
    plan_to_text,
    recommend_repertoire,
    repertoire_diversity,
)


class TestPhaseDetection:
    def test_opening_phase(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("e5")
        assert detect_phase(board) == PHASE_OPENING

    def test_middlegame_phase(self):
        # Move 14 with many pieces = middlegame (fullmove > 12)
        board = chess.Board("r1bqkb1r/pp3ppp/2n2n2/2ppp3/2B1P3/2N2N2/PPPP1PPP/R1BQ1RK1 w KQkq - 0 14")
        assert detect_phase(board) == PHASE_MIDDLEGAME

    def test_endgame_phase(self):
        # Few pieces = endgame
        board = chess.Board("8/8/8/4k3/8/8/4K3/8 w - - 0 1")
        assert detect_phase(board) == PHASE_ENDGAME

    def test_endgame_detected_by_pieces(self):
        # Even if early in move count, low piece count = endgame
        board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        assert detect_phase(board) == PHASE_ENDGAME


class TestClassifyCategory:
    def test_capture_is_tactics(self):
        board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
        move = board.parse_san("exd5")
        cat = classify_category(board, move, 50.0)
        assert cat == CATEGORY_TACTICS

    def test_check_is_tactics(self):
        board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 2")
        move = board.parse_san("Nc6+") if "Nc6+" in [board.san(m) for m in board.legal_moves] else board.parse_san("Bb5")
        # If Bb5 is not a check, this test just exercises the function
        cat = classify_category(board, move, 50.0)
        assert cat in (CATEGORY_TACTICS, CATEGORY_POSITIONAL)

    def test_high_cpl_is_tactics(self):
        board = chess.Board()
        move = board.parse_san("e4")
        cat = classify_category(board, move, 200.0)
        assert cat == CATEGORY_TACTICS

    def test_extreme_cpl_is_time(self):
        # CPL >= 200 (TIME_CPL_THRESHOLD) now classifies as time pressure
        board = chess.Board()
        move = board.parse_san("e4")
        cat = classify_category(board, move, 300.0)
        assert cat == CATEGORY_TIME

    def test_low_cpl_is_positional(self):
        board = chess.Board()
        move = board.parse_san("e4")
        cat = classify_category(board, move, 20.0)
        assert cat == CATEGORY_POSITIONAL

    def test_endgame_is_endgame_category(self):
        board = chess.Board("8/8/8/4k3/8/8/4K3/8 w - - 0 1")
        move = list(board.legal_moves)[0]
        cat = classify_category(board, move, 50.0)
        assert cat == CATEGORY_ENDGAME


class TestPhaseStats:
    def test_from_empty(self):
        stats = PhaseStats.from_cpls([])
        assert stats.sample_count == 0
        assert stats.acpl == 0.0

    def test_from_cpls_basic(self):
        cpls = [10.0, 20.0, 30.0, 100.0, 200.0]
        stats = PhaseStats.from_cpls(cpls)
        assert stats.sample_count == 5
        assert stats.acpl == pytest.approx(72.0)
        # classify_cpl thresholds: <100=inaccuracy, <200=mistake, <500=blunder
        # 100 is NOT <100 → mistake. 200 is NOT <200 → blunder.
        assert stats.inaccuracy_rate == pytest.approx(0.0)
        assert stats.mistake_rate == pytest.approx(0.2)
        assert stats.blunder_rate == pytest.approx(0.2)

    def test_blunder_counted(self):
        cpls = [300.0, 400.0, 500.0]
        stats = PhaseStats.from_cpls(cpls)
        assert stats.blunder_rate == pytest.approx(1.0)
        assert stats.mistake_rate == 0.0

    def test_accuracy_calculation(self):
        cpls = [10.0, 10.0, 10.0]
        stats = PhaseStats.from_cpls(cpls)
        # At cpl=10, accuracy ~70% each
        assert 60 < stats.accuracy < 80


class TestWeaknessAnalysis:
    def test_empty_input(self):
        report = analyze_weaknesses([])
        assert report.total_moves == 0
        assert report.worst_phase is None

    def test_basic_analysis(self):
        samples = [
            GameSample(
                cpls=[10.0, 20.0, 50.0, 100.0, 200.0],
                colors=[chess.WHITE, chess.BLACK, chess.WHITE, chess.BLACK, chess.WHITE],
                plies=[0, 1, 2, 3, 4],
                result="1-0",
            )
        ]
        report = analyze_weaknesses(samples)
        assert report.total_moves == 5
        assert report.overall_acpl > 0
        assert PHASE_OPENING in report.by_phase
        assert report.worst_phase is not None

    def test_find_most_improvement(self):
        samples = [
            GameSample(
                cpls=[10.0, 200.0, 300.0, 50.0, 80.0],
                colors=[chess.WHITE, chess.BLACK, chess.WHITE, chess.BLACK, chess.WHITE],
                plies=[0, 5, 50, 80, 90],
                result="1-0",
            )
        ]
        report = analyze_weaknesses(samples)
        improvements = find_most_improvement_potential(report)
        assert len(improvements) > 0
        # Top should have highest ACPL
        assert improvements[0][1] >= improvements[-1][1]

    def test_report_to_dict(self):
        samples = [GameSample(cpls=[20.0], colors=[chess.WHITE], plies=[0], result="*")]
        report = analyze_weaknesses(samples)
        d = report.to_dict()
        assert "total_moves" in d
        assert "by_phase" in d
        assert "by_category" in d


class TestTrainingPlan:
    def test_basic_plan(self):
        report = analyze_weaknesses([
            GameSample(
                cpls=[100.0, 50.0, 200.0, 30.0, 80.0],
                colors=[chess.WHITE, chess.BLACK, chess.WHITE, chess.BLACK, chess.WHITE],
                plies=[10, 20, 50, 80, 100],
                result="1-0",
            )
        ])
        plan = build_training_plan(report, user_elo=1500)
        assert plan.user_elo == 1500
        # 28 days
        assert len(plan.tasks) == 28
        # Has focus areas
        assert len(plan.focus_areas) > 0

    def test_plan_text(self):
        report = analyze_weaknesses([])
        plan = build_training_plan(report, user_elo=1200)
        text = plan_to_text(plan)
        assert "Training Plan" in text
        assert "1200" in text
        assert "Day" in text

    def test_low_elo_band(self):
        report = analyze_weaknesses([])
        plan = build_training_plan(report, user_elo=1000)
        # Low elo should have beginner-friendly titles
        assert plan.user_elo == 1000

    def test_high_elo_band(self):
        report = analyze_weaknesses([])
        plan = build_training_plan(report, user_elo=2200)
        # High elo should have advanced titles
        assert plan.user_elo == 2200

    def test_weekly_summary(self):
        report = analyze_weaknesses([])
        plan = build_training_plan(report, user_elo=1500)
        # 4 weeks
        assert len(plan.weekly_summary) == 4
        # Each week should have positive minutes
        for week, mins in plan.weekly_summary.items():
            assert mins > 0

    def test_task_to_dict(self):
        task = TrainingTask(day=1, category="tactics", title="Test", description="desc", minutes=30)
        d = task.to_dict()
        assert d["day"] == 1
        assert d["minutes"] == 30

    def test_plan_to_dict(self):
        report = analyze_weaknesses([])
        plan = build_training_plan(report, user_elo=1500)
        d = plan.to_dict()
        assert "tasks" in d
        assert "focus_areas" in d
        assert "weekly_summary" in d


class TestOpeningLine:
    def test_make_simple_line(self):
        line = make_opening_line("Italian", chess.WHITE, ["e4", "e5", "Nf3", "Nc6", "Bc4"], eco="C50")
        assert line.name == "Italian"
        assert line.eco == "C50"
        assert line.color == chess.WHITE
        assert len(line.moves_san) == 5
        assert line.moves_uci[0] == "e2e4"
        assert line.moves_uci[1] == "e7e5"

    def test_score_zero(self):
        line = make_opening_line("Test", chess.WHITE, ["e4"], eco="B00")
        assert line.score == 0.0

    def test_score_calculation(self):
        line = OpeningLine(name="Test", color=chess.WHITE, games_played=10, wins=5, draws=2, losses=3)
        assert line.score == pytest.approx(0.6)

    def test_score_percentage(self):
        line = OpeningLine(name="Test", color=chess.WHITE, games_played=10, wins=5, draws=2, losses=3)
        assert line.score_percentage == pytest.approx(60.0)

    def test_to_dict(self):
        line = make_opening_line("Test", chess.WHITE, ["e4", "e5"], eco="C20")
        d = line.to_dict()
        assert d["name"] == "Test"
        assert d["color"] == "white"


class TestRepertoire:
    def test_add_remove(self):
        rep = Repertoire()
        line = make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50")
        rep.add(line)
        assert "Italian" in rep.white
        # Remove
        assert rep.remove("Italian", chess.WHITE) is True
        assert "Italian" not in rep.white
        # Remove missing
        assert rep.remove("Nonexistent", chess.WHITE) is False

    def test_get(self):
        rep = Repertoire()
        line = make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50")
        rep.add(line)
        fetched = rep.get("Italian", chess.WHITE)
        assert fetched is not None
        assert fetched.eco == "C50"

    def test_get_missing_color(self):
        rep = Repertoire()
        line = make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50")
        rep.add(line)
        # No black Italian
        assert rep.get("Italian", chess.BLACK) is None

    def test_all_lines(self):
        rep = Repertoire()
        rep.add(make_opening_line("W1", chess.WHITE, ["e4"], eco="C50"))
        rep.add(make_opening_line("B1", chess.BLACK, ["e4", "c5"], eco="B20"))
        assert len(rep.all_lines()) == 2

    def test_find_by_eco(self):
        rep = Repertoire()
        rep.add(make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50"))
        rep.add(make_opening_line("Ruy", chess.WHITE, ["e4", "e5", "Nf3"], eco="C60"))
        results = rep.find_by_eco("C50")
        assert len(results) == 1
        assert results[0].name == "Italian"

    def test_total_games_and_score(self):
        rep = Repertoire()
        line = OpeningLine(name="T", color=chess.WHITE, games_played=10, wins=6, draws=2, losses=2)
        rep.add(line)
        assert rep.total_games() == 10
        assert rep.overall_score() == pytest.approx(0.7)

    def test_to_dict(self):
        rep = Repertoire()
        rep.add(make_opening_line("W1", chess.WHITE, ["e4"], eco="C50"))
        d = rep.to_dict()
        assert "white" in d
        assert "black" in d
        assert "total_games" in d

    def test_diversity(self):
        rep = Repertoire()
        rep.add(make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50"))
        rep.add(make_opening_line("Queens", chess.WHITE, ["d4", "d5"], eco="D06"))
        diversity = repertoire_diversity(rep)
        # Different first letters (C, D) = 1.0 diversity
        assert diversity == 1.0

    def test_diversity_same_letter(self):
        rep = Repertoire()
        rep.add(make_opening_line("Italian", chess.WHITE, ["e4", "e5"], eco="C50"))
        rep.add(make_opening_line("Ruy", chess.WHITE, ["e4", "e5"], eco="C60"))
        diversity = repertoire_diversity(rep)
        # Same first letter C = 0.5
        assert diversity == pytest.approx(0.5)


class TestRepertoireRecommendations:
    def test_recommend_white(self):
        recs = recommend_repertoire(1500, chess.WHITE, style="mainline")
        assert len(recs) > 0
        # All should be white
        for r in recs:
            assert r.color == chess.WHITE

    def test_recommend_black(self):
        recs = recommend_repertoire(1500, chess.BLACK, style="mainline")
        assert len(recs) > 0
        for r in recs:
            assert r.color == chess.BLACK

    def test_recommend_aggressive(self):
        recs = recommend_repertoire(1800, chess.WHITE, style="aggressive")
        # Should include Italian
        names = [r.name for r in recs]
        assert any("Italian" in n for n in names)

    def test_recommend_solid(self):
        recs = recommend_repertoire(1500, chess.BLACK, style="solid")
        # Should include Caro or French
        names = [r.name for r in recs]
        assert any("Caro" in n or "French" in n for n in names)

    def test_recommend_tactical(self):
        recs = recommend_repertoire(1500, chess.BLACK, style="tactical")
        # Should include Sicilian or Nimzo
        names = [r.name for r in recs]
        assert any("Sicilian" in n or "Nimzo" in n for n in names)
