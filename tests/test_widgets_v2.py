"""Tests for the 7 new SOTA widgets."""

from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import chess

from chess_coach.widgets import (
    EvalBar, CapturedPieces, ClockWidget, WDLWidget,
    WinProbChart, Toast, ToastManager, SettingsDialog,
)
from chess_coach.theme_manager import get_theme


# ---------------------------------------------------------------------------
# EvalBar
# ---------------------------------------------------------------------------

class TestEvalBar:
    def test_init(self):
        bar = EvalBar()
        assert bar._cp == 0.0

    def test_set_eval_animates(self):
        bar = EvalBar()
        bar.set_eval(150)
        # The animation should be running
        assert bar._target_cp == 150.0

    def test_set_eval_mate(self):
        bar = EvalBar()
        bar.set_eval(None, mate=5)
        assert bar._target_cp == 10000
        assert bar._mate == 5

    def test_set_wdl(self):
        bar = EvalBar()
        bar.set_wdl(40, 30, 30)
        assert bar._wdl == (40, 30, 30)

    def test_cp_to_fraction_zero(self):
        from chess_coach.widgets.eval_bar import _cp_to_fraction
        assert abs(_cp_to_fraction(0)) < 0.01

    def test_cp_to_fraction_positive(self):
        from chess_coach.widgets.eval_bar import _cp_to_fraction
        v = _cp_to_fraction(500)
        assert 0.5 < v < 1.0  # sigmoid 500cp ≈ 0.82

    def test_cp_to_fraction_negative(self):
        from chess_coach.widgets.eval_bar import _cp_to_fraction
        v = _cp_to_fraction(-500)
        assert -1.0 < v < -0.5

    def test_cp_to_fraction_none(self):
        from chess_coach.widgets.eval_bar import _cp_to_fraction
        assert _cp_to_fraction(None) == 0.0

    def test_set_theme(self):
        bar = EvalBar()
        bar.set_theme(get_theme("sepia"))
        assert bar._theme.name == "sepia"

    def test_show_wdl(self):
        bar = EvalBar()
        bar.show_wdl(False)
        assert bar._show_wdl is False


# ---------------------------------------------------------------------------
# CapturedPieces
# ---------------------------------------------------------------------------

class TestCapturedPieces:
    def test_init(self):
        w = CapturedPieces()
        assert w._board.fen() == chess.STARTING_FEN

    def test_set_board(self):
        w = CapturedPieces()
        # After 1.e4 d5 2.exd5, black captured a pawn
        b = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/8/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
        w.set_board(b)
        assert w._board.fen() == b.fen()

    def test_set_theme(self):
        w = CapturedPieces()
        w.set_theme(get_theme("forest"))
        assert w._theme.name == "forest"


# ---------------------------------------------------------------------------
# ClockWidget
# ---------------------------------------------------------------------------

class TestClockWidget:
    def test_init(self):
        w = ClockWidget()
        assert w._white_ms == 5 * 60 * 1000
        assert w._black_ms == 5 * 60 * 1000

    def test_set_time_control(self):
        w = ClockWidget()
        w.set_time_control(3, 2.0)  # 3 min + 2s increment
        assert w._white_ms == 3 * 60 * 1000
        assert w._black_ms == 3 * 60 * 1000

    def test_set_white_ms_clamps_zero(self):
        w = ClockWidget()
        w.set_white_ms(-100)
        assert w._white_ms == 0

    def test_set_black_ms_clamps_zero(self):
        w = ClockWidget()
        w.set_black_ms(-100)
        assert w._black_ms == 0

    def test_format_time_zero(self):
        assert ClockWidget._format_time(0) == "0:00.0"

    def test_format_time_minutes(self):
        s = ClockWidget._format_time(5 * 60 * 1000)
        assert s == "5:00"

    def test_format_time_seconds(self):
        s = ClockWidget._format_time(65 * 1000)
        assert s == "1:05"

    def test_format_time_tenths_below_10s(self):
        s = ClockWidget._format_time(5 * 1000)
        assert s.startswith("0:05.")
        assert len(s) >= 6

    def test_set_theme(self):
        w = ClockWidget()
        w.set_theme(get_theme("lichess"))
        assert w._theme.name == "lichess"


