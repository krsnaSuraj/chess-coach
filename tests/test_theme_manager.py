"""Tests for theme_manager.py — 8 themes, dataclass integrity, manager signal."""

from __future__ import annotations

import os

import pytest

from chess_coach.theme_manager import (
    THEMES, DEFAULT_THEME, Theme, ThemeManager, SoundPalette,
    AnimationPreset, get_theme, list_themes, manager,
)


class TestThemeRegistry:
    def test_has_10_themes(self):
        assert len(THEMES) == 10

    def test_all_themes_have_unique_names(self):
        names = [t.name for t in THEMES.values()]
        assert len(names) == len(set(names))

    def test_default_theme_is_midnight(self):
        assert DEFAULT_THEME == "midnight"
        assert "midnight" in THEMES

    def test_every_theme_has_required_color_keys(self):
        required = ("board_light", "board_dark", "bg", "sidebar", "accent",
                    "text", "text_dim", "last_move", "check", "legal_dot",
                    "capture_ring", "arrow_best", "eval_loss", "eval_draw",
                    "eval_win")
        for theme in THEMES.values():
            for k in required:
                assert hasattr(theme, k), f"Theme {theme.name} missing {k}"
                v = getattr(theme, k)
                assert isinstance(v, str) and v.startswith("#"), \
                    f"Theme {theme.name}.{k} = {v!r} not #hex"

    def test_every_theme_has_sound_and_animation(self):
        for theme in THEMES.values():
            assert isinstance(theme.sound, SoundPalette)
            assert isinstance(theme.animation, AnimationPreset)

    def test_all_themes_have_3_eval_colors(self):
        for theme in THEMES.values():
            for k in ("eval_loss", "eval_draw", "eval_win"):
                v = getattr(theme, k)
                assert len(v) == 7 and v.startswith("#")


class TestThemeDataclass:
    def test_theme_is_frozen(self):
        theme = get_theme("midnight")
        with pytest.raises(Exception):
            theme.bg = "#000000"  # type: ignore[misc]

    def test_to_dict_round_trip(self):
        theme = get_theme("cyber_neon")
        d = theme.to_dict()
        assert d["name"] == "cyber_neon"
        assert d["board_light"] == theme.board_light
        assert "is_dark" in d

    def test_sound_palette_defaults(self):
        pal = SoundPalette()
        assert pal.attack_ms >= 0
        assert pal.decay_ms > 0
        assert pal.fundamental_hz > 0
        assert 0.0 <= pal.brightness <= 1.0

    def test_animation_preset_defaults(self):
        anim = AnimationPreset()
        assert anim.move_duration_ms > 0
        assert anim.easing in ("OutCubic", "InOutCubic", "OutBack", "Linear")
        assert anim.css_easing.startswith("cubic-bezier")


class TestGetTheme:
    def test_get_known_theme(self):
        for name in THEMES:
            t = get_theme(name)
            assert t.name == name

    def test_get_unknown_falls_back_to_default(self, caplog):
        t = get_theme("nonexistent_xyz")
        assert t.name == DEFAULT_THEME

    def test_case_insensitive(self):
        assert get_theme("MIDNIGHT").name == "midnight"
        assert get_theme("Cyber_Neon").name == "cyber_neon"

    def test_strip_whitespace(self):
        assert get_theme("  lichess  ").name == "lichess"


class TestListThemes:
    def test_returns_10_metadata_dicts(self):
        themes = list_themes()
        assert len(themes) == 10
        for t in themes:
            assert "name" in t
            assert "display_name" in t
            assert "description" in t
            assert "is_dark" in t

    def test_metadata_contains_all_keys(self):
        names = {t["name"] for t in list_themes()}
        assert "midnight" in names
        assert "cyber_neon" in names
        assert "sepia" in names


class TestThemeManager:
    def test_default_is_midnight(self):
        m = ThemeManager()
        assert m.current.name == "midnight"

    def test_apply_changes_theme(self):
        m = ThemeManager()
        m.apply("sunset")
        assert m.current.name == "sunset"

    def test_apply_is_idempotent(self):
        m = ThemeManager()
        m.apply("forest")
        m.apply("forest")
        assert m.current.name == "forest"

    def test_apply_emits_signal(self):
        m = ThemeManager()
        received: list[Theme] = []
        m.themeChanged.connect(lambda t: received.append(t))
        m.apply("marble")
        m.apply("lichess")
        assert len(received) == 2
        assert received[0].name == "marble"
        assert received[1].name == "lichess"

    def test_apply_object_also_works(self):
        m = ThemeManager()
        m.apply(get_theme("blue_glass"))
        assert m.current.name == "blue_glass"

    def test_module_singleton_manager(self):
        m1 = manager()
        m2 = manager()
        assert m1 is m2


class TestThemeColorContrast:
    """Sanity checks that each theme has reasonable visual contrast."""

    def _hex_to_rgb(self, h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def test_board_light_dark_are_distinct(self):
        for theme in THEMES.values():
            l = self._hex_to_rgb(theme.board_light)
            d = self._hex_to_rgb(theme.board_dark)
            assert l != d, f"{theme.name}: light and dark squares identical"

    def test_text_contrasts_with_bg(self):
        for theme in THEMES.values():
            bg = self._hex_to_rgb(theme.bg)
            text = self._hex_to_rgb(theme.text)
            # Simple luminance distance check
            bg_lum = sum(bg) / 3
            text_lum = sum(text) / 3
            diff = abs(bg_lum - text_lum)
            assert diff > 80, f"{theme.name}: text vs bg too similar ({diff:.0f})"
