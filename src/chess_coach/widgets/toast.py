"""Toast — slide-in notification with auto-dismiss.

Used for: "Brilliant move!", "Best in 3 lines", "Mistake detected", etc.
Positioned bottom-right of parent widget by default.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QPainter, QColor,
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect,
)

from chess_coach.theme_manager import Theme, get_theme


class Toast(QWidget):
    """Single toast notification. Auto-dismisses after duration_ms."""

    def __init__(self, message: str, theme: Theme | None = None,
                 severity: str = "info", duration_ms: int = 2500,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or get_theme()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._duration_ms = duration_ms
        # Build content
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        # Color by severity
        color_map = {
            "info": self._theme.accent,
            "success": self._theme.success,
            "warning": self._theme.warning,
            "danger": self._theme.danger,
            "brilliant": self._theme.brilliant or self._theme.accent_secondary,
        }
        self._border_color = QColor(color_map.get(severity, self._theme.accent))
        self._icon = {"info": "ℹ", "success": "✓", "warning": "⚠",
                      "danger": "✕", "brilliant": "★"}.get(severity, "•")
        icon_lbl = QLabel(self._icon)
        icon_lbl.setStyleSheet(f"color: {self._border_color.name()}; font-size: 18px; font-weight: bold;")
        icon_lbl.setFixedWidth(22)
        layout.addWidget(icon_lbl)
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color: {self._theme.text}; font-size: 13px;")
        layout.addWidget(msg_lbl, 1)
        self.setMaximumWidth(380)
        # Opacity effect for fade in/out
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade_anim: QPropertyAnimation | None = None
        # Slide animation
        self._slide_anim: QPropertyAnimation | None = None

    def show_at(self, x: int, y: int) -> None:
        """Show toast at given bottom-right anchor, then slide in."""
        self.adjustSize()
        # Position so that (x, y) is the bottom-right corner
        self.move(x - self.width(), y - self.height())
        self.show()
        # Fade in
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()
        # Auto-dismiss
        QTimer.singleShot(self._duration_ms, self.dismiss)

    def dismiss(self) -> None:
        """Fade out and close."""
        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(300)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_anim.finished.connect(self.close)
        self._fade_anim.start()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Card background
        bg = QColor(self._theme.card_bg)
        p.setBrush(bg)
        pen = self._border_color
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)


class ToastManager:
    """Manages a stack of toasts on a parent widget.

    New toasts push older ones up. Max 4 visible.
    """

    def __init__(self, parent: QWidget, theme: Theme | None = None) -> None:
        self._parent = parent
        self._theme = theme or get_theme()
        self._toasts: list[Toast] = []

    def show(self, message: str, severity: str = "info",
             duration_ms: int = 2500) -> Toast:
        toast = Toast(message, theme=self._theme, severity=severity,
                      duration_ms=duration_ms)
        self._toasts.append(toast)
        if len(self._toasts) > 4:
            old = self._toasts.pop(0)
            old.dismiss()
        self._reposition_all()
        toast.show_at(self._parent.width(), self._parent.height() - 12)
        return toast

    def _reposition_all(self) -> None:
        # Already positioned by show_at; nothing to do here for now.
        pass


__all__ = ["Toast", "ToastManager"]
