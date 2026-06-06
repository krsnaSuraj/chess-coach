"""Tests for tablebase module (Phase I)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import chess
import pytest

from chess_coach.tablebase.syzygy import (
    SyzygyProbe,
    TablebaseResult,
    empty_tablebase_result,
    WDL_WIN,
    WDL_DRAW,
    WDL_LOSS,
    WDL_UNKNOWN,
    WDL_NAMES,
)


class TestTablebaseResult:
    def test_construction(self) -> None:
        r = TablebaseResult(wdl=WDL_WIN, dtz=5, category="win", moves=[], source="local")
        assert r.wdl == WDL_WIN
        assert r.dtz == 5

    def test_winrate(self) -> None:
        assert TablebaseResult(wdl=WDL_WIN, dtz=1, category="win", moves=[], source="local").winrate == 1.0
        assert TablebaseResult(wdl=WDL_DRAW, dtz=0, category="draw", moves=[], source="local").winrate == 0.5
        assert TablebaseResult(wdl=WDL_LOSS, dtz=1, category="loss", moves=[], source="local").winrate == 0.0
        # Unknown defaults to 0.5
        assert TablebaseResult(wdl=WDL_UNKNOWN, dtz=None, category="unknown", moves=[], source="none").winrate == 0.5


class TestSyzygyProbe:
    def test_init_no_path(self) -> None:
        probe = SyzygyProbe(path=None)
        assert probe.is_available() is False

    def test_init_with_nonexistent_path(self) -> None:
        probe = SyzygyProbe(path="/nonexistent/syzygy")
        assert probe.is_available() is False

    def test_empty_result_helper(self) -> None:
        r = empty_tablebase_result()
        assert r.wdl == WDL_UNKNOWN
        assert r.dtz is None
        assert r.source == "none"

    def test_wdl_names_complete(self) -> None:
        for code in [WDL_WIN, WDL_DRAW, WDL_LOSS]:
            assert code in WDL_NAMES

    def test_probe_falls_back_to_api_or_empty(self) -> None:
        """With no local tablebase, probe should return either API result or empty."""
        probe = SyzygyProbe(path=None)
        board = chess.Board("k7/8/8/8/8/8/8/7K w - - 0 1")  # kings only
        result = probe.probe(board)
        # Should not crash; either got API data or unknown
        assert result is not None
        assert isinstance(result, TablebaseResult)


class TestSyzygyWdlThresholds:
    """Test that the WDL enum values are correct (matches python-chess)."""

    def test_wdl_values(self) -> None:
        # python-chess.syzygy uses these specific values
        assert WDL_WIN == 2
        assert WDL_DRAW == 0
        assert WDL_LOSS == -2
