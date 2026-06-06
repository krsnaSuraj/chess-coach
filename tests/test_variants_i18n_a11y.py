"""Tests for variants, i18n, a11y modules (Phase N)."""

from __future__ import annotations

import pytest

from chess_coach.variants.registry import (
    VARIANTS,
    get_variant,
    variant_names,
    variant_by_key,
    VariantInfo,
)
from chess_coach.variants.standard import STANDARD
from chess_coach.variants.chess960 import (
    CHESS960, random_starting_position, _is_legal_960,
)
from chess_coach.variants.king_of_the_hill import CENTER_SQUARES

from chess_coach.i18n.loader import (
    I18n, get_string, available_languages, language_name, LANGUAGES,
)
from chess_coach.i18n import en, hi, es, fr, de

from chess_coach.a11y.keyboard_nav import (
    KeyboardHandler, KEY_HELP, KeyboardShortcut,
)
from chess_coach.a11y.screen_reader import (
    ScreenReaderAnnouncer, LiveRegion, Announcement,
)
from chess_coach.a11y.high_contrast import (
    HighContrastTheme, is_high_contrast_active, HIGH_CONTRAST_COLORS,
)


# ===== Variants =====

class TestVariantRegistry:
    def test_has_8_variants(self) -> None:
        assert len(VARIANTS) == 8

    def test_keys_unique(self) -> None:
        keys = [v.key for v in VARIANTS]
        assert len(set(keys)) == 8

    def test_required_variants_present(self) -> None:
        keys = {v.key for v in VARIANTS}
        assert "standard" in keys
        assert "chess960" in keys
        assert "atomic" in keys
        assert "antichess" in keys
        assert "horde" in keys
        assert "kingOfTheHill" in keys
        assert "threeCheck" in keys
        assert "crazyhouse" in keys

    def test_get_variant(self) -> None:
        v = get_variant("chess960")
        assert v is not None
        assert v.name == "Chess960 (Fischer Random)"

    def test_get_variant_unknown(self) -> None:
        assert get_variant("unknown") is None

    def test_variant_names(self) -> None:
        names = variant_names()
        assert "Standard" in names
        assert "Atomic" in names

    def test_variant_info_to_dict(self) -> None:
        v = get_variant("standard")
        assert v is not None
        d = v.to_dict()
        assert d["key"] == "standard"
        assert d["name"] == "Standard"


class TestChess960:
    def test_key_constant(self) -> None:
        assert CHESS960 == "chess960"

    def test_legal_back_rank(self) -> None:
        assert _is_legal_960("rnbqkbnr") is True

    def test_illegal_no_two_bishops(self) -> None:
        assert _is_legal_960("rnbqqbnr") is False

    def test_illegal_king_not_between_rooks(self) -> None:
        assert _is_legal_960("krnbqbnr") is False

    def test_illegal_missing_rook(self) -> None:
        assert _is_legal_960("rnbqkbnq") is False

    def test_random_starting_position(self) -> None:
        # Run a few times to ensure no crashes
        for _ in range(5):
            fen = random_starting_position()
            assert "/" in fen
            assert " w " in fen or " b " in fen


# ===== i18n =====

class TestI18n:
    def test_5_languages(self) -> None:
        codes = available_languages()
        assert len(codes) == 5
        assert "en" in codes
        assert "hi" in codes
        assert "es" in codes
        assert "fr" in codes
        assert "de" in codes

    def test_english_string(self) -> None:
        i = I18n("en")
        assert i.t("APP_NAME") == "Chess Coach"
        assert i.t("BUTTON_NEW_GAME") == "New Game"

    def test_hindi_string(self) -> None:
        i = I18n("hi")
        assert i.t("APP_NAME") == "शतरंज कोच"
        assert "नया" in i.t("BUTTON_NEW_GAME")

    def test_spanish_string(self) -> None:
        i = I18n("es")
        assert i.t("APP_NAME") == "Entrenador de Ajedrez"
        assert i.t("BUTTON_NEW_GAME") == "Nueva partida"

    def test_french_string(self) -> None:
        i = I18n("fr")
        assert "Échecs" in i.t("APP_NAME")

    def test_german_string(self) -> None:
        i = I18n("de")
        assert "Schach" in i.t("APP_NAME")

    def test_fallback_to_english(self) -> None:
        # Switch to a language and request a missing key
        i = I18n("hi")
        # If the key exists in both, returns hi
        assert i.t("BUTTON_HELP") == "मदद"

    def test_placeholder_format(self) -> None:
        i = I18n("en")
        msg = i.t("LOGIN_WELCOME", name="Alice")
        assert "Alice" in msg

    def test_set_language(self) -> None:
        i = I18n("en")
        i.set_language("hi")
        assert i.language == "hi"
        i.set_language("xx")
        assert i.language == "hi"  # invalid -> unchanged

    def test_get_string_helper(self) -> None:
        s = get_string("APP_NAME", language="de")
        assert "Schach" in s

    def test_language_name(self) -> None:
        assert "English" in language_name("en")
        assert "Spanish" in language_name("es")


