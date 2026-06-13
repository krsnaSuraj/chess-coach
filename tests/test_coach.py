"""Tests for coach flow."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"

def _load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _SRC / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

for _pkg in ("chess_coach", "chess_coach.coach"):
    if _pkg not in sys.modules:
        pkg_mod = type(sys)(_pkg)
        pkg_mod.__path__ = [str(_SRC / _pkg.replace(".", "/"))]
        sys.modules[_pkg] = pkg_mod

_side_selector = _load_module("chess_coach.coach.side_selector", "chess_coach/coach/side_selector.py")
_opponent_entry = _load_module("chess_coach.coach.opponent_entry", "chess_coach/coach/opponent_entry.py")

import chess
import pytest

SideSelector = _side_selector.SideSelector
OpponentEntry = _opponent_entry.OpponentEntry


class TestSideSelector:
    def test_select_white(self):
        selector = SideSelector()
        result = selector.select_side("w", rating=1500)
        assert result.side == "w"
        assert result.rating == 1500
    
    def test_select_black(self):
        selector = SideSelector()
        result = selector.select_side("b", rating=1800, classical=0.7)
        assert result.side == "b"
        assert result.rating == 1800
        assert result.classical == 0.7
    
    def test_invalid_side(self):
        selector = SideSelector()
        with pytest.raises(ValueError):
            selector.select_side("x")
    
    def test_is_user_turn_white(self):
        selector = SideSelector()
        selector.select_side("w")
        board = chess.Board()
        assert selector.is_user_turn(board) is True
    
    def test_is_user_turn_black(self):
        selector = SideSelector()
        selector.select_side("b")
        board = chess.Board()
        assert selector.is_user_turn(board) is False


class TestOpponentEntry:
    def test_parse_valid_move(self):
        entry = OpponentEntry()
        board = chess.Board()
        result = entry.parse_move("e2e4", board)
        assert result.is_valid is True
        assert result.move == chess.Move(chess.E2, chess.E4)
    
    def test_parse_invalid_move(self):
        entry = OpponentEntry()
        board = chess.Board()
        result = entry.parse_move("e2e5", board)
        assert result.is_valid is False
        assert result.error is not None
    
    def test_parse_invalid_uci(self):
        entry = OpponentEntry()
        board = chess.Board()
        result = entry.parse_move("xyz", board)
        assert result.is_valid is False
    
    def test_parse_san(self):
        entry = OpponentEntry()
        board = chess.Board()
        result = entry.parse_san("e4", board)
        assert result.is_valid is True
        assert result.move == chess.Move(chess.E2, chess.E4)
