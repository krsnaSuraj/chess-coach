"""SettingsDialog — tabbed settings dialog (Engine / Humanizer / Display / Sound / Theme).

Opened from main menu via Settings... action (F2).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QSlider, QLabel,
    QPushButton, QDialogButtonBox, QHBoxLayout, QGroupBox,
)

from chess_coach.theme_manager import ThemeManager, list_themes
from chess_coach.sound_manager import SoundManager, SFX_TYPES, MUSIC_TRACKS


class SettingsDialog(QDialog):
    """Tabbed settings: Engine, Humanizer, Display, Sound, Theme."""

    def __init__(self, config: dict, theme_manager: ThemeManager,
                 sound_manager: SoundManager | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = dict(config)
        self._theme_manager = theme_manager
        self._sound_manager = sound_manager
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 480)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        tabs.addTab(self._build_engine_tab(), "Engine")
        tabs.addTab(self._build_humanizer_tab(), "Humanizer")
        tabs.addTab(self._build_display_tab(), "Display")
        tabs.addTab(self._build_sound_tab(), "Sound")
        tabs.addTab(self._build_theme_tab(), "Theme")
        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    # --- tabs ---

    def _build_engine_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        eng = self._config.get("engine", {})
        # Threads
        self._threads = QSpinBox()
        self._threads.setRange(0, 32)
        self._threads.setValue(int(eng.get("threads", 2)))
        self._threads.setSpecialValueText("Auto")
        form.addRow("Threads (0=auto):", self._threads)
        # Hash
        self._hash = QSpinBox()
        self._hash.setRange(0, 4096)
        self._hash.setSingleStep(64)
        self._hash.setValue(int(eng.get("hash_mb", 64)))
        self._hash.setSpecialValueText("Auto (25% RAM)")
        form.addRow("Hash MB (0=auto):", self._hash)
        # MultiPV
        self._multipv = QSpinBox()
        self._multipv.setRange(1, 5)
        self._multipv.setValue(int(eng.get("multipv", 3)))
        form.addRow("MultiPV (top-N lines):", self._multipv)
        # Movetime
        self._movetime = QSpinBox()
        self._movetime.setRange(100, 60000)
        self._movetime.setSingleStep(100)
        self._movetime.setValue(int(eng.get("movetime_ms", 2000)))
        form.addRow("Move time (ms):", self._movetime)
        # WDL
        self._wdl = QCheckBox("Show Win/Draw/Loss percentages")
        self._wdl.setChecked(bool(eng.get("show_wdl", True)))
        form.addRow(self._wdl)
        return w

    def _build_humanizer_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        h = self._config.get("humanizer", {})
        self._blunder_threshold = QDoubleSpinBox()
        self._blunder_threshold.setRange(0.5, 5.0)
        self._blunder_threshold.setSingleStep(0.1)
        self._blunder_threshold.setValue(float(h.get("blunder_threshold", 1.5)))
        form.addRow("Blunder threshold (pawns):", self._blunder_threshold)
        self._oscillation_penalty = QDoubleSpinBox()
        self._oscillation_penalty.setRange(0.0, 1.0)
        self._oscillation_penalty.setSingleStep(0.05)
        self._oscillation_penalty.setValue(float(h.get("oscillation_penalty", 0.2)))
        form.addRow("Oscillation penalty:", self._oscillation_penalty)
        self._think_time_min = QSpinBox()
        self._think_time_min.setRange(0, 30000)
        self._think_time_min.setSingleStep(100)
        self._think_time_min.setValue(int(h.get("think_time_min_ms", 800)))
        form.addRow("Min think time (ms):", self._think_time_min)
        self._think_time_max = QSpinBox()
        self._think_time_max.setRange(0, 60000)
        self._think_time_max.setSingleStep(100)
        self._think_time_max.setValue(int(h.get("think_time_max_ms", 5000)))
        form.addRow("Max think time (ms):", self._think_time_max)
        return w

    def _build_display_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        disp = self._config.get("display", {})
        self._flip_on_first = QCheckBox("Play as Black (board flipped)")
        self._flip_on_first.setChecked(bool(disp.get("play_as_black", False)))
        form.addRow(self._flip_on_first)
        self._show_coordinates = QCheckBox("Show coordinates")
        self._show_coordinates.setChecked(bool(disp.get("show_coordinates", True)))
        form.addRow(self._show_coordinates)
        self._show_legal_moves = QCheckBox("Show legal move dots")
        self._show_legal_moves.setChecked(bool(disp.get("show_legal_moves", True)))
        form.addRow(self._show_legal_moves)
        self._animate_moves = QCheckBox("Animate piece moves")
        self._animate_moves.setChecked(bool(disp.get("animate_moves", True)))
        form.addRow(self._animate_moves)
        return w

    def _build_sound_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        # Enabled
        self._sound_enabled = QCheckBox("Enable sounds")
        sm_enabled = bool(self._sound_manager.is_enabled()) if self._sound_manager else True
        self._sound_enabled.setChecked(sm_enabled)
        layout.addWidget(self._sound_enabled)
        # Volume
        vol_group = QGroupBox("Volume")
        vol_layout = QHBoxLayout(vol_group)
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        sm_vol = int(self._sound_manager._volume * 100) if self._sound_manager else 50
        self._volume.setValue(sm_vol)
        self._volume_label = QLabel(f"{sm_vol}%")
        self._volume.valueChanged.connect(lambda v: self._volume_label.setText(f"{v}%"))
        vol_layout.addWidget(self._volume, 1)
        vol_layout.addWidget(self._volume_label)
        layout.addWidget(vol_group)
        # Test buttons
        test_group = QGroupBox("Test sounds")
        test_layout = QHBoxLayout(test_group)
        for sfx in SFX_TYPES:
            btn = QPushButton(sfx.replace("_", " ").title())
            btn.clicked.connect(lambda _=False, s=sfx: self._test_sound(s))
            test_layout.addWidget(btn)
        layout.addWidget(test_group)
        # Music preview
        music_group = QGroupBox("Background music")
        music_layout = QHBoxLayout(music_group)
        for track in MUSIC_TRACKS:
            btn = QPushButton(track.title())
            btn.clicked.connect(lambda _=False, t=track: self._preview_music(t))
            music_layout.addWidget(btn)
        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self._stop_music)
        music_layout.addWidget(stop_btn)
        layout.addWidget(music_group)
        layout.addStretch(1)
        return w

    def _build_theme_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._theme_combo = QComboBox()
        for t in list_themes():
            self._theme_combo.addItem(t["display_name"], t["name"])
        # Select current
        cur = self._theme_manager.current.name
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == cur:
                self._theme_combo.setCurrentIndex(i)
                break
        form.addRow("Theme:", self._theme_combo)
        # Live preview
        self._theme_combo.currentIndexChanged.connect(
            lambda i: self._theme_manager.apply(self._theme_combo.itemData(i))
        )
        # Description label
        self._theme_desc = QLabel()
        self._theme_desc.setWordWrap(True)
        self._update_theme_desc()
        self._theme_combo.currentIndexChanged.connect(self._update_theme_desc)
        form.addRow(self._theme_desc)
        return w

    def _update_theme_desc(self) -> None:
        idx = self._theme_combo.currentIndex()
        themes = list_themes()
        if 0 <= idx < len(themes):
            self._theme_desc.setText(themes[idx]["description"])

    # --- sound helpers ---

    def _test_sound(self, sfx_type: str) -> None:
        if self._sound_manager:
            self._sound_manager.play(sfx_type)

    def _preview_music(self, track: str) -> None:
        if self._sound_manager:
            self._sound_manager.play_music(track)

    def _stop_music(self) -> None:
        if self._sound_manager:
            self._sound_manager.stop_music()

    # --- save ---

    def _on_apply(self) -> None:
        self._apply_to_config()
        if self.parent() and hasattr(self.parent(), "apply_settings"):
            self.parent().apply_settings(self._config)  # type: ignore[attr-defined]

    def _on_ok(self) -> None:
        self._on_apply()
        self.accept()

    def _apply_to_config(self) -> None:
        self._config.setdefault("engine", {})
        self._config["engine"]["threads"] = self._threads.value()
        self._config["engine"]["hash_mb"] = self._hash.value()
        self._config["engine"]["multipv"] = self._multipv.value()
        self._config["engine"]["movetime_ms"] = self._movetime.value()
        self._config["engine"]["show_wdl"] = self._wdl.isChecked()
        self._config.setdefault("humanizer", {})
        self._config["humanizer"]["blunder_threshold"] = self._blunder_threshold.value()
        self._config["humanizer"]["oscillation_penalty"] = self._oscillation_penalty.value()
        self._config["humanizer"]["think_time_min_ms"] = self._think_time_min.value()
        self._config["humanizer"]["think_time_max_ms"] = self._think_time_max.value()
        self._config.setdefault("display", {})
        self._config["display"]["play_as_black"] = self._flip_on_first.isChecked()
        self._config["display"]["show_coordinates"] = self._show_coordinates.isChecked()
        self._config["display"]["show_legal_moves"] = self._show_legal_moves.isChecked()
        self._config["display"]["animate_moves"] = self._animate_moves.isChecked()
        if self._sound_manager:
            self._sound_manager.set_enabled(self._sound_enabled.isChecked())
            self._sound_manager.set_volume(self._volume.value() / 100.0)
        # Theme
        self._theme_manager.apply(self._theme_combo.currentData())


__all__ = ["SettingsDialog"]
