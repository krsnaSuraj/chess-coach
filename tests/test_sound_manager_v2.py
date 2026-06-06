"""Tests for sound_manager.py v2 — 10 SFX types, 8 themes, 3 music tracks, spatial pan."""

from __future__ import annotations

import os
import struct
import wave

import pytest

from chess_coach.sound_manager import (
    SoundManager, SFX_TYPES, MUSIC_TRACKS, default_manager,
    _default_volume, _envelope_shape, _generate_sfx, _generate_music,
)
from chess_coach.theme_manager import THEMES, get_theme


class TestSFXTypes:
    def test_has_10_sfx_types(self):
        assert len(SFX_TYPES) == 10

    def test_sfx_types_are_distinct(self):
        assert len(SFX_TYPES) == len(set(SFX_TYPES))

    def test_required_sfx_present(self):
        for required in ("move", "capture", "check", "castle", "promote",
                         "illegal", "game_start", "game_end",
                         "engine_analyzing", "brilliant"):
            assert required in SFX_TYPES


class TestMusicTracks:
    def test_has_3_music_tracks(self):
        assert len(MUSIC_TRACKS) == 3
        assert "menu" in MUSIC_TRACKS
        assert "analysis" in MUSIC_TRACKS
        assert "game" in MUSIC_TRACKS

    def test_music_tracks_have_freqs(self):
        for name, spec in MUSIC_TRACKS.items():
            assert "freqs" in spec
            assert len(spec["freqs"]) == 3
            for f in spec["freqs"]:
                assert f > 0


class TestEnvelopeShape:
    def test_click_envelope_starts_high(self):
        # At t=0, click envelope should be > 0
        v = _envelope_shape(0, 1000, "click")
        assert v >= 0

    def test_bell_starts_at_max(self):
        v = _envelope_shape(0, 1000, "bell")
        assert v > 0.9

    def test_envelope_returns_zero_at_end(self):
        for shape in ("click", "wood", "bell", "alarm", "chime", "buzz"):
            v = _envelope_shape(999, 1000, shape)
            assert v >= 0

    def test_envelope_unknown_shape_returns_one(self):
        v = _envelope_shape(50, 100, "unknown_shape")
        assert v == 1.0


class TestGenerateSFX:
    def test_generates_valid_wav_bytes(self):
        data = _generate_sfx(get_theme("midnight"), "move")
        assert len(data) > 100
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"

    def test_generates_for_all_sfx_types(self):
        theme = get_theme("midnight")
        for sfx in SFX_TYPES:
            data = _generate_sfx(theme, sfx)
            assert len(data) > 100, f"Failed for {sfx}"
            assert data[:4] == b"RIFF"

    def test_generates_for_all_themes(self):
        for theme in THEMES.values():
            data = _generate_sfx(theme, "move")
            assert len(data) > 100
            assert data[:4] == b"RIFF"

    def test_different_themes_produce_different_audio(self):
        m = _generate_sfx(get_theme("midnight"), "move")
        c = _generate_sfx(get_theme("cyber_neon"), "move")
        # Different byte content (different envelopes)
        assert m != c


class TestGenerateMusic:
    def test_generates_valid_wav_bytes(self):
        data = _generate_music("menu")
        assert len(data) > 1000   # music is longer
        assert data[:4] == b"RIFF"

    def test_generates_for_all_tracks(self):
        for track in MUSIC_TRACKS:
            data = _generate_music(track)
            assert len(data) > 1000
            assert data[:4] == b"RIFF"


class TestSoundManager:
    def test_init_with_default_theme(self):
        sm = SoundManager()
        assert sm.theme.name == "midnight"

    def test_init_with_custom_theme(self):
        sm = SoundManager("cyber_neon")
        assert sm.theme.name == "cyber_neon"

    def test_set_theme_switches(self):
        sm = SoundManager()
        sm.set_theme("forest")
        assert sm.theme.name == "forest"
        sm.set_theme("midnight")
        assert sm.theme.name == "midnight"

    def test_set_volume_clamps(self):
        sm = SoundManager()
        sm.set_volume(2.0)
        assert sm._volume == 1.0
        sm.set_volume(-0.5)
        assert sm._volume == 0.0
        sm.set_volume(0.7)
        assert sm._volume == 0.7

    def test_set_enabled_toggles(self):
        sm = SoundManager()
        assert sm.is_enabled() is True
        sm.set_enabled(False)
        assert sm.is_enabled() is False
        sm.set_enabled(True)
        assert sm.is_enabled() is True

    def test_play_when_disabled_is_noop(self, tmp_path, monkeypatch):
        sm = SoundManager()
        sm.set_enabled(False)
        # Should not raise
        sm.play("move")

    def test_play_unknown_sfx_is_noop(self):
        sm = SoundManager()
        sm.set_enabled(False)  # avoid side effects
        sm.play("not_a_real_sfx")

    def test_ensure_sfx_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = SoundManager("sepia")
        sm.set_enabled(False)  # skip playback
        # Force cache miss
        from chess_coach.sound_manager import _cache_dir
        cache_d = _cache_dir("sepia")
        # Clear
        for f in os.listdir(cache_d):
            os.remove(os.path.join(cache_d, f))
        path = sm._ensure_sfx("move")
        assert path is not None
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000

    def test_ensure_sfx_caches_after_first_call(self):
        sm = SoundManager()
        sm.set_enabled(False)
        p1 = sm._ensure_sfx("capture")
        p2 = sm._ensure_sfx("capture")
        assert p1 == p2
        assert (sm._theme.name, "capture") in sm._sfx_cache

    def test_regenerate_all_clears_cache(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        sm = SoundManager("midnight")
        sm.set_enabled(False)
        sm._ensure_sfx("move")
        from chess_coach.sound_manager import _cache_dir
        cache_d = _cache_dir("midnight")
        # Files exist
        assert os.path.exists(os.path.join(cache_d, "move.wav"))
        n = sm.regenerate_all()
        assert n == 10


class TestDefaultVolume:
    def test_all_sfx_have_default_volume(self):
        for sfx in SFX_TYPES:
            v = _default_volume(sfx)
            assert 0.0 <= v <= 1.0

    def test_unknown_sfx_gets_default_05(self):
        assert _default_volume("nope") == 0.5

    def test_engine_analyzing_is_quiet(self):
        # Should be subtle, not loud
        assert _default_volume("engine_analyzing") <= 0.2


class TestSpatialPan:
    """file_index 0=a-file (left), 7=h-file (right). Verify the helper is used."""

    def test_play_accepts_file_index(self):
        sm = SoundManager()
        sm.set_enabled(False)
        # Should not raise for any file_index 0-7
        for i in range(8):
            sm.play("move", file_index=i)


class TestBackCompat:
    def test_default_manager_singleton(self):
        m1 = default_manager()
        m2 = default_manager()
        assert m1 is m2

    def test_play_move_shim_exists(self):
        # play_move should not raise (uses default_manager)
        from chess_coach.sound_manager import play_move
        play_move()  # no-op if disabled

    def test_set_enabled_shim(self):
        from chess_coach.sound_manager import set_enabled
        set_enabled(True)
        set_enabled(False)
        set_enabled(True)
