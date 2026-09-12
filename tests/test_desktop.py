"""Desktop (PyQt6) offscreen tests — v0.1.1.

Runs with QT_QPA_PLATFORM=offscreen (also set in CI). No dialogs, no engine
binary, no network: QInputDialog + EngineHandler are stubbed.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import chess
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QEvent
from PyQt6.QtGui import QMouseEvent, QImage

from chess_coach.chess_board import ChessBoard
from chess_coach.coach_dashboard import CoachDashboard


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def board(qt_app):
    b = ChessBoard({"display": {}})
    b.resize(400, 400)
    b.show()
    qt_app.processEvents()
    return b


def _grab_gray(widget) -> tuple[bytes, int, int]:
    img = widget.grab().toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    w, h = img.width(), img.height()
    return bytes(img.bits().asarray(w * h)), w, h


def _press(board, qt_app, sq_name: str) -> tuple[float, float]:
    sq = chess.parse_square(sq_name)
    size = min(board.width(), board.height())
    s = size / 8
    ox = (board.width() - size) / 2
    oy = (board.height() - size) / 2
    x = ox + chess.square_file(sq) * s + s / 2
    y = oy + (7 - chess.square_rank(sq)) * s + s / 2
    pos = QPointF(x, y)
    board.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    qt_app.processEvents()
    return x, y


class TestBoardRender:
    def test_paint_smoke(self, board, qt_app):
        board.set_board(chess.Board())
        board.set_best_move(chess.Move.from_uci("e2e4"))
        qt_app.processEvents()
        px, w, h = _grab_gray(board)
        assert (w, h) == (400, 400)
        assert any(v < 128 for v in px)  # pieces actually drawn

    def test_opaque_paint_flag(self, board):
        from PyQt6.QtCore import Qt as _Qt

        assert board.testAttribute(_Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def test_flipped_symmetry(self, board, qt_app):
        board.set_flipped(False)
        qt_app.processEvents()
        a, _, _ = _grab_gray(board)
        board.set_flipped(True)
        qt_app.processEvents()
        c, _, _ = _grab_gray(board)
        assert a != c


class TestDragNoGlitch:
    def test_drag_frames_localized(self, board, qt_app):
        board.set_flipped(False)
        board.set_board(chess.Board())
        x, y = _press(board, qt_app, "e2")
        assert board.dragged_square == chess.E2
        assert not hasattr(board, "drag_cache")  # cache layer deleted v0.1.1
        prev, w, h = _grab_gray(board)
        total = w * h
        for i in range(1, 5):
            pos = QPointF(x, y - i * 20.0)
            board.mouseMoveEvent(
                QMouseEvent(
                    QEvent.Type.MouseMove,
                    pos,
                    pos,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
            )
            qt_app.processEvents()
            cur, _, _ = _grab_gray(board)
            changed = sum(1 for p, q in zip(prev, cur) if abs(p - q) > 12)
            # Only the lifted piece + shadow move: <3% of pixels may change.
            assert changed < total * 0.03, f"frame {i}: {changed/total:.1%} changed"
            prev = cur

    def test_drag_throttle(self, board, qt_app):
        board.set_board(chess.Board())
        x, y = _press(board, qt_app, "e2")
        board.mouse_pos = QPointF(x, y)
        board._last_drag_paint = QPointF(x, y)
        paints = []
        orig_update = board.update
        board.update = lambda *a, **k: (paints.append(1), orig_update(*a, **k))
        try:
            tiny = QPointF(x + 0.5, y)
            board.mouseMoveEvent(
                QMouseEvent(
                    QEvent.Type.MouseMove,
                    tiny,
                    tiny,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
            )
            assert paints == []
            far = QPointF(x + 10.0, y)
            board.mouseMoveEvent(
                QMouseEvent(
                    QEvent.Type.MouseMove,
                    far,
                    far,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
            )
            assert len(paints) == 1
        finally:
            board.update = orig_update

    def test_resize_during_drag_repaints_cleanly(self, board, qt_app):
        board.set_board(chess.Board())
        _press(board, qt_app, "e2")
        board.resize(401, 401)
        qt_app.processEvents()
        board.repaint()
        qt_app.processEvents()
        px, w, h = _grab_gray(board)
        assert (w, h) == (401, 401)
        assert len(px) == w * h

    def test_offboard_drag_no_crash_no_ghost_outside(self, board, qt_app):
        board.set_board(chess.Board())
        _press(board, qt_app, "e2")
        # Press grabs the mouse so off-window releases still arrive.
        assert board.mouseGrabber() is board
        far = QPointF(-500.0, 900.0)
        board.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                far,
                far,
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        qt_app.processEvents()
        board.repaint()
        qt_app.processEvents()
        px, w, h = _grab_gray(board)
        assert len(px) == w * h
        # Release outside the board: snapback must clear everything + ungrab.
        board.mouseReleaseEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                far,
                far,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        qt_app.processEvents()
        assert board.dragged_piece is None
        assert board.mouseGrabber() is not board

    def test_pickup_frame_single_ghost(self, board, qt_app):
        # Right after pickup (no movement yet) the lifted ghost must be
        # visible around the cursor (bright region on/around e2).
        board.set_flipped(False)
        board.set_board(chess.Board())
        x, y = _press(board, qt_app, "e2")
        px, w, h = _grab_gray(board)
        size = min(board.width(), board.height())
        s = size / 8
        ox = (board.width() - size) / 2
        oy = (board.height() - size) / 2

        def region_mean(cx, cy, r=7):
            vals = []
            for yy in range(int(cy) - r, int(cy) + r + 1):
                for xx in range(int(cx) - r, int(cx) + r + 1):
                    vals.append(px[max(0, min(h - 1, yy)) * w + max(0, min(w - 1, xx))])
            return sum(vals) / len(vals)

        e2x, e2y = ox + 4 * s + s / 2, oy + 6 * s + s / 2
        assert region_mean(e2x, e2y) > 180, region_mean(e2x, e2y)

    def test_drag_leaves_no_trails(self, board, qt_app):
        # The trail bug: drag e2 across the board; squares far from the path
        # (a-file) must stay pixel-identical to the pre-drag frame.
        board.set_flipped(False)
        board.set_board(chess.Board())
        base, w, h = _grab_gray(board)
        size = min(board.width(), board.height())
        s = size / 8
        ox = (board.width() - size) / 2
        oy = (board.height() - size) / 2
        x, y = _press(board, qt_app, "e2")
        for i in range(1, 9):
            pos = QPointF(x + i * 20.0, y - i * 22.0)
            board.mouseMoveEvent(
                QMouseEvent(
                    QEvent.Type.MouseMove,
                    pos,
                    pos,
                    Qt.MouseButton.NoButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                )
            )
            qt_app.processEvents()
        cur, _, _ = _grab_gray(board)

        def col_pixels(frame, file_idx, rows):
            out = []
            for vr in rows:
                xx, yy = int(ox + file_idx * s + s / 2), int(oy + vr * s + s / 2)
                out.append(frame[yy * w + xx])
            return out

        # a-file rows 2..5 (visual rows far from the e2->NE diagonal path)
        assert col_pixels(cur, 0, [2, 3, 4, 5]) == col_pixels(base, 0, [2, 3, 4, 5])


class TestDashboard:
    def test_eval_bar_animates(self, qt_app):
        import time

        d = CoachDashboard()
        d.show()
        qt_app.processEvents()
        d.set_eval_bar_value(1500)
        deadline = time.time() + 2.0
        while d.eval_bar.value() != 1500 and time.time() < deadline:
            qt_app.processEvents()
            time.sleep(0.02)
        assert d.eval_bar.value() == 1500
        d.set_eval_bar_gradient(True)
        qt_app.processEvents()
        d.set_eval_bar_gradient(False)
        qt_app.processEvents()


class TestMainWindow:
    @pytest.fixture
    def window(self, qt_app, monkeypatch):
        from chess_coach import main_window as mw_mod
        from chess_coach.main_window import MainWindow
        from chess_coach.engine_handler import EngineHandler

        monkeypatch.setattr(
            mw_mod.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("White", True))
        )
        monkeypatch.setattr(EngineHandler, "start_engine", lambda self: None)
        monkeypatch.setattr(EngineHandler, "start_analysis", lambda self, b: None)
        monkeypatch.setattr(EngineHandler, "stop_analysis", lambda self: None)
        monkeypatch.setattr(EngineHandler, "stop_engine", lambda self: None)
        w = MainWindow()
        w.show()
        qt_app.processEvents()
        yield w
        w.close()

    def test_view_menu_only(self, window):
        menus = [a.text().replace("&", "") for a in window.menuBar().actions()]
        assert menus == ["View"]

    def test_startup_asks_color(self, qt_app, monkeypatch):
        from chess_coach import main_window as mw_mod
        from chess_coach.main_window import MainWindow
        from chess_coach.engine_handler import EngineHandler

        monkeypatch.setattr(EngineHandler, "start_engine", lambda self: None)
        monkeypatch.setattr(EngineHandler, "start_analysis", lambda self, b: None)
        monkeypatch.setattr(EngineHandler, "stop_analysis", lambda self: None)
        monkeypatch.setattr(EngineHandler, "stop_engine", lambda self: None)

        import chess as _chess

        # Black choice flips the board.
        monkeypatch.setattr(
            mw_mod.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("Black", True))
        )
        w = MainWindow()
        assert w.user_color == _chess.BLACK
        assert w.board_flipped is True
        w.close()

        # Cancel falls back to White (never bricks with None).
        monkeypatch.setattr(
            mw_mod.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("White", False))
        )
        w2 = MainWindow()
        assert w2.user_color == _chess.WHITE
        assert w2.board_flipped is False
        w2.close()

    def test_pin_toggle_no_crash(self, window, qt_app):
        from PyQt6.QtCore import Qt as _Qt

        window.pin_action.trigger()  # ON attempt
        qt_app.processEvents()
        window.pin_action.trigger()  # OFF attempt
        qt_app.processEvents()
        # Offscreen the native call cannot succeed: the checkbox must stay
        # honest (unchecked) instead of claiming a pin that never applied.
        assert window.pin_action.isChecked() is False
        # No Qt-flag window recreation may EVER happen on Windows runs:
        # flags must not carry StaysOnTopHint from our toggle path.
        assert not (window.windowFlags() & _Qt.WindowType.WindowStaysOnTopHint)

    def test_pin_applies_saved_setting_on_show(self, window, qt_app):
        # showEvent re-applies a checked pin without raising.
        from PyQt6.QtGui import QShowEvent

        window.pin_action.setChecked(True)
        window.showEvent(QShowEvent())
        qt_app.processEvents()

    def test_modes_all_work(self, window, qt_app):
        for m in ("must_win", "safe", "human"):
            window._set_mode(m)
            qt_app.processEvents()
            assert window.humanizer.mode == m
            assert window.mode_buttons[m].isChecked()

    def test_move_undo_redo_list_sync(self, window, qt_app):
        window._on_move(chess.Move.from_uci("e2e4"))
        qt_app.processEvents()
        assert len(window.board.move_stack) == 1
        assert window.move_list.count() == 1
        window._undo()
        qt_app.processEvents()
        assert len(window.board.move_stack) == 0
        assert window.move_list.count() == 0
        window._redo()
        qt_app.processEvents()
        assert len(window.board.move_stack) == 1
        assert window.move_list.count() == 1

    def test_undo_during_animation_no_phantom(self, window, qt_app, monkeypatch):
        # Simulate a drag whose 150ms animation is still in flight:
        # undo/redo/new must refuse so no phantom move lands later.
        window.chess_board._pending_move = chess.Move.from_uci("e2e4")
        window._undo()
        window._redo()
        qt_app.processEvents()
        assert len(window.board.move_stack) == 0
        window.chess_board._pending_move = None

    def test_new_game_cancel_keeps_board(self, window, qt_app, monkeypatch):
        from chess_coach import main_window as mw_mod

        window._on_move(chess.Move.from_uci("e2e4"))
        qt_app.processEvents()
        monkeypatch.setattr(
            mw_mod.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("White", False))
        )
        window._new_game()
        qt_app.processEvents()
        assert len(window.board.move_stack) == 1  # untouched

    def test_promotion_dialog_has_cancel(self, qt_app):
        from chess_coach.promotion_dialog import PromotionDialog

        d = PromotionDialog(chess.WHITE)
        labels = [
            d.layout().itemAt(i).widget().text()
            for i in range(d.layout().count())
            if hasattr(d.layout().itemAt(i).widget(), "text")
        ]
        assert "Cancel" in labels
        d.close()

    def test_close_during_analysis_no_crash(self, window, qt_app):
        window.run_analysis()  # engine stubbed; thread may or may not exist
        qt_app.processEvents()
        window.close()
        qt_app.processEvents()

    def test_history_smooth_scroll_and_wheel(self, window, qt_app):
        from PyQt6.QtWidgets import QAbstractItemView

        assert window.move_list.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
        for u in ("e2e4", "e7e5", "g1f3"):
            window._on_move(chess.Move.from_uci(u))
        qt_app.processEvents()
        sb = window.move_list.verticalScrollBar()
        sb.setValue(sb.maximum())
        qt_app.processEvents()
        assert sb.value() == sb.maximum()

    def test_history_click_previews_and_returns_live(self, window, qt_app):
        for u in ("e2e4", "e7e5", "g1f3"):
            window._on_move(chess.Move.from_uci(u))
        qt_app.processEvents()
        assert window.move_uci_history == ["e2e4", "e7e5", "g1f3"]
        assert window.move_list.count() == 3
        # Click first row -> preview after 1.e4 (live board untouched).
        window._preview_history_move(window.move_list.item(0))
        qt_app.processEvents()
        assert window._previewing is True
        assert len(window.board.move_stack) == 3  # live game intact
        assert window.chess_board.board.fen().startswith("rnbqkbnr/pppppppp/8/8/4P3")
        # Click latest row -> back to live.
        window._preview_history_move(window.move_list.item(2))
        qt_app.processEvents()
        assert window._previewing is False
        assert window.chess_board.board is window.board
        # Undo keeps UCI history in sync.
        window._undo()
        qt_app.processEvents()
        assert window.move_uci_history == ["e2e4", "e7e5"]
        assert window.move_list.count() == 2

    def test_set_mode_clears_stale_selection(self, window, qt_app):
        window._human_move_selected = chess.Move.from_uci("e2e4")
        window._multi_pv = {1: {}}
        window._set_mode("must_win")
        qt_app.processEvents()
        assert window._human_move_selected is None
        assert window._multi_pv == {}

    def test_analysis_ui_throttled(self, window, qt_app):
        # Engine streams dozens of infos/sec: visual updates (board repaint,
        # labels, humanizer) must be throttled, or they fight drag paints
        # and read as flicker. Data accumulation stays live, UI does not.
        import chess.engine

        window.run_analysis()
        qt_app.processEvents()
        info = {
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "score": chess.engine.PovScore(chess.engine.Cp(40), chess.WHITE),
            "multipv": 1,
            "depth": 18,
            "seldepth": 24,
        }
        calls = {"best": 0, "pv": 0, "select": 0}
        orig_best = window.chess_board.set_best_move
        window.chess_board.set_best_move = lambda m: (
            calls.__setitem__("best", calls["best"] + 1),
            orig_best(m),
        )
        orig_pv = window.dashboard.lbl_pv.setText
        window.dashboard.lbl_pv.setText = lambda t: (
            calls.__setitem__("pv", calls["pv"] + 1),
            orig_pv(t),
        )
        orig_sel = window.humanizer.select_move
        window.humanizer.select_move = lambda *a, **k: (
            calls.__setitem__("select", calls["select"] + 1),
            orig_sel(*a, **k),
        )[1]
        try:
            for _ in range(30):
                window._on_analysis(dict(info))
            qt_app.processEvents()
        finally:
            window.chess_board.set_best_move = orig_best
            window.dashboard.lbl_pv.setText = orig_pv
            window.humanizer.select_move = orig_sel
        assert calls["best"] <= 2, calls
        assert calls["pv"] <= 2, calls
        assert calls["select"] <= 2, calls
        # ...but MultiPV data kept accumulating for the next tick.
        assert 1 in window._multi_pv
