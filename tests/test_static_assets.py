"""Tests for static web assets — verify HTML/CSS/JS structure, manifest, SW.

These are not full E2E (those need Playwright, see test_e2e_web.py) but they
parse the assets and assert structural invariants: theme count, JS file
presence, manifest validity, etc.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "static"


class TestStaticAssets:
    def test_index_html_exists(self):
        assert (STATIC / "index.html").exists()

    def test_themes_css_exists(self):
        assert (STATIC / "css" / "themes.css").exists()

    def test_chessboard_css_exists(self):
        assert (STATIC / "css" / "chessboard.css").exists()

    def test_app_js_exists(self):
        assert (STATIC / "js" / "app.js").exists()

    def test_board_js_exists(self):
        assert (STATIC / "js" / "board.js").exists()

    def test_sound_js_exists(self):
        assert (STATIC / "js" / "sound.js").exists()

    def test_manifest_exists(self):
        assert (STATIC / "manifest.json").exists()

    def test_service_worker_exists(self):
        assert (STATIC / "service-worker.js").exists()

    def test_piece_images_present(self):
        piece_dir = STATIC / "img" / "chesspieces" / "wikipedia"
        assert piece_dir.is_dir()
        for color in ("w", "b"):
            for letter in ("P", "N", "B", "R", "Q", "K"):
                assert (piece_dir / f"{color}{letter}.png").exists()


class TestThemesCSS:
    @pytest.fixture
    def themes_css(self) -> str:
        return (STATIC / "css" / "themes.css").read_text(encoding="utf-8")

    def test_has_8_themes(self, themes_css):
        # Each theme is defined as html[data-theme="<name>"]
        themes = re.findall(r'html\[data-theme="(\w+)"\]', themes_css)
        assert len(themes) == 8

    def test_expected_theme_names(self, themes_css):
        themes = set(re.findall(r'html\[data-theme="(\w+)"\]', themes_css))
        assert themes == {"midnight", "forest", "sunset", "marble", "lichess",
                          "blue_glass", "cyber_neon", "sepia"}

    def test_required_css_vars(self, themes_css):
        required = ("--board-light", "--board-dark", "--bg", "--accent",
                    "--text", "--text-dim", "--arrow-best", "--arrow-plan",
                    "--arrow-threat", "--arrow-user", "--last-move", "--check",
                    "--premove", "--legal-dot", "--eval-win", "--eval-loss",
                    "--brilliant", "--easing", "--move-dur")
        for var in required:
            assert var in themes_css, f"Missing CSS variable {var}"


def _strip_js_comments(text: str) -> str:
    """Remove // line comments and /* block */ comments, keep code only."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//[^\n]*', '', text)
    return text


class TestBoardJS:
    @pytest.fixture
    def board_js(self) -> str:
        return (STATIC / "js" / "board.js").read_text(encoding="utf-8")

    @pytest.fixture
    def board_code(self, board_js: str) -> str:
        return _strip_js_comments(board_js)

    def test_no_jquery(self, board_code):
        # jQuery is identifiable by jQuery(...) calls or $( selector ) patterns
        assert "jQuery(" not in board_code
        assert re.search(r'\$\s*\(', board_code) is None
        assert "require('jquery" not in board_code
        assert "from 'jquery" not in board_code
        assert 'require("jquery' not in board_code
        assert 'from "jquery' not in board_code

    def test_no_chessboard_js_dep(self, board_code):
        # No require/import of chessboard.js
        assert "require('chessboard" not in board_code
        assert 'require("chessboard' not in board_code
        assert "from 'chessboard" not in board_code
        assert 'from "chessboard' not in board_code

    def test_exposes_ChessBoard_class(self, board_js):
        assert "window.ChessBoard" in board_js

    def test_supports_drag(self, board_code):
        assert "mousedown" in board_code
        assert "touchstart" in board_code

    def test_supports_right_click(self, board_code):
        assert "contextmenu" in board_code
        assert "button === 2" in board_code or "button == 2" in board_code

    def test_supports_arrows(self, board_code):
        assert "arrow" in board_code.lower()

    def test_supports_flipped_board(self, board_code):
        assert "flipped" in board_code


