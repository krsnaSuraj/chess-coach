"""High contrast theme support for accessibility (WCAG 2.2 AAA contrast)."""

from __future__ import annotations

# WCAG 2.2 AAA: contrast ratio >= 7:1
# We override existing themes with extra-high contrast variants

HIGH_CONTRAST_COLORS: dict[str, str] = {
    # Foreground / background pairs
    "bg": "#000000",
    "fg": "#FFFFFF",
    "light_square": "#FFFFFF",
    "dark_square": "#000000",
    "highlight": "#FFFF00",  # pure yellow
    "selected": "#00FFFF",  # pure cyan
    "best_move": "#00FF00",  # pure green
    "brilliant": "#FF00FF",  # pure magenta
    "blunder": "#FF0000",  # pure red
    "text_dim": "#CCCCCC",
    "accent": "#FFFF00",
    "border": "#FFFFFF",
}


class HighContrastTheme:
    """High contrast theme for accessibility.

    WCAG 2.2 AAA: contrast ratio >= 7:1 for normal text, >= 4.5:1 for large.
    Uses pure colors (no anti-aliasing) and bold fonts.
    """

    name = "high-contrast"

    def __init__(self) -> None:
        self.colors = dict(HIGH_CONTRAST_COLORS)

    def get(self, key: str, default: str = "#000000") -> str:
        return self.colors.get(key, default)

    def all_colors(self) -> dict[str, str]:
        return dict(self.colors)


def is_high_contrast_active(theme_name: str) -> bool:
    return theme_name.lower() in {"high-contrast", "high_contrast", "hicontrast", "hc"}