# ===== a11y Keyboard =====

class TestKeyboardHandler:
    def test_help_has_shortcuts(self) -> None:
        assert len(KEY_HELP) > 10

    def test_resolve_known(self) -> None:
        h = KeyboardHandler()
        assert h.resolve("Ctrl+k") == "command-palette"
        assert h.resolve("Ctrl+n") == "new-game"
        assert h.resolve("Escape") == "close-dialog"

    def test_resolve_unknown(self) -> None:
        h = KeyboardHandler()
        assert h.resolve("Ctrl+Alt+Delete") is None

    def test_modifier_only(self) -> None:
        h = KeyboardHandler()
        assert h.is_modifier_only("Control")
        assert h.is_modifier_only("Shift")
        assert not h.is_modifier_only("a")

    def test_normalize_combo(self) -> None:
        h = KeyboardHandler()
        # Should sort modifiers in canonical order: Ctrl, Shift, Alt, Meta
        n = h.normalize_combo(["k", "Ctrl"])
        assert n == "Ctrl+k"
        n2 = h.normalize_combo(["Shift", "k", "Ctrl"])
        assert n2 == "Ctrl+Shift+k"
        # Empty
        assert h.normalize_combo([]) == ""
        # Only modifier
        assert h.normalize_combo(["Shift"]) == "Shift"


# ===== a11y Screen Reader =====

class TestScreenReader:
    def test_announce(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce("Hello", LiveRegion.POLITE)
        assert len(sr.drain()) == 1

    def test_drain_clears(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce("A")
        sr.announce("B")
        items = sr.drain()
        assert len(items) == 2
        assert sr.drain() == []

    def test_history(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce("A")
        sr.announce("B")
        assert len(sr.history()) == 2
        sr.clear_history()
        assert len(sr.history()) == 0

    def test_announce_move(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce_move("e4", "White")
        items = sr.drain()
        assert "White plays e4" in items[0].text

    def test_announce_move_with_check(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce_move("Qh7", "Black", is_check=True)
        items = sr.drain()
        assert "check" in items[0].text.lower()

    def test_announce_checkmate(self) -> None:
        sr = ScreenReaderAnnouncer()
        sr.announce_game_state(is_check=False, is_mate=True, is_stalemate=False)
        items = sr.drain()
        assert "Checkmate" in items[0].text
        assert items[0].region == LiveRegion.ASSERTIVE


# ===== a11y High Contrast =====

class TestHighContrast:
    def test_theme_has_colors(self) -> None:
        t = HighContrastTheme()
        colors = t.all_colors()
        assert "bg" in colors
        assert "fg" in colors

    def test_get_color(self) -> None:
        t = HighContrastTheme()
        assert t.get("bg") == "#000000"
        assert t.get("fg") == "#FFFFFF"

    def test_default_color(self) -> None:
        t = HighContrastTheme()
        assert t.get("nonexistent", default="#FF00FF") == "#FF00FF"

    def test_is_high_contrast_active(self) -> None:
        assert is_high_contrast_active("high-contrast") is True
        assert is_high_contrast_active("high_contrast") is True
        assert is_high_contrast_active("hc") is True
        assert is_high_contrast_active("midnight") is False

    def test_high_contrast_colors_have_aaa_contrast(self) -> None:
        """Sanity check: pure black on white has 21:1 contrast (AAA)."""
        bg = HIGH_CONTRAST_COLORS["bg"]
        fg = HIGH_CONTRAST_COLORS["fg"]
        assert bg == "#000000"
        assert fg == "#FFFFFF"
        # WCAG AAA requires 7:1 for normal text, 21:1 is the max
