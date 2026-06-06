"""Custom-painted eval bar with WDL gradient.

Vertical bar showing position evaluation in centipawns (or mate). White on top,
black on bottom. Bar height is interpolated smoothly via QPropertyAnimation.
Includes WDL (win/draw/loss) sparkline on the side when enabled.

No QtCharts dep — pure QWidget + QPainter.
"""

from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QFont
from PyQt6.QtWidgets import QWidget

from chess_coach.theme_manager import Theme, get_theme


def _cp_to_fraction(cp: int) -> float:
    """Map centipawns to [-1, 1] using Stockfish-style sigmoid."""
    if cp is None:
        return 0.0
    # sigmoid with k=0.004 (≈250 cp = 0.5)
    return 2.0 / (1.0 + math.exp(-0.004 * cp)) - 1.0


class EvalBar(QWidget):
    """SOTA vertical eval bar with smooth animation + WDL display.

    Set eval in centipawns (positive = white winning). Set WDL as (w, d, l)
    in permille (0-1000). Use show_wdl() to display the WDL text.
    """

    def __init__(self, theme: Theme | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self._cp: float = 0.0
        self._target_cp: float = 0.0
        self._mate: int | None = None  # +N = white mates in N, -N = black mates
        self._wdl: tuple[int, int, int] = (500, 0, 500)  # 500/0/500 in permille
        self._show_wdl = True
        self._anim = QPropertyAnimation(self, b"cp", self)
        self._anim.setDuration(self._theme.animation.eval_duration_ms)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMinimumWidth(28)
        self.setMinimumHeight(120)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(),
                           self.sizePolicy().verticalPolicy())

    # --- PyQt property for animation ---

    def _get_cp(self) -> float:
        return self._cp

    def _set_cp(self, v: float) -> None:
        self._cp = v
        self.update()

    cp = pyqtProperty(float, _get_cp, _set_cp)

    # --- Public API ---

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._anim.setDuration(theme.animation.eval_duration_ms)
        self.update()

    def set_eval(self, cp: int | None, mate: int | None = None) -> None:
        """Set evaluation. cp=None + mate=N means mate in N (positive = white wins)."""
        self._anim.stop()
        if mate is not None:
            self._target_cp = 10000 if mate > 0 else -10000
            self._mate = mate
        else:
            self._target_cp = float(cp or 0)
            self._mate = None
        self._anim.setStartValue(self._cp)
        self._anim.setEndValue(self._target_cp)
        self._anim.start()

    def set_wdl(self, w: int, d: int, l: int) -> None:
        """Set WDL in permille (0-1000)."""
        self._wdl = (int(w), int(d), int(l))
        self.update()

    def show_wdl(self, show: bool = True) -> None:
        self._show_wdl = show
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Draw gradient bg (white top, black bottom)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(self._theme.eval_win))
        grad.setColorAt(0.5, QColor(self._theme.eval_draw))
        grad.setColorAt(1, QColor(self._theme.eval_loss))
        p.fillRect(0, 0, w, h, grad)
        # Compute bar position
        frac = _cp_to_fraction(int(self._cp))
        # frac in [-1, 1]; map to height: -1=bottom, +1=top, 0=center
        center_y = h * (1.0 - (frac + 1.0) / 2.0)
        # Bar fill (winning color)
        win_color = QColor(self._theme.eval_win)
        loss_color = QColor(self._theme.eval_loss)
        if self._cp >= 0:
            p.fillRect(0, int(center_y), w, h - int(center_y), win_color)
        else:
            p.fillRect(0, 0, w, int(center_y), loss_color)
        # Center line
        pen = QPen(QColor(0, 0, 0, 80), 1)
        p.setPen(pen)
        p.drawLine(0, h // 2, w, h // 2)
        # Eval text
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(self._theme.text))
        if self._mate is not None:
            txt = f"M{abs(self._mate)}"
        else:
            txt = f"{int(self._cp/100):+d}" if abs(self._cp) >= 100 else f"{int(self._cp):+d}"
        # Draw text at the bar's edge (inside winning color region)
        text_y = int(center_y) + (12 if self._cp >= 0 else -4)
        text_y = max(10, min(h - 4, text_y))
        p.drawText(QRectF(0, text_y - 10, w, 14),
                   Qt.AlignmentFlag.AlignCenter, txt)
        # WDL display on side (small)
        if self._show_wdl:
            w_pct = self._wdl[0] / 10
            d_pct = self._wdl[1] / 10
            l_pct = self._wdl[2] / 10
            wdl_text = f"{w_pct:.0f}/{d_pct:.0f}/{l_pct:.0f}"
            p.setPen(QColor(self._theme.text_dim))
            font2 = QFont("Segoe UI", 7)
            p.setFont(font2)
            # Draw in top-left corner
            p.drawText(QRectF(2, 2, w - 4, 12),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, wdl_text)


__all__ = ["EvalBar", "_cp_to_fraction"]
