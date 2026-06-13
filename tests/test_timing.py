"""Tests for timing simulation."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SRC = Path(__file__).resolve().parent.parent / "src"

def _load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _SRC / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

for _pkg in ("chess_coach", "chess_coach.timing", "chess_coach.anti_detect"):
    if _pkg not in sys.modules:
        pkg_mod = type(sys)(_pkg)
        pkg_mod.__path__ = [str(_SRC / _pkg.replace(".", "/"))]
        sys.modules[_pkg] = pkg_mod

_base = _load_module("chess_coach.engines.base", "chess_coach/engines/base.py")
_nova = _load_module("chess_coach.engines.nova", "chess_coach/engines/nova.py")
_signals = _load_module("chess_coach.anti_detect.signals", "chess_coach/anti_detect/signals.py")
_model = _load_module("chess_coach.timing.model", "chess_coach/timing/model.py")
_simulator = _load_module("chess_coach.timing.simulator", "chess_coach/timing/simulator.py")

import chess
import numpy as np

ThinkTimeModel = _model.ThinkTimeModel
ThinkTimeConfig = _model.ThinkTimeConfig
TimingSimulator = _simulator.TimingSimulator


class TestThinkTimeModel:
    def test_opening_think_time(self):
        config = ThinkTimeConfig(rating=1500)
        model = ThinkTimeModel(config)
        board = chess.Board()
        think_time = model.calculate_think_time(board, remaining_time=600, move_number=1)
        assert 0.5 <= think_time <= 10.0
    
    def test_middlegame_think_time(self):
        config = ThinkTimeConfig(rating=1500)
        model = ThinkTimeModel(config)
        board = chess.Board()
        think_time = model.calculate_think_time(board, remaining_time=600, move_number=20)
        assert 1.0 <= think_time <= 20.0
    
    def test_time_pressure(self):
        config = ThinkTimeConfig(rating=1500)
        model = ThinkTimeModel(config)
        board = chess.Board()
        think_time = model.calculate_think_time(board, remaining_time=20, move_number=20)
        assert think_time < 5.0
    
    def test_cv_calculation(self):
        config = ThinkTimeConfig(rating=1500)
        model = ThinkTimeModel(config)
        for _ in range(10):
            model.calculate_think_time(chess.Board(), 600, 1)
        cv = model.get_cv()
        assert 0.2 <= cv <= 0.6


class TestTimingSimulator:
    def test_simulator_get_think_time(self):
        config = ThinkTimeConfig(rating=1500)
        simulator = TimingSimulator(config)
        board = chess.Board()
        think_time = simulator.get_think_time(board, remaining_time=600, move_number=1)
        assert think_time > 0
    
    def test_simulator_cv_check(self):
        config = ThinkTimeConfig(rating=1500)
        simulator = TimingSimulator(config)
        for _ in range(10):
            simulator.get_think_time(chess.Board(), 600, 1)
        cv = simulator._estimate_cv()
        assert cv > 0.25
