"""Accessibility helpers: keyboard nav, screen reader, high contrast.

SOTA 2026: WCAG 2.2 AA compliance. Lichess-grade a11y.
"""

from chess_coach.a11y.keyboard_nav import (
    KeyboardHandler,
    KEY_HELP,
    KeyboardShortcut,
)
from chess_coach.a11y.screen_reader import ScreenReaderAnnouncer, LiveRegion
from chess_coach.a11y.high_contrast import HighContrastTheme, is_high_contrast_active

__all__ = [
    "KeyboardHandler",
    "KEY_HELP",
    "KeyboardShortcut",
    "ScreenReaderAnnouncer",
    "LiveRegion",
    "HighContrastTheme",
    "is_high_contrast_active",
]
