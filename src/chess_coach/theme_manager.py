"""
theme_manager.py
----------------
SOTA-level theme system for Chess Coach v3.0.0.

Provides 8 built-in themes with full token coverage:
    board squares, piece shadows, accents, dashboard cards, eval bar gradients,
    last-move/check/legal-move highlights, arrows, coordinate text, sidebar,
    sound palettes (envelope shaping), animation presets (durations + easing).

Hot-swap at runtime via QSettings persistence and a signal-based API.
Web counterpart: ``static/css/themes.css`` mirrors these as CSS custom properties.

Public API:
    ThemeManager:    singleton-ish manager with QSettings persistence + signal
    Theme:           frozen dataclass with all tokens (color, sound, animation)
    THEMES:          registry of all 8 built-in themes
    get_theme(name): fetch by name (case-insensitive)
    list_themes():   return list of theme metadata for menu
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import QObject, QSettings, pyqtSignal
    _HAS_QT = True
except ImportError:
    QObject = object  # type: ignore
    pyqtSignal = None  # type: ignore
    QSettings = None  # type: ignore
    _HAS_QT = False


@dataclass(frozen=True)
class SoundPalette:
    """Envelope + harmonic parameters for procedural SFX generation.

    Each parameter shapes the SFX character of one theme:
    - attack_ms: rise time (0=instant, longer=softer/wooden)
    - decay_ms: fall time
    - fundamental_hz: base pitch
    - harmonics: tuple of (multiplier, amplitude) pairs for richer sound
    - brightness: 0-1, controls high-frequency content
    - reverb_ms: tail length
    """
    attack_ms: float = 5.0
    decay_ms: float = 60.0
    fundamental_hz: float = 600.0
    harmonics: tuple[tuple[float, float], ...] = ((2.0, 0.3), (3.0, 0.15))
    brightness: float = 0.5
    reverb_ms: float = 0.0


@dataclass(frozen=True)
class AnimationPreset:
    """Animation timing + easing tokens.

    All durations in milliseconds. easing values map to Q QEasingCurve enums
    and CSS easing-function keywords.
    """
    move_duration_ms: int = 200
    flip_duration_ms: int = 500
    eval_duration_ms: int = 400
    arrow_draw_ms: int = 200
    toast_duration_ms: int = 2500
    piece_settle_ms: int = 80
    easing: str = "OutCubic"           # OutCubic | InOutCubic | OutBack | Linear
    css_easing: str = "cubic-bezier(0.215, 0.610, 0.355, 1.000)"  # easeOutCubic


@dataclass(frozen=True)
class Theme:
    """Immutable theme definition.

    All colors are 7-char hex strings (#RRGGBB). Opacity is applied separately
    by the renderer. Keep this dataclass frozen so accidental mutation is
    impossible — use ThemeManager.apply() to switch.
    """
    name: str
    display_name: str
    description: str
    is_dark: bool

    # Board
    board_light: str
    board_dark: str
    board_border: str

    # Sidebar / window chrome
    bg: str
    sidebar: str
    card_bg: str
    card_border: str

    # Accents
    accent: str
    accent_secondary: str
    success: str
    warning: str
    danger: str

    # Text
    text: str
    text_dim: str

    # Board overlays
    last_move: str
    check: str
    legal_dot: str
    capture_ring: str
    selected: str
    premove: str

    # Engine arrows
    arrow_best: str        # best move
    arrow_plan: str        # plan arrow
    arrow_threat: str      # threat arrow
    arrow_user: str        # freehand user arrow

    # Eval bar gradient stops (low to high)
    eval_loss: str         # -infinity cp
    eval_draw: str         # 0 cp
    eval_win: str          # +infinity cp

    # Brilliant move highlight (move-class special effect)
    brilliant: str         # usually accent_secondary or warm gold

    # Sound
    sound: SoundPalette = field(default_factory=SoundPalette)

    # Animation
    animation: AnimationPreset = field(default_factory=AnimationPreset)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for web counterpart (static/js/theme.js consumes JSON)."""
        d: dict[str, Any] = {"name": self.name, "display_name": self.display_name,
                             "description": self.description, "is_dark": self.is_dark}
        for k in ("board_light", "board_dark", "board_border", "bg", "sidebar",
                  "card_bg", "card_border", "accent", "accent_secondary",
                  "success", "warning", "danger", "text", "text_dim",
                  "last_move", "check", "legal_dot", "capture_ring", "selected",
                  "premove", "arrow_best", "arrow_plan", "arrow_threat",
                  "arrow_user", "eval_loss", "eval_draw", "eval_win", "brilliant"):
            d[k] = getattr(self, k)
        return d


# ============================================================================
# 8 Built-in Themes
# ============================================================================

_MIDNIGHT = Theme(
    name="midnight",
    display_name="Midnight",
    description="Deep blue-black, neon blue accents. Default.",
    is_dark=True,
    board_light="#e8e6df", board_dark="#3a4660", board_border="#1a1f2e",
    bg="#0d1117", sidebar="#161b22", card_bg="#1c2128", card_border="#30363d",
    accent="#58a6ff", accent_secondary="#a371f7",
    success="#3fb950", warning="#d29922", danger="#f85149",
    text="#f0f6fc", text_dim="#8b949e",
    last_move="#FFFF64", check="#FF3232", legal_dot="#646464",
    capture_ring="#323232", selected="#58a6ff", premove="#a371f7",
    arrow_best="#00FF00", arrow_plan="#58a6ff", arrow_threat="#FF6B6B",
    arrow_user="#FFD700",
    eval_loss="#FF3232", eval_draw="#646464", eval_win="#3FB950",
    brilliant="#FFD700",
    sound=SoundPalette(attack_ms=2, decay_ms=80, fundamental_hz=800,
                       harmonics=((2.0, 0.25),), brightness=0.6, reverb_ms=20),
    animation=AnimationPreset(move_duration_ms=180, easing="OutCubic",
                              css_easing="cubic-bezier(0.215, 0.610, 0.355, 1.000)"),
)

_FOREST = Theme(
    name="forest",
    display_name="Forest",
    description="Dark green, earthy browns, organic feel.",
    is_dark=True,
    board_light="#ebecd0", board_dark="#779952", board_border="#1f2a1c",
    bg="#0e1a0e", sidebar="#162616", card_bg="#1d2d1d", card_border="#2c4a2c",
    accent="#a3d977", accent_secondary="#d4a373",
    success="#7cc473", warning="#d4a373", danger="#e07a5f",
    text="#e8f0d8", text_dim="#7d9471",
    last_move="#f6f669", check="#e07a5f", legal_dot="#5a7245",
    capture_ring="#3d5a3d", selected="#a3d977", premove="#d4a373",
    arrow_best="#7cc473", arrow_plan="#a3d977", arrow_threat="#e07a5f",
    arrow_user="#f6f669",
    eval_loss="#e07a5f", eval_draw="#5a7245", eval_win="#7cc473",
    brilliant="#f6f669",
    sound=SoundPalette(attack_ms=8, decay_ms=120, fundamental_hz=400,
                       harmonics=((2.0, 0.4), (3.0, 0.2)), brightness=0.3,
                       reverb_ms=40),
    animation=AnimationPreset(move_duration_ms=220, easing="InOutCubic",
                              css_easing="cubic-bezier(0.645, 0.045, 0.355, 1.000)"),
)

_SUNSET = Theme(
    name="sunset",
    display_name="Sunset",
    description="Warm orange/red, golden hour atmosphere.",
    is_dark=True,
    board_light="#f5e6d3", board_dark="#b86b4a", board_border="#2d1a14",
    bg="#1a0f0a", sidebar="#2d1810", card_bg="#3a2218", card_border="#5a3424",
    accent="#ff8c42", accent_secondary="#ffd166",
    success="#ffb84d", warning="#ff6b35", danger="#d62828",
    text="#fff3e0", text_dim="#c4a484",
    last_move="#ffd166", check="#d62828", legal_dot="#8b4513",
    capture_ring="#5a2e1a", selected="#ff8c42", premove="#ffd166",
    arrow_best="#ffb84d", arrow_plan="#ff8c42", arrow_threat="#d62828",
    arrow_user="#fff3e0",
    eval_loss="#d62828", eval_draw="#8b4513", eval_win="#ffb84d",
    brilliant="#ffd166",
    sound=SoundPalette(attack_ms=10, decay_ms=140, fundamental_hz=350,
                       harmonics=((2.0, 0.35), (3.0, 0.15)), brightness=0.4,
                       reverb_ms=60),
    animation=AnimationPreset(move_duration_ms=250, easing="OutBack",
                              css_easing="cubic-bezier(0.340, 1.560, 0.640, 1.000)"),
)

_MARBLE = Theme(
    name="marble",
    display_name="Marble",
    description="White/gray stone, cool classical.",
    is_dark=False,
    board_light="#f0f0f0", board_dark="#7a7a7a", board_border="#c0c0c0",
    bg="#fafafa", sidebar="#f0f0f0", card_bg="#ffffff", card_border="#d0d0d0",
    accent="#1e88e5", accent_secondary="#5e35b1",
    success="#43a047", warning="#fb8c00", danger="#e53935",
    text="#212121", text_dim="#616161",
    last_move="#bbdefb", check="#e53935", legal_dot="#9e9e9e",
    capture_ring="#757575", selected="#1e88e5", premove="#5e35b1",
    arrow_best="#43a047", arrow_plan="#1e88e5", arrow_threat="#e53935",
    arrow_user="#fb8c00",
    eval_loss="#e53935", eval_draw="#9e9e9e", eval_win="#43a047",
    brilliant="#5e35b1",
    sound=SoundPalette(attack_ms=3, decay_ms=70, fundamental_hz=1000,
                       harmonics=((2.0, 0.3), (4.0, 0.1)), brightness=0.7,
                       reverb_ms=10),
    animation=AnimationPreset(move_duration_ms=160, easing="OutCubic",
                              css_easing="cubic-bezier(0.215, 0.610, 0.355, 1.000)"),
)

_LICHESS = Theme(
    name="lichess",
    display_name="Lichess",
    description="Official brown/cream Lichess look.",
    is_dark=False,
    board_light="#f0d9b5", board_dark="#b58863", board_border="#704624",
    bg="#312e2b", sidebar="#262522", card_bg="#34302e", card_border="#4a4540",
    accent="#629924", accent_secondary="#3893e8",
    success="#629924", warning="#d59120", danger="#cd3232",
    text="#bababa", text_dim="#898378",
    last_move="#f6f669", check="#cd3232", legal_dot="#898378",
    capture_ring="#4a4540", selected="#629924", premove="#3893e8",
    arrow_best="#629924", arrow_plan="#3893e8", arrow_threat="#cd3232",
    arrow_user="#d59120",
    eval_loss="#cd3232", eval_draw="#898378", eval_win="#629924",
    brilliant="#d59120",
    sound=SoundPalette(attack_ms=4, decay_ms=80, fundamental_hz=600,
                       harmonics=((2.0, 0.3), (3.0, 0.15)), brightness=0.5,
                       reverb_ms=15),
    animation=AnimationPreset(move_duration_ms=200, easing="InOutCubic",
                              css_easing="cubic-bezier(0.645, 0.045, 0.355, 1.000)"),
)

_BLUE_GLASS = Theme(
    name="blue_glass",
    display_name="Blue Glass",
    description="Cool blue/cyan, glassmorphism, frosted.",
    is_dark=True,
    board_light="#e0f2ff", board_dark="#4a90c2", board_border="#0a2540",
    bg="#06121e", sidebar="#0e1e2e", card_bg="#14304a", card_border="#1e5078",
    accent="#4fc3f7", accent_secondary="#81d4fa",
    success="#4dd0e1", warning="#ffb74d", danger="#ff5252",
    text="#e1f5fe", text_dim="#90caf9",
    last_move="#b3e5fc", check="#ff5252", legal_dot="#4fc3f7",
    capture_ring="#1e5078", selected="#4fc3f7", premove="#81d4fa",
    arrow_best="#4dd0e1", arrow_plan="#4fc3f7", arrow_threat="#ff5252",
    arrow_user="#fff59d",
    eval_loss="#ff5252", eval_draw="#4fc3f7", eval_win="#4dd0e1",
    brilliant="#fff59d",
    sound=SoundPalette(attack_ms=1, decay_ms=60, fundamental_hz=1200,
                       harmonics=((2.0, 0.2), (3.0, 0.1)), brightness=0.8,
                       reverb_ms=5),
    animation=AnimationPreset(move_duration_ms=200, easing="OutCubic",
                              css_easing="cubic-bezier(0.215, 0.610, 0.355, 1.000)"),
)

_CYBER_NEON = Theme(
    name="cyber_neon",
    display_name="Cyber Neon",
    description="Electric magenta/cyan, futuristic synthwave.",
    is_dark=True,
    board_light="#ff00ff", board_dark="#0ff0fc", board_border="#1a0033",
    bg="#0a0014", sidebar="#1a0033", card_bg="#2a0044", card_border="#ff00ff",
    accent="#ff00ff", accent_secondary="#0ff0fc",
    success="#0ff0fc", warning="#ffff00", danger="#ff0055",
    text="#ffffff", text_dim="#ff77ff",
    last_move="#ffff00", check="#ff0055", legal_dot="#ff00ff",
    capture_ring="#ff00ff", selected="#ffff00", premove="#0ff0fc",
    arrow_best="#0ff0fc", arrow_plan="#ff00ff", arrow_threat="#ff0055",
    arrow_user="#ffff00",
    eval_loss="#ff0055", eval_draw="#ff00ff", eval_win="#0ff0fc",
    brilliant="#ffff00",
    sound=SoundPalette(attack_ms=1, decay_ms=40, fundamental_hz=1500,
                       harmonics=((2.0, 0.4), (3.0, 0.2), (4.0, 0.1)),
                       brightness=0.9, reverb_ms=5),
    animation=AnimationPreset(move_duration_ms=140, easing="OutBack",
                              css_easing="cubic-bezier(0.340, 1.560, 0.640, 1.000)"),
)

_SEPIA = Theme(
    name="sepia",
    display_name="Sepia",
    description="Warm brown, paper-like, vintage book feel.",
    is_dark=False,
    board_light="#f4e8d0", board_dark="#a07855", board_border="#5c3a1e",
    bg="#fbf2dc", sidebar="#f0e4c8", card_bg="#fff8e7", card_border="#d4b896",
    accent="#8b4513", accent_secondary="#a0522d",
    success="#6b8e23", warning="#daa520", danger="#8b0000",
    text="#3e2723", text_dim="#795548",
    last_move="#ffd54f", check="#8b0000", legal_dot="#8b4513",
    capture_ring="#a0522d", selected="#8b4513", premove="#a0522d",
    arrow_best="#6b8e23", arrow_plan="#8b4513", arrow_threat="#8b0000",
    arrow_user="#daa520",
    eval_loss="#8b0000", eval_draw="#8b4513", eval_win="#6b8e23",
    brilliant="#daa520",
    sound=SoundPalette(attack_ms=12, decay_ms=160, fundamental_hz=300,
                       harmonics=((2.0, 0.4), (3.0, 0.2)), brightness=0.2,
                       reverb_ms=80),
    animation=AnimationPreset(move_duration_ms=240, easing="InOutCubic",
                              css_easing="cubic-bezier(0.645, 0.045, 0.355, 1.000)"),
)


_PAPER = Theme(
    display_name="Paper",
    description="Clean white paper, high readability, accessible.",
    is_dark=False,
    name="paper",
    board_light="#fafaf9",
    board_dark="#d6d3d1",
    board_border="#1c1917",
    bg="#f5f5f4",
    sidebar="#e7e5e4",
    card_bg="#ffffff",
    card_border="#d6d3d1",
    accent="#0c4a6e",
    accent_secondary="#7c2d12",
    success="#16a34a",
    warning="#f59e0b",
    danger="#dc2626",
    text="#1c1917",
    text_dim="#57534e",
    last_move="#fde047",
    check="#dc2626",
    legal_dot="#78716c",
    capture_ring="#a8a29e",
    selected="#0c4a6e",
    premove="#a16207",
    arrow_best="#16a34a",
    arrow_plan="#0c4a6e",
    arrow_threat="#dc2626",
    arrow_user="#7c2d12",
    eval_loss="#dc2626",
    eval_draw="#737373",
    eval_win="#16a34a",
    brilliant="#fbbf24",
    sound=SoundPalette(harmonics=((1.0, 0.5),), brightness=0.4, reverb_ms=120),
    animation=AnimationPreset(move_duration_ms=200, easing="ease-out", css_easing="ease-out"),
)

_HIGH_CONTRAST = Theme(
    display_name="High Contrast",
    description="Maximum contrast, accessibility-first, monochrome accents.",
    is_dark=True,
    name="high_contrast",
    board_light="#ffffff",
    board_dark="#000000",
    board_border="#ffffff",
    bg="#000000",
    sidebar="#000000",
    card_bg="#0a0a0a",
    card_border="#ffffff",
    accent="#ffff00",
    accent_secondary="#00ffff",
    success="#00ff00",
    warning="#ffff00",
    danger="#ff0000",
    text="#ffffff",
    text_dim="#cccccc",
    last_move="#ffff00",
    check="#ff0000",
    legal_dot="#ffff00",
    capture_ring="#ff00ff",
    selected="#ffff00",
    premove="#00ffff",
    arrow_best="#00ff00",
    arrow_plan="#00ffff",
    arrow_threat="#ff0000",
    arrow_user="#ff00ff",
    eval_loss="#ff0000",
    eval_draw="#ffffff",
    eval_win="#00ff00",
    brilliant="#ffff00",
    sound=SoundPalette(harmonics=((1.0, 1.0),), brightness=0.8, reverb_ms=0),
    animation=AnimationPreset(move_duration_ms=120, easing="linear", css_easing="linear"),
)


THEMES: dict[str, Theme] = {
    "midnight": _MIDNIGHT,
    "forest": _FOREST,
    "sunset": _SUNSET,
    "marble": _MARBLE,
    "lichess": _LICHESS,
    "blue_glass": _BLUE_GLASS,
    "cyber_neon": _CYBER_NEON,
    "sepia": _SEPIA,
    "paper": _PAPER,
    "high_contrast": _HIGH_CONTRAST,
}

DEFAULT_THEME = "midnight"


def get_theme(name: str | None = None) -> Theme:
    """Fetch theme by name (case-insensitive). Falls back to default.

    Calling ``get_theme()`` with no argument returns the default theme.
    """
    if name is None:
        return THEMES[DEFAULT_THEME]
    key = name.lower().strip()
    if key in THEMES:
        return THEMES[key]
    logger.warning("Unknown theme %r, falling back to %r", name, DEFAULT_THEME)
    return THEMES[DEFAULT_THEME]


def list_themes() -> list[dict[str, str]]:
    """Return metadata for theme picker UIs."""
    return [
        {"name": t.name, "display_name": t.display_name, "description": t.description,
         "is_dark": str(t.is_dark).lower()}
        for t in THEMES.values()
    ]


# ============================================================================
# ThemeManager — singleton with QSettings persistence + signal
# ============================================================================

if _HAS_QT and pyqtSignal is not None:
    class _Signal:
        """Lightweight signal shim to allow ThemeManager.themeChanged to work
        both with and without a real QObject parent."""
        def __init__(self) -> None:
            self._slots: list = []
        def connect(self, slot) -> None:
            self._slots.append(slot)
        def emit(self, theme: Theme) -> None:
            for s in self._slots:
                try:
                    s(theme)
                except Exception as e:
                    logger.warning("Theme signal slot failed: %s", e)
else:
    class _Signal:  # type: ignore[no-redef]
        def __init__(self) -> None: self._slots = []
        def connect(self, slot): self._slots.append(slot)
        def emit(self, theme): [s(theme) for s in self._slots]


class ThemeManager:
    """Manages current theme + signals on change.

    Persists choice to QSettings under "ui/theme" (or plain attribute in tests
    where QSettings is unavailable).
    """

    def __init__(self, parent: QObject | None = None) -> None:
        self._current: Theme = THEMES[DEFAULT_THEME]
        self.themeChanged = _Signal()
        if QSettings is not None:
            try:
                s = QSettings() if parent is None else QSettings(parent)
                saved = str(s.value("ui/theme", DEFAULT_THEME))
                self._current = get_theme(saved)
            except Exception as e:
                logger.debug("QSettings unavailable for theme persistence: %s", e)

    @property
    def current(self) -> Theme:
        return self._current

    def apply(self, theme: Theme | str) -> None:
        """Switch theme, persist, emit signal."""
        new = get_theme(theme) if isinstance(theme, str) else theme
        if new.name == self._current.name:
            return
        self._current = new
        if QSettings is not None:
            try:
                s = QSettings()
                s.setValue("ui/theme", new.name)
            except Exception:
                pass
        self.themeChanged.emit(new)
        logger.info("Theme applied: %s", new.display_name)

    def apply_by_name(self, name: str) -> None:
        self.apply(name)


# Module-level singleton for app-wide use
_manager: ThemeManager | None = None


def manager() -> ThemeManager:
    """Get or create the module-level ThemeManager singleton."""
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager


__all__ = [
    "Theme", "SoundPalette", "AnimationPreset", "THEMES", "DEFAULT_THEME",
    "get_theme", "list_themes", "ThemeManager", "manager",
]