# ---------------------------------------------------------------------------
# WDLWidget
# ---------------------------------------------------------------------------

class TestWDLWidget:
    def test_init(self):
        w = WDLWidget()
        assert w._w + w._d + w._l == 100  # sums to 100

    def test_set_wdl_normalized(self):
        w = WDLWidget()
        w.set_wdl(60, 20, 20)
        assert w._w + w._d + w._l == 100

    def test_set_wdl_unnormalized(self):
        w = WDLWidget()
        w.set_wdl(120, 40, 40)  # 200 total
        # Should normalize to 60/20/20
        assert w._w == 60
        assert w._d == 20
        assert w._l == 20

    def test_set_theme(self):
        w = WDLWidget()
        w.set_theme(get_theme("cyber_neon"))
        assert w._theme.name == "cyber_neon"


# ---------------------------------------------------------------------------
# WinProbChart
# ---------------------------------------------------------------------------

class TestWinProbChart:
    def test_init(self):
        w = WinProbChart()
        assert len(w._data) == 0

    def test_add_wp(self):
        w = WinProbChart()
        w.add_wp(50.0)
        w.add_wp(60.0)
        assert list(w._data) == [50.0, 60.0]

    def test_set_data(self):
        w = WinProbChart()
        w.set_data([30.0, 40.0, 50.0, 60.0])
        assert list(w._data) == [30.0, 40.0, 50.0, 60.0]

    def test_clear(self):
        w = WinProbChart()
        w.add_wp(50.0)
        w.clear()
        assert len(w._data) == 0

    def test_maxlen_caps(self):
        w = WinProbChart(max_points=3)
        w.add_wp(10.0)
        w.add_wp(20.0)
        w.add_wp(30.0)
        w.add_wp(40.0)  # overwrites first
        assert list(w._data) == [20.0, 30.0, 40.0]

    def test_critical_threshold(self):
        assert WinProbChart.CRITICAL_THRESHOLD == 10.0

    def test_set_theme(self):
        w = WinProbChart()
        w.set_theme(get_theme("marble"))
        assert w._theme.name == "marble"


# ---------------------------------------------------------------------------
# Toast / ToastManager
# ---------------------------------------------------------------------------

class TestToast:
    def test_init_default(self):
        t = Toast("Hello")
        # Window flags, no widget parent - just constructable
        assert t._icon in ("ℹ", "✓", "⚠", "✕", "★", "•")

    def test_severity_to_color(self):
        t = Toast("X", severity="success")
        assert t._border_color.name() == get_theme().success

    def test_severity_to_color_warning(self):
        t = Toast("X", severity="warning")
        assert t._border_color.name() == get_theme().warning

    def test_severity_to_color_danger(self):
        t = Toast("X", severity="danger")
        assert t._border_color.name() == get_theme().danger


class TestToastManager:
    def test_init(self, qtbot_shim):
        from PyQt6.QtWidgets import QWidget
        parent = QWidget()
        qtbot_shim.addWidget(parent)
        tm = ToastManager(parent)
        assert len(tm._toasts) == 0

    def test_show_adds_toast(self, qtbot_shim):
        from PyQt6.QtWidgets import QWidget
        parent = QWidget()
        qtbot_shim.addWidget(parent)
        tm = ToastManager(parent)
        toast = tm.show("Hello")
        assert len(tm._toasts) == 1


# ---------------------------------------------------------------------------
# SettingsDialog
# ---------------------------------------------------------------------------

class TestSettingsDialog:
    def test_init(self, qtbot_shim):
        from PyQt6.QtWidgets import QWidget
        from chess_coach.theme_manager import ThemeManager
        parent = QWidget()
        qtbot_shim.addWidget(parent)
        config = {"engine": {}, "humanizer": {}, "display": {}}
        dlg = SettingsDialog(config, ThemeManager(), None, parent)
        qtbot_shim.addWidget(dlg)
        assert dlg.windowTitle() == "Settings"
