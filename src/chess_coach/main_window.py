from __future__ import annotations

import sys
import os
import time
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QInputDialog, QMenuBar, QMenu,
    QFileDialog,
)
from PyQt6.QtGui import QShortcut, QKeySequence, QAction, QCloseEvent
from PyQt6.QtCore import QTimer

import chess
from chess_coach.config import load_config
from chess_coach.chess_board import ChessBoard, COLORS
from chess_coach.coach_dashboard import CoachDashboard
from chess_coach.eco_handler import get_opening
from chess_coach.engine_handler import EngineHandler
from chess_coach.sound_manager import SoundManager
from chess_coach.pgn_handler import board_to_pgn

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess Coach")
        self.resize(1100, 720)

        self.config = load_config()
        self.board = chess.Board()

        self.user_color = self._select_color()
        self.board_flipped = self.user_color == chess.BLACK

        self.engine_handler = EngineHandler(self.config)
        self.engine_handler.analysis_update.connect(self._on_analysis)
        self.engine_handler.error_occurred.connect(self._on_engine_error)
        self.engine_handler.start_engine()

        self.sound_manager = SoundManager()

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

        self._heartbeat = QTimer()
        self._heartbeat.timeout.connect(self._heartbeat_check)
        self._heartbeat.setInterval(2000)
        self._heartbeat.start()

        self._setup_ui()
        self.dashboard.set_eval_bar_gradient(self.board_flipped)
        self._update_feedback()

    def _select_color(self) -> chess.Color | None:
        items = ["White", "Black"]
        item, ok = QInputDialog.getItem(
            self, "Play as", "Select your color:", items, 0, False
        )
        if not ok:
            return None
        return chess.WHITE if item == "White" else chess.BLACK

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()
        file_menu = QMenu("File", self)
        export_action = QAction("Export PGN", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_pgn)
        file_menu.addAction(export_action)
        import_action = QAction("Import PGN", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._import_pgn)
        file_menu.addAction(import_action)
        file_menu.addSeparator()
        analysis_action = QAction("Analysis Board", self)
        analysis_action.setShortcut(QKeySequence("Ctrl+A"))
        analysis_action.triggered.connect(self._analysis_board)
        file_menu.addAction(analysis_action)
        file_menu.addSeparator()
        new_action = QAction("New Game", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._new_game)
        file_menu.addAction(new_action)
        menubar.addMenu(file_menu)

    def _export_pgn(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PGN", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if not path:
            return
        try:
            pgn = board_to_pgn(self.board)
            with open(path, "w", encoding="utf-8") as f:
                f.write(pgn)
            self.statusBar().showMessage(f"PGN exported: {os.path.basename(path)}")
        except Exception as e:
            logger.error(f"PGN export error: {e}")
            QMessageBox.warning(self, "Export Error", str(e))

    def _import_pgn(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import PGN", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                pgn = f.read()
            moves = pgn_to_moves(pgn)
            self.board.reset()
            self.redo_stack.clear()
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.move_list.clear()
            for move in moves:
                if move in self.board.legal_moves:
                    san = self.board.san(move)
                    self.board.push(move)
                    mn = (len(self.board.move_stack) + 1) // 2
                    turn = "W" if self.board.turn == chess.BLACK else "B"
                    suffix = "#" if self.board.is_checkmate() else "+" if self.board.is_check() else ""
                    self.move_list.addItem(f"{mn}{turn}  {san}{suffix}")
            self.chess_board.set_board(self.board)
            self._update_feedback()
            self.statusBar().showMessage(f"PGN imported: {os.path.basename(path)} ({len(moves)} moves)")
        except Exception as e:
            logger.error(f"PGN import error: {e}")
            QMessageBox.warning(self, "Import Error", str(e))

    def _setup_ui(self) -> None:
        self._setup_menubar()
        central = QWidget()
        central.setObjectName("centralContainer")
        central.setStyleSheet(f"""
            #centralContainer {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0a0e14, stop:0.5 #0d1117, stop:1 #0a0e14);
            }}
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
        self.chess_board.move_made.connect(lambda _: self.sound_manager.play_move())
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

        self.dashboard.layout().addLayout(btn_row)

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
        self.dashboard.layout().addWidget(self.move_list, stretch=2)

        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._new_game)

        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['sidebar']};
                color: {COLORS['text_dim']};
                font-size: 10px;
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        self.statusBar().showMessage("Powered by Stockfish 18")

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS['accent']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(22,27,34,0.9), stop:1 rgba(13,17,23,0.9));
                color: {COLORS['accent']};
            }}
        """

    def _btn_new_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['red']};
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

    def _undo(self) -> None:
        if not self.board.move_stack:
            return
        try:
            self.engine_handler.stop_analysis()
            if self.move_list.count() == 0:
                return
            item = self.move_list.takeItem(self.move_list.count() - 1)
            san_text = item.text() if item else ""
            move = self.board.pop()
            self.redo_stack.append((move, san_text))
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.has_prev_eval = False

            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"Undo error: {e}")

    def _redo(self) -> None:
        if not self.redo_stack:
            return
        try:
            self.engine_handler.stop_analysis()
            move, san_text = self.redo_stack.pop()
            self.board.push(move)
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.has_prev_eval = False

            if san_text:
                self.move_list.addItem(san_text)
            else:
                move_num = (len(self.board.move_stack) + 1) // 2
                turn = "W" if self.board.turn == chess.BLACK else "B"
                suffix = "#" if self.board.is_checkmate() else "+" if self.board.is_check() else ""
                san = ""
                try:
                    if self.board.move_stack:
                        san = self.board.san(self.board.peek())
                except Exception:
                    san = move.uci()
                self.move_list.addItem(f"{move_num}{turn}  {san}{suffix}")
            self.move_list.scrollToBottom()

            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"Redo error: {e}")

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
            self, "Analysis Board", "Enter FEN position:",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        if not ok or not fen:
            return
        fen = fen.strip()
        try:
            new_board = chess.Board(fen)
        except ValueError:
            QMessageBox.warning(self, "Invalid FEN", "The entered FEN is not valid.")
            return
        self.engine_handler.stop_analysis()
        self.board = new_board
        self.redo_stack.clear()
        self.position_version += 1
        self.analysis_received = False
        self.last_known_move = None
        self.current_eval = 0.0
        self.prev_eval = 0.0
        self.has_prev_eval = False
        self.move_list.clear()
        self._reset_dashboard("Analysis position set")
        self.chess_board.playable_side = None
        self.chess_board.set_board(self.board)
        self._update_feedback()

    def _new_game(self) -> None:
        try:
            color = self._select_color()
            if color is None:
                return
            self.user_color = color
            self.board_flipped = self.user_color == chess.BLACK
            self.dashboard.set_eval_bar_gradient(self.board_flipped)

            self.engine_handler.stop_analysis()
            self.board.reset()
            self.redo_stack.clear()
            self.position_version += 1
            self.analysis_received = False
            self.last_known_move = None
            self.current_eval = 0.0
            self.prev_eval = 0.0
            self.has_prev_eval = False
            self.move_list.clear()
            self._reset_dashboard("New game started")
            self.chess_board.set_flipped(self.board_flipped)
            self.chess_board.playable_side = None
            self.chess_board.set_board(self.board)
            self._update_feedback()
        except Exception as e:
            logger.error(f"New game error: {e}")

    def run_analysis(self) -> None:
        self.analyzing_fen = self.board.fen()
        self.analyzing_version_id = self.position_version
        self.engine_handler.start_analysis(self.board.copy())

    def _update_turn_display(self) -> None:
        dash = self.dashboard
        turn_name = "White" if self.board.turn == chess.WHITE else "Black"
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            dash.lbl_turn.setText(f"# Checkmate! {winner} wins")
            dash.lbl_turn.setStyleSheet(f"""
                background-color: {COLORS['green']}; color: white; font-size: 13px; font-weight: bold;
                padding: 6px; border: 2px solid {COLORS['green']}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Checkmate")
        elif self.board.is_stalemate():
            dash.lbl_turn.setText("Stalemate! Draw")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['yellow']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['yellow']}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Stalemate")
        elif self.board.is_insufficient_material():
            dash.lbl_turn.setText("Draw! Insufficient material")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['yellow']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['yellow']}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  Draw")
        elif self.board.is_fifty_moves():
            dash.lbl_turn.setText("Draw! 50-move rule")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['yellow']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['yellow']}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Game Over  |  50-move Draw")
        elif self.board.can_claim_draw():
            dash.lbl_turn.setText("Draw can be claimed!")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['yellow']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['yellow']}; border-radius: 4px;
            """)
            dash.lbl_info.setText("Draw by repetition available")
        elif self.board.is_check():
            dash.lbl_turn.setText(f"{turn_name} is in check!")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['red']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['red']}; border-radius: 4px;
            """)
            dash.lbl_info.setText(f"Move {len(self.board.move_stack) // 2 + 1}  |  Check!")
        else:
            dash.lbl_turn.setText(f"{turn_name} to move")
            dash.lbl_turn.setStyleSheet(f"""
                color: {COLORS['accent']}; font-size: 12px; font-weight: bold;
                padding: 4px; border: 1px solid {COLORS['border']}; border-radius: 4px;
            """)
            mc = len(self.board.move_stack) // 2 + 1
            gp = "Endgame" if mc > 40 else "Middlegame" if mc > 15 else "Opening"
            dash.lbl_info.setText(f"Move {mc}  |  {gp}")

    def can_show_coach(self) -> bool:
        if self.board.is_game_over():
            return False
        if self.board.is_fifty_moves() or self.board.can_claim_draw():
            return False
        return self.board.turn == self.user_color

    def _on_analysis(self, info: dict) -> None:
        try:
            if self.analyzing_version_id != self.position_version:
                return
            if self.analyzing_fen and self.analyzing_fen != self.board.fen():
                return

            score = info.get("score")
            if not score:
                return

            now = time.time()
            if (now - self._last_ui_update) * 1000 < self._ui_throttle_ms:
                return
            self._last_ui_update = now

            dash = self.dashboard
            cur_eval: float = 0.0
            val: float = 0.0
            text = "0.00"

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
            if self.user_color is not None:
                self.has_prev_eval = True

            depth = info.get("depth", 0)
            dash.lbl_engine.setText(f"Depth {depth}  |  {info.get('seldepth', depth)}")

            eval_color = (
                COLORS["green"] if user_eval > 0.3
                else COLORS["red"] if user_eval < -0.3
                else COLORS["text"]
            )
            dash.lbl_eval.setStyleSheet(
                f"color: {eval_color}; font-size: 26px; font-weight: bold; font-family: 'Segoe UI', monospace;"
            )
            dash.lbl_eval.setText(text)

            if score.is_mate():
                if mate > 0:
                    dash.lbl_advantage.setText("White can mate")
                    dash.lbl_advantage.setStyleSheet(
                        f"color: {COLORS['green']}; font-size: 10px; font-weight: bold;"
                    )
                else:
                    dash.lbl_advantage.setText("Black can mate")
                    dash.lbl_advantage.setStyleSheet(
                        f"color: {COLORS['red']}; font-size: 10px; font-weight: bold;"
                    )
            else:
                adv, adv_color = self._eval_text(user_eval)
                dash.lbl_advantage.setText(adv)
                dash.lbl_advantage.setStyleSheet(
                    f"color: {adv_color}; font-size: 10px; font-weight: bold;"
                )

            bar_val = user_val + 1000
            dash.set_eval_bar_value(int(bar_val))

            self._update_turn_display()

            if not self.can_show_coach():
                self.chess_board.set_best_move(None)
                return

            if self.board.is_checkmate():
                self.engine_handler.stop_analysis()
                dash.lbl_feedback.setText("CHECKMATE! Game over.")
                dash.lbl_feedback.setStyleSheet(
                    f"color: {COLORS['green']}; padding: 10px; font-weight: bold;"
                    f"border: 2px solid {COLORS['green']}; border-radius: 4px;"
                )
                self.analysis_received = True
                return

            if score.is_mate():
                pv = info.get("pv")
                if pv:
                    self.last_known_move = pv[0]
                    self.chess_board.set_best_move(pv[0])
                    dash.lbl_best.setText(pv[0].uci())
                    dash.lbl_pv.setText("")
                    dash.lbl_feedback.setText(f"Forced mate in {abs(mate)} moves")
                    dash.lbl_feedback.setStyleSheet(
                        f"color: {COLORS['green']}; padding: 10px;"
                        f"border: 1px solid {COLORS['green']}; border-radius: 4px;"
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
                    dash.lbl_feedback.setStyleSheet(
                        f"color: {COLORS['red']}; padding: 10px; font-weight: bold;"
                        f"border: 1px solid {COLORS['red']}; border-radius: 4px;"
                    )
                elif delta > 1.0:
                    feedback = "MISS! Opponent blundered — you missed a chance!"
                    feed_color = COLORS["yellow"]
                    dash.lbl_feedback.setStyleSheet(
                        f"color: {COLORS['yellow']}; padding: 10px; font-weight: bold;"
                        f"border: 1px solid {COLORS['yellow']}; border-radius: 4px;"
                    )
                else:
                    dash.lbl_feedback.setStyleSheet(
                        f"color: {feed_color}; padding: 10px;"
                        f"background: {COLORS['bg']};"
                        f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
                    )
            else:
                dash.lbl_feedback.setStyleSheet(
                    f"color: {feed_color}; padding: 10px;"
                    f"background: {COLORS['bg']};"
                    f"border: 1px solid {COLORS['border']}; border-radius: 4px;"
                )

            dash.lbl_feedback.setText(feedback)

            pv = info.get("pv")
            if pv:
                self.last_known_move = pv[0]
                self.chess_board.set_best_move(pv[0])
                dash.lbl_best.setText(pv[0].uci())
                dash.lbl_pv.setText("Line: " + " ".join(m.uci() for m in pv[:4]))
                self.analysis_received = True

        except Exception as e:
            logger.error(f"Analysis error: {e}")

    def _eval_text(self, user_eval: float) -> tuple[str, str]:
        if user_eval > 0.5:
            return "You are winning", COLORS["green"]
        if user_eval > 0.2:
            return "You are better", COLORS["green"]
        if user_eval < -0.5:
            return "Opponent is winning", COLORS["red"]
        if user_eval < -0.2:
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
        if self.board.is_game_over() or self.board.is_fifty_moves() or self.board.can_claim_draw():
            self.engine_handler.stop_analysis()
            self.last_known_move = None
            self.chess_board.set_best_move(None)
            dash.lbl_best.setText("-")
            dash.lbl_pv.setText("")
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
            dash.lbl_feedback.setText(f"Waiting — {tn}'s turn to play")
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
        if self.board.is_game_over() or self.board.is_fifty_moves():
            return
        if not self.can_show_coach():
            return
        if self.analysis_received:
            self.analysis_received = False
            return
        if self.last_known_move:
            self.chess_board.set_best_move(self.last_known_move)
            self.dashboard.lbl_best.setText(f"{self.last_known_move.uci()} (cached)")

    def _on_engine_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Engine Error", msg)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self._heartbeat.stop()
        self.engine_handler.stop_engine()
        event.accept()
