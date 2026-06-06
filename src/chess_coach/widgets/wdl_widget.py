"""WDLWidget — 3-bar win/draw/loss display.

Stacked horizontal bar showing the engine's win/draw/loss percentages.
Updates live as analysis progresses.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from chess_coach.theme_manager import Theme, get_theme


class WDLWidget(QWidget):
    """3-segment horizontal bar: W | D | L (win | draw | loss)."""

    def __init__(self, theme: Theme | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self._w = 33
        self._d = 34
        self._l = 33
        self.setMinimumHeight(36)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_wdl(self, w: int, d: int, l: int) -> None:
        """Set WDL percentages (0-100)."""
        total = max(1, w + d + l)
        self._w = int(w * 100 / total)
        self._d = int(d * 100 / total)
        self._l = 100 - self._w - self._d
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # 3 colored bars stacked horizontally
        bar_h = h - 14
        y = 2
        x = 0
        w_w = w * self._w / 100
        d_w = w * self._d / 100
        l_w = w - w_w - d_w
        p.fillRect(QRectF(x, y, w_w, bar_h), QColor(self._theme.success))
        p.fillRect(QRectF(x + w_w, y, d_w, bar_h), QColor(self._theme.text_dim))
        p.fillRect(QRectF(x + w_w + d_w, y, l_w, bar_h), QColor(self._theme.danger))
        # Labels
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor("white"))
        p.drawText(QRectF(x, y, w_w, bar_h), Qt.AlignmentFlag.AlignCenter,
                   f"W {self._w}%")
        p.setPen(QColor(self._theme.text))
        p.drawText(QRectF(x + w_w, y, d_w, bar_h), Qt.AlignmentFlag.AlignCenter,
                   f"D {self._d}%")
        p.setPen(QColor("white"))
        p.drawText(QRectF(x + w_w + d_w, y, l_w, bar_h), Qt.AlignmentFlag.AlignCenter,
                   f"L {self._l}%")


__all__ = ["WDLWidget"]
