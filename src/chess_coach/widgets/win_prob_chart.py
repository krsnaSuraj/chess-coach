"""WinProbChart — sparkline chart of win probability over the game.

Plots a smooth area chart of white's win probability (0-100%) across the
moves played. Highlights critical moments (turning points where |Δwp| > 10%).

Pure QPainter (no QtCharts dep).
"""

from __future__ import annotations

from collections import deque
from typing import Iterable

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget

from chess_coach.theme_manager import Theme, get_theme


class WinProbChart(QWidget):
    """Sparkline area chart of win-probability vs move number.

    Usage: feed ``add_wp(wp_pct)`` after each half-move. Critical moments
    (|Δwp| > 10) are marked with a dot.
    """

    CRITICAL_THRESHOLD = 10.0  # percentage points

    def __init__(self, max_points: int = 200, theme: Theme | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self._data: deque[float] = deque(maxlen=max_points)
        self.setMinimumHeight(80)
        self.setMinimumWidth(200)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def add_wp(self, wp_pct: float) -> None:
        """Add a win-probability point (0-100)."""
        self._data.append(float(wp_pct))
        self.update()

    def set_data(self, data: Iterable[float]) -> None:
        self._data = deque((float(x) for x in data), maxlen=self._data.maxlen)
        self.update()

    def clear(self) -> None:
        self._data.clear()
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Background
        p.fillRect(self.rect(), QColor(self._theme.bg))
        # Draw 50% line
        pen = QPen(QColor(self._theme.text_dim), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        mid_y = h / 2
        p.drawLine(0, int(mid_y), w, int(mid_y))
        if not self._data:
            # Hint text
            p.setPen(QColor(self._theme.text_dim))
            font = QFont("Segoe UI", 9)
            p.setFont(font)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Win probability will appear here")
            return
        n = len(self._data)
        if n < 2:
            return
        # Build path
        path = QPainterPath()
        for i, v in enumerate(self._data):
            x = i * w / max(1, n - 1)
            y = h * (1.0 - v / 100.0)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        # Fill area
        fill_path = QPainterPath(path)
        fill_path.lineTo(w, h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()
        grad_color = QColor(self._theme.success)
        grad_color.setAlpha(60)
        p.fillPath(fill_path, grad_color)
        # Line
        pen = QPen(QColor(self._theme.success), 2)
        p.setPen(pen)
        p.drawPath(path)
        # Critical moments
        pen2 = QPen(QColor(self._theme.warning), 1)
        p.setPen(pen2)
        prev = self._data[0]
        for i, v in enumerate(self._data):
            if abs(v - prev) > self.CRITICAL_THRESHOLD:
                x = i * w / max(1, n - 1)
                y = h * (1.0 - v / 100.0)
                p.setBrush(QColor(self._theme.warning))
                p.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
            prev = v
        # Last-value label
        p.setPen(QColor(self._theme.text))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(font)
        last = self._data[-1]
        p.drawText(QRectF(w - 50, 4, 46, 14),
                   Qt.AlignmentFlag.AlignRight, f"{last:.0f}%")


__all__ = ["WinProbChart"]
