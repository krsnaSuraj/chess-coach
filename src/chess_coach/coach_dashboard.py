from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QElapsedTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QProgressBar,
)

from chess_coach.chess_board import COLORS


class CoachDashboard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setStyleSheet(self._base_style())
        self._anim_start_val = 1000
        self._anim_target_val = 1000
        self._anim_progress = 1.0
        self._anim_elapsed = QElapsedTimer()
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_eval_bar)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        heading = QLabel("BOARD")
        heading.setObjectName("heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        self.lbl_turn = QLabel("White to move")
        self.lbl_turn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_turn.setStyleSheet(self._style_turn())
        layout.addWidget(self.lbl_turn)

        s1 = QLabel("EVALUATION")
        s1.setObjectName("section")
        layout.addWidget(s1)

        ew = QWidget()
        ew.setStyleSheet("border: none;")
        er = QHBoxLayout(ew)
        er.setContentsMargins(0, 0, 0, 0)
        er.setSpacing(8)

        self.eval_bar = QProgressBar()
        self.eval_bar.setOrientation(Qt.Orientation.Vertical)
        self.eval_bar.setRange(0, 2000)
        self.eval_bar.setValue(1000)
        self.eval_bar.setTextVisible(False)
        self.eval_bar.setFixedWidth(22)
        self.set_eval_bar_gradient()

        er.addWidget(self.eval_bar)

        stats = QVBoxLayout()
        stats.setSpacing(1)
        self.lbl_eval = QLabel("0.00")
        self.lbl_eval.setObjectName("eval")
        stats.addWidget(self.lbl_eval)
        self.lbl_advantage = QLabel("Equal")
        self.lbl_advantage.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; font-weight: bold;"
        )
        stats.addWidget(self.lbl_advantage)
        self.lbl_engine = QLabel("Ready")
        self.lbl_engine.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        stats.addWidget(self.lbl_engine)
        er.addLayout(stats)
        layout.addWidget(ew)

        s_open = QLabel("OPENING")
        s_open.setObjectName("section")
        layout.addWidget(s_open)

        self.lbl_opening = QLabel("Starting position")
        self.lbl_opening.setObjectName("opening")
        self.lbl_opening.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_opening)

        s2 = QLabel("BEST LINE")
        s2.setObjectName("section")
        layout.addWidget(s2)
        self.lbl_best = QLabel("-")
        self.lbl_best.setObjectName("bestmove")
        layout.addWidget(self.lbl_best)
        self.lbl_pv = QLabel("")
        self.lbl_pv.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px; font-family: 'Consolas', monospace;"
        )
        self.lbl_pv.setWordWrap(True)
        layout.addWidget(self.lbl_pv)

        s3 = QLabel("GAME INFO")
        s3.setObjectName("section")
        layout.addWidget(s3)
        self.lbl_info = QLabel("Move 1")
        self.lbl_info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        layout.addWidget(self.lbl_info)

        s4 = QLabel("COACH FEEDBACK")
        s4.setObjectName("section")
        layout.addWidget(s4)
        self.lbl_feedback = QLabel("Analyzing position...")
        self.lbl_feedback.setObjectName("feedback")
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.lbl_feedback, stretch=1)

    def _base_style(self) -> str:
        return f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(22,27,34,0.85), stop:1 rgba(13,17,23,0.75));
                border: 1px solid rgba(48,54,61,0.5);
                border-radius: 8px;
            }}
            QLabel {{
                color: {COLORS["text"]};
                background: transparent;
                border: none;
            }}
            QLabel#heading {{
                color: {COLORS["accent"]};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
                padding: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13,17,23,0.9), stop:1 rgba(22,27,34,0.7));
                border: 1px solid rgba(48,54,61,0.4);
                border-radius: 4px;
            }}
            QLabel#section {{
                color: {COLORS["text_dim"]};
                font-size: 9px;
                font-weight: bold;
                letter-spacing: 1.5px;
                padding: 2px 0;
            }}
            QLabel#eval {{
                color: {COLORS["text"]};
                font-size: 26px;
                font-weight: bold;
                font-family: 'Segoe UI', monospace;
            }}
            QLabel#opening {{
                color: {COLORS["accent"]};
                font-size: 11px;
                font-weight: bold;
                font-family: 'Segoe UI', monospace;
                padding: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13,17,23,0.9), stop:1 rgba(22,27,34,0.7));
                border: 1px solid rgba(48,54,61,0.4);
                border-radius: 4px;
            }}
            QLabel#bestmove {{
                color: {COLORS["green"]};
                font-size: 13px;
                font-family: 'Consolas', monospace;
                background: transparent;
            }}
            QLabel#feedback {{
                color: {COLORS["text"]};
                font-size: 11px;
                padding: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13,17,23,0.9), stop:1 rgba(22,27,34,0.7));
                border: 1px solid rgba(48,54,61,0.4);
                border-radius: 4px;
                min-height: 50px;
            }}
        """

    def _style_turn(self) -> str:
        return f"""
            color: {COLORS["accent"]}; font-size: 12px; font-weight: bold;
            padding: 4px; border: 1px solid {COLORS["border"]}; border-radius: 4px;
        """

    def set_eval_bar_value(self, value: int) -> None:
        self._anim_start_val = self.eval_bar.value()
        self._anim_target_val = max(0, min(2000, value))
        self._anim_progress = 0.0
        self._anim_elapsed.start()
        self._anim_timer.start(16)

    def _animate_eval_bar(self) -> None:
        elapsed = self._anim_elapsed.elapsed()
        self._anim_progress = min(1.0, elapsed / 200)
        t = 1.0 - (1.0 - self._anim_progress) ** 2
        val = int(self._anim_start_val + (self._anim_target_val - self._anim_start_val) * t)
        self.eval_bar.setValue(val)
        if self._anim_progress >= 1.0:
            self._anim_timer.stop()
            self.eval_bar.setValue(self._anim_target_val)

    def set_eval_bar_gradient(self, is_flipped: bool = False) -> None:
        if is_flipped:
            self.eval_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #30363d;
                    background-color: #0d1117;
                    border-radius: 3px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #3fb950, stop: 0.35 #ffffff, stop: 0.5 #8b949e,
                        stop: 0.65 #ffffff, stop: 1 #3fb950);
                    border-radius: 2px;
                }
            """)
        else:
            self.eval_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #30363d;
                    background-color: #0d1117;
                    border-radius: 3px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #f85149, stop: 0.35 #ffffff, stop: 0.5 #8b949e,
                        stop: 0.65 #ffffff, stop: 1 #f85149);
                    border-radius: 2px;
                }
            """)