class TestSoundJS:
    @pytest.fixture
    def sound_js(self) -> str:
        return (STATIC / "js" / "sound.js").read_text(encoding="utf-8")

    def test_uses_web_audio(self, sound_js):
        assert "AudioContext" in sound_js or "webkitAudioContext" in sound_js

    def test_has_10_sfx_types(self, sound_js):
        # Should have entries for all 10 SFX
        sfx_types = ["move", "capture", "check", "castle", "promote",
                     "illegal", "game_start", "game_end", "engine_analyzing",
                     "brilliant"]
        for sfx in sfx_types:
            assert sfx in sound_js, f"Missing SFX: {sfx}"

    def test_has_8_theme_palettes(self, sound_js):
        themes = ["midnight", "forest", "sunset", "marble", "lichess",
                  "blue_glass", "cyber_neon", "sepia"]
        for t in themes:
            assert t in sound_js, f"Missing theme palette: {t}"

    def test_spatial_pan(self, sound_js):
        assert "StereoPanner" in sound_js or "pan" in sound_js.lower()

    def test_music_playback(self, sound_js):
        assert "playMusic" in sound_js
        assert "stopMusic" in sound_js


class TestAppJS:
    @pytest.fixture
    def app_js(self) -> str:
        return (STATIC / "js" / "app.js").read_text(encoding="utf-8")

    @pytest.fixture
    def app_code(self, app_js: str) -> str:
        return _strip_js_comments(app_js)

    def test_no_jquery(self, app_code):
        assert "jQuery(" not in app_code
        assert re.search(r'\$\s*\(', app_code) is None
        assert "require('jquery" not in app_code
        assert "from 'jquery" not in app_code
        assert 'require("jquery' not in app_code
        assert 'from "jquery' not in app_code

    def test_websocket(self, app_code):
        assert "WebSocket" in app_code

    def test_theme_picker(self, app_code):
        assert "themeSelect" in app_code
        assert "chess_theme" in app_code  # localStorage key

    def test_keyboard_shortcuts(self, app_code):
        assert "keydown" in app_code
        assert "F2" in app_code

    def test_service_worker_register(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        assert "serviceWorker" in html


class TestManifest:
    @pytest.fixture
    def manifest(self) -> dict:
        return json.loads((STATIC / "manifest.json").read_text(encoding="utf-8"))

    def test_has_name(self, manifest):
        assert "name" in manifest
        assert "Chess Coach" in manifest["name"]

    def test_has_start_url(self, manifest):
        assert "start_url" in manifest

    def test_has_display(self, manifest):
        assert "display" in manifest
        assert manifest["display"] in ("standalone", "fullscreen", "minimal-ui")

    def test_has_icons(self, manifest):
        assert "icons" in manifest
        assert len(manifest["icons"]) >= 1


class TestServiceWorker:
    @pytest.fixture
    def sw(self) -> str:
        return (STATIC / "service-worker.js").read_text(encoding="utf-8")

    def test_precaches_assets(self, sw):
        assert "PRECACHE" in sw or "addAll" in sw

    def test_handles_fetch(self, sw):
        assert "fetch" in sw

    def test_network_first_for_api(self, sw):
        assert "/api/" in sw

    def test_has_versioned_cache(self, sw):
        assert "CACHE_NAME" in sw
        assert "v3.0" in sw

    def test_cleans_old_caches(self, sw):
        assert "delete" in sw


class TestNoLegacyJQuery:
    def test_jquery_min_js_gone(self):
        assert not (STATIC / "js" / "jquery.min.js").exists()

    def test_chessboard_js_gone(self):
        assert not (STATIC / "js" / "chessboard.js").exists()
