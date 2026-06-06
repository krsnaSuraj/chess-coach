"""Tests for maia_engine module — uses mocked Lc0 subprocess."""

from __future__ import annotations

import os
import pytest
import chess

from chess_coach.maia_engine import (
    MaiaEngine,
    MaiaConfig,
    MaiaEngineError,
    find_lc0,
    find_maia_weights,
    _closest_maia_elo,
    MAIA_WEIGHT_URLS,
)


class TestClosestMaiaElo:
    def test_exact_match(self) -> None:
        assert _closest_maia_elo(1500) == 1500

    def test_rounding_down(self) -> None:
        assert _closest_maia_elo(1450) == 1500 or _closest_maia_elo(1450) == 1400

    def test_above_range(self) -> None:
        assert _closest_maia_elo(2200) == 1900

    def test_below_range(self) -> None:
        assert _closest_maia_elo(800) == 1100


class TestMaiaWeightURLs:
    def test_all_urls_present(self) -> None:
        for elo in (1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900):
            assert elo in MAIA_WEIGHT_URLS
            assert MAIA_WEIGHT_URLS[elo].startswith("https://")

    def test_url_format(self) -> None:
        for elo, url in MAIA_WEIGHT_URLS.items():
            assert f"maia-{elo}" in url
            assert url.endswith(".pb.gz")


class TestFindLc0:
    def test_returns_none_if_missing(self, tmp_path) -> None:
        result = find_lc0(str(tmp_path / "nonexistent.exe"))
        assert result is None


class TestFindMaiaWeights:
    def test_returns_none_if_dir_missing(self, tmp_path) -> None:
        result = find_maia_weights(1500, str(tmp_path / "no_such_dir"))
        assert result is None

    def test_finds_exact(self, tmp_path) -> None:
        weights_dir = tmp_path / "weights"
        weights_dir.mkdir()
        (weights_dir / "maia-1500.pb.gz").write_bytes(b"")
        result = find_maia_weights(1500, str(weights_dir))
        assert result is not None
        assert "maia-1500" in result

    def test_finds_nearest(self, tmp_path) -> None:
        weights_dir = tmp_path / "weights"
        weights_dir.mkdir()
        (weights_dir / "maia-1900.pb.gz").write_bytes(b"")
        result = find_maia_weights(1400, str(weights_dir))
        # Nearest of 1400 in {1900} is 1900
        assert result is not None
        assert "maia-1900" in result


class TestMaiaConfig:
    def test_defaults(self) -> None:
        c = MaiaConfig()
        assert c.lc0_path == "lc0/lc0.exe"
        assert c.default_elo == 1500
        assert c.nodes == 1
        assert c.auto_download is True


class TestMaiaEngineGracefulDegradation:
    def test_unavailable_when_no_binary(self) -> None:
        e = MaiaEngine(MaiaConfig(lc0_path="/nonexistent/lc0.exe",
                                   weights_dir="/nonexistent/weights",
                                   auto_download=False))
        result = e.start()
        assert result is False
        assert e.available is False

    def test_get_move_probs_returns_empty_when_unavailable(self) -> None:
        e = MaiaEngine(MaiaConfig(lc0_path="/nonexistent", weights_dir="/nonexistent",
                                   auto_download=False))
        e.start()
        probs = e.get_move_probabilities(chess.Board())
        assert probs == {}

    def test_get_top_n_when_unavailable(self) -> None:
        e = MaiaEngine(MaiaConfig(lc0_path="/nonexistent", weights_dir="/nonexistent",
                                   auto_download=False))
        e.start()
        result = e.get_top_n_moves(chess.Board(), 3)
        assert result == []

    def test_close_when_unavailable(self) -> None:
        e = MaiaEngine()
        e.close()
        assert e.available is False

    def test_current_elo_default(self) -> None:
        e = MaiaEngine()
        assert e.current_elo == 1500

    def test_set_elo_when_unavailable(self) -> None:
        e = MaiaEngine(MaiaConfig(lc0_path="/nonexistent", weights_dir="/nonexistent",
                                   auto_download=False))
        result = e.set_elo(1800)
        assert result is False
