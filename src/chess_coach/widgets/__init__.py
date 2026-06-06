"""
widgets/__init__.py — Package for standalone widgets.
"""

from chess_coach.widgets.eval_bar import EvalBar, _cp_to_fraction
from chess_coach.widgets.captured_pieces import CapturedPieces
from chess_coach.widgets.clock_widget import ClockWidget
from chess_coach.widgets.wdl_widget import WDLWidget
from chess_coach.widgets.toast import Toast, ToastManager
from chess_coach.widgets.win_prob_chart import WinProbChart
from chess_coach.widgets.settings_dialog import SettingsDialog

__all__ = [
    "EvalBar", "_cp_to_fraction",
    "CapturedPieces",
    "ClockWidget",
    "WDLWidget",
    "Toast", "ToastManager",
    "WinProbChart",
    "SettingsDialog",
]
