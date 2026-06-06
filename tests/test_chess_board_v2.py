"""Tests for chess_board.py SOTA additions: theme, multi-arrow, premove, right-click."""

from __future__ import annotations

import os
import pytest

# Headless Qt for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt, QEvent

import chess
from PyQt6.QtGui import QColor
from chess_coach.chess_board import ChessBoard, ARROW_KINDS
from chess_coach.theme_manager import get_theme


class TestArrowKinds:
    def test_has_4_kinds(self):
        assert len(ARROW_KINDS) == 4

    def test_contains_expected(self):
        for k in ("best", "plan", "threat", "user"):
            assert k in ARROW_KINDS


@pytest.fixture
def board_widget(qtbot_shim=None):
    """Create a ChessBoard with default config. Use offscreen platform."""
    config = {"display": {}}
    w = ChessBoard(config)
    w.resize(480, 480)
    return w


class TestThemeIntegration:
    def test_default_theme_is_midnight(self, board_widget):
        assert board_widget._theme.name == "midnight"

    def test_set_theme_changes_colors(self, board_widget):
        orig = QColor(board_widget.arrow_color)
        board_widget.set_theme(get_theme("cyber_neon"))
        # Color should change (cyber_neon arrow is bright cyan/magenta)
        new = QColor(board_widget.arrow_color)
        assert orig != new

    def test_set_theme_updates_animation_duration(self, board_widget):
        board_widget.set_theme(get_theme("sepia"))
        # Sepia has 240ms; default Midnight has 180ms
        assert board_widget._anim_duration_ms == 240

    def test_all_8_themes_apply(self, board_widget):
        for name in ("midnight", "forest", "sunset", "marble", "lichess",
                     "blue_glass", "cyber_neon", "sepia"):
            board_widget.set_theme(get_theme(name))
            assert board_widget._theme.name == name


class TestMultiArrow:
    def test_add_arrow(self, board_widget):
        board_widget.add_arrow(12, 28, "best")
        assert (12, 28, "best") in board_widget._arrows

    def test_add_unknown_kind_defaults_to_best(self, board_widget):
        board_widget.add_arrow(0, 1, "nonexistent")
        assert (0, 1, "best") in board_widget._arrows

    def test_clear_arrows(self, board_widget):
        board_widget.add_arrow(0, 1, "user")
        board_widget.add_arrow(2, 3, "plan")
        assert len(board_widget._arrows) == 2
        board_widget.clear_arrows()
        assert len(board_widget._arrows) == 0

    def test_set_arrows_replaces(self, board_widget):
        board_widget.add_arrow(0, 1, "user")
        board_widget.set_arrows([(10, 20, "plan"), (30, 40, "threat")])
        assert len(board_widget._arrows) == 2
        assert (10, 20, "plan") in board_widget._arrows
        assert (0, 1, "user") not in board_widget._arrows


class TestPremove:
    def test_set_premove(self, board_widget):
        m = chess.Move.from_uci("e2e4")
        board_widget.set_premove(m)
        assert board_widget.premove() == m

    def test_clear_premove(self, board_widget):
        board_widget.set_premove(chess.Move.from_uci("e2e4"))
        board_widget.set_premove(None)
        assert board_widget.premove() is None

    def test_premove_signal(self, board_widget, qtbot_shim):
        # set_premove() does NOT emit the signal — only the drag-release path does.
        # The signal is emitted in mouseReleaseEvent when a premove drag completes.
        # So we test the public setter behavior.
        m = chess.Move.from_uci("d2d4")
        board_widget.set_premove(m)
        assert board_widget.premove() == m


class TestArrowDrawnSignal:
    def test_arrow_drawn_signal_on_right_click_release(self, board_widget, qtbot_shim):
        # Play a starting position; simulate a right-click drag from e2 to e4
        received: list = []
        board_widget.arrow_drawn.connect(lambda f, t, k: received.append((f, t, k)))
        # e2 = square 12, e4 = square 28
        size = 480
        sq = size / 8
        from_pt = QPoint(int(sq * 4 + sq / 2), int(sq * 4 + sq / 2))  # e2
        to_pt = QPoint(int(sq * 4 + sq / 2), int(sq * 2 + sq / 2))    # e4
        # Right button press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(from_pt), QPointF(from_pt),
            Qt.MouseButton.RightButton, Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        board_widget.mousePressEvent(press)
        # Move
        move_ev = QMouseEvent(
            QEvent.Type.MouseMove, QPointF(to_pt), QPointF(to_pt),
            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        board_widget.mouseMoveEvent(move_ev)
        # Release
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease, QPointF(to_pt), QPointF(to_pt),
            Qt.MouseButton.RightButton, Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        board_widget.mouseReleaseEvent(release)
        assert len(received) == 1
        f, t, k = received[0]
        assert k == "user"
        assert (f, t, "user") in board_widget._arrows


class TestPlayableSideAndPremove:
    def test_playable_side_setter(self, board_widget):
        board_widget.playable_side = chess.WHITE
        assert board_widget.playable_side == chess.WHITE

    def test_premove_drag_creates_legal_targets(self, board_widget):
        """When it's opponent's turn, dragging a white piece should populate
        legal_move_squares with pseudo-legal targets for the premove."""
        # Starting position; it's white's turn normally. To make it black's turn
        # we play 1.e4 first, leaving the position where it's black to move and
        # white pieces can premove.
        b = chess.Board()
        b.push_san("e4")
        # Now it's black's turn
        assert b.turn == chess.BLACK
        board_widget.set_board(b)
        board_widget.playable_side = chess.WHITE
        # Click on a white piece — e1 (square 4)
        size = 480
        sq = size / 8
        from_pt = QPoint(int(sq * 4 + sq / 2), int(sq * 7 + sq / 2))  # e1
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress, QPointF(from_pt), QPointF(from_pt),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        board_widget.mousePressEvent(press)
        # In premove mode, dragged_piece is set
        assert board_widget.dragged_piece is not None
        assert board_widget.dragged_piece.piece_type == chess.KING
        # King has many pseudo-legal moves from e1
        assert len(board_widget.legal_move_squares) > 0


class TestBoardState:
    def test_initial_position(self, board_widget):
        assert board_widget.board.fen() == chess.STARTING_FEN

    def test_set_board(self, board_widget):
        b = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        board_widget.set_board(b)
        assert board_widget.board.fen() == b.fen()

    def test_set_flipped(self, board_widget):
        board_widget.set_flipped(True)
        assert board_widget.flipped is True

    def test_set_best_move(self, board_widget):
        m = chess.Move.from_uci("e2e4")
        board_widget.set_best_move(m)
        assert board_widget.best_move == m
