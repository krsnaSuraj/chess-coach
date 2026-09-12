from __future__ import annotations

import os
import time
import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QMenu,
    QAbstractItemView,
)
from PyQt6.QtGui import QShortcut, QKeySequence, QAction, QCloseEvent
from PyQt6.QtCore import QTimer, Qt, QSettings

import chess
from chess_coach.config import load_config
from chess_coach.chess_board import ChessBoard, COLORS
from chess_coach.coach_dashboard import CoachDashboard
from chess_coach.eco_handler import get_opening
from chess_coach.engine_handler import EngineHandler
from chess_coach.humanizer import Humanizer, ComplexityDetector, _accuracy_for_elo

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        try:
            from chess_coach import __version__

            self.setWindowTitle(f"Chess Coach v{__version__}")
        except Exception:
            self.setWindowTitle("Chess Coach")
        self.resize(740, 620)
        self.setMinimumSize(380, 520)

        self.config = load_config()
        self.board = chess.Board()

        # Startup: ask color like before (Cancel/close falls back to White
        # so the app never bricks with user_color=None).
        picked = self._select_color()
        self.user_color: chess.Color = picked if picked is not None else chess.WHITE
        self.board_flipped = self.user_color == chess.BLACK
        self._engine_error_shown = False

        self.engine_handler = EngineHandler(self.config)
        self.engine_handler.analysis_update.connect(self._on_analysis)
        self.engine_handler.error_occurred.connect(self._on_engine_error)
        self.engine_handler.start_engine()

        self.humanizer = Humanizer(self.config)

        self.analyzing_fen: str | None = None
        self.position_version: int = 0
        self.analyzing_version_id: int | None = None
        self.last_known_move: chess.Move | None = None
        self.analysis_received: bool = False
        self.current_eval: float = 0.0
        self.prev_eval: float = 0.0
        self.has_prev_eval: bool = False
        self.redo_stack: list[tuple[chess.Move, str]] = []
        self._last_ui_update: float = 0.0
        self._ui_throttle_ms: int = 50

        self._multi_pv: dict[int, dict] = {}
        self._multi_pv_depth: int = 0
        self._human_move_selected: chess.Move | None = None
        self._eval_seen: bool = False
        self._game_result_recorded = False
        self._game_result_fen: str | None = None
        self.move_uci_history: list[str] = []
        self._previewing = False

        self._heartbeat = QTimer()
        self._heartbeat.timeout.connect(self._heartbeat_check)
        self._heartbeat.setInterval(2000)
        self._heartbeat.start()
        self._last_analysis_restart: float = 0.0

        self._setup_ui()
        self.dashboard.set_eval_bar_gradient(self.board_flipped)
        self._update_feedback()

    def _select_color(self) -> chess.Color | None:
        items = ["White", "Black"]
        item, ok = QInputDialog.getItem(self, "Play as", "Select your color:", items, 0, False)
        if not ok:
            return None
        return chess.WHITE if item == "White" else chess.BLACK

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()
        view_menu = QMenu("View", self)
        self.pin_action = QAction("Always on Top", self)
        self.pin_action.setShortcut(QKeySequence("Ctrl+T"))
        self.pin_action.setCheckable(True)
        settings = QSettings("ChessCoach", "MainWindow")
        pinned = bool(settings.value("alwaysOnTop", False, type=bool))
        self.pin_action.setChecked(pinned)
        self.pin_action.triggered.connect(self._toggle_pin)
        view_menu.addAction(self.pin_action)
        view_menu.addSeparator()
        analysis_action = QAction("Analysis Board", self)
        analysis_action.setShortcut(QKeySequence("Ctrl+A"))
        analysis_action.triggered.connect(self._analysis_board)
        view_menu.addAction(analysis_action)
        new_action = QAction("New Game", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._new_game)
        view_menu.addAction(new_action)
        menubar.addMenu(view_menu)
        # NOTE: never touch window flags here — the native window does not
        # exist yet. Desired state applies on first show (see showEvent).

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            if self.pin_action.isChecked():
                self._apply_pin(True)
        except Exception:
            logger.warning("Pin apply on show failed", exc_info=True)

    def _apply_pin(self, on: bool) -> None:
        # Recreation-free pinning (the old setWindowFlag+show path destroyed
        # the native window on Windows: black flashes + intermittent crash).
        #   Windows: SetWindowPos TOPMOST/NOTOPMOST only. No flags, no show().
        #   Other OS: Qt flag; show() only to re-apply when already visible.
        # The checkbox always ends in sync with what actually applied.
        applied = False
        try:
            if os.name == "nt":
                try:
                    hwnd = int(self.winId())  # ensure handle exists, no recreate
                except Exception:
                    hwnd = 0
                applied = self._set_topmost_native(on, hwnd) if hwnd else False
                if not applied:
                    logger.warning("Pin unchanged: native call failed")
            else:
                was_visible = self.isVisible()
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
                if was_visible:
                    self.show()
                applied = True
        except Exception:
            logger.warning("Pin apply failed", exc_info=True)
            applied = False
        try:
            self.pin_action.setChecked(bool(applied and on))
            QSettings("ChessCoach", "MainWindow").setValue("alwaysOnTop", bool(applied and on))
            self.statusBar().showMessage("Pinned on top" if (applied and on) else "Unpinned", 2000)
        except Exception:
            pass

    def _toggle_pin(self, checked: bool) -> None:
        # All state sync (checkbox, settings, status) lives in _apply_pin.
        self._apply_pin(checked)

    @staticmethod
    def _set_topmost_native(on: bool, hwnd: int) -> bool:
        if os.name != "nt" or not hwnd:
            return False
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            res = user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST if on else HWND_NOTOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
            if not res:
                err = ctypes.windll.kernel32.GetLastError()
                logger.warning("SetWindowPos failed, err=%s", err)
                return False
            return True
        except Exception:
            logger.warning("Native pin failed", exc_info=True)
            return False

    def _setup_ui(self) -> None:
        self._setup_menubar()
        central = QWidget()
        central.setObjectName("centralContainer")
        central.setStyleSheet("""
            #centralContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0e14, stop:0.5 #0d1117, stop:1 #0a0e14);
            }
        """)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.chess_board = ChessBoard(self.config)
        self.chess_board.set_flipped(self.board_flipped)
        self.chess_board.playable_side = None
        self.chess_board.set_board(self.board)
        self.chess_board.move_made.connect(self._on_move)
        layout.addWidget(self.chess_board, stretch=3)

        self.dashboard = CoachDashboard()
        layout.addWidget(self.dashboard, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_undo = QPushButton("Undo")
        self.btn_undo.setStyleSheet(self._btn_style())
        self.btn_undo.clicked.connect(self._undo)
        btn_row.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("Redo")
        self.btn_redo.setStyleSheet(self._btn_style())
        self.btn_redo.clicked.connect(self._redo)
        btn_row.addWidget(self.btn_redo)

        self.btn_new = QPushButton("New Game")
        self.btn_new.setStyleSheet(self._btn_new_style())
        self.btn_new.clicked.connect(self._new_game)
        btn_row.addWidget(self.btn_new)

        self.dashboard.layout().addLayout(btn_row)  # type: ignore[attr-defined]

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("human", "Human-like"),
            ("must_win", "Must Win"),
            ("safe", "Safe"),
        ):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setStyleSheet(self._btn_style())
            b.clicked.connect(lambda _checked=False, m=key: self._set_mode(m))
            mode_row.addWidget(b)
            self.mode_buttons[key] = b
        self.dashboard.layout().addLayout(mode_row)  # type: ignore[attr-defined]
        self._refresh_mode_buttons()

        s5 = QLabel("MOVE HISTORY")
        s5.setObjectName("section")
        self.dashboard.layout().addWidget(s5)

        self.move_list = QListWidget()
        self.move_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                font-family: 'Consolas', monospace;
                padding: 4px;
            }
            QListWidget::item {
                padding: 2px 6px;
                border-bottom: 1px solid #1a1a2e;
            }
            QListWidget::item:alternate {
                background-color: #161b22;
            }
        """)
        self.move_list.setAlternatingRowColors(True)
        # Cap history height: an unbounded QListWidget minimum forces the
        # whole row taller than short screens, clipping the board bottom.
        self.move_list.setMaximumHeight(140)
        # Smooth per-pixel scrolling (touchpads/touch feel broken on the
        # default per-item mode) + click-to-preview any history position.
        self.move_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.move_list.itemClicked.connect(self._preview_history_move)
        self.dashboard.layout().addWidget(self.move_list, stretch=2)  # type: ignore[call-arg]

        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)

        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS["sidebar"]};
                color: {COLORS["text_dim"]};
                font-size: 10px;
                border-top: 1px solid {COLORS["border"]};
            }}
        """)
        self.statusBar().showMessage("Ready")

    def _refresh_mode_buttons(self) -> None:
        current = self.humanizer.mode
        for key, btn in self.mode_buttons.items():
            btn.setChecked(key == current)

    def _set_mode(self, mode: str) -> None:
        """Switch coach mode mid-game; takes effect on the next analysis."""
        self.humanizer.set_mode(mode)
        self._refresh_mode_buttons()
        # Discard the previous mode's selection so fresh analysis applies it.
        self._human_move_selected = None
        self._multi_pv = {}
        self.statusBar().showMessage(f"Mode: {mode}", 2000)
        self._update_feedback()

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS["bg"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS["accent"]};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(22,27,34,0.9), stop:1 rgba(13,17,23,0.9));
                color: {COLORS["accent"]};
            }}
        """

    def _btn_new_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS["red"]};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #d03540;
            }}
        """

    def _on_move(self, move: chess.Move) -> None:
        # Batch all widget changes into ONE repaint (kills move flicker).
        self._previewing = False
        self.setUpdatesEnabled(False)
        try:
            self.prev_eval = self.current_eval
            self.engine_handler.stop_analysis()
            self.chess_board.set_best_move(None)

            if move not in self.board.legal_moves:
                self.chess_board.update()
                return

            san = self.board.san(move)
            self.board.push(move)
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.redo_stack.clear()
            self.move_uci_history.append(move.uci())
            self._game_result_recorded = False
            self._game_result_fen = None

            move_num = (len(self.board.move_stack) + 1) // 2
            turn = "W" if self.board.turn == chess.BLACK else "B"
            suffix = "#" if self.board.is_checkmate() else "+" if self.board.is_check() else ""
            item_text = f"{move_num}{turn}  {san}{suffix}"
            self.move_list.addItem(item_text)
            self.move_list.scrollToBottom()

            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"Move error: {e}")
        finally:
            self.setUpdatesEnabled(True)
            self.chess_board.update()
            self.update()

    def _undo(self) -> None:
        if not self.board.move_stack:
            return
        if self.chess_board._pending_move:
            return  # animation in flight — its move_made owns the board
        self._previewing = False
        self.setUpdatesEnabled(False)
        try:
            self.engine_handler.stop_analysis()
            if self.move_list.count() == 0:
                return
            move = self.board.peek()
            try:
                san_only = self.board.san(move)
            except Exception:
                san_only = move.uci()
            self.move_list.takeItem(self.move_list.count() - 1)
            self.board.pop()
            self.redo_stack.append((move, san_only))
            if self.move_uci_history:
                self.move_uci_history.pop()
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.has_prev_eval = False
            # NOTE: result flags NOT reset — replays of the same terminal
            # via redo must not double-count; a genuinely new move re-arms.

            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"Undo error: {e}")
        finally:
            self.setUpdatesEnabled(True)
            self.chess_board.update()
            self.update()

    def _redo(self) -> None:
        if not self.redo_stack:
            return
        if self.chess_board._pending_move:
            return
        self._previewing = False
        self.setUpdatesEnabled(False)
        try:
            self.engine_handler.stop_analysis()
            move, san_text = self.redo_stack.pop()

            if not san_text:
                try:
                    san_text = self.board.san(move)
                except Exception:
                    san_text = move.uci()

            if move not in self.board.legal_moves:
                self.redo_stack.append((move, san_text))
                return
            self.board.push(move)
            self.move_uci_history.append(move.uci())
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.has_prev_eval = False

            move_num = (len(self.board.move_stack) + 1) // 2
            turn = "W" if self.board.turn == chess.BLACK else "B"
            suffix = "#" if self.board.is_checkmate() else "+" if self.board.is_check() else ""
            self.move_list.addItem(f"{move_num}{turn}  {san_text}{suffix}")
            self.move_list.scrollToBottom()

            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"Redo error: {e}")
        finally:
            self.setUpdatesEnabled(True)
            self.chess_board.update()
            self.update()

    def _preview_history_move(self, item) -> None:
        """Click a history row to VIEW that position (game state untouched).

        Rebuilds from scratch and replays UCI so the preview can never
        desync. Any live action (move/undo/redo/new/analysis-board) calls
        set_board(self.board) and returns to the live game automatically.
        """
        try:
            row = self.move_list.row(item)
            if row < 0 or row >= len(self.move_uci_history):
                return
            if row == len(self.move_uci_history) - 1:
                # Latest row = live position.
                self._previewing = False
                self.chess_board.set_board(self.board)
                self._update_feedback()
                return
            preview = chess.Board()
            for uci in self.move_uci_history[: row + 1]:
                move = chess.Move.from_uci(uci)
                if move not in preview.legal_moves:
                    return
                preview.push(move)
            self.engine_handler.stop_analysis()
            self._previewing = True
            self.chess_board.set_board(preview, clear_arrow=True)
            self.statusBar().showMessage(
                f"Viewing move {row + 1}/{len(self.move_uci_history)}"
                " — move/undo/redo/new returns LIVE",
                5000,
            )
        except Exception as e:
            logger.error(f"Preview error: {e}")

    def _reset_dashboard(self, feedback_text: str = "") -> None:
        self.dashboard.lbl_eval.setText("0.00")
        self.dashboard.lbl_eval.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 26px; font-weight: bold; font-family: 'Segoe UI', monospace;"
        )
        self.dashboard.lbl_best.setText("-")
        self.dashboard.lbl_pv.setText("")
        self.dashboard.lbl_advantage.setText("Equal")
        self.dashboard.lbl_advantage.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; font-weight: bold;"
        )
        self.dashboard.lbl_feedback.setText(feedback_text)
        self.dashboard.lbl_feedback.setStyleSheet(
            f"color: {COLORS['text']}; padding: 10px;"
            f"background: {COLORS['bg']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
        )
        self.dashboard.lbl_engine.setText("Ready")
        self.dashboard.set_eval_bar_value(1000)

    def _analysis_board(self) -> None:
        fen, ok = QInputDialog.getMultiLineText(
            self,
            "Analysis Board",
            "Enter FEN position:",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        )
        if not ok or not fen:
            return
        fen = fen.strip()
        try:
            new_board = chess.Board(fen)
        except ValueError:
            QMessageBox.warning(self, "Invalid FEN", "The entered FEN is not valid.")
            return
        if self.chess_board._pending_move:
            return
        self._previewing = False
        self.engine_handler.stop_analysis()
        self.board = new_board
        self.redo_stack.clear()
        self.move_uci_history.clear()
        self._game_result_recorded = False
        self._game_result_fen = None
        self.position_version += 1
        self.analysis_received = False
        self.last_known_move = None
        self._multi_pv = {}
        self._multi_pv_depth = 0
        self._human_move_selected = None
        self.chess_board.set_best_move(None)
        self.current_eval = 0.0
        self.prev_eval = 0.0
        self.has_prev_eval = False
        self._eval_seen = False
        self.move_list.clear()
        self._reset_dashboard("Analysis position set")
        self.chess_board.playable_side = None
        self.chess_board.set_board(self.board)
        self._update_feedback()

    def _new_game(self) -> None:
        try:
            if self.chess_board._pending_move:
                return  # animation in flight — don't strand it
            color = self._select_color()
            if color is None:
                return  # Cancel: leave the current game untouched
            self._previewing = False
            self.user_color = color
            self.board_flipped = self.user_color == chess.BLACK
            self.dashboard.set_eval_bar_gradient(self.board_flipped)

            self.engine_handler.stop_analysis()
            self.board.reset()
            self.redo_stack.clear()
            self.move_uci_history.clear()
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.current_eval = 0.0
            self.prev_eval = 0.0
            self.has_prev_eval = False
            self.move_list.clear()
            self._reset_dashboard("New game started")
            self.humanizer.new_game()
            self._refresh_mode_buttons()
            self._multi_pv = {}
            self._multi_pv_depth = 0
            self._human_move_selected = None
            self._game_result_recorded = False
            self._game_result_fen = None
            self.chess_board.set_flipped(self.board_flipped)
            self.chess_board.playable_side = None
            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"New game error: {e}")

    def run_analysis(self) -> None:
        self.analyzing_fen = self.board.fen()
        self.analyzing_version_id = self.position_version
        self._multi_pv = {}
        self._multi_pv_depth = 0
        self._human_move_selected = None
        self.engine_handler.start_analysis(self.board.copy())

    def _update_turn_display(self) -> None:
        # Change-gated: identical setText/setStyleSheet 20×/sec still repaints.
        key = (
            self.board.turn,
            self.board.is_checkmate(),
            self.board.is_stalemate(),
            self.board.is_insufficient_material(),
            self.board.is_fifty_moves(),
            self.board.can_claim_draw(),
            self.board.is_check(),
            len(self.board.move_stack),
            self.user_color,
        )
        if key == getattr(self, "_turn_key", None):
            return
        self._turn_key = key
        dash = self.dashboard
        turn_name = "White" if self.board.turn == chess.WHITE else "Black"
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            dash.lbl_turn.setText(f"# Checkmate! {winner} wins")
            dash.lbl_turn.setStyleSheet(f"""
                background-color: {COLORS["green"]}; color: white; font-size: 13px; font-weight: bold;
                padding: 6px; border: 2px solid {COLORS["green"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Checkmate")
        elif self.board.is_stalemate():
            dash.lbl_turn.setText("Stalemate! Draw")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["yellow"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["yellow"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Stalemate")
        elif self.board.is_insufficient_material():
            dash.lbl_turn.setText("Draw! Insufficient material")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["yellow"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["yellow"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Draw")
        elif self.board.is_fifty_moves():
            dash.lbl_turn.setText("Draw! 50-move rule")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["yellow"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["yellow"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  50-move Draw")
        elif self.board.can_claim_draw():
            dash.lbl_turn.setText("Draw can be claimed!")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["yellow"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["yellow"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Draw by repetition available")
        elif self.board.is_check():
            dash.lbl_turn.setText(f"{turn_name} is in check!")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["red"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["red"]}; border-radius: 4px;
            """)
            dash.lbl_info.setText(f"Move {len(self.board.move_stack) // 2 + 1}  |  Check!")
        else:
            dash.lbl_turn.setText(f"{turn_name} to move")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS["accent"]}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS["border"]}; border-radius: 4px;
            """)
            mc = len(self.board.move_stack) // 2 + 1
            gp = "Endgame" if mc > 40 else "Middlegame" if mc > 15 else "Opening"
            dash.lbl_info.setText(f"Move {mc}  |  {gp}")

    def can_show_coach(self) -> bool:
        if self.board.is_game_over():
            return False
        return self.board.turn == self.user_color

    def _on_analysis(self, info: dict) -> None:
        try:
            if self._previewing:
                return  # history preview: never paint live analysis onto it
            if self.analyzing_version_id != self.position_version:
                return
            if self.analyzing_fen and self.analyzing_fen != self.board.fen():
                return

            self.analysis_received = True

            pv = info.get("pv")
            multipv_num = info.get("multipv", 1)
            depth = info.get("depth", 0)

            if depth > self._multi_pv_depth and self._human_move_selected is None:
                self._multi_pv = {}
                self._multi_pv_depth = depth
            if pv and len(pv) > 0:
                self._multi_pv[multipv_num] = info

            score = info.get("score")
            if not score:
                return

            if multipv_num != 1:
                return

            # Throttle EVERYTHING visual below (humanizer + labels + board +
            # eval): engine streams dozens of infos/sec and each one used to
            # repaint the board and rewrite labels — that storm fought drag
            # paints and read as flicker. Data accumulation above stays live.
            now = time.time()
            if (now - self._last_ui_update) * 1000 < self._ui_throttle_ms:
                return
            self._last_ui_update = now

            multi_pv_list = [
                self._multi_pv[k] for k in sorted(self._multi_pv) if self._multi_pv[k].get("pv")
            ]
            if multi_pv_list and self._human_move_selected is None:
                is_complex = ComplexityDetector.is_complex(self.board)
                eval_score = 0.0
                scores = multi_pv_list[0].get("score")
                if scores:
                    try:
                        cp_val = scores.relative.score(mate_score=10000)
                        eval_score = abs(cp_val) / 100.0 if cp_val is not None else 10.0
                    except Exception:
                        eval_score = 10.0
                human_move = self.humanizer.select_move(
                    multi_pv_list,
                    self.board,
                    is_complex=is_complex,
                    eval_score=eval_score,
                )
                if human_move:
                    self._human_move_selected = human_move

            if self._human_move_selected:
                self.last_known_move = self._human_move_selected
                # Change-gated: re-setting the SAME arrow/labels 20×/sec
                # repaints the board and churns the dashboard for nothing —
                # that storm fights drag paints and reads as flicker.
                if self.chess_board.best_move != self._human_move_selected:
                    self.chess_board.set_best_move(self._human_move_selected)
                self._set_label_text(self.dashboard.lbl_best, self._human_move_selected.uci())
                pv_line = self._multi_pv.get(1, {}).get("pv", pv or [])
                if pv_line:
                    self._set_label_text(
                        self.dashboard.lbl_pv,
                        "Line: " + " ".join(m.uci() for m in pv_line[:4]),
                    )

            score = info.get("score")
            if not score:
                return

            if multipv_num != 1:
                return

            dash = self.dashboard
            cur_eval: float = 0.0
            val: float = 0.0
            text = "0.00"
            mate = 0

            if score.is_mate():
                mate = score.relative.mate() or 0
                text = f"M{mate}"
                val = 1000 if mate > 0 else -1000
                cur_eval = float("inf") if mate > 0 else float("-inf")
            else:
                cp = score.white().score(mate_score=10000)
                text = f"{cp / 100:.2f}"
                val = max(-1000, min(1000, cp))
                cur_eval = cp / 100.0

            user_eval = cur_eval if self.user_color != chess.BLACK else -cur_eval
            user_val = val if self.user_color != chess.BLACK else -val
            self.current_eval = cur_eval
            if self._eval_seen and self.user_color is not None:
                self.has_prev_eval = True
            self._eval_seen = True

            self._set_label_text(
                dash.lbl_engine, f"Depth {depth}  |  {info.get('seldepth', depth)}"
            )

            eval_color = (
                COLORS["green"]
                if user_eval > 0.3
                else COLORS["red"] if user_eval < -0.3 else COLORS["text"]
            )
            new_style = f"color: {eval_color}; font-size: 26px; font-weight: bold; font-family: 'Segoe UI', monospace;"
            if dash.lbl_eval.text() != text or dash.lbl_eval.styleSheet() != new_style:
                dash.lbl_eval.setStyleSheet(new_style)
                dash.lbl_eval.setText(text)

            if score.is_mate():
                if mate > 0:
                    self._set_label_text(dash.lbl_advantage, "White can mate")
                    dash.lbl_advantage.setStyleSheet(
                        f"color: {COLORS['green']}; font-size: 10px; font-weight: bold;"
                    )
                else:
                    self._set_label_text(dash.lbl_advantage, "Black can mate")
                    dash.lbl_advantage.setStyleSheet(
                        f"color: {COLORS['red']}; font-size: 10px; font-weight: bold;"
                    )
            else:
                adv, adv_color = self._eval_text(user_eval)
                self._set_label_text(dash.lbl_advantage, adv)
                dash.lbl_advantage.setStyleSheet(
                    f"color: {adv_color}; font-size: 10px; font-weight: bold;"
                )

            bar_val = user_val + 1000
            dash.set_eval_bar_value(int(bar_val))

            self._update_turn_display()

            if not self.can_show_coach():
                if self.chess_board.best_move is not None:
                    self.chess_board.set_best_move(None)
                self._set_label_text(self.dashboard.lbl_best, "-")
                self._set_label_text(self.dashboard.lbl_pv, "")
                return

            if self.board.is_checkmate():
                self.engine_handler.stop_analysis()
                self._set_feedback(
                    "CHECKMATE! Game over.",
                    f"color: {COLORS['green']}; padding: 10px; font-weight: bold;"
                    f"border: 2px solid {COLORS['green']}; border-radius: 4px;",
                )
                self.analysis_received = True
                return

            if score.is_mate():
                self._set_label_text(dash.lbl_pv, "")
                self._set_feedback(
                    f"Forced mate in {abs(mate)} moves",
                    f"color: {COLORS['green']}; padding: 10px;"
                    f"border: 1px solid {COLORS['green']}; border-radius: 4px;",
                )
                self.analysis_received = True
                return

            feedback, feed_color = self._feedback_text(user_val)
            prev = self.prev_eval if self.has_prev_eval else None
            if prev is not None and not score.is_mate():
                prev_user = prev if self.user_color != chess.BLACK else -prev
                delta = user_eval - prev_user
                if delta < -1.0:
                    feedback = "BLUNDER! You lost advantage this move"
                    feed_color = COLORS["red"]
                    self._set_feedback(
                        feedback,
                        f"color: {COLORS['red']}; padding: 10px; font-weight: bold;"
                        f"border: 1px solid {COLORS['red']}; border-radius: 4px;",
                    )
                    return
                elif delta > 1.0:
                    feedback = "MISS! Opponent blundered — you missed a chance!"
                    feed_color = COLORS["yellow"]
                    self._set_feedback(
                        feedback,
                        f"color: {COLORS['yellow']}; padding: 10px; font-weight: bold;"
                        f"border: 1px solid {COLORS['yellow']}; border-radius: 4px;",
                    )
                    return
            self._set_feedback(
                feedback,
                f"color: {feed_color}; padding: 10px;"
                f"background: {COLORS['bg']};"
                f"border: 1px solid {COLORS['border']}; border-radius: 4px;",
            )

        except Exception as e:
            logger.error(f"Analysis error: {e}")

    @staticmethod
    def _set_label_text(label, text: str) -> None:
        """setText only on real change — identical setText still repaints."""
        try:
            if label.text() != text:
                label.setText(text)
        except Exception:
            label.setText(text)

    def _set_feedback(self, text: str, style: str) -> None:
        """Feedback text+style only on real change (restyle relayouts)."""
        dash = self.dashboard
        try:
            if dash.lbl_feedback.text() == text:
                return
        except Exception:
            pass
        dash.lbl_feedback.setStyleSheet(style)
        dash.lbl_feedback.setText(text)

    def _eval_text(self, user_eval: float) -> tuple[str, str]:
        # Thresholds mirror server._coach_label (0.5/0.3) — one scale everywhere.
        if user_eval > 0.5:
            return "You are winning", COLORS["green"]
        if user_eval > 0.3:
            return "You are better", COLORS["green"]
        if user_eval < -0.5:
            return "Opponent is winning", COLORS["red"]
        if user_eval < -0.3:
            return "Opponent is better", COLORS["red"]
        return "Equal", COLORS["text_dim"]

    def _feedback_text(self, user_val: float) -> tuple[str, str]:
        if user_val > 300:
            return "You have a winning advantage", COLORS["green"]
        if user_val > 100:
            return "You are better (+1 pawn advantage)", COLORS["green"]
        if user_val < -300:
            return "Opponent has a winning advantage", COLORS["red"]
        if user_val < -100:
            return "Opponent is better (-1 pawn advantage)", COLORS["red"]
        return "Position is balanced", COLORS["text_dim"]

    def _update_feedback(self) -> None:
        dash = self.dashboard
        self._update_turn_display()
        # Only AUTOMATIC terminations end the game. 50-move / threefold are
        # claimable (FIDE 9.2/9.3) — play continues, coach keeps coaching.
        if self.board.is_game_over():
            self.engine_handler.stop_analysis()
            self.last_known_move = None
            self.chess_board.set_best_move(None)
            dash.lbl_best.setText("-")
            dash.lbl_pv.setText("")
            if self._game_result_fen != self.board.fen():
                if self.board.is_checkmate():
                    won = self.board.turn != self.user_color
                    result = "win" if won else "loss"
                else:
                    result = "draw"
                self.humanizer.record_result(
                    result, _accuracy_for_elo(self.humanizer.effective_elo)
                )
                self._game_result_recorded = True
                self._game_result_fen = self.board.fen()
            if self.board.is_checkmate():
                winner = "Black" if self.board.turn == chess.WHITE else "White"
                dash.lbl_feedback.setText(f"Game over! {winner} wins by checkmate.")
                dash.lbl_feedback.setStyleSheet(
                    f"color: {COLORS['green']}; padding: 10px; font-weight: bold;"
                    f"background: {COLORS['bg']};"
                    f"border: 2px solid {COLORS['green']}; border-radius: 4px;"
                )
            elif self.board.is_stalemate():
                dash.lbl_feedback.setText("Game over! Stalemate — draw.")
                dash.lbl_feedback.setStyleSheet(
                    f"color: {COLORS['yellow']}; padding: 10px;"
                    f"background: {COLORS['bg']};"
                    f"border: 1px solid {COLORS['yellow']}; border-radius: 4px;"
                )
            elif self.board.is_insufficient_material():
                dash.lbl_feedback.setText("Game over! Draw by insufficient material.")
                dash.lbl_feedback.setStyleSheet(
                    f"color: {COLORS['yellow']}; padding: 10px;"
                    f"background: {COLORS['bg']};"
                    f"border: 1px solid {COLORS['yellow']}; border-radius: 4px;"
                )
            else:
                dash.lbl_feedback.setText("Game over! Draw.")
                dash.lbl_feedback.setStyleSheet(
                    f"color: {COLORS['text']}; padding: 10px;"
                    f"background: {COLORS['bg']};"
                    f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
                )
        elif self.can_show_coach():
            self.run_analysis()
        else:
            self.last_known_move = None
            self.chess_board.set_best_move(None)
            dash.lbl_best.setText("-")
            dash.lbl_pv.setText("")
            tn = "White" if self.board.turn == chess.WHITE else "Black"
            note = f"Waiting — {tn}'s turn to play"
            if self.board.is_fifty_moves() or self.board.can_claim_draw():
                note += " (draw available — claim or play on)"
            dash.lbl_feedback.setText(note)
            dash.lbl_feedback.setStyleSheet(
                f"color: {COLORS['text']}; padding: 10px;"
                f"background: {COLORS['bg']};"
                f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
            )
        self._update_opening()

    def _update_opening(self) -> None:
        opening = get_opening(self.board)
        if opening:
            eco_code, name = opening
            self.dashboard.lbl_opening.setText(f"[{eco_code}] {name}")
        else:
            self.dashboard.lbl_opening.setText("—")

    def _heartbeat_check(self) -> None:
        if self._previewing:
            return  # history preview: don't restart live analysis over it
        if self.board.is_game_over() or self.board.is_fifty_moves():
            return
        if not self.can_show_coach():
            return
        if self.analysis_received:
            self.analysis_received = False
            return
        alive = (
            self.engine_handler.analysis_thread and self.engine_handler.analysis_thread.isRunning()
        )
        if alive:
            if self.last_known_move:
                self.chess_board.set_best_move(self.last_known_move)
                self.dashboard.lbl_best.setText(f"{self.last_known_move.uci()} (cached)")
        else:
            now = time.time()
            if now - self._last_analysis_restart > 3.0:
                self._last_analysis_restart = now
                self.run_analysis()

    def _on_engine_error(self, msg: str) -> None:
        # Modal per failure spams a loop when the engine is dead — show once,
        # then downgrade to the status bar.
        if not self._engine_error_shown:
            self._engine_error_shown = True
            QMessageBox.warning(self, "Engine Error", msg)
        else:
            self.statusBar().showMessage(f"Engine: {msg}", 5000)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self._heartbeat.stop()
        # Stop the worker FIRST and wait for it out of engine.analysis()
        # before quit(): quit-while-analyzing hangs/crashes.
        try:
            self.engine_handler.stop_analysis()
            self.engine_handler.pending_board = None
            th = self.engine_handler.analysis_thread
            if th is not None and th.isRunning():
                th.wait(3000)
        except Exception:
            pass
        self.engine_handler.stop_engine()
        if event is not None:
            event.accept()
