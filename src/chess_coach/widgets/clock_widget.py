"""ClockWidget — digital chess clock with low-time pulse animation.

Each side has its own countdown. Pauses/resumes on demand. Pulses red
below 30 seconds. Shows tenths-of-a-second in last 10 seconds.

Active side is identified by chess.WHITE (=True) or chess.BLACK (=False).
"""

from __future__ import annotations

import chess
from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from chess_coach.theme_manager import Theme, get_theme


class ClockWidget(QWidget):
    """Two-row clock display: top = white's time, bottom = black's time.

    The active side's row is highlighted. Pulses red below 30s.
    """

    flag_fell = pyqtSignal(object)  # chess.Color

    def __init__(self, theme: Theme | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self._white_ms = 5 * 60 * 1000
        self._black_ms = 5 * 60 * 1000
        self._active: chess.Color | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._last_tick: QTime | None = None
        self._pulse_alpha = 255
        self.setMinimumHeight(60)
        self.setMinimumWidth(140)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_time_control(self, minutes: float, increment_s: float = 0.0) -> None:
        ms = int(minutes * 60 * 1000)
        self._white_ms = ms
        self._black_ms = ms
        self.update()

    def set_white_ms(self, ms: int) -> None:
        self._white_ms = max(0, int(ms))
        self.update()

    def set_black_ms(self, ms: int) -> None:
        self._black_ms = max(0, int(ms))
        self.update()

    def start(self, side: chess.Color) -> None:
        self._active = side
        self._last_tick = QTime.currentTime()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._active = None
        self.update()

    def pause(self) -> None:
        self._timer.stop()

    def resume(self) -> None:
        if self._active is not None:
            self._last_tick = QTime.currentTime()
            self._timer.start()

    def _tick(self) -> None:
        if self._active is None or self._last_tick is None:
            return
        now = QTime.currentTime()
        elapsed = self._last_tick.msecsTo(now)
        self._last_tick = now
        if self._active == chess.WHITE:
            self._white_ms = max(0, self._white_ms - elapsed)
            if self._white_ms == 0:
                self._timer.stop()
                self.flag_fell.emit(self._active)
        else:
            self._black_ms = max(0, self._black_ms - elapsed)
            if self._black_ms == 0:
                self._timer.stop()
                self.flag_fell.emit(self._active)
        active_ms = self._white_ms if self._active == chess.WHITE else self._black_ms
        if active_ms < 30 * 1000:
            self._pulse_alpha = int(155 + 100 * abs(((now.msec() // 5) % 20) - 10) / 10)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        row_h = h // 2
        w_active = self._active == chess.WHITE
        b_active = self._active == chess.BLACK
        self._draw_row(p, 0, row_h, "White", self._white_ms, w_active)
        self._draw_row(p, row_h, row_h, "Black", self._black_ms, b_active)

    def _draw_row(self, p: QPainter, y: int, h: int, label: str, ms: int, active: bool) -> None:
        if active:
            bg = QColor(self._theme.card_bg)
            p.fillRect(0, y, self.width(), h, bg)
        text = self._format_time(ms)
        font = QFont("Consolas", 18, QFont.Weight.Bold)
        p.setFont(font)
        if ms == 0:
            color = QColor(self._theme.danger)
        elif ms < 30 * 1000 and active:
            color = QColor(self._theme.danger)
            color.setAlpha(self._pulse_alpha)
        else:
            color = QColor(self._theme.text if not active else self._theme.accent)
        p.setPen(color)
        p.drawText(self.rect().adjusted(0, y, 0, 0),
                   Qt.AlignmentFlag.AlignCenter, text)
        font2 = QFont("Segoe UI", 7)
        p.setFont(font2)
        p.setPen(QColor(self._theme.text_dim))
        p.drawText(4, y + 12, label)

    @staticmethod
    def _format_time(ms: int) -> str:
        if ms <= 0:
            return "0:00.0"
        total_s = ms / 1000
        m = int(total_s // 60)
        s = int(total_s % 60)
        tenths = int((ms % 1000) // 100)
        if ms < 10 * 1000:
            return f"{m}:{s:02d}.{tenths}"
        return f"{m}:{s:02d}"


__all__ = ["ClockWidget"]
